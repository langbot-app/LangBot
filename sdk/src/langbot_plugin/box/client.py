"""BoxRuntimeClient abstraction for Box Runtime access."""

from __future__ import annotations

import abc
import logging
from typing import Any

from langbot_plugin.runtime.io.handler import Handler
from langbot_plugin.entities.io.context import ActionContext

from .actions import LangBotToBoxAction
from .errors import BoxError, BoxRuntimeUnavailableError
from .models import (
    BoxExecutionResult,
    BoxExecutionStatus,
    BoxManagedProcessInfo,
    BoxManagedProcessSpec,
    BoxSpec,
    SandboxAdmissionGrant,
    SandboxAdmissionRevocation,
)


class BoxRuntimeClient(abc.ABC):
    """Abstract interface that BoxService uses to talk to a Box Runtime."""

    @abc.abstractmethod
    async def initialize(self) -> None: ...

    @abc.abstractmethod
    async def execute(
        self, spec: BoxSpec, action_context: ActionContext | None = None
    ) -> BoxExecutionResult: ...

    @abc.abstractmethod
    async def shutdown(self) -> None: ...

    @abc.abstractmethod
    async def get_status(self, action_context: ActionContext | None = None) -> dict: ...

    @abc.abstractmethod
    async def get_sessions(
        self, action_context: ActionContext | None = None
    ) -> list[dict]: ...

    @abc.abstractmethod
    async def get_backend_info(self) -> dict: ...

    async def get_storage_analysis(
        self, action_context: ActionContext | None = None
    ) -> dict:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_session(
        self, session_id: str, action_context: ActionContext | None = None
    ) -> None: ...

    @abc.abstractmethod
    async def create_session(
        self, spec: BoxSpec, action_context: ActionContext | None = None
    ) -> dict: ...

    @abc.abstractmethod
    async def start_managed_process(
        self,
        session_id: str,
        spec: BoxManagedProcessSpec,
        action_context: ActionContext | None = None,
    ) -> BoxManagedProcessInfo: ...

    @abc.abstractmethod
    async def get_managed_process(
        self,
        session_id: str,
        process_id: str = "default",
        action_context: ActionContext | None = None,
    ) -> BoxManagedProcessInfo: ...

    @abc.abstractmethod
    async def stop_managed_process(
        self,
        session_id: str,
        process_id: str = "default",
        action_context: ActionContext | None = None,
    ) -> None: ...

    @abc.abstractmethod
    async def get_session(
        self, session_id: str, action_context: ActionContext | None = None
    ) -> dict: ...

    @abc.abstractmethod
    async def init(self, config: dict) -> None: ...

    async def verify_shared_workspace(self, marker_name: str) -> dict:
        raise NotImplementedError

    async def upsert_sandbox_admission_grant(
        self, grant: SandboxAdmissionGrant
    ) -> dict:
        raise NotImplementedError

    async def revoke_sandbox_admission_grant(
        self, revocation: SandboxAdmissionRevocation
    ) -> dict:
        raise NotImplementedError


def _translate_action_error(exc: Exception) -> BoxError:
    """Convert an ActionCallError message back into the appropriate BoxError subclass."""
    from .errors import (
        BoxBackendUnavailableError,
        BoxAdmissionError,
        BoxManagedProcessConflictError,
        BoxManagedProcessNotFoundError,
        BoxCapacityExceededError,
        BoxReadinessError,
        BoxSessionConflictError,
        BoxSessionNotFoundError,
        BoxValidationError,
    )

    msg = str(exc)
    _ERROR_PREFIX_MAP: list[tuple[str, type[BoxError]]] = [
        ("BoxAdmissionError:", BoxAdmissionError),
        ("BoxReadinessError:", BoxReadinessError),
        ("BoxCapacityExceededError:", BoxCapacityExceededError),
        ("BoxValidationError:", BoxValidationError),
        ("BoxSessionNotFoundError:", BoxSessionNotFoundError),
        ("BoxSessionConflictError:", BoxSessionConflictError),
        ("BoxManagedProcessNotFoundError:", BoxManagedProcessNotFoundError),
        ("BoxManagedProcessConflictError:", BoxManagedProcessConflictError),
        ("BoxBackendUnavailableError:", BoxBackendUnavailableError),
        ("BoxCapacityExceededError:", BoxCapacityExceededError),
    ]
    for prefix, cls in _ERROR_PREFIX_MAP:
        if prefix in msg:
            return cls(msg)
    return BoxError(msg)


class ActionRPCBoxClient(BoxRuntimeClient):
    """Client that talks to BoxRuntime via the action RPC protocol."""

    def __init__(self, logger: logging.Logger):
        self._logger = logger
        self._handler: Handler | None = None

    @property
    def handler(self) -> Handler:
        if self._handler is None:
            raise BoxRuntimeUnavailableError("box runtime not connected")
        return self._handler

    def set_handler(self, handler: Handler | None) -> None:
        self._handler = handler

    async def _call(
        self,
        action: LangBotToBoxAction,
        data: dict[str, Any],
        timeout: float = 15.0,
        action_context: ActionContext | None = None,
    ) -> dict[str, Any]:
        try:
            return await self.handler.call_action(
                action,
                data,
                timeout=timeout,
                action_context=action_context,
                cancel_peer_on_cancel=action == LangBotToBoxAction.EXEC,
            )
        except BoxRuntimeUnavailableError:
            raise
        except Exception as exc:
            raise _translate_action_error(exc) from exc

    async def initialize(self) -> None:
        try:
            await self._call(LangBotToBoxAction.HEALTH, {})
            self._logger.info("LangBot Box runtime connected via action RPC.")
        except Exception as exc:
            raise BoxRuntimeUnavailableError(f"box runtime unavailable: {exc}") from exc

    async def execute(
        self, spec: BoxSpec, action_context: ActionContext | None = None
    ) -> BoxExecutionResult:
        data = await self._call(
            LangBotToBoxAction.EXEC,
            spec.model_dump(mode="json"),
            timeout=300.0,
            action_context=action_context,
        )
        return BoxExecutionResult(
            session_id=data["session_id"],
            backend_name=data["backend_name"],
            status=BoxExecutionStatus(data["status"]),
            exit_code=data.get("exit_code"),
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            duration_ms=data["duration_ms"],
        )

    async def shutdown(self) -> None:
        if self._handler is not None:
            try:
                await self._call(LangBotToBoxAction.SHUTDOWN, {})
            except Exception as exc:
                self._logger.debug(
                    "Box runtime shutdown action failed during cleanup: %s",
                    exc,
                    exc_info=True,
                )
            self._handler = None

    async def get_status(self, action_context: ActionContext | None = None) -> dict:
        return await self._call(
            LangBotToBoxAction.STATUS, {}, action_context=action_context
        )

    async def get_sessions(
        self, action_context: ActionContext | None = None
    ) -> list[dict]:
        data = await self._call(
            LangBotToBoxAction.GET_SESSIONS, {}, action_context=action_context
        )
        return data["sessions"]

    async def get_session(
        self, session_id: str, action_context: ActionContext | None = None
    ) -> dict:
        return await self._call(
            LangBotToBoxAction.GET_SESSION,
            {"session_id": session_id},
            action_context=action_context,
        )

    async def get_backend_info(self) -> dict:
        return await self._call(LangBotToBoxAction.GET_BACKEND_INFO, {})

    async def get_storage_analysis(
        self, action_context: ActionContext | None = None
    ) -> dict:
        return await self._call(
            LangBotToBoxAction.GET_STORAGE_ANALYSIS,
            {},
            timeout=60.0,
            action_context=action_context,
        )

    async def delete_session(
        self, session_id: str, action_context: ActionContext | None = None
    ) -> None:
        await self._call(
            LangBotToBoxAction.DELETE_SESSION,
            {"session_id": session_id},
            timeout=30.0,
            action_context=action_context,
        )

    async def create_session(
        self, spec: BoxSpec, action_context: ActionContext | None = None
    ) -> dict:
        return await self._call(
            LangBotToBoxAction.CREATE_SESSION,
            spec.model_dump(mode="json"),
            # Backend session startup may run a full sandbox/container create
            # path. The Docker backend itself allows up to 30s, so the RPC
            # client must wait longer than the backend's own operation limit.
            timeout=60.0,
            action_context=action_context,
        )

    async def start_managed_process(
        self,
        session_id: str,
        spec: BoxManagedProcessSpec,
        action_context: ActionContext | None = None,
    ) -> BoxManagedProcessInfo:
        data = await self._call(
            LangBotToBoxAction.START_MANAGED_PROCESS,
            {"session_id": session_id, "spec": spec.model_dump(mode="json")},
            # Starting a managed process can involve a cold dependency bootstrap
            # (e.g. `uvx <pkg>` downloading the package + interpreter on first
            # run), which easily exceeds the default 15s action timeout and
            # caused stdio MCP servers to be torn down mid-install. Give it
            # headroom so the first launch can complete.
            timeout=30.0,
            action_context=action_context,
        )
        return BoxManagedProcessInfo.model_validate(data)

    async def get_managed_process(
        self,
        session_id: str,
        process_id: str = "default",
        action_context: ActionContext | None = None,
    ) -> BoxManagedProcessInfo:
        data = await self._call(
            LangBotToBoxAction.GET_MANAGED_PROCESS,
            {
                "session_id": session_id,
                "process_id": process_id,
            },
            action_context=action_context,
        )
        return BoxManagedProcessInfo.model_validate(data)

    async def stop_managed_process(
        self,
        session_id: str,
        process_id: str = "default",
        action_context: ActionContext | None = None,
    ) -> None:
        await self._call(
            LangBotToBoxAction.STOP_MANAGED_PROCESS,
            {
                "session_id": session_id,
                "process_id": process_id,
            },
            timeout=30.0,
            action_context=action_context,
        )

    def get_managed_process_websocket_url(
        self,
        session_id: str,
        ws_relay_base_url: str,
        process_id: str = "default",
        action_context: ActionContext | None = None,
    ) -> str:
        if action_context is not None:
            from .tenancy import namespace_session_id

            session_id = namespace_session_id(action_context, session_id)
        base = ws_relay_base_url
        if base.startswith("https://"):
            scheme = "wss://"
            suffix = base[len("https://") :]
        elif base.startswith("http://"):
            scheme = "ws://"
            suffix = base[len("http://") :]
        else:
            scheme = "ws://"
            suffix = base
        return (
            f"{scheme}{suffix}/v1/sessions/{session_id}/managed-process/{process_id}/ws"
        )

    async def init(self, config: dict) -> None:
        await self._call(LangBotToBoxAction.INIT, config)

    async def verify_shared_workspace(self, marker_name: str) -> dict:
        return await self._call(
            LangBotToBoxAction.VERIFY_SHARED_WORKSPACE,
            {"marker_name": marker_name},
        )

    async def upsert_sandbox_admission_grant(
        self, grant: SandboxAdmissionGrant
    ) -> dict:
        return await self._call(
            LangBotToBoxAction.UPSERT_SANDBOX_ADMISSION_GRANT,
            grant.model_dump(mode="json"),
        )

    async def revoke_sandbox_admission_grant(
        self, revocation: SandboxAdmissionRevocation
    ) -> dict:
        return await self._call(
            LangBotToBoxAction.REVOKE_SANDBOX_ADMISSION_GRANT,
            revocation.model_dump(mode="json"),
            timeout=30.0,
        )
