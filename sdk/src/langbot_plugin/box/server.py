"""Box Runtime service exposing BoxRuntime via action RPC.

This module is the implementation of the `box` CLI subcommand. The only
supported entry point is the `lbp` CLI, which mirrors the plugin runtime's
`rt` subcommand:

    lbp box        # WebSocket control transport (default)
    lbp box -s     # stdio control transport

`main()` is invoked by the CLI with the parsed argument namespace, exactly
as `lbp rt` drives ``langbot_plugin.runtime.app.main``. There is no
``python -m langbot_plugin.box`` / ``python -m langbot_plugin.box.server``
launch path.

All WebSocket endpoints share a single port (default 5410):
    /rpc/ws                                                      — Action RPC (control channel)
    /v1/sessions/{session_id}/managed-process/{process_id}/ws    — Managed process stdio relay
    /v1/sessions/{session_id}/managed-process/ws                 — Legacy (process_id defaults to 'default')
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import datetime as dt
import hmac
import hashlib
import logging
import os
import sys
from typing import Any

import pydantic
from aiohttp import WSCloseCode, web

from langbot_plugin.entities.io.actions.enums import CommonAction
from langbot_plugin.entities.io.errors import ConnectionClosedError
from langbot_plugin.entities.io.resp import ActionResponse
from langbot_plugin.entities.io.context import ActionContext
from langbot_plugin.runtime.io.connection import Connection, MAX_MESSAGE_BYTES
from langbot_plugin.runtime.io.handler import Handler
from langbot_plugin.runtime.bounded_executor import (
    configure_bounded_default_executor_from_env,
)
from langbot_plugin.utils.log import configure_process_logging

from .actions import LangBotToBoxAction
from .errors import (
    BoxAdmissionError,
    BoxManagedProcessConflictError,
    BoxManagedProcessNotFoundError,
    BoxReadinessError,
    BoxSessionNotFoundError,
)
from .models import (
    BoxExecutionResult,
    BoxFileRequest,
    BoxFileUploadRequest,
    BoxManagedProcessSpec,
    BoxSpec,
    SandboxAdmissionGrant,
    SandboxAdmissionRevocation,
)
from .runtime import BoxRuntime
from .security import (
    BOX_CONTROL_TOKEN_ENV,
    BOX_CONTROL_TOKEN_HEADER,
    BOX_INSTANCE_HEADER,
    BOX_PLACEMENT_GENERATION_HEADER,
    BOX_TRUSTED_INSTANCE_ENV,
    BOX_WORKSPACE_HEADER,
    normalize_instance_uuid,
    validate_control_token,
)
from .tenancy import (
    logical_session_id,
    namespace_session_id,
    session_belongs_to_placement,
    session_namespace_prefix,
    workspace_session_namespace_prefix,
)

logger = logging.getLogger("langbot.box.server")

_ACTIVE_WEBSOCKETS_KEY = web.AppKey("active_websockets", set)
_APP_RUNTIME_KEY = "runtime"
_APP_CONTROL_TOKEN_KEY = "_box_control_token"
_APP_TRUSTED_INSTANCE_KEY = "_box_trusted_instance_uuid"
_APP_GENERATION_FENCE_KEY = "_box_generation_fence"


def _result_to_dict(result: BoxExecutionResult) -> dict:
    return result.model_dump(mode="json")


def _authenticate_host_request(
    request: web.Request,
    *,
    bind_instance: bool,
) -> str | None:
    """Validate the optional control secret and pin one instance identity."""

    expected_token = str(request.app.get(_APP_CONTROL_TOKEN_KEY) or "")
    supplied_token = str(request.headers.get(BOX_CONTROL_TOKEN_HEADER) or "")
    if expected_token and (
        not supplied_token or not hmac.compare_digest(expected_token, supplied_token)
    ):
        return None
    try:
        instance_uuid = normalize_instance_uuid(
            request.headers.get(BOX_INSTANCE_HEADER, "")
        )
    except ValueError:
        return None

    instance_state = request.app.get(_APP_TRUSTED_INSTANCE_KEY)
    if not isinstance(instance_state, dict):
        return None
    trusted_instance_uuid = instance_state.get("value")
    if trusted_instance_uuid is None:
        if not bind_instance:
            return None
        instance_state["value"] = instance_uuid
    elif not hmac.compare_digest(str(trusted_instance_uuid), instance_uuid):
        return None
    return instance_uuid


def _unauthorized_response() -> web.Response:
    return web.Response(status=401, text="Unauthorized")


class BoxGenerationFence:
    """Monotonic placement-generation authority shared by RPC and relays.

    The authenticated LangBot host advances this fence by making a tenant RPC.
    Advancing immediately invalidates older relay waiters and removes every
    session owned by an older placement.  Durable Workspace data is unaffected
    because its namespace intentionally excludes the generation.
    """

    def __init__(self, *, max_records: int = 100_000) -> None:
        self._max_records = max(int(max_records), 1)
        self._current: dict[tuple[str, str], int] = {}
        self._stale_events: dict[tuple[str, str, int], asyncio.Event] = {}
        self._active_tasks: dict[tuple[str, str, int], set[asyncio.Task[Any]]] = {}
        self._active_task_keys_by_workspace: dict[
            tuple[str, str], set[tuple[str, str, int]]
        ] = {}

    @staticmethod
    def _workspace_key(context: ActionContext) -> tuple[str, str]:
        context = ActionContext.model_validate(context).without_installation()
        return context.instance_uuid, context.workspace_uuid

    def observe(self, action_context: ActionContext) -> bool:
        """Record a trusted generation, rejecting rollback attempts.

        Returns ``True`` when the placement advanced.  This method contains no
        await points, so observations are atomic within the server event loop.
        """

        context = ActionContext.model_validate(action_context).without_installation()
        key = self._workspace_key(context)
        current = self._current.get(key)
        if current is None and len(self._current) >= self._max_records:
            raise PermissionError(
                "Box generation fence capacity reached; "
                "refusing an unbounded Workspace allocation"
            )
        if current is not None and context.placement_generation < current:
            raise PermissionError("Stale Box placement generation")
        if current == context.placement_generation:
            return False

        self._current[key] = context.placement_generation
        if current is not None:
            previous_event = self._stale_events.pop((*key, current), None)
            if previous_event is not None:
                # Existing waiters keep their Event reference. The fence only
                # needs to index the current generation for future waiters.
                previous_event.set()
        try:
            observing_task = asyncio.current_task()
        except RuntimeError:
            observing_task = None
        task_keys = self._active_task_keys_by_workspace.get(key, ())
        for task_key in tuple(task_keys):
            if task_key[2] >= context.placement_generation:
                continue
            tasks = self._active_tasks.get(task_key, ())
            for task in tuple(tasks):
                if task is not observing_task and not task.done():
                    task.cancel()
        return True

    def require_current(self, action_context: ActionContext) -> None:
        context = ActionContext.model_validate(action_context).without_installation()
        current = self._current.get(self._workspace_key(context))
        if current != context.placement_generation:
            raise PermissionError("Stale Box placement generation")

    async def wait_until_stale(self, action_context: ActionContext) -> None:
        context = ActionContext.model_validate(action_context).without_installation()
        if (
            self._current.get(self._workspace_key(context))
            != context.placement_generation
        ):
            return
        key = (*self._workspace_key(context), context.placement_generation)
        event = self._stale_events.setdefault(key, asyncio.Event())
        await event.wait()

    async def activate(
        self,
        runtime: BoxRuntime,
        action_context: ActionContext,
    ) -> None:
        """Activate one placement and synchronously retire stale sessions."""

        context = ActionContext.model_validate(action_context).without_installation()
        self.observe(context)
        task = asyncio.current_task()
        task_key = (*self._workspace_key(context), context.placement_generation)
        if task is not None:
            self._active_tasks.setdefault(task_key, set()).add(task)
            self._active_task_keys_by_workspace.setdefault(
                self._workspace_key(context),
                set(),
            ).add(task_key)
        try:
            await self._retire_stale_sessions(runtime, context)
            self.require_current(context)
        except BaseException:
            self._discard_task(task_key, task)
            raise

    async def finish(
        self,
        runtime: BoxRuntime,
        action_context: ActionContext,
        lease_task: asyncio.Task[Any] | None,
    ) -> None:
        """Release an RPC lease and remove sessions a cancelled lease left."""

        context = ActionContext.model_validate(action_context).without_installation()
        task_key = (*self._workspace_key(context), context.placement_generation)
        self._discard_task(task_key, lease_task)
        await self._retire_stale_sessions(runtime, context)

    def _discard_task(
        self,
        task_key: tuple[str, str, int],
        task: asyncio.Task[Any] | None,
    ) -> None:
        if task is None:
            return
        tasks = self._active_tasks.get(task_key)
        if tasks is None:
            return
        tasks.discard(task)
        if not tasks:
            self._active_tasks.pop(task_key, None)
            workspace_key = task_key[:2]
            workspace_task_keys = self._active_task_keys_by_workspace.get(workspace_key)
            if workspace_task_keys is not None:
                workspace_task_keys.discard(task_key)
                if not workspace_task_keys:
                    self._active_task_keys_by_workspace.pop(workspace_key, None)

    async def _retire_stale_sessions(
        self,
        runtime: BoxRuntime,
        action_context: ActionContext,
    ) -> None:
        context = ActionContext.model_validate(action_context).without_installation()
        current_generation = self._current.get(self._workspace_key(context))
        if current_generation is None:
            return
        current_context = context.model_copy(
            update={"placement_generation": current_generation}
        )
        current_prefix = session_namespace_prefix(current_context)
        workspace_prefix = workspace_session_namespace_prefix(current_context)
        stale_session_ids = [
            str(session.get("session_id") or "")
            for session in runtime.get_sessions_for_workspace(context)
            if str(session.get("session_id") or "").startswith(workspace_prefix)
            and not str(session.get("session_id") or "").startswith(current_prefix)
        ]
        for session_id in stale_session_ids:
            try:
                await runtime.delete_session(session_id)
            except BoxSessionNotFoundError:
                pass


def _relay_action_context(
    request: web.Request,
    instance_uuid: str,
) -> ActionContext | None:
    workspace_uuid = str(request.headers.get(BOX_WORKSPACE_HEADER) or "").strip()
    raw_generation = str(
        request.headers.get(BOX_PLACEMENT_GENERATION_HEADER) or ""
    ).strip()
    if not workspace_uuid or len(workspace_uuid) > 256:
        return None
    try:
        generation = int(raw_generation)
    except (TypeError, ValueError):
        return None
    if raw_generation != str(generation):
        return None
    try:
        return ActionContext(
            instance_uuid=instance_uuid,
            workspace_uuid=workspace_uuid,
            placement_generation=generation,
        )
    except pydantic.ValidationError:
        return None


# ── aiohttp WebSocket → Connection adapter ───────────────────────────


class AiohttpWSConnection(Connection):
    """Adapt an aiohttp ``WebSocketResponse`` to the SDK ``Connection`` interface.

    This allows ``BoxServerHandler`` (and therefore ``Handler``) to work over
    an aiohttp WebSocket without any changes to the handler/IO layer.
    """

    def __init__(self, ws: web.WebSocketResponse) -> None:
        self._ws = ws
        self._send_lock = asyncio.Lock()

    async def send(self, message: str) -> None:
        if len(message.encode("utf-8")) > MAX_MESSAGE_BYTES:
            raise ValueError(f"Runtime message exceeds {MAX_MESSAGE_BYTES} byte limit")
        async with self._send_lock:
            try:
                await self._ws.send_str(message)
            except ConnectionResetError:
                raise ConnectionClosedError("Connection closed during send")

    async def receive(self) -> str:
        msg = await self._ws.receive()
        if msg.type == web.WSMsgType.TEXT:
            return msg.data
        if msg.type in (
            web.WSMsgType.CLOSE,
            web.WSMsgType.CLOSING,
            web.WSMsgType.CLOSED,
            web.WSMsgType.ERROR,
        ):
            raise ConnectionClosedError("Connection closed")
        raise ConnectionClosedError(f"Unexpected message type: {msg.type}")

    async def close(self) -> None:
        await self._ws.close()


# ── BoxServerHandler ─────────────────────────────────────────────────


class BoxServerHandler(Handler):
    """Server-side handler that registers box actions backed by BoxRuntime."""

    name = "BoxServerHandler"

    _HOST_CONTROL_ACTIONS = frozenset(
        {
            CommonAction.PING.value,
            LangBotToBoxAction.HEALTH.value,
            LangBotToBoxAction.GET_BACKEND_INFO.value,
            LangBotToBoxAction.GET_BACKENDS.value,
            LangBotToBoxAction.INIT.value,
            LangBotToBoxAction.UPSERT_SANDBOX_ADMISSION_GRANT.value,
            LangBotToBoxAction.REVOKE_SANDBOX_ADMISSION_GRANT.value,
            LangBotToBoxAction.VERIFY_SHARED_WORKSPACE.value,
            LangBotToBoxAction.SHUTDOWN.value,
        }
    )

    _SANDBOX_ACTIONS = frozenset(
        {
            CommonAction.FILE_CHUNK.value,
            LangBotToBoxAction.UPLOAD_FILE.value,
            LangBotToBoxAction.DOWNLOAD_FILE.value,
            LangBotToBoxAction.EXEC.value,
            LangBotToBoxAction.CREATE_SESSION.value,
            LangBotToBoxAction.GET_SESSION.value,
            LangBotToBoxAction.GET_SESSIONS.value,
            LangBotToBoxAction.DELETE_SESSION.value,
            LangBotToBoxAction.START_MANAGED_PROCESS.value,
            LangBotToBoxAction.GET_MANAGED_PROCESS.value,
            LangBotToBoxAction.STOP_MANAGED_PROCESS.value,
        }
    )

    def __init__(
        self,
        connection: Connection,
        runtime: BoxRuntime,
        *,
        host_control_authenticated: bool,
        trusted_instance_uuid: str,
        allow_host_backend: bool = False,
        generation_fence: BoxGenerationFence | None = None,
    ):
        super().__init__(
            connection,
            max_file_bytes=runtime.max_rpc_file_bytes,
        )
        self._runtime = runtime
        self._host_control_authenticated = bool(host_control_authenticated)
        self._allow_host_backend = bool(allow_host_backend)
        self._trusted_instance_uuid = normalize_instance_uuid(trusted_instance_uuid)
        self._generation_fence = generation_fence or BoxGenerationFence(
            max_records=runtime.max_admission_records
        )
        inherited_file_chunk = self.actions[CommonAction.FILE_CHUNK.value]

        async def authenticated_file_chunk(data: dict[str, Any]) -> ActionResponse:
            self._require_host_control()
            return await inherited_file_chunk(data)

        self.actions[CommonAction.FILE_CHUNK.value] = authenticated_file_chunk
        self._register_actions()
        self._wrap_tenant_actions_with_generation_fence()

    def _wrap_tenant_actions_with_generation_fence(self) -> None:
        for action, action_handler in tuple(self.actions.items()):
            if (
                action in self._HOST_CONTROL_ACTIONS
                or action == LangBotToBoxAction.DELETE_FILE_TRANSFER.value
            ):
                continue

            async def fenced_action(
                data: dict[str, Any],
                *,
                _handler=action_handler,
                _action=action,
            ) -> ActionResponse:
                # Legacy instance-level transfers remain compatible; new file
                # operations can consume only explicitly Workspace-owned payloads.
                if (
                    _action == CommonAction.FILE_CHUNK.value
                    and self.current_action_context is None
                ):
                    return await _handler(data)
                context = self._action_context()
                lease_task = asyncio.current_task()
                if (
                    _action in self._SANDBOX_ACTIONS
                    and self._runtime.admission_required
                ):
                    await self._runtime.require_sandbox_admission(context)
                await self._generation_fence.activate(self._runtime, context)
                try:
                    response = await _handler(data)
                finally:
                    cleanup_task = asyncio.create_task(
                        self._generation_fence.finish(
                            self._runtime,
                            context,
                            lease_task,
                        )
                    )
                    try:
                        await asyncio.shield(cleanup_task)
                    except asyncio.CancelledError:
                        await cleanup_task
                        raise
                self._generation_fence.require_current(context)
                return response

            self.actions[action] = fenced_action

    def _require_host_control(self) -> None:
        if not self._host_control_authenticated:
            raise PermissionError("Box host control authentication is required")

    def validate_inbound_action_context(
        self,
        action: str,
        action_context: ActionContext | None,
    ) -> ActionContext | None:
        """Accept tenant envelopes only from the authenticated host instance.

        A Box control connection intentionally serves multiple Workspaces, so
        it is bound to the trusted LangBot instance rather than one Workspace.
        Workspace fencing remains a LangBot Host responsibility and each
        tenant action must carry its explicit generation.
        """

        self._require_host_control()
        if action == CommonAction.FILE_CHUNK.value and action_context is None:
            return None
        if action in self._HOST_CONTROL_ACTIONS:
            if (
                action_context is not None
                and action_context.instance_uuid != self._trusted_instance_uuid
            ):
                raise PermissionError(
                    "Box action context does not match the trusted instance"
                )
            return None
        if action_context is None:
            raise PermissionError(
                "Box tenant action requires a trusted Workspace context"
            )
        context = ActionContext.model_validate(action_context).without_installation()
        if context.instance_uuid != self._trusted_instance_uuid:
            raise PermissionError(
                "Box action context does not match the trusted instance"
            )
        return context

    def _action_context(self) -> ActionContext:
        self._require_host_control()
        context = self.current_action_context or self.bound_action_context
        if context is None:
            raise ValueError("Box action requires a trusted Workspace context")
        return context.without_installation()

    def _session_id(self, logical_session_id: str) -> str:
        context = self._action_context()
        if self._runtime.admission_required:
            canonical_id = self._runtime.admission_policy.logical_session_id
            if str(logical_session_id or "").strip() != canonical_id:
                raise BoxAdmissionError("Managed sandbox session_id is runtime-owned")
            logical_session_id = canonical_id
        return namespace_session_id(context, logical_session_id)

    def _workspace_sessions(self) -> list[dict]:
        prefix = session_namespace_prefix(self._action_context())
        return [
            self._logical_session_data(session)
            for session in self._runtime.get_sessions_for_workspace(
                self._action_context()
            )
            if str(session.get("session_id") or "").startswith(prefix)
        ]

    def _logical_session_data(self, value: Any) -> Any:
        """Hide physical namespace prefixes from caller-visible payloads."""

        if isinstance(value, list):
            return [self._logical_session_data(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {key: self._logical_session_data(item) for key, item in value.items()}
        if "session_id" in result:
            result["session_id"] = logical_session_id(
                self._action_context(),
                result["session_id"],
            )
        return result

    def _register_actions(self) -> None:
        @self.action(CommonAction.PING)
        async def ping(data: dict[str, Any]) -> ActionResponse:
            self._require_host_control()
            return ActionResponse.success({})

        @self.action(LangBotToBoxAction.HEALTH)
        async def health(data: dict[str, Any]) -> ActionResponse:
            self._require_host_control()
            if self._runtime.admission_required:
                readiness = await self._runtime.get_readiness()
                if not readiness.get("ready"):
                    return ActionResponse.error(
                        "BoxReadinessError: managed sandbox isolation is not ready"
                    )
                return ActionResponse.success(readiness)
            info = await self._runtime.get_backend_info()
            return ActionResponse.success(info)

        @self.action(LangBotToBoxAction.STATUS)
        async def status(data: dict[str, Any]) -> ActionResponse:
            result = await self._runtime.get_status()
            sessions = self._workspace_sessions()
            result = dict(result)
            result["capacity"] = await self._runtime.get_capacity(
                self._action_context()
            )
            result["active_sessions"] = len(sessions)
            result["managed_processes"] = sum(
                int(session.get("managed_process_count") or 0) for session in sessions
            )
            return ActionResponse.success(result)

        @self.action(LangBotToBoxAction.EXEC)
        async def exec_cmd(data: dict[str, Any]) -> ActionResponse:
            try:
                context = self._action_context()
                spec = BoxSpec.model_validate(data)
                if self._runtime.admission_required:
                    result = await self._runtime.execute(spec, action_context=context)
                else:
                    spec = spec.model_copy(
                        update={"session_id": self._session_id(spec.session_id)}
                    )
                    result = await self._runtime.execute(
                        spec,
                        action_context=context,
                    )
            except (pydantic.ValidationError, ValueError) as exc:
                if data.get("e2b_config") is not None:
                    return ActionResponse.error(
                        "BoxValidationError: Invalid E2B connection configuration"
                    )
                return ActionResponse.error(f"BoxValidationError: {exc}")
            return ActionResponse.success(
                self._logical_session_data(_result_to_dict(result))
            )

        @self.action(LangBotToBoxAction.UPLOAD_FILE)
        async def upload_file(data: dict[str, Any]) -> ActionResponse:
            request = BoxFileUploadRequest.model_validate(data)
            context = self._action_context()
            try:
                if request.size > self._runtime.max_rpc_file_bytes:
                    raise ValueError("File exceeds the configured transfer size limit")
                content = await self.read_local_file(
                    request.file_key, action_context=context
                )
                digest = hashlib.sha256(content).hexdigest()
                if len(content) != request.size or digest != request.sha256:
                    raise ValueError("Upload receipt does not match its content")
                await self._runtime.upload_file(
                    self._session_id(request.session_id),
                    request.path,
                    content,
                    context,
                )
                return ActionResponse.success(
                    {"path": request.path, "size": len(content), "sha256": digest}
                )
            finally:
                await self.delete_local_file(request.file_key, action_context=context)

        @self.action(LangBotToBoxAction.DOWNLOAD_FILE)
        async def download_file(data: dict[str, Any]) -> ActionResponse:
            request = BoxFileRequest.model_validate(data)
            context = self._action_context()
            content = await self._runtime.download_file(
                self._session_id(request.session_id),
                request.path,
                context,
            )
            await self.send_file(
                content, "", action_context=context, file_key=request.file_key
            )
            return ActionResponse.success(
                {
                    "file_key": request.file_key,
                    "path": request.path,
                    "size": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            )

        @self.action(LangBotToBoxAction.DELETE_FILE_TRANSFER)
        async def delete_file_transfer(data: dict[str, Any]) -> ActionResponse:
            await self.delete_local_file(
                data["file_key"], action_context=self._action_context()
            )
            return ActionResponse.success({})

        @self.action(LangBotToBoxAction.CREATE_SESSION)
        async def create_session(data: dict[str, Any]) -> ActionResponse:
            try:
                context = self._action_context()
                spec = BoxSpec.model_validate(data)
                if self._runtime.admission_required:
                    info = await self._runtime.create_session(
                        spec, action_context=context
                    )
                else:
                    spec = spec.model_copy(
                        update={"session_id": self._session_id(spec.session_id)}
                    )
                    info = await self._runtime.create_session(
                        spec,
                        action_context=context,
                    )
            except (pydantic.ValidationError, ValueError) as exc:
                if data.get("e2b_config") is not None:
                    return ActionResponse.error(
                        "BoxValidationError: Invalid E2B connection configuration"
                    )
                return ActionResponse.error(f"BoxValidationError: {exc}")
            return ActionResponse.success(self._logical_session_data(info))

        @self.action(LangBotToBoxAction.GET_SESSION)
        async def get_session(data: dict[str, Any]) -> ActionResponse:
            return ActionResponse.success(
                self._logical_session_data(
                    self._runtime.get_session(self._session_id(data["session_id"]))
                )
            )

        @self.action(LangBotToBoxAction.GET_SESSIONS)
        async def get_sessions(data: dict[str, Any]) -> ActionResponse:
            return ActionResponse.success({"sessions": self._workspace_sessions()})

        @self.action(LangBotToBoxAction.DELETE_SESSION)
        async def delete_session(data: dict[str, Any]) -> ActionResponse:
            physical_session_id = self._session_id(data["session_id"])
            await self._runtime.delete_session(physical_session_id)
            return ActionResponse.success({"deleted": data["session_id"]})

        @self.action(LangBotToBoxAction.START_MANAGED_PROCESS)
        async def start_managed_process(data: dict[str, Any]) -> ActionResponse:
            session_id = self._session_id(data["session_id"])
            try:
                spec = BoxManagedProcessSpec.model_validate(data["spec"])
            except pydantic.ValidationError as exc:
                return ActionResponse.error(f"BoxValidationError: {exc}")
            if self._runtime.admission_required:
                info = await self._runtime.start_managed_process(
                    session_id,
                    spec,
                    action_context=self._action_context(),
                )
            else:
                info = await self._runtime.start_managed_process(session_id, spec)
            return ActionResponse.success(self._logical_session_data(info))

        @self.action(LangBotToBoxAction.GET_MANAGED_PROCESS)
        async def get_managed_process(data: dict[str, Any]) -> ActionResponse:
            return ActionResponse.success(
                self._logical_session_data(
                    self._runtime.get_managed_process(
                        self._session_id(data["session_id"]),
                        data.get("process_id", "default"),
                    )
                )
            )

        @self.action(LangBotToBoxAction.STOP_MANAGED_PROCESS)
        async def stop_managed_process(data: dict[str, Any]) -> ActionResponse:
            await self._runtime.stop_managed_process(
                self._session_id(data["session_id"]),
                data.get("process_id", "default"),
            )
            return ActionResponse.success(
                {"stopped": data.get("process_id", "default")}
            )

        @self.action(LangBotToBoxAction.GET_BACKENDS)
        async def get_backends(data: dict[str, Any]) -> ActionResponse:
            self._require_host_control()
            from .models import E2BConnectionConfig

            options = {}
            if data.get("validate_e2b_template") is True:
                options["validate_e2b_template"] = True
            if data.get("e2b_config") is not None:
                try:
                    options["e2b_config"] = E2BConnectionConfig.model_validate(
                        data["e2b_config"]
                    )
                except pydantic.ValidationError:
                    return ActionResponse.error(
                        "BoxValidationError: Invalid E2B connection configuration"
                    )
            return ActionResponse.success(
                {
                    "backends": await self._runtime.get_backends(
                        refresh=data.get("refresh") is True, **options
                    )
                }
            )

        @self.action(LangBotToBoxAction.GET_BACKEND_INFO)
        async def get_backend_info(data: dict[str, Any]) -> ActionResponse:
            self._require_host_control()
            info = await self._runtime.get_backend_info()
            return ActionResponse.success(info)

        @self.action(LangBotToBoxAction.GET_STORAGE_ANALYSIS)
        async def get_storage_analysis(data: dict[str, Any]) -> ActionResponse:
            result = await self._runtime.get_storage_analysis(self._action_context())
            return ActionResponse.success(result)

        @self.action(LangBotToBoxAction.UPSERT_SANDBOX_ADMISSION_GRANT)
        async def upsert_sandbox_admission_grant(
            data: dict[str, Any],
        ) -> ActionResponse:
            self._require_host_control()
            try:
                grant = SandboxAdmissionGrant.model_validate(data)
            except pydantic.ValidationError as exc:
                return ActionResponse.error(f"BoxValidationError: {exc}")
            if grant.instance_uuid != self._trusted_instance_uuid:
                raise PermissionError(
                    "Sandbox admission grant does not match the trusted instance"
                )
            result = await self._runtime.upsert_sandbox_admission_grant(grant)
            self._generation_fence.observe(
                ActionContext(
                    instance_uuid=grant.instance_uuid,
                    workspace_uuid=grant.workspace_uuid,
                    placement_generation=grant.execution_generation,
                )
            )
            return ActionResponse.success(result)

        @self.action(LangBotToBoxAction.REVOKE_SANDBOX_ADMISSION_GRANT)
        async def revoke_sandbox_admission_grant(
            data: dict[str, Any],
        ) -> ActionResponse:
            self._require_host_control()
            try:
                revocation = SandboxAdmissionRevocation.model_validate(data)
            except pydantic.ValidationError as exc:
                return ActionResponse.error(f"BoxValidationError: {exc}")
            if revocation.instance_uuid != self._trusted_instance_uuid:
                raise PermissionError(
                    "Sandbox admission revocation does not match the trusted instance"
                )
            result = await self._runtime.revoke_sandbox_admission_grant(revocation)
            return ActionResponse.success(result)

        @self.action(LangBotToBoxAction.VERIFY_SHARED_WORKSPACE)
        async def verify_shared_workspace(data: dict[str, Any]) -> ActionResponse:
            self._require_host_control()
            try:
                result = await asyncio.to_thread(
                    self._runtime.verify_shared_workspace,
                    data.get("marker_name", ""),
                )
            except Exception as exc:
                return ActionResponse.error(f"BoxReadinessError: {exc}")
            return ActionResponse.success(result)

        @self.action(LangBotToBoxAction.INIT)
        async def init(data: dict[str, Any]) -> ActionResponse:
            self._require_host_control()
            if data.get("backend") == "host" and not self._allow_host_backend:
                return ActionResponse.error(
                    "BoxValidationError: host backend requires local stdio control "
                    "or WebSocket control protected by LANGBOT_BOX_CONTROL_TOKEN"
                )
            self._runtime.init(data)
            return ActionResponse.success({"initialized": True})

        @self.action(LangBotToBoxAction.SHUTDOWN)
        async def shutdown(data: dict[str, Any]) -> ActionResponse:
            self._require_host_control()
            await self._runtime.shutdown(release_identity=False)
            return ActionResponse.success({})


# Server-driven WebSocket keepalive interval (seconds) for the managed-process
# stdio relay. The Box runtime is lightly loaded and answers pings reliably;
# emitting pings from the server keeps a long-idle relay alive even when the
# LangBot client's event loop stalls briefly (which would otherwise trip the
# mcp websocket client's 20s ping/pong timeout and drop the connection).
_MANAGED_PROCESS_WS_HEARTBEAT_SEC = 30.0

# ── Managed process WebSocket relay ──────────────────────────────────


def _error_response(exc: Exception) -> web.Response:
    return web.json_response(
        {"error": {"code": type(exc).__name__, "message": str(exc)}},
        status=400,
    )


async def handle_managed_process_ws(request: web.Request) -> web.StreamResponse:
    instance_uuid = _authenticate_host_request(request, bind_instance=False)
    if instance_uuid is None:
        return _unauthorized_response()

    action_context = _relay_action_context(request, instance_uuid)
    generation_fence = request.app.get(_APP_GENERATION_FENCE_KEY)
    if action_context is None or not isinstance(generation_fence, BoxGenerationFence):
        return _unauthorized_response()
    try:
        generation_fence.require_current(action_context)
    except PermissionError:
        return _unauthorized_response()

    runtime: BoxRuntime = request.app[_APP_RUNTIME_KEY]
    if runtime.admission_required:
        try:
            grant = await runtime.require_sandbox_admission(action_context)
            if grant.max_managed_processes <= 0:
                raise BoxAdmissionError(
                    "Sandbox admission grant does not permit managed process relay"
                )
        except (BoxAdmissionError, BoxReadinessError) as exc:
            return _error_response(exc)
    session_id = request.match_info["session_id"]
    process_id = request.match_info.get("process_id", "default")
    if not session_belongs_to_placement(action_context, session_id):
        return _unauthorized_response()

    runtime_session = runtime._sessions.get(session_id)
    if runtime_session is None:
        return _error_response(
            BoxSessionNotFoundError(f"session {session_id} not found")
        )

    managed_process = runtime_session.managed_processes.get(process_id)
    if managed_process is None:
        return _error_response(
            BoxManagedProcessNotFoundError(
                f"session {session_id} has no managed process with process_id={process_id}"
            )
        )
    if not managed_process.is_running:
        return _error_response(
            BoxManagedProcessConflictError(
                f"managed process {process_id} in session {session_id} is not running"
            )
        )

    ws = web.WebSocketResponse(
        protocols=("mcp",),
        heartbeat=_MANAGED_PROCESS_WS_HEARTBEAT_SEC,
        max_msg_size=MAX_MESSAGE_BYTES,
    )
    await ws.prepare(request)
    active_websockets = request.app.setdefault(_ACTIVE_WEBSOCKETS_KEY, set())
    active_websockets.add(ws)

    try:
        async with managed_process.attach_lock:
            process = managed_process.process
            stdout = process.stdout
            stdin = process.stdin
            if stdout is None or stdin is None:
                await ws.close(message=b"managed process stdio unavailable")
                return ws

            async def _stdout_to_ws() -> None:
                while True:
                    chunk = await stdout.read(64 * 1024)
                    if not chunk:
                        break
                    generation_fence.require_current(action_context)
                    await ws.send_str(chunk.decode("utf-8", errors="replace"))
                    runtime_session.info.last_used_at = dt.datetime.now(dt.timezone.utc)

            async def _ws_to_stdin() -> None:
                async for msg in ws:
                    if msg.type == web.WSMsgType.TEXT:
                        generation_fence.require_current(action_context)
                        stdin.write((msg.data + "\n").encode("utf-8"))
                        await stdin.drain()
                        runtime_session.info.last_used_at = dt.datetime.now(
                            dt.timezone.utc
                        )
                    elif msg.type in (
                        web.WSMsgType.CLOSE,
                        web.WSMsgType.CLOSING,
                        web.WSMsgType.CLOSED,
                        web.WSMsgType.ERROR,
                    ):
                        break

            stdout_task = asyncio.create_task(_stdout_to_ws())
            stdin_task = asyncio.create_task(_ws_to_stdin())
            stale_task = asyncio.create_task(
                generation_fence.wait_until_stale(action_context)
            )
            try:
                done, pending = await asyncio.wait(
                    [stdout_task, stdin_task, stale_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                for task in done:
                    task.result()
            finally:
                for task in (stdout_task, stdin_task, stale_task):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(
                    stdout_task,
                    stdin_task,
                    stale_task,
                    return_exceptions=True,
                )
                await ws.close()
    finally:
        active_websockets.discard(ws)

    return ws


# ── Action RPC WebSocket handler ─────────────────────────────────────


async def handle_rpc_ws(request: web.Request) -> web.StreamResponse:
    """Handle action RPC over a single aiohttp WebSocket connection."""
    trusted_instance_uuid = _authenticate_host_request(request, bind_instance=True)
    if trusted_instance_uuid is None:
        return _unauthorized_response()

    runtime: BoxRuntime = request.app[_APP_RUNTIME_KEY]
    generation_fence = request.app.get(_APP_GENERATION_FENCE_KEY)
    if not isinstance(generation_fence, BoxGenerationFence):
        return _unauthorized_response()

    ws = web.WebSocketResponse(max_msg_size=MAX_MESSAGE_BYTES)
    await ws.prepare(request)
    active_websockets = request.app.setdefault(_ACTIVE_WEBSOCKETS_KEY, set())
    active_websockets.add(ws)

    connection = AiohttpWSConnection(ws)
    handler = BoxServerHandler(
        connection,
        runtime,
        host_control_authenticated=True,
        trusted_instance_uuid=trusted_instance_uuid,
        allow_host_backend=bool(request.app.get(_APP_CONTROL_TOKEN_KEY)),
        generation_fence=generation_fence,
    )
    try:
        await handler.run()
    finally:
        active_websockets.discard(ws)

    return ws


def _runtime_resource_stats(runtime: BoxRuntime) -> dict[str, Any]:
    """Return aggregate O(active-process-session) public health counters."""

    blocking_executor = getattr(runtime, "blocking_executor", None)
    managed_session_ids = getattr(
        runtime,
        "_managed_process_session_ids",
        runtime._sessions,
    )
    managed_processes = [
        managed
        for session_id in managed_session_ids
        if (session := runtime._sessions.get(session_id)) is not None
        for managed in session.managed_processes.values()
    ]
    event_loop_monitor = getattr(runtime, "event_loop_monitor", None)
    return {
        "event_loop": (
            event_loop_monitor.snapshot() if event_loop_monitor is not None else {}
        ),
        "blocking_executor": (
            blocking_executor.snapshot() if blocking_executor is not None else {}
        ),
        "sessions": len(runtime._sessions),
        "managed_processes": sum(
            1 for managed in managed_processes if managed.is_running
        ),
        "completed_processes": sum(
            1 for managed in managed_processes if not managed.is_running
        ),
        "creating_session_tasks": len(runtime._creating_session_tasks),
        "closing_session_tasks": len(runtime._closing_session_tasks),
        "background_tasks": len(runtime._background_tasks),
    }


async def handle_healthz(request: web.Request) -> web.Response:
    """Process liveness probe; it intentionally does not claim isolation readiness."""

    runtime: BoxRuntime = request.app[_APP_RUNTIME_KEY]
    return web.json_response(
        {
            "live": True,
            "resources": _runtime_resource_stats(runtime),
        }
    )


async def handle_readyz(request: web.Request) -> web.Response:
    """Strict readiness probe used by shared managed-sandbox deployments."""

    runtime: BoxRuntime = request.app[_APP_RUNTIME_KEY]
    readiness = dict(await runtime.get_readiness())
    readiness["resources"] = _runtime_resource_stats(runtime)
    return web.json_response(
        readiness,
        status=200 if readiness.get("ready") else 503,
    )


async def _close_active_websockets(app: web.Application) -> None:
    """Close live clients before aiohttp waits for request handlers to drain."""

    active_websockets = list(app.get(_ACTIVE_WEBSOCKETS_KEY, ()))
    if active_websockets:
        await asyncio.gather(
            *(
                ws.close(
                    code=WSCloseCode.GOING_AWAY,
                    message=b"Box runtime shutting down",
                )
                for ws in active_websockets
            ),
            return_exceptions=True,
        )


# ── App factory ──────────────────────────────────────────────────────


def create_app(
    runtime: BoxRuntime,
    *,
    control_token: str | None = None,
    trusted_instance_uuid: str | None = None,
    generation_fence: BoxGenerationFence | None = None,
) -> web.Application:
    """Create the aiohttp app with all WebSocket routes on a single port."""
    token = str(control_token or os.environ.get(BOX_CONTROL_TOKEN_ENV, "")).strip()
    if token:
        token = validate_control_token(token)
    app = web.Application()
    app[_APP_RUNTIME_KEY] = runtime
    app[_APP_CONTROL_TOKEN_KEY] = token
    app[_APP_TRUSTED_INSTANCE_KEY] = {
        "value": (
            normalize_instance_uuid(trusted_instance_uuid)
            if trusted_instance_uuid is not None
            else None
        )
    }
    app[_APP_GENERATION_FENCE_KEY] = generation_fence or BoxGenerationFence(
        max_records=runtime.max_admission_records
    )
    app[_ACTIVE_WEBSOCKETS_KEY] = set()
    app.on_shutdown.append(_close_active_websockets)
    app.router.add_get("/healthz", handle_healthz)
    app.router.add_get("/readyz", handle_readyz)
    app.router.add_get("/rpc/ws", handle_rpc_ws)
    app.router.add_get(
        "/v1/sessions/{session_id}/managed-process/{process_id}/ws",
        handle_managed_process_ws,
    )
    # Backward-compatible route (defaults to process_id='default')
    app.router.add_get(
        "/v1/sessions/{session_id}/managed-process/ws", handle_managed_process_ws
    )
    return app


def create_ws_relay_app(
    runtime: BoxRuntime,
    *,
    control_token: str | None = None,
    trusted_instance_uuid: str | None = None,
    generation_fence: BoxGenerationFence | None = None,
) -> web.Application:
    """Backward-compatible alias for older callers.

    The relay and action RPC endpoints now live in one aiohttp app.
    """
    return create_app(
        runtime,
        control_token=control_token,
        trusted_instance_uuid=trusted_instance_uuid,
        generation_fence=generation_fence,
    )


# ── Entry point ──────────────────────────────────────────────────────


async def _run_server(
    host: str,
    port: int,
    mode: str,
    instance_id: str | None = None,
    data_dir: str | None = None,
) -> None:
    blocking_executor = configure_bounded_default_executor_from_env(
        thread_name_prefix="langbot-box-runtime-blocking",
    )
    control_token = str(os.environ.get(BOX_CONTROL_TOKEN_ENV, "")).strip()
    if control_token:
        control_token = validate_control_token(control_token)
    configured_instance_uuid = (
        os.environ.get(BOX_TRUSTED_INSTANCE_ENV, "").strip() or None
    )
    if mode == "stdio" and configured_instance_uuid is None:
        raise RuntimeError(
            f"{BOX_TRUSTED_INSTANCE_ENV} is required for stdio Box control"
        )
    if configured_instance_uuid is not None:
        configured_instance_uuid = normalize_instance_uuid(configured_instance_uuid)

    runtime = BoxRuntime(logger=logger, instance_id=instance_id, data_dir=data_dir)
    runtime.blocking_executor = blocking_executor
    runtime_box_config = getattr(runtime, "_box_config", {})
    if (
        mode != "stdio"
        and runtime_box_config.get("backend") == "host"
        and not control_token
    ):
        raise RuntimeError(
            "WebSocket-controlled host backend requires LANGBOT_BOX_CONTROL_TOKEN"
        )
    runner: web.AppRunner | None = None
    initialized = False
    try:
        await runtime.initialize()
        initialized = True

        # Start aiohttp — serves managed-process relay and (in ws mode)
        # also the action RPC endpoint, all on the same port.
        generation_fence = BoxGenerationFence(max_records=runtime.max_admission_records)
        try:
            ws_app = create_app(
                runtime,
                control_token=control_token,
                trusted_instance_uuid=configured_instance_uuid,
                generation_fence=generation_fence,
            )
            runner = web.AppRunner(ws_app)
            await runner.setup()
            site = web.TCPSite(runner, host, port)
            await site.start()
            logger.info(f"Box server listening on {host}:{port}")
        except OSError as exc:
            logger.warning(f"Box server failed to bind {host}:{port}: {exc}")
            logger.warning("Managed process WebSocket attach will be unavailable.")
            if mode != "stdio":
                raise

        if mode == "stdio":
            from langbot_plugin.runtime.io.controllers.stdio.server import (
                StdioServerController,
            )

            assert configured_instance_uuid is not None

            async def new_connection_callback(connection: Connection) -> None:
                handler = BoxServerHandler(
                    connection,
                    runtime,
                    host_control_authenticated=True,
                    trusted_instance_uuid=configured_instance_uuid,
                    allow_host_backend=True,
                    generation_fence=generation_fence,
                )
                await handler.run()

            ctrl = StdioServerController()
            await ctrl.run(new_connection_callback)
        else:
            # In ws mode, action RPC is served via aiohttp on /rpc/ws.
            # Keep the server alive until cancelled.
            logger.info(f"Box action RPC available at ws://{host}:{port}/rpc/ws")
            stop_event = asyncio.Event()
            await stop_event.wait()
    finally:
        if runner is not None:
            with contextlib.suppress(Exception):
                await runner.cleanup()
        if initialized:
            try:
                await runtime.shutdown()
            finally:
                await runtime.stop_background_reaper()


def main(args: argparse.Namespace) -> None:
    """Run the Box runtime service.

    Invoked by the `box` CLI subcommand with the parsed argument namespace,
    mirroring how `lbp rt` drives ``langbot_plugin.runtime.app.main``. The
    argument schema is defined once, on the `box` subparser in
    ``langbot_plugin.cli``.
    """
    # Mode selection mirrors the plugin runtime (`lbp rt`): WebSocket by
    # default, stdio when `-s`/`--stdio-control` is passed.
    control_mode = "stdio" if args.stdio_control else "ws"

    configure_process_logging(stream=sys.stderr)
    try:
        asyncio.run(
            _run_server(
                args.host,
                args.ws_control_port,
                control_mode,
                getattr(args, "instance_id", None),
                getattr(args, "data_dir", None),
            )
        )
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt, Box runtime stopped")
