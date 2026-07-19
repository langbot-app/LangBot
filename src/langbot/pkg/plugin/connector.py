# For connect to plugin runtime.
from __future__ import annotations

import asyncio
import contextvars
import hashlib
import io
import time
import uuid
import zipfile
from typing import Any
import typing
import os
import secrets
import sys
import httpx
import sqlalchemy
import yaml
from urllib.parse import urljoin, urlparse
from langbot_plugin.api.entities.builtin.pipeline.query import provider_session

from ..core import app
from . import handler
from .github import (
    validate_github_plugin_install_info,
    validate_github_release_asset_url,
)
from ..utils import constants, platform
from ..utils.managed_runtime import ManagedRuntimeConnector
from langbot_plugin.runtime.io.controllers.stdio import (
    client as stdio_client_controller,
)
from langbot_plugin.runtime.io.controllers.ws import client as ws_client_controller
from langbot_plugin.api.entities import events
from langbot_plugin.api.entities import context
import langbot_plugin.runtime.io.connection as base_connection
from langbot_plugin.api.definition.components.manifest import ComponentManifest
from langbot_plugin.api.entities.builtin.command import (
    context as command_context,
    errors as command_errors,
)
from langbot_plugin.runtime.plugin.mgr import PluginInstallSource
from langbot_plugin.runtime.security import (
    PLUGIN_RUNTIME_CONTROL_TOKEN_ENV,
    PLUGIN_RUNTIME_CONTROL_TOKEN_HEADER,
    validate_runtime_secret,
)
from langbot_plugin.entities.io.context import (
    InstallationBinding,
    PluginInstallationDesiredState,
    PluginWorkerPolicy,
    RuntimeIdentity,
)
from ..core import taskmgr
from ..entity.persistence import bstorage as persistence_bstorage
from ..entity.persistence import plugin as persistence_plugin
from ..api.http.context import ExecutionContext
from ..api.http.service.tenant import TenantContext, require_workspace_uuid
from ..workspace.errors import WorkspaceNotFoundError


_PLUGIN_ARTIFACT_OWNER_TYPE = 'plugin_artifact'
_PLUGIN_ARTIFACT_KEY = 'package.lbpkg'
_PLUGIN_ARTIFACT_STORAGE_MARKER = 'tenant_binary_storage_v1'
_GITHUB_PLUGIN_DOWNLOAD_MAX_BYTES = 10 * 1024 * 1024
_GITHUB_PLUGIN_DOWNLOAD_MAX_REDIRECTS = 5
_GITHUB_ASSET_HOSTS = frozenset(
    {
        'api.github.com',
        'github.com',
        'objects.githubusercontent.com',
        'release-assets.githubusercontent.com',
    }
)
_HTTP_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


class PluginRuntimeNotConnectedError(RuntimeError):
    """Raised when plugin runtime operations are requested before connection."""


class PluginInstallationFailedError(RuntimeError):
    """Stable Runtime desired-state failure for one plugin installation."""

    def __init__(
        self,
        installation_uuid: str,
        error_code: str,
        message: str,
    ) -> None:
        self.installation_uuid = installation_uuid
        self.error_code = error_code
        self.runtime_message = message
        super().__init__(f'Plugin installation {installation_uuid} failed [{error_code}]: {message}')


class PluginRuntimeConnector(ManagedRuntimeConnector):
    """Plugin runtime connector"""

    handler: handler.RuntimeConnectionHandler

    handler_task: asyncio.Task

    heartbeat_task: asyncio.Task | None = None

    stdio_client_controller: stdio_client_controller.StdioClientController

    ctrl: stdio_client_controller.StdioClientController | ws_client_controller.WebSocketClientController

    runtime_disconnect_callback: typing.Callable[
        [PluginRuntimeConnector], typing.Coroutine[typing.Any, typing.Any, None]
    ]

    is_enable_plugin: bool = True
    """Mark if the plugin system is enabled"""

    def __init__(
        self,
        ap: app.Application,
        runtime_disconnect_callback: typing.Callable[
            [PluginRuntimeConnector], typing.Coroutine[typing.Any, typing.Any, None]
        ],
    ):
        super().__init__(ap)
        self.runtime_disconnect_callback = runtime_disconnect_callback
        self.is_enable_plugin = self.ap.instance_config.data.get('plugin', {}).get('enable', True)
        self.runtime_profile: typing.Literal['oss_dev', 'shared'] = (
            'shared' if getattr(getattr(ap, 'deployment', None), 'mode', 'oss') == 'cloud' else 'oss_dev'
        )
        self.runtime_identity: RuntimeIdentity | None = None
        self._runtime_id = str(uuid.uuid4())
        self.worker_policy: PluginWorkerPolicy | None = None
        self._execution_context: contextvars.ContextVar[ExecutionContext | None] = contextvars.ContextVar(
            f'{self.__class__.__name__}_{id(self)}_execution_context',
            default=None,
        )
        self._known_desired_states: dict[str, PluginInstallationDesiredState] = {}
        self._workspace_installations: dict[str, set[str]] = {}
        self._installation_failures: dict[str, dict[str, str]] = {}
        self._state_lock = asyncio.Lock()
        self._control_token = str(os.environ.get(PLUGIN_RUNTIME_CONTROL_TOKEN_ENV) or '').strip()

    def _load_worker_policy(self) -> PluginWorkerPolicy:
        """Validate the instance policy without consulting plugin manifests."""

        worker = self.ap.instance_config.data.get('plugin', {}).get('worker')
        if not isinstance(worker, dict):
            raise ValueError('plugin.worker must be configured')
        return PluginWorkerPolicy.model_validate(
            {
                'max_cpus': worker.get('max_cpus'),
                'max_memory_mb': worker.get('max_memory_mb'),
                'max_pids': worker.get('max_pids'),
                'max_open_files': worker.get('max_open_files'),
                'max_file_size_mb': worker.get('max_file_size_mb'),
                'require_hard_limits': worker.get('require_hard_limits', False),
            }
        )

    def _control_headers(self, *, allow_generate: bool) -> dict[str, str]:
        if not self._control_token and allow_generate:
            self._control_token = secrets.token_urlsafe(48)
        try:
            self._control_token = validate_runtime_secret(
                self._control_token,
                name=PLUGIN_RUNTIME_CONTROL_TOKEN_ENV,
            )
        except ValueError as exc:
            raise PluginRuntimeNotConnectedError(
                f'{PLUGIN_RUNTIME_CONTROL_TOKEN_ENV} must be configured with a strong shared secret '
                'for an external Plugin Runtime'
            ) from exc
        return {PLUGIN_RUNTIME_CONTROL_TOKEN_HEADER: self._control_token}

    @staticmethod
    def _execution_from_binding(binding: Any) -> ExecutionContext:
        return ExecutionContext(
            instance_uuid=str(binding.instance_uuid),
            workspace_uuid=str(binding.workspace_uuid),
            placement_generation=int(binding.placement_generation),
        )

    @staticmethod
    def _binding_from_setting(
        execution_context: ExecutionContext,
        setting: persistence_plugin.PluginSetting,
    ) -> InstallationBinding:
        return InstallationBinding(
            instance_uuid=execution_context.instance_uuid,
            workspace_uuid=execution_context.workspace_uuid,
            placement_generation=execution_context.placement_generation,
            installation_uuid=setting.installation_uuid,
            runtime_revision=setting.runtime_revision,
            artifact_digest=setting.artifact_digest,
        )

    def _legacy_oss_bridge_binding(self, execution_context: ExecutionContext) -> InstallationBinding:
        seed = f'langbot:oss-plugin-bridge:{execution_context.instance_uuid}:{execution_context.workspace_uuid}'
        return InstallationBinding(
            instance_uuid=execution_context.instance_uuid,
            workspace_uuid=execution_context.workspace_uuid,
            placement_generation=execution_context.placement_generation,
            installation_uuid=str(uuid.uuid5(uuid.NAMESPACE_URL, seed)),
            runtime_revision=1,
            artifact_digest=hashlib.sha256(seed.encode()).hexdigest(),
        )

    @staticmethod
    def _artifact_unique_key(execution_context: ExecutionContext, artifact_digest: str) -> str:
        # StorageMgr imports the Application graph that wires this connector;
        # keep the dependency lazy so either module remains independently
        # importable by tools and focused tests.
        from ..storage.mgr import StorageMgr

        return StorageMgr.canonical_binary_storage_key(
            execution_context,
            owner_type=_PLUGIN_ARTIFACT_OWNER_TYPE,
            owner=artifact_digest,
            key=_PLUGIN_ARTIFACT_KEY,
        )

    async def _store_artifact_package(
        self,
        execution_context: ExecutionContext,
        artifact_digest: str,
        artifact_package: bytes,
    ) -> None:
        """Persist one verified lbpkg in the existing tenant-scoped blob table."""

        if hashlib.sha256(artifact_package).hexdigest() != artifact_digest:
            raise ValueError('Plugin package digest does not match its desired state')
        unique_key = self._artifact_unique_key(execution_context, artifact_digest)

        async def store(execute) -> None:
            result = await execute(
                sqlalchemy.select(persistence_bstorage.BinaryStorage.value)
                .where(persistence_bstorage.BinaryStorage.workspace_uuid == execution_context.workspace_uuid)
                .where(persistence_bstorage.BinaryStorage.unique_key == unique_key)
            )
            existing_value = result.scalar_one_or_none()
            if existing_value is not None:
                if hashlib.sha256(bytes(existing_value)).hexdigest() != artifact_digest:
                    raise ValueError('Persisted plugin package failed digest verification')
                return
            await execute(
                sqlalchemy.insert(persistence_bstorage.BinaryStorage).values(
                    workspace_uuid=execution_context.workspace_uuid,
                    unique_key=unique_key,
                    key=_PLUGIN_ARTIFACT_KEY,
                    owner_type=_PLUGIN_ARTIFACT_OWNER_TYPE,
                    owner=artifact_digest,
                    value=artifact_package,
                )
            )

        tenant_uow = getattr(self.ap.persistence_mgr, 'tenant_uow', None)
        if callable(tenant_uow):
            async with tenant_uow(execution_context.workspace_uuid) as uow:
                await store(uow.execute)
        else:
            await store(self.ap.persistence_mgr.execute_async)

    async def _load_artifact_package(
        self,
        execution_context: ExecutionContext,
        artifact_digest: str,
    ) -> bytes | None:
        unique_key = self._artifact_unique_key(execution_context, artifact_digest)
        statement = (
            sqlalchemy.select(persistence_bstorage.BinaryStorage.value)
            .where(persistence_bstorage.BinaryStorage.workspace_uuid == execution_context.workspace_uuid)
            .where(persistence_bstorage.BinaryStorage.unique_key == unique_key)
        )

        async def load(execute) -> bytes | None:
            result = await execute(statement)
            stored_value = result.scalar_one_or_none()
            if stored_value is None:
                return None
            artifact_package = bytes(stored_value)
            if hashlib.sha256(artifact_package).hexdigest() != artifact_digest:
                raise ValueError('Persisted plugin package failed digest verification')
            return artifact_package

        tenant_uow = getattr(self.ap.persistence_mgr, 'tenant_uow', None)
        if callable(tenant_uow):
            async with tenant_uow(execution_context.workspace_uuid) as uow:
                return await load(uow.execute)
        return await load(self.ap.persistence_mgr.execute_async)

    async def _delete_artifact_if_unreferenced(
        self,
        execution_context: ExecutionContext,
        artifact_digest: str,
        *,
        execute=None,
    ) -> None:
        """Delete a tenant copy only after its last desired-state reference."""

        async def cleanup(run) -> None:
            result = await run(
                sqlalchemy.select(sqlalchemy.func.count())
                .select_from(persistence_plugin.PluginSetting)
                .where(persistence_plugin.PluginSetting.workspace_uuid == execution_context.workspace_uuid)
                .where(persistence_plugin.PluginSetting.artifact_digest == artifact_digest)
            )
            if int(result.scalar_one()) != 0:
                return
            await run(
                sqlalchemy.delete(persistence_bstorage.BinaryStorage)
                .where(persistence_bstorage.BinaryStorage.workspace_uuid == execution_context.workspace_uuid)
                .where(persistence_bstorage.BinaryStorage.owner_type == _PLUGIN_ARTIFACT_OWNER_TYPE)
                .where(persistence_bstorage.BinaryStorage.owner == artifact_digest)
            )

        if execute is not None:
            await cleanup(execute)
            return
        tenant_uow = getattr(self.ap.persistence_mgr, 'tenant_uow', None)
        if callable(tenant_uow):
            async with tenant_uow(execution_context.workspace_uuid) as uow:
                await cleanup(uow.execute)
        else:
            await cleanup(self.ap.persistence_mgr.execute_async)

    async def _load_workspace_settings(
        self,
        execution_context: ExecutionContext,
    ) -> list[persistence_plugin.PluginSetting]:
        statement = (
            sqlalchemy.select(*persistence_plugin.PluginSetting.__table__.c)
            .where(persistence_plugin.PluginSetting.workspace_uuid == execution_context.workspace_uuid)
            .order_by(
                persistence_plugin.PluginSetting.priority.desc(),
                persistence_plugin.PluginSetting.created_at.asc(),
            )
        )
        tenant_uow = getattr(self.ap.persistence_mgr, 'tenant_uow', None)
        if callable(tenant_uow):
            async with tenant_uow(execution_context.workspace_uuid) as uow:
                result = await uow.execute(statement)
                return [persistence_plugin.PluginSetting(**dict(row)) for row in result.mappings().all()]
        result = await self.ap.persistence_mgr.execute_async(statement)
        return [persistence_plugin.PluginSetting(**dict(row)) for row in result.mappings().all()]

    async def _load_workspace_desired_states(
        self,
        execution_context: ExecutionContext,
    ) -> tuple[PluginInstallationDesiredState, ...]:
        settings = await self._load_workspace_settings(execution_context)
        desired_states: list[PluginInstallationDesiredState] = []
        for setting in settings:
            binding = self._binding_from_setting(execution_context, setting)
            if hasattr(self, 'handler'):
                self.handler.register_installation_binding(
                    binding,
                    plugin_author=setting.plugin_author,
                    plugin_name=setting.plugin_name,
                )
            desired_states.append(
                PluginInstallationDesiredState(
                    binding=binding,
                    enabled=setting.enabled,
                )
            )
        return tuple(desired_states)

    async def _apply_desired_state(
        self,
        desired: PluginInstallationDesiredState,
        *,
        artifact_package: bytes | None = None,
    ) -> dict[str, Any]:
        result = await self.handler.apply_plugin_installation(
            desired.binding,
            artifact_package=artifact_package,
            enabled=desired.enabled,
        )
        self._raise_apply_failure(desired, result)
        if result.get('state') != 'artifact_missing':
            self._installation_failures.pop(desired.binding.installation_uuid, None)
            return result
        execution_context = self._execution_from_binding(desired.binding)
        persisted_package = await self._load_artifact_package(
            execution_context,
            desired.binding.artifact_digest,
        )
        if persisted_package is None:
            if self.runtime_profile == 'oss_dev':
                self.ap.logger.warning(
                    'Keeping legacy OSS plugin installation %s on data/plugins; no durable lbpkg is available',
                    desired.binding.installation_uuid,
                )
                return result
            raise RuntimeError(
                f'Durable plugin artifact {desired.binding.artifact_digest} is missing for '
                f'installation {desired.binding.installation_uuid}'
            )
        repaired = await self.handler.apply_plugin_installation(
            desired.binding,
            artifact_package=persisted_package,
            enabled=desired.enabled,
        )
        self._raise_apply_failure(desired, repaired)
        if repaired.get('state') == 'artifact_missing':
            raise RuntimeError(
                f'Runtime rejected durable plugin artifact for installation {desired.binding.installation_uuid}'
            )
        self._installation_failures.pop(desired.binding.installation_uuid, None)
        return repaired

    @staticmethod
    def _runtime_failure_fields(
        installation_uuid: str,
        value: Any,
    ) -> tuple[str, str, str]:
        if not isinstance(value, dict):
            return (
                installation_uuid,
                'runtime_installation_failed',
                ('Plugin Runtime returned a malformed installation failure'),
            )
        reported_uuid = str(value.get('installation_uuid') or installation_uuid).strip()
        if reported_uuid != installation_uuid:
            return (
                installation_uuid,
                'runtime_installation_failed',
                ('Plugin Runtime returned a mismatched installation failure'),
            )
        error_code = str(value.get('error_code') or 'runtime_installation_failed').strip()
        if (
            not error_code
            or len(error_code) > 64
            or not error_code.isascii()
            or any(not (character.isalnum() or character in {'_', '-'}) for character in error_code)
        ):
            error_code = 'runtime_installation_failed'
        message = 'Plugin Runtime failed to apply the desired installation'
        candidate = str(value.get('message') or '').replace('\r', ' ').replace('\n', ' ').strip()
        if candidate:
            message = candidate[:512]
        return installation_uuid, error_code, message

    def _raise_apply_failure(
        self,
        desired: PluginInstallationDesiredState,
        result: dict[str, Any],
    ) -> None:
        if result.get('state') != 'failed':
            return
        installation_uuid, error_code, message = self._runtime_failure_fields(
            desired.binding.installation_uuid,
            result,
        )
        failure = {
            'installation_uuid': installation_uuid,
            'error_code': error_code,
            'message': message,
        }
        self._installation_failures[installation_uuid] = failure
        self.ap.logger.error(
            'Plugin installation %s failed during apply [%s]: %s',
            installation_uuid,
            error_code,
            message,
        )
        raise PluginInstallationFailedError(
            installation_uuid,
            error_code,
            message,
        )

    def _record_reconcile_failures(
        self,
        desired_states: dict[str, PluginInstallationDesiredState],
        result: dict[str, Any],
    ) -> None:
        reported = result.get('failed_installations', [])
        if not isinstance(reported, list):
            self.ap.logger.error('Plugin Runtime returned malformed failed_installations during reconcile')
            reported = []

        failures: dict[str, dict[str, str]] = {}
        for value in reported:
            requested_uuid = str(value.get('installation_uuid') or '').strip() if isinstance(value, dict) else ''
            if requested_uuid not in desired_states:
                self.ap.logger.error(
                    'Plugin Runtime reported failure for unknown installation %s',
                    requested_uuid or '<missing>',
                )
                continue
            installation_uuid, error_code, message = self._runtime_failure_fields(
                requested_uuid,
                value,
            )
            failure = {
                'installation_uuid': installation_uuid,
                'error_code': error_code,
                'message': message,
            }
            failures[installation_uuid] = failure
            if self._installation_failures.get(installation_uuid) != failure:
                self.ap.logger.error(
                    'Plugin installation %s failed during reconcile [%s]: %s',
                    installation_uuid,
                    error_code,
                    message,
                )

        for installation_uuid in tuple(self._installation_failures):
            if installation_uuid not in failures:
                self._installation_failures.pop(installation_uuid, None)
        self._installation_failures.update(failures)

    async def _repair_reconcile_missing_artifacts(
        self,
        desired_states: dict[str, PluginInstallationDesiredState],
        result: dict[str, Any],
    ) -> None:
        for installation_uuid in result.get('missing_artifacts', []):
            desired = desired_states.get(str(installation_uuid))
            if desired is None:
                raise RuntimeError(f'Runtime reported an unknown missing installation {installation_uuid}')
            execution_context = self._execution_from_binding(desired.binding)
            persisted_package = await self._load_artifact_package(
                execution_context,
                desired.binding.artifact_digest,
            )
            if persisted_package is None:
                if self.runtime_profile == 'oss_dev':
                    self.ap.logger.warning(
                        'Keeping legacy OSS plugin installation %s on data/plugins; no durable lbpkg is available',
                        desired.binding.installation_uuid,
                    )
                    continue
                raise RuntimeError(
                    f'Durable plugin artifact {desired.binding.artifact_digest} is missing for '
                    f'installation {desired.binding.installation_uuid}'
                )
            try:
                await self._apply_desired_state(
                    desired,
                    artifact_package=persisted_package,
                )
            except PluginInstallationFailedError as exc:
                failures = result.setdefault('failed_installations', [])
                if not any(
                    isinstance(item, dict) and item.get('installation_uuid') == exc.installation_uuid
                    for item in failures
                ):
                    failures.append(
                        {
                            'installation_uuid': exc.installation_uuid,
                            'error_code': exc.error_code,
                            'message': exc.runtime_message,
                        }
                    )

    async def _prepare_connected_runtime(self) -> None:
        """Handshake follow-up: pin OSS compatibility, then replay authority."""

        workspace_service = getattr(self.ap, 'workspace_service', None)
        if workspace_service is None:
            raise RuntimeError('Plugin Runtime requires the Workspace projection service')

        if self.runtime_profile == 'shared':
            list_bindings = getattr(workspace_service, 'list_active_execution_bindings', None)
            if not callable(list_bindings):
                raise RuntimeError('Shared plugin Runtime requires instance-scoped Workspace discovery')
            projected_bindings = await list_bindings()
            await self.reconcile_projected_workspaces(
                self._execution_from_binding(binding) for binding in projected_bindings
            )
            return

        if self.runtime_profile == 'oss_dev':
            local_binding = await workspace_service.get_local_execution_binding()
            execution_context = self._execution_from_binding(local_binding)
            bridge = self._legacy_oss_bridge_binding(execution_context)
            # One fully-bound action releases the SDK's deliberately retained
            # pre-v4 data/plugins/debug compatibility path. Shared mode never
            # creates this bridge.
            with self.handler.installation_scope(bridge):
                await self.handler.list_plugins()
            desired_states = await self._load_workspace_desired_states(execution_context)
            self._workspace_installations[execution_context.workspace_uuid] = {
                state.binding.installation_uuid for state in desired_states
            }
            self._known_desired_states.update({state.binding.installation_uuid: state for state in desired_states})

        result = await self.handler.reconcile_plugin_installations(tuple(self._known_desired_states.values()))
        await self._repair_reconcile_missing_artifacts(self._known_desired_states, result)
        self._record_reconcile_failures(self._known_desired_states, result)

    async def reconcile_projected_workspaces(
        self,
        contexts: typing.Iterable[ExecutionContext],
    ) -> dict[str, Any]:
        """Replay a closed control plane's complete projected Workspace set.

        PostgreSQL RLS intentionally prevents Core from globally scanning
        Workspaces. The caller enumerates authoritative projections; Core then
        reads each Workspace inside a tenant UoW and performs one instance-wide
        Runtime reconcile.
        """

        if not hasattr(self, 'handler'):
            raise PluginRuntimeNotConnectedError('Plugin runtime is not connected')
        async with self._state_lock:
            all_states: dict[str, PluginInstallationDesiredState] = {}
            workspace_installations: dict[str, set[str]] = {}
            for context in contexts:
                execution_context = await self._validate_execution_context(context)
                states = await self._load_workspace_desired_states(execution_context)
                workspace_installations[execution_context.workspace_uuid] = {
                    state.binding.installation_uuid for state in states
                }
                for state in states:
                    if state.binding.installation_uuid in all_states:
                        raise ValueError('Duplicate plugin installation UUID across projected Workspaces')
                    all_states[state.binding.installation_uuid] = state
            result = await self.handler.reconcile_plugin_installations(tuple(all_states.values()))
            await self._repair_reconcile_missing_artifacts(all_states, result)
            self._record_reconcile_failures(all_states, result)
            for installation_uuid, previous in tuple(self._known_desired_states.items()):
                if installation_uuid not in all_states:
                    self.handler.unregister_installation_binding(previous.binding)
            self._known_desired_states = all_states
            self._workspace_installations = workspace_installations
            return result

    async def _validate_execution_context(self, context: TenantContext) -> ExecutionContext:
        workspace_uuid = require_workspace_uuid(context)
        instance_uuid = str(getattr(context, 'instance_uuid', '') or '').strip()
        generation = getattr(context, 'placement_generation', None)
        if not instance_uuid or isinstance(generation, bool) or not isinstance(generation, int) or generation <= 0:
            raise WorkspaceNotFoundError('Plugin resource not found')
        binding = await self.ap.workspace_service.get_execution_binding(
            workspace_uuid,
            expected_generation=generation,
        )
        if binding.instance_uuid != instance_uuid:
            raise WorkspaceNotFoundError('Plugin resource not found')
        return ExecutionContext(
            instance_uuid=instance_uuid,
            workspace_uuid=workspace_uuid,
            placement_generation=generation,
            trigger_principal=getattr(context, 'principal', None),
            entitlement_revision=getattr(context, 'entitlement_revision', 0),
        )

    async def _synchronize_workspace(self, execution_context: ExecutionContext) -> None:
        if not self.is_enable_plugin or not hasattr(self, 'handler'):
            return
        desired_states = await self._load_workspace_desired_states(execution_context)
        desired_by_uuid = {state.binding.installation_uuid: state for state in desired_states}
        async with self._state_lock:
            previous_ids = set(self._workspace_installations.get(execution_context.workspace_uuid, set()))
            for installation_uuid in previous_ids - set(desired_by_uuid):
                previous = self._known_desired_states.get(installation_uuid)
                if previous is not None:
                    await self.handler.remove_plugin_installation(previous.binding)
                    self.handler.unregister_installation_binding(previous.binding)
                    self._known_desired_states.pop(installation_uuid, None)
                    self._installation_failures.pop(installation_uuid, None)

            for installation_uuid, desired in desired_by_uuid.items():
                if self._known_desired_states.get(installation_uuid) == desired:
                    continue
                try:
                    await self._apply_desired_state(desired)
                except PluginInstallationFailedError:
                    # The failure is retained per installation. Continue
                    # restoring the remaining desired state in this Workspace.
                    pass
                self._known_desired_states[installation_uuid] = desired
            self._workspace_installations[execution_context.workspace_uuid] = set(desired_by_uuid)

    async def _current_execution_context(self) -> ExecutionContext:
        current = self._execution_context.get()
        if current is not None:
            return current
        if self.runtime_profile != 'oss_dev':
            raise WorkspaceNotFoundError('Plugin resource not found')
        binding = await self.ap.workspace_service.get_local_execution_binding()
        current = self._execution_from_binding(binding)
        self._execution_context.set(current)
        await self._synchronize_workspace(current)
        return current

    async def heartbeat_loop(self):
        while True:
            await asyncio.sleep(20)
            try:
                await self.ping_plugin_runtime()
                self.ap.logger.debug('Heartbeat to plugin runtime success.')
            except Exception as e:
                self.ap.logger.debug(f'Failed to heartbeat to plugin runtime: {e}')

    async def initialize(self):
        if not self.is_enable_plugin:
            self.ap.logger.info('Plugin system is disabled.')
            return
        self.runtime_identity = RuntimeIdentity(
            instance_uuid=constants.instance_id,
            runtime_id=self._runtime_id,
        )
        self.worker_policy = self._load_worker_policy()

        async def new_connection_callback(connection: base_connection.Connection):
            async def disconnect_callback(
                rchandler: handler.RuntimeConnectionHandler,
            ) -> bool:
                if platform.get_platform() == 'docker' or platform.use_websocket_to_connect_plugin_runtime():
                    self.ap.logger.error('Disconnected from plugin runtime, trying to reconnect...')
                    await self.runtime_disconnect_callback(self)
                    return False
                else:
                    self.ap.logger.error(
                        'Disconnected from plugin runtime, cannot automatically reconnect while LangBot connects to plugin runtime via stdio, please restart LangBot.'
                    )
                    return False

            self.handler = handler.RuntimeConnectionHandler(
                connection,
                disconnect_callback,
                self.ap,
            )

            self.handler_task = asyncio.create_task(self.handler.run())
            _ = await self.handler.ping()
            # Push the configured marketplace (Space) URL to the runtime so it
            # downloads plugins from the same Space LangBot is bound to, rather
            # than relying on the runtime's own env/default.
            space_url = self.ap.instance_config.data.get('space', {}).get('url', '').rstrip('/')
            try:
                if self.runtime_identity is None or self.worker_policy is None:  # pragma: no cover
                    raise RuntimeError('Plugin Runtime identity or worker policy was not loaded')
                await self.handler.set_runtime_config(
                    runtime_identity=self.runtime_identity,
                    worker_policy=self.worker_policy,
                    runtime_profile=self.runtime_profile,
                    cloud_service_url=space_url or None,
                )
                if space_url:
                    self.ap.logger.info(f'Pushed marketplace URL to plugin runtime: {space_url}')
            except Exception as e:
                self.ap.logger.warning(f'Failed to bind plugin runtime config: {e}')
                raise
            await self._prepare_connected_runtime()
            self.ap.logger.info('Connected to instance-scoped plugin runtime.')
            await self.handler_task

        task: asyncio.Task | None = None

        if platform.get_platform() == 'docker' or platform.use_websocket_to_connect_plugin_runtime():  # use websocket
            self.ap.logger.info('use websocket to connect to plugin runtime')
            control_headers = self._control_headers(allow_generate=False)
            ws_url = self.ap.instance_config.data.get('plugin', {}).get(
                'runtime_ws_url', 'ws://langbot_plugin_runtime:5400/control/ws'
            )

            async def make_connection_failed_callback(
                ctrl: ws_client_controller.WebSocketClientController,
                exc: Exception = None,
            ) -> None:
                if exc is not None:
                    self.ap.logger.error(f'Failed to connect to plugin runtime({ws_url}): {exc}')
                else:
                    self.ap.logger.error(f'Failed to connect to plugin runtime({ws_url}), trying to reconnect...')
                await self.runtime_disconnect_callback(self)

            self.ctrl = ws_client_controller.WebSocketClientController(
                ws_url=ws_url,
                make_connection_failed_callback=make_connection_failed_callback,
                additional_headers=control_headers,
            )
            task = self.ctrl.run(new_connection_callback)
        elif platform.get_platform() == 'win32':
            # Due to Windows's lack of supports for both stdio and subprocess:
            # See also: https://docs.python.org/zh-cn/3.13/library/asyncio-platforms.html
            # We have to launch runtime via cmd but communicate via ws.
            self.ap.logger.info('(windows) use cmd to launch plugin runtime and communicate via ws')

            control_headers = self._control_headers(allow_generate=True)
            await self._start_runtime_subprocess(
                '-m',
                'langbot_plugin.cli.__init__',
                'rt',
                env_overrides={PLUGIN_RUNTIME_CONTROL_TOKEN_ENV: self._control_token},
            )

            ws_url = 'ws://localhost:5400/control/ws'

            async def make_connection_failed_callback(
                ctrl: ws_client_controller.WebSocketClientController,
                exc: Exception = None,
            ) -> None:
                if exc is not None:
                    self.ap.logger.error(f'(windows) Failed to connect to plugin runtime({ws_url}): {exc}')
                else:
                    self.ap.logger.error(
                        f'(windows) Failed to connect to plugin runtime({ws_url}), trying to reconnect...'
                    )
                await self.runtime_disconnect_callback(self)

            self.ctrl = ws_client_controller.WebSocketClientController(
                ws_url=ws_url,
                make_connection_failed_callback=make_connection_failed_callback,
                additional_headers=control_headers,
            )
            task = self.ctrl.run(new_connection_callback)

        else:  # stdio
            self.ap.logger.info('use stdio to connect to plugin runtime')
            # cmd: lbp rt -s
            python_path = sys.executable
            env = os.environ.copy()
            self.ctrl = stdio_client_controller.StdioClientController(
                command=python_path,
                args=['-m', 'langbot_plugin.cli.__init__', 'rt', '-s'],
                env=env,
            )
            task = self.ctrl.run(new_connection_callback)

        if self.heartbeat_task is None:
            self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())

        asyncio.create_task(task)

    async def initialize_plugins(self):
        pass

    async def ping_plugin_runtime(self):
        if not hasattr(self, 'handler'):
            raise PluginRuntimeNotConnectedError('Plugin runtime is not connected')

        return await self.handler.ping()

    async def require_workspace_context(self, context: TenantContext) -> ExecutionContext:
        """Validate and select one Workspace for this asyncio request task."""

        execution_context = await self._validate_execution_context(context)
        self._execution_context.set(execution_context)
        if not self.is_enable_plugin:
            return execution_context
        if not hasattr(self, 'handler'):
            raise PluginRuntimeNotConnectedError('Plugin runtime is not connected')
        await self._synchronize_workspace(execution_context)
        return execution_context

    def _inspect_plugin_package(
        self,
        file_bytes: bytes,
        task_context: taskmgr.TaskContext | None,
    ) -> tuple[str | None, str | None]:
        """Extract plugin identity and dependency metadata from a plugin package."""
        plugin_author = None
        plugin_name = None

        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                try:
                    manifest = yaml.safe_load(zf.read('manifest.yaml').decode('utf-8', errors='ignore')) or {}
                    metadata = manifest.get('metadata', {})
                    plugin_author = metadata.get('author')
                    plugin_name = metadata.get('name')
                except Exception:
                    pass

                if task_context is not None:
                    for name in zf.namelist():
                        if name.endswith('requirements.txt'):
                            content = zf.read(name).decode('utf-8', errors='ignore')
                            deps = [
                                line.strip()
                                for line in content.splitlines()
                                if line.strip() and not line.strip().startswith('#')
                            ]
                            task_context.metadata['deps_total'] = len(deps)
                            task_context.metadata['deps_list'] = deps
                            break
        except Exception:
            pass

        return plugin_author, plugin_name

    async def _operation_bindings(
        self,
        *,
        include_plugins: list[str] | None = None,
        include_disabled: bool = False,
    ) -> list[InstallationBinding]:
        execution_context = await self._current_execution_context()
        settings = await self._load_workspace_settings(execution_context)
        bindings: list[InstallationBinding] = (
            [self._legacy_oss_bridge_binding(execution_context)] if self.runtime_profile == 'oss_dev' else []
        )
        for setting in settings:
            plugin_id = f'{setting.plugin_author}/{setting.plugin_name}'
            if not include_disabled and not setting.enabled:
                continue
            if include_plugins is not None and plugin_id not in include_plugins:
                continue
            if self.runtime_profile == 'oss_dev' and (
                not isinstance(setting.install_info, dict)
                or setting.install_info.get('_artifact_storage') != _PLUGIN_ARTIFACT_STORAGE_MARKER
            ):
                continue
            bindings.append(self._binding_from_setting(execution_context, setting))
        return bindings

    async def _setting_for_plugin(
        self,
        plugin_author: str,
        plugin_name: str,
        *,
        require_enabled: bool = False,
    ) -> tuple[ExecutionContext, persistence_plugin.PluginSetting]:
        execution_context = await self._current_execution_context()
        settings = await self._load_workspace_settings(execution_context)
        for setting in settings:
            if setting.plugin_author == plugin_author and setting.plugin_name == plugin_name:
                if require_enabled and not setting.enabled:
                    raise ValueError(f'Plugin {plugin_author}/{plugin_name} is disabled')
                return execution_context, setting
        raise ValueError(f'Plugin {plugin_author}/{plugin_name} is not installed in this Workspace')

    async def _target_binding(
        self,
        plugin_author: str,
        plugin_name: str,
        *,
        require_enabled: bool = True,
    ) -> InstallationBinding:
        execution_context, setting = await self._setting_for_plugin(
            plugin_author,
            plugin_name,
            require_enabled=require_enabled,
        )
        if self.runtime_profile == 'oss_dev' and (
            not isinstance(setting.install_info, dict)
            or setting.install_info.get('_artifact_storage') != _PLUGIN_ARTIFACT_STORAGE_MARKER
        ):
            return self._legacy_oss_bridge_binding(execution_context)
        return self._binding_from_setting(execution_context, setting)

    async def _target_binding_for_component(
        self,
        component_name: str,
        *,
        component_kind: typing.Literal['tool', 'command'],
        include_plugins: list[str] | None,
    ) -> InstallationBinding:
        for binding in await self._operation_bindings(include_plugins=include_plugins):
            with self.handler.installation_scope(binding):
                components = (
                    await self.handler.list_tools(include_plugins=include_plugins)
                    if component_kind == 'tool'
                    else await self.handler.list_commands(include_plugins=include_plugins)
                )
            for component in components:
                manifest = ComponentManifest.model_validate(component)
                if manifest.metadata.name == component_name:
                    return binding
        raise ValueError(f'Plugin {component_kind} {component_name!r} was not found in this Workspace')

    async def _install_mcp_from_marketplace(
        self,
        execution_context: ExecutionContext,
        mcp_data: dict[str, Any],
        task_context: taskmgr.TaskContext | None = None,
    ):
        """Install an MCP server from marketplace data.

        Marketplace MCP records carry the runtime-ready ``mode`` and
        ``extra_args`` directly (the same shape LangBot stores in
        ``mcp_servers``), so they are used as-is rather than reconstructed.
        For ``stdio`` this preserves ``command``/``args``/``env``/``box``;
        for ``http``/``sse`` it preserves ``url``/``headers``/``timeout``/
        ``ssereadtimeout``.
        """
        mode = mcp_data.get('mode') or 'stdio'
        extra_args = mcp_data.get('extra_args') or {}
        # The MCP transport selection was simplified to two modes: 'stdio'
        # (local, Box-sandboxed) and 'remote' (the runtime auto-detects
        # Streamable HTTP vs. legacy SSE from the URL). Marketplace records may
        # still carry the older 'http'/'sse' modes — normalize them to 'remote'
        # so the installed server shows up correctly in the two-option UI. The
        # connection args (url/headers/timeout/ssereadtimeout) are preserved and
        # consumed by the auto-detecting remote transport regardless.
        if mode in ('http', 'sse'):
            mode = 'remote'
        # Marketplace records carry the rendered README markdown; persist it so
        # the detail page Docs tab works offline and without a marketplace round-trip.
        readme = mcp_data.get('readme') or ''
        # Use __ instead of / to avoid URL routing issues with slashes
        name = f'{mcp_data.get("author", "")}__{mcp_data.get("name", "")}'

        existing = await self.ap.mcp_service.get_mcp_server_by_name(execution_context, name)
        if existing is not None:
            self.ap.logger.info(f'MCP server {name} already exists, skipping installation')
            return

        server_data = {
            'name': name,
            'enable': True,
            'mode': mode,
            'extra_args': extra_args,
            'readme': readme,
        }

        await self.ap.mcp_service.create_mcp_server(execution_context, server_data)

        self.ap.logger.info(f'Installed MCP server {name} from marketplace')

    async def _install_skill_from_zip(
        self,
        execution_context: ExecutionContext,
        file_bytes: bytes,
        filename: str,
        task_context: taskmgr.TaskContext | None = None,
    ):
        """Install a skill from marketplace ZIP data."""
        from ..api.http.service.skill import SkillService

        skill_service = SkillService(self.ap)

        self.ap.logger.info(f'Installing skill from marketplace ZIP ({len(file_bytes)} bytes)')

        # Install from ZIP using skill service
        result = await skill_service.install_from_zip_upload(
            execution_context,
            file_bytes=file_bytes,
            filename=filename + '.zip',
        )
        self.ap.logger.info(f'Skill installed successfully: {result}')

    def _build_plugin_startup_failure_message(
        self,
        plugin_author: str,
        plugin_name: str,
        task_context: taskmgr.TaskContext | None,
    ) -> str:
        dep_hint = ''
        if task_context is not None:
            current_dep = task_context.metadata.get('current_dep')
            if current_dep:
                dep_hint = f' Last dependency: {current_dep}.'

        return (
            f'Plugin {plugin_author}/{plugin_name} failed to start after installation. '
            f'Dependency installation or plugin initialization may have failed.{dep_hint} '
            f'Please check the plugin requirements and runtime logs.'
        )

    async def _wait_for_installed_plugin_ready(
        self,
        plugin_author: str | None,
        plugin_name: str | None,
        task_context: taskmgr.TaskContext | None,
        timeout: float = 30,
    ):
        """Wait until the installed plugin is registered by the runtime.

        The plugin runtime launches plugins asynchronously. If dependency installation
        fails, the plugin process exits before registration; without this check the
        install task can incorrectly finish successfully.
        """
        if not plugin_author or not plugin_name:
            return

        deadline = time.time() + timeout
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                plugin = await self.get_plugin_info(plugin_author, plugin_name)
                if plugin is not None:
                    status = plugin.get('status')
                    if status == 'initialized':
                        return
            except Exception as e:
                last_error = e

            await asyncio.sleep(0.5)

        message = self._build_plugin_startup_failure_message(plugin_author, plugin_name, task_context)
        if last_error is not None:
            message = f'{message} Last runtime error: {last_error}'
        raise RuntimeError(message)

    async def _persist_installation_package(
        self,
        execution_context: ExecutionContext,
        *,
        plugin_author: str,
        plugin_name: str,
        install_source: PluginInstallSource,
        install_info: dict[str, Any],
        artifact_digest: str,
    ) -> tuple[InstallationBinding, str | None, bool]:
        safe_install_info = {
            key: value
            for key, value in install_info.items()
            if key not in {'plugin_file', 'plugin_file_key'}
            and key != '_artifact_storage'
            and isinstance(value, (str, int, float, bool, list, dict, type(None)))
        }
        safe_install_info['_artifact_storage'] = _PLUGIN_ARTIFACT_STORAGE_MARKER
        statement = (
            sqlalchemy.select(
                persistence_plugin.PluginSetting.installation_uuid,
                persistence_plugin.PluginSetting.runtime_revision,
                persistence_plugin.PluginSetting.artifact_digest,
                persistence_plugin.PluginSetting.install_info,
            )
            .where(persistence_plugin.PluginSetting.workspace_uuid == execution_context.workspace_uuid)
            .where(persistence_plugin.PluginSetting.plugin_author == plugin_author)
            .where(persistence_plugin.PluginSetting.plugin_name == plugin_name)
        )

        async def persist(execute):
            result = await execute(statement)
            setting = result.first()
            if setting is None:
                installation_uuid = str(uuid.uuid4())
                runtime_revision = 1
                previous_digest = None
                previous_was_durable = False
                await execute(
                    sqlalchemy.insert(persistence_plugin.PluginSetting).values(
                        workspace_uuid=execution_context.workspace_uuid,
                        plugin_author=plugin_author,
                        plugin_name=plugin_name,
                        installation_uuid=installation_uuid,
                        artifact_digest=artifact_digest,
                        runtime_revision=runtime_revision,
                        install_source=install_source.value,
                        install_info=safe_install_info,
                        enabled=True,
                        priority=0,
                        config={},
                    )
                )
            else:
                installation_uuid = setting.installation_uuid
                runtime_revision = setting.runtime_revision + 1
                previous_digest = setting.artifact_digest
                previous_was_durable = (
                    isinstance(setting.install_info, dict)
                    and setting.install_info.get('_artifact_storage') == _PLUGIN_ARTIFACT_STORAGE_MARKER
                )
                await execute(
                    sqlalchemy.update(persistence_plugin.PluginSetting)
                    .where(persistence_plugin.PluginSetting.workspace_uuid == execution_context.workspace_uuid)
                    .where(persistence_plugin.PluginSetting.plugin_author == plugin_author)
                    .where(persistence_plugin.PluginSetting.plugin_name == plugin_name)
                    .values(
                        artifact_digest=artifact_digest,
                        runtime_revision=runtime_revision,
                        install_source=install_source.value,
                        install_info=safe_install_info,
                        enabled=True,
                    )
                )
            return (
                InstallationBinding(
                    instance_uuid=execution_context.instance_uuid,
                    workspace_uuid=execution_context.workspace_uuid,
                    placement_generation=execution_context.placement_generation,
                    installation_uuid=installation_uuid,
                    runtime_revision=runtime_revision,
                    artifact_digest=artifact_digest,
                ),
                previous_digest,
                previous_was_durable,
            )

        tenant_uow = getattr(self.ap.persistence_mgr, 'tenant_uow', None)
        if callable(tenant_uow):
            async with tenant_uow(execution_context.workspace_uuid) as uow:
                return await persist(uow.execute)
        return await persist(self.ap.persistence_mgr.execute_async)

    async def _download_github_package(
        self,
        install_info: dict[str, Any],
        task_context: taskmgr.TaskContext | None,
    ) -> bytes:
        normalized = validate_github_plugin_install_info(install_info)
        owner = normalized['owner']
        repo = normalized['repo']
        release_tag = normalized['release_tag']

        async with httpx.AsyncClient(
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(60, connect=10),
        ) as client:
            asset_id: int | None = None
            if 'asset_id' in normalized:
                release_id = normalized['release_id']
                asset_id = normalized['asset_id']
                metadata_url = f'https://api.github.com/repos/{owner}/{repo}/releases/{release_id}'
                response = await client.get(
                    metadata_url,
                    headers={
                        'Accept': 'application/vnd.github+json',
                        'X-GitHub-Api-Version': '2022-11-28',
                        'User-Agent': 'LangBot-Plugin-Installer',
                    },
                )
                if response.status_code in _HTTP_REDIRECT_STATUSES:
                    raise ValueError('GitHub release metadata unexpectedly redirected')
                response.raise_for_status()
                release = response.json()
                if not isinstance(release, dict):
                    raise ValueError('GitHub release metadata is invalid')
                if release.get('id') != release_id or str(release.get('tag_name') or '') != release_tag:
                    raise ValueError('GitHub release metadata does not match the requested release')
                assets = release.get('assets')
                if not isinstance(assets, list):
                    raise ValueError('GitHub release has no asset metadata')
                asset = next(
                    (
                        candidate
                        for candidate in assets
                        if isinstance(candidate, dict) and candidate.get('id') == asset_id
                    ),
                    None,
                )
                if asset is None:
                    raise ValueError('GitHub release asset does not belong to the requested release')
                declared_size = asset.get('size')
                if isinstance(declared_size, int) and declared_size > _GITHUB_PLUGIN_DOWNLOAD_MAX_BYTES:
                    raise ValueError('GitHub plugin package exceeds the 10 MiB download limit')
                if asset.get('state') not in {None, 'uploaded'}:
                    raise ValueError('GitHub release asset is not ready for download')
                asset_url = f'https://api.github.com/repos/{owner}/{repo}/releases/assets/{asset_id}'
            else:
                asset_url = normalized['asset_url']

            downloaded = 0
            chunks: list[bytes] = []
            start_time = time.time()
            current_url = asset_url
            if task_context is not None:
                task_context.set_current_action('downloading plugin package')
                task_context.metadata.update({'download_total': 0, 'download_current': 0, 'download_speed': 0})

            for redirect_count in range(_GITHUB_PLUGIN_DOWNLOAD_MAX_REDIRECTS + 1):
                self._validate_github_download_hop(
                    current_url,
                    owner=owner,
                    repo=repo,
                    release_tag=release_tag,
                    asset_id=asset_id,
                )
                parsed = urlparse(current_url)
                request_headers = {
                    'Accept-Encoding': 'identity',
                    'User-Agent': 'LangBot-Plugin-Installer',
                }
                if (parsed.hostname or '').lower() == 'api.github.com':
                    request_headers.update(
                        {
                            'Accept': 'application/octet-stream',
                            'X-GitHub-Api-Version': '2022-11-28',
                        }
                    )

                async with client.stream('GET', current_url, headers=request_headers) as response:
                    if response.status_code in _HTTP_REDIRECT_STATUSES:
                        location = response.headers.get('location')
                        if not location:
                            raise ValueError('GitHub release asset redirect is missing a location')
                        if redirect_count >= _GITHUB_PLUGIN_DOWNLOAD_MAX_REDIRECTS:
                            raise ValueError('GitHub release asset exceeded the redirect limit')
                        next_url = urljoin(current_url, location)
                        self._validate_github_download_hop(
                            next_url,
                            owner=owner,
                            repo=repo,
                            release_tag=release_tag,
                            asset_id=asset_id,
                        )
                        current_url = next_url
                        continue

                    response.raise_for_status()
                    content_length_header = response.headers.get('content-length')
                    try:
                        content_length = int(content_length_header) if content_length_header is not None else 0
                    except ValueError as exc:
                        raise ValueError('GitHub release asset has an invalid content length') from exc
                    if content_length < 0:
                        raise ValueError('GitHub release asset has an invalid content length')
                    if content_length > _GITHUB_PLUGIN_DOWNLOAD_MAX_BYTES:
                        raise ValueError('GitHub plugin package exceeds the 10 MiB download limit')
                    if task_context is not None:
                        task_context.metadata['download_total'] = content_length

                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        downloaded += len(chunk)
                        if downloaded > _GITHUB_PLUGIN_DOWNLOAD_MAX_BYTES:
                            raise ValueError('GitHub plugin package exceeds the 10 MiB download limit')
                        chunks.append(chunk)
                        if task_context is not None:
                            elapsed = time.time() - start_time
                            task_context.metadata.update(
                                {
                                    'download_current': downloaded,
                                    'download_speed': downloaded / elapsed if elapsed > 0 else 0,
                                }
                            )
                    return b''.join(chunks)

            raise ValueError('GitHub release asset exceeded the redirect limit')

    @staticmethod
    def _validate_github_download_hop(
        url: str,
        *,
        owner: str,
        repo: str,
        release_tag: str,
        asset_id: int | None,
    ) -> None:
        """Reject redirects away from the small set of GitHub asset hosts."""

        parsed = urlparse(str(url or '').strip())
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError('GitHub release asset URL has an invalid port') from exc
        hostname = (parsed.hostname or '').lower()
        if (
            parsed.scheme != 'https'
            or hostname not in _GITHUB_ASSET_HOSTS
            or parsed.username is not None
            or parsed.password is not None
            or port not in {None, 443}
            or parsed.fragment
        ):
            raise ValueError('GitHub release asset redirected to an untrusted host')
        if hostname == 'api.github.com':
            expected_path = f'/repos/{owner}/{repo}/releases/assets/{asset_id}'
            if asset_id is None or parsed.path != expected_path or parsed.query:
                raise ValueError('GitHub release asset API URL is not trusted')
        elif hostname == 'github.com':
            validate_github_release_asset_url(
                url,
                owner=owner,
                repo=repo,
                release_tag=release_tag,
            )
        elif not parsed.path or parsed.path == '/':
            raise ValueError('GitHub release asset redirect has no object path')

    async def _download_marketplace_package(
        self,
        execution_context: ExecutionContext,
        plugin_author: str,
        plugin_name: str,
        task_context: taskmgr.TaskContext | None,
    ) -> tuple[bytes | None, str | None]:
        """Return a plugin package, or install an MCP/skill and return none."""

        space_url = self.ap.instance_config.data.get('space', {}).get('url', 'https://space.langbot.app').rstrip('/')
        async with httpx.AsyncClient(trust_env=True, timeout=15) as client:
            mcp_resp = await client.get(f'{space_url}/api/v1/marketplace/mcps/{plugin_author}/{plugin_name}')
            if mcp_resp.status_code == 200:
                mcp_data = mcp_resp.json().get('data', {}).get('mcp', {})
                if not mcp_data.get('mode'):
                    raise ValueError(f'MCP {plugin_author}/{plugin_name} has no mode')
                await self._install_mcp_from_marketplace(execution_context, mcp_data, task_context)
                try:
                    await client.post(f'{space_url}/api/v1/marketplace/mcps/{plugin_author}/{plugin_name}/install')
                except Exception as report_err:
                    self.ap.logger.debug(f'Failed to report MCP install: {report_err}')
                return None, None
            if mcp_resp.status_code != 404:
                mcp_resp.raise_for_status()

            skill_resp = await client.get(f'{space_url}/api/v1/marketplace/skills/{plugin_author}/{plugin_name}')
            if skill_resp.status_code == 200:
                download_resp = await client.get(
                    f'{space_url}/api/v1/marketplace/skills/download/{plugin_author}/{plugin_name}'
                )
                download_resp.raise_for_status()
                await self._install_skill_from_zip(
                    execution_context,
                    download_resp.content,
                    f'{plugin_author}-{plugin_name}',
                    task_context,
                )
                return None, None
            if skill_resp.status_code != 404:
                skill_resp.raise_for_status()

            versions_resp = await client.get(
                f'{space_url}/api/v1/marketplace/plugins/{plugin_author}/{plugin_name}/versions'
            )
            versions_resp.raise_for_status()
            versions = versions_resp.json().get('data', {}).get('versions', [])
            if not versions or not versions[0].get('version'):
                raise ValueError(f'Plugin {plugin_author}/{plugin_name} has no versions')
            latest_version = str(versions[0]['version'])
            download_resp = await client.get(
                f'{space_url}/api/v1/marketplace/plugins/download/{plugin_author}/{plugin_name}/{latest_version}'
            )
            download_resp.raise_for_status()
            return download_resp.content, latest_version

    async def install_plugin(
        self,
        install_source: PluginInstallSource,
        install_info: dict[str, Any],
        task_context: taskmgr.TaskContext | None = None,
    ) -> None:
        execution_context = await self._current_execution_context()
        plugin_author = str(install_info.get('plugin_author') or '')
        plugin_name = str(install_info.get('plugin_name') or '')
        file_bytes: bytes | None

        if install_source == PluginInstallSource.MARKETPLACE:
            file_bytes, version = await self._download_marketplace_package(
                execution_context,
                plugin_author,
                plugin_name,
                task_context,
            )
            if file_bytes is None:
                return
            install_info = {**install_info, 'plugin_version': version}
        elif install_source == PluginInstallSource.LOCAL:
            candidate = install_info.get('plugin_file')
            if not isinstance(candidate, bytes):
                raise ValueError('Local plugin package is missing')
            file_bytes = candidate
        elif install_source == PluginInstallSource.GITHUB:
            file_bytes = await self._download_github_package(
                install_info,
                task_context,
            )
            install_info = validate_github_plugin_install_info(install_info)
        else:
            raise ValueError(f'Unsupported plugin install source: {install_source.value}')

        manifest_author, manifest_name = self._inspect_plugin_package(file_bytes, task_context)
        if not manifest_author or not manifest_name:
            raise ValueError('Plugin package manifest identity is missing')
        if plugin_author and plugin_author != manifest_author:
            raise ValueError('Plugin package author does not match the requested plugin')
        if plugin_name and plugin_name != manifest_name:
            raise ValueError('Plugin package name does not match the requested plugin')
        plugin_author, plugin_name = manifest_author, manifest_name
        if task_context is not None:
            task_context.metadata['plugin_name'] = f'{plugin_author}/{plugin_name}'

        artifact_digest = hashlib.sha256(file_bytes).hexdigest()
        await self._store_artifact_package(execution_context, artifact_digest, file_bytes)
        try:
            binding, previous_digest, previous_was_durable = await self._persist_installation_package(
                execution_context,
                plugin_author=plugin_author,
                plugin_name=plugin_name,
                install_source=install_source,
                install_info=install_info,
                artifact_digest=artifact_digest,
            )
        except Exception:
            await self._delete_artifact_if_unreferenced(execution_context, artifact_digest)
            raise
        self.handler.register_installation_binding(
            binding,
            plugin_author=plugin_author,
            plugin_name=plugin_name,
        )
        await self._apply_desired_state(
            PluginInstallationDesiredState(binding=binding, enabled=True),
            artifact_package=file_bytes,
        )
        desired = PluginInstallationDesiredState(binding=binding, enabled=True)
        self._known_desired_states[binding.installation_uuid] = desired
        self._workspace_installations.setdefault(binding.workspace_uuid, set()).add(binding.installation_uuid)
        if previous_digest is not None and previous_digest != artifact_digest:
            await self._delete_artifact_if_unreferenced(execution_context, previous_digest)
        if previous_digest is not None and not previous_was_durable and self.runtime_profile == 'oss_dev':
            bridge = self._legacy_oss_bridge_binding(execution_context)
            try:
                with self.handler.installation_scope(bridge):
                    async for _ in self.handler.delete_plugin(plugin_author, plugin_name):
                        pass
            except Exception as exc:
                self.ap.logger.debug(f'Legacy OSS plugin cleanup skipped: {exc}')
        await self._wait_for_installed_plugin_ready(plugin_author, plugin_name, task_context)

    async def upgrade_plugin(
        self,
        plugin_author: str,
        plugin_name: str,
        task_context: taskmgr.TaskContext | None = None,
    ) -> dict[str, Any]:
        _execution_context, setting = await self._setting_for_plugin(plugin_author, plugin_name)
        if setting.install_source != PluginInstallSource.MARKETPLACE.value:
            raise ValueError(f'Plugin {plugin_author}/{plugin_name} is not installed from marketplace')
        if task_context is not None:
            task_context.set_current_action('checking for latest version')
        await self.install_plugin(
            PluginInstallSource.MARKETPLACE,
            {'plugin_author': plugin_author, 'plugin_name': plugin_name},
            task_context=task_context,
        )
        return {}

    async def delete_plugin(
        self,
        plugin_author: str,
        plugin_name: str,
        delete_data: bool = False,
        task_context: taskmgr.TaskContext | None = None,
    ) -> dict[str, Any]:
        execution_context, setting = await self._setting_for_plugin(plugin_author, plugin_name)
        binding = self._binding_from_setting(execution_context, setting)
        is_legacy_oss = self.runtime_profile == 'oss_dev' and (
            not isinstance(setting.install_info, dict)
            or setting.install_info.get('_artifact_storage') != _PLUGIN_ARTIFACT_STORAGE_MARKER
        )
        if is_legacy_oss:
            bridge = self._legacy_oss_bridge_binding(execution_context)
            with self.handler.installation_scope(bridge):
                async for _ in self.handler.delete_plugin(plugin_author, plugin_name):
                    pass
        await self.handler.remove_plugin_installation(binding)
        self.handler.unregister_installation_binding(binding)

        async def delete(execute):
            await execute(
                sqlalchemy.delete(persistence_plugin.PluginSetting)
                .where(persistence_plugin.PluginSetting.workspace_uuid == execution_context.workspace_uuid)
                .where(persistence_plugin.PluginSetting.plugin_author == plugin_author)
                .where(persistence_plugin.PluginSetting.plugin_name == plugin_name)
            )
            await self._delete_artifact_if_unreferenced(
                execution_context,
                setting.artifact_digest,
                execute=execute,
            )
            if delete_data:
                await execute(
                    sqlalchemy.delete(persistence_bstorage.BinaryStorage)
                    .where(persistence_bstorage.BinaryStorage.workspace_uuid == execution_context.workspace_uuid)
                    .where(persistence_bstorage.BinaryStorage.owner_type == 'plugin')
                    .where(persistence_bstorage.BinaryStorage.owner == f'{plugin_author}/{plugin_name}')
                )

        tenant_uow = getattr(self.ap.persistence_mgr, 'tenant_uow', None)
        if callable(tenant_uow):
            async with tenant_uow(execution_context.workspace_uuid) as uow:
                await delete(uow.execute)
        else:
            await delete(self.ap.persistence_mgr.execute_async)

        self._known_desired_states.pop(binding.installation_uuid, None)
        self._workspace_installations.setdefault(binding.workspace_uuid, set()).discard(binding.installation_uuid)
        if task_context is not None:
            task_context.set_current_action('plugin removed')
        return {}

    async def list_plugins(self, component_kinds: list[str] | None = None) -> list[dict[str, Any]]:
        """List plugins, optionally filtered by component kinds.

        Args:
            component_kinds: Optional list of component kinds to filter by.
                           If provided, only plugins that contain at least one
                           component of the specified kinds will be returned.
                           E.g., ['Command', 'EventListener', 'Tool'] for pipeline-related plugins.
        """
        if not self.is_enable_plugin:
            return []

        plugins: list[dict[str, Any]] = []
        seen_plugin_ids: set[str] = set()
        for binding in await self._operation_bindings():
            with self.handler.installation_scope(binding):
                scoped_plugins = await self.handler.list_plugins()
            for plugin in scoped_plugins:
                metadata = plugin.get('manifest', {}).get('manifest', {}).get('metadata', {})
                plugin_id = f'{metadata.get("author", "")}/{metadata.get("name", "")}'
                if plugin_id not in seen_plugin_ids:
                    seen_plugin_ids.add(plugin_id)
                    plugins.append(plugin)

        # Filter plugins by component kinds if specified
        if component_kinds is not None:
            filtered_plugins = []
            for plugin in plugins:
                components = plugin.get('components', [])
                has_matching_component = False
                for component in components:
                    component_kind = component.get('manifest', {}).get('manifest', {}).get('kind', '')
                    if component_kind in component_kinds:
                        has_matching_component = True
                        break
                if has_matching_component:
                    filtered_plugins.append(plugin)
            plugins = filtered_plugins

        # Sort plugins: debug plugins first, then by installation time (newest first)
        # Get installation timestamps from database in a single query
        plugin_timestamps = {}

        if plugins:
            execution_context = await self._current_execution_context()
            for setting in await self._load_workspace_settings(execution_context):
                plugin_timestamps[f'{setting.plugin_author}/{setting.plugin_name}'] = setting.created_at

        # Sort: debug plugins first (descending), then by created_at (descending)
        def sort_key(plugin):
            author = plugin.get('manifest', {}).get('manifest', {}).get('metadata', {}).get('author', '')
            name = plugin.get('manifest', {}).get('manifest', {}).get('metadata', {}).get('name', '')
            plugin_id = f'{author}/{name}'

            is_debug = plugin.get('debug', False)
            created_at = plugin_timestamps.get(plugin_id)

            # Return tuple: (not is_debug, -timestamp)
            # not is_debug: False (0) for debug plugins, True (1) for non-debug
            # -timestamp: to sort newest first (will be None for plugins without timestamp)
            timestamp_value = -created_at.timestamp() if created_at else 0
            return (not is_debug, timestamp_value)

        plugins.sort(key=sort_key)

        return plugins

    async def get_plugin_info(self, author: str, plugin_name: str) -> dict[str, Any]:
        binding = await self._target_binding(author, plugin_name)
        with self.handler.installation_scope(binding):
            return await self.handler.get_plugin_info(author, plugin_name)

    async def set_plugin_config(self, plugin_author: str, plugin_name: str, config: dict[str, Any]) -> dict[str, Any]:
        execution_context, setting = await self._setting_for_plugin(plugin_author, plugin_name)
        next_revision = setting.runtime_revision + 1
        statement = (
            sqlalchemy.update(persistence_plugin.PluginSetting)
            .where(persistence_plugin.PluginSetting.workspace_uuid == execution_context.workspace_uuid)
            .where(persistence_plugin.PluginSetting.plugin_author == plugin_author)
            .where(persistence_plugin.PluginSetting.plugin_name == plugin_name)
            .where(persistence_plugin.PluginSetting.runtime_revision == setting.runtime_revision)
            .values(config=config, runtime_revision=next_revision)
        )
        tenant_uow = getattr(self.ap.persistence_mgr, 'tenant_uow', None)
        if callable(tenant_uow):
            async with tenant_uow(execution_context.workspace_uuid) as uow:
                result = await uow.execute(statement)
        else:
            result = await self.ap.persistence_mgr.execute_async(statement)
        if result.rowcount != 1:
            raise RuntimeError('Plugin configuration changed concurrently')
        binding = InstallationBinding(
            instance_uuid=execution_context.instance_uuid,
            workspace_uuid=execution_context.workspace_uuid,
            placement_generation=execution_context.placement_generation,
            installation_uuid=setting.installation_uuid,
            runtime_revision=next_revision,
            artifact_digest=setting.artifact_digest,
        )
        self.handler.register_installation_binding(
            binding,
            plugin_author=plugin_author,
            plugin_name=plugin_name,
        )
        desired = PluginInstallationDesiredState(
            binding=binding,
            enabled=setting.enabled,
        )
        is_legacy_oss = self.runtime_profile == 'oss_dev' and (
            not isinstance(setting.install_info, dict)
            or setting.install_info.get('_artifact_storage') != _PLUGIN_ARTIFACT_STORAGE_MARKER
        )
        if is_legacy_oss:
            bridge = self._legacy_oss_bridge_binding(execution_context)
            with self.handler.installation_scope(bridge):
                await self.handler.set_plugin_config(plugin_author, plugin_name, config)
        else:
            await self._apply_desired_state(desired)
        self._known_desired_states[binding.installation_uuid] = desired
        return {}

    async def get_plugin_icon(self, plugin_author: str, plugin_name: str) -> dict[str, Any]:
        binding = await self._target_binding(plugin_author, plugin_name)
        with self.handler.installation_scope(binding):
            return await self.handler.get_plugin_icon(plugin_author, plugin_name)

    async def get_plugin_readme(self, plugin_author: str, plugin_name: str, language: str = 'en') -> str:
        binding = await self._target_binding(plugin_author, plugin_name)
        with self.handler.installation_scope(binding):
            return await self.handler.get_plugin_readme(plugin_author, plugin_name, language)

    async def get_plugin_logs(
        self,
        plugin_author: str,
        plugin_name: str,
        limit: int = 200,
        level: str | None = None,
    ) -> list[dict[str, Any]]:
        binding = await self._target_binding(plugin_author, plugin_name)
        with self.handler.installation_scope(binding):
            return await self.handler.get_plugin_logs(plugin_author, plugin_name, limit, level)

    async def get_plugin_assets(self, plugin_author: str, plugin_name: str, filepath: str) -> dict[str, Any]:
        binding = await self._target_binding(plugin_author, plugin_name)
        with self.handler.installation_scope(binding):
            return await self.handler.get_plugin_assets(plugin_author, plugin_name, filepath)

    async def handle_page_api(
        self,
        plugin_author: str,
        plugin_name: str,
        page_id: str,
        endpoint: str,
        method: str,
        body: Any = None,
    ) -> dict[str, Any]:
        binding = await self._target_binding(plugin_author, plugin_name)
        with self.handler.installation_scope(binding):
            return await self.handler.handle_page_api(plugin_author, plugin_name, page_id, endpoint, method, body)

    async def get_debug_info(self) -> dict[str, Any]:
        """Get debug information including debug key and WS URL"""
        if not self.is_enable_plugin:
            return {}
        return await self.handler.get_debug_info()

    async def emit_event(
        self,
        event: events.BaseEventModel,
        bound_plugins: list[str] | None = None,
    ) -> context.EventContext:
        query = getattr(event, 'query', None)
        if query is not None:
            from ..pipeline.pool import get_query_execution_context

            await self.require_workspace_context(get_query_execution_context(query))
        event_ctx = context.EventContext.from_event(event)

        if not self.is_enable_plugin:
            event_ctx._emitted_plugins = []
            event_ctx._response_sources = []
            return event_ctx

        emitted_plugins: list[Any] = []
        response_sources: list[dict[str, Any]] = []
        for binding in await self._operation_bindings(include_plugins=bound_plugins):
            with self.handler.installation_scope(binding):
                result = await self.handler.emit_event(
                    event_ctx.model_dump(serialize_as_any=False),
                    include_plugins=bound_plugins,
                )
            event_ctx = context.EventContext.model_validate(result['event_context'])
            emitted_plugins.extend(result.get('emitted_plugins', []))
            response_sources.extend(result.get('response_sources', []))
        event_ctx._emitted_plugins = emitted_plugins
        event_ctx._response_sources = response_sources

        return event_ctx

    async def notify_plugin_diagnostic(self, diagnostic: dict[str, Any]) -> None:
        """Best-effort diagnostic forwarding to the plugin runtime."""
        if not self.is_enable_plugin:
            return
        try:
            plugin_ref = diagnostic.get('plugin') if isinstance(diagnostic, dict) else None
            if isinstance(plugin_ref, dict):
                author = plugin_ref.get('author') or plugin_ref.get('plugin_author')
                name = plugin_ref.get('name') or plugin_ref.get('plugin_name')
                if author and name:
                    binding = await self._target_binding(str(author), str(name))
                    with self.handler.installation_scope(binding):
                        await self.handler.notify_plugin_diagnostic(diagnostic)
                    return
            for binding in await self._operation_bindings():
                with self.handler.installation_scope(binding):
                    await self.handler.notify_plugin_diagnostic(diagnostic)
        except Exception as e:
            self.ap.logger.debug(f'Plugin diagnostic forwarding skipped: {e}')

    async def list_tools(self, bound_plugins: list[str] | None = None) -> list[ComponentManifest]:
        if not self.is_enable_plugin:
            return []

        tools: list[ComponentManifest] = []
        seen: set[tuple[str, str]] = set()
        for binding in await self._operation_bindings(include_plugins=bound_plugins):
            with self.handler.installation_scope(binding):
                scoped = await self.handler.list_tools(include_plugins=bound_plugins)
            for raw_tool in scoped:
                tool = ComponentManifest.model_validate(raw_tool)
                key = (str(tool.owner), tool.metadata.name)
                if key not in seen:
                    seen.add(key)
                    tools.append(tool)
        return tools

    async def call_tool(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        session: provider_session.Session,
        query_id: int,
        bound_plugins: list[str] | None = None,
        query_uuid: str | None = None,
    ) -> dict[str, Any]:
        if not self.is_enable_plugin:
            return {'error': 'Tool not found: plugin system is disabled'}
        await self.require_workspace_context(
            ExecutionContext(
                instance_uuid=session.instance_uuid,
                workspace_uuid=session.workspace_uuid,
                placement_generation=session.placement_generation,
                query_uuid=query_uuid,
                bot_uuid=session.bot_uuid,
            )
        )
        binding = await self._target_binding_for_component(
            tool_name,
            component_kind='tool',
            include_plugins=bound_plugins,
        )
        with self.handler.installation_scope(binding):
            return await self.handler.call_tool(
                tool_name,
                parameters,
                session.model_dump(serialize_as_any=True),
                query_id,
                query_uuid=query_uuid,
                include_plugins=bound_plugins,
            )

    async def list_commands(self, bound_plugins: list[str] | None = None) -> list[ComponentManifest]:
        if not self.is_enable_plugin:
            return []

        commands: list[ComponentManifest] = []
        seen: set[tuple[str, str]] = set()
        for binding in await self._operation_bindings(include_plugins=bound_plugins):
            with self.handler.installation_scope(binding):
                scoped = await self.handler.list_commands(include_plugins=bound_plugins)
            for raw_command in scoped:
                command = ComponentManifest.model_validate(raw_command)
                key = (str(command.owner), command.metadata.name)
                if key not in seen:
                    seen.add(key)
                    commands.append(command)
        return commands

    async def execute_command(
        self, command_ctx: command_context.ExecuteContext, bound_plugins: list[str] | None = None
    ) -> typing.AsyncGenerator[command_context.CommandReturn, None]:
        if not self.is_enable_plugin:
            yield command_context.CommandReturn(error=command_errors.CommandNotFoundError(command_ctx.command))
            return

        await self.require_workspace_context(
            ExecutionContext(
                instance_uuid=command_ctx.instance_uuid,
                workspace_uuid=command_ctx.workspace_uuid,
                placement_generation=command_ctx.placement_generation,
                query_uuid=command_ctx.query_uuid,
            )
        )
        binding = await self._target_binding_for_component(
            command_ctx.command,
            component_kind='command',
            include_plugins=bound_plugins,
        )
        with self.handler.installation_scope(binding):
            gen = self.handler.execute_command(
                command_ctx.model_dump(serialize_as_any=True),
                include_plugins=bound_plugins,
            )
            async for ret in gen:
                yield command_context.CommandReturn.model_validate(ret)

    async def retrieve_knowledge(
        self,
        plugin_author: str,
        plugin_name: str,
        retriever_name: str,
        retrieval_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Retrieve knowledge using a KnowledgeEngine instance."""
        if not self.is_enable_plugin:
            return {'results': []}

        binding = await self._target_binding(plugin_author, plugin_name)
        with self.handler.installation_scope(binding):
            return await self.handler.retrieve_knowledge(plugin_author, plugin_name, retriever_name, retrieval_context)

    def dispose(self):
        # On non-Windows stdio mode, terminate via the controller's process handle.
        # On Windows, the managed subprocess is cleaned up by the base class.
        if (
            self.is_enable_plugin
            and hasattr(self, 'ctrl')
            and isinstance(self.ctrl, stdio_client_controller.StdioClientController)
        ):
            self.ap.logger.info('Terminating plugin runtime process...')
            self.ctrl.process.terminate()

        self._dispose_subprocess()

        if self.heartbeat_task is not None:
            self.heartbeat_task.cancel()
            self.heartbeat_task = None

    @staticmethod
    def _parse_plugin_id(plugin_id: str) -> tuple[str, str]:
        """Parse a plugin ID string into (author, name).

        Args:
            plugin_id: Plugin ID in 'author/name' format.

        Returns:
            Tuple of (plugin_author, plugin_name).

        Raises:
            ValueError: If plugin_id is not in the expected 'author/name' format.
        """
        segments = plugin_id.split('/')
        if len(segments) != 2 or not all(segments):
            raise ValueError(
                f"Invalid plugin_id format: '{plugin_id}'. Expected 'author/name' format (e.g. 'langbot/rag-engine')."
            )
        return segments[0], segments[1]

    async def call_rag_ingest(self, plugin_id: str, context_data: dict[str, Any]) -> dict[str, Any]:
        """Call plugin to ingest document.

        Args:
            plugin_id: Target plugin ID (author/name).
            context_data: IngestionContext data.
        """
        plugin_author, plugin_name = self._parse_plugin_id(plugin_id)
        binding = await self._target_binding(plugin_author, plugin_name)
        with self.handler.installation_scope(binding):
            return await self.handler.rag_ingest_document(plugin_author, plugin_name, context_data)

    async def call_rag_delete_document(self, plugin_id: str, document_id: str, kb_id: str) -> bool:
        plugin_author, plugin_name = self._parse_plugin_id(plugin_id)
        binding = await self._target_binding(plugin_author, plugin_name)
        with self.handler.installation_scope(binding):
            return await self.handler.rag_delete_document(plugin_author, plugin_name, document_id, kb_id)

    async def get_rag_creation_schema(self, plugin_id: str) -> dict[str, Any]:
        plugin_author, plugin_name = self._parse_plugin_id(plugin_id)
        binding = await self._target_binding(plugin_author, plugin_name)
        with self.handler.installation_scope(binding):
            return await self.handler.get_rag_creation_schema(plugin_author, plugin_name)

    async def get_rag_retrieval_schema(self, plugin_id: str) -> dict[str, Any]:
        plugin_author, plugin_name = self._parse_plugin_id(plugin_id)
        binding = await self._target_binding(plugin_author, plugin_name)
        with self.handler.installation_scope(binding):
            return await self.handler.get_rag_retrieval_schema(plugin_author, plugin_name)

    async def rag_on_kb_create(self, plugin_id: str, kb_id: str, config: dict[str, Any]) -> dict[str, Any]:
        """Notify plugin about KB creation."""
        plugin_author, plugin_name = self._parse_plugin_id(plugin_id)
        binding = await self._target_binding(plugin_author, plugin_name)
        with self.handler.installation_scope(binding):
            return await self.handler.rag_on_kb_create(plugin_author, plugin_name, kb_id, config)

    async def rag_on_kb_delete(self, plugin_id: str, kb_id: str) -> dict[str, Any]:
        """Notify plugin about KB deletion."""
        plugin_author, plugin_name = self._parse_plugin_id(plugin_id)
        binding = await self._target_binding(plugin_author, plugin_name)
        with self.handler.installation_scope(binding):
            return await self.handler.rag_on_kb_delete(plugin_author, plugin_name, kb_id)

    async def call_rag_retrieve(self, plugin_id: str, retrieval_context: dict[str, Any]) -> dict[str, Any]:
        """Call plugin to retrieve knowledge.

        Args:
            plugin_id: Target plugin ID (author/name).
            retrieval_context: RetrievalContext data.
        """
        plugin_author, plugin_name = self._parse_plugin_id(plugin_id)
        binding = await self._target_binding(plugin_author, plugin_name)
        with self.handler.installation_scope(binding):
            return await self.handler.retrieve_knowledge(plugin_author, plugin_name, '', retrieval_context)

    async def list_knowledge_engines(self) -> list[dict[str, Any]]:
        """List all available Knowledge Engines from plugins.

        Returns a list of Knowledge Engines with their capabilities and configuration schemas.
        """
        if not self.is_enable_plugin:
            return []

        engines: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for binding in await self._operation_bindings():
            with self.handler.installation_scope(binding):
                scoped = await self.handler.list_knowledge_engines()
            for engine in scoped:
                key = (str(engine.get('plugin_id', '')), str(engine.get('name', '')))
                if key not in seen:
                    seen.add(key)
                    engines.append(engine)
        return engines

    async def list_parsers(self) -> list[dict[str, Any]]:
        """List all available parsers from plugins."""
        if not self.is_enable_plugin:
            return []
        parsers: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for binding in await self._operation_bindings():
            with self.handler.installation_scope(binding):
                scoped = await self.handler.list_parsers()
            for parser in scoped:
                key = (str(parser.get('plugin_id', '')), str(parser.get('name', '')))
                if key not in seen:
                    seen.add(key)
                    parsers.append(parser)
        return parsers

    async def call_parser(self, plugin_id: str, context_data: dict[str, Any], file_bytes: bytes) -> dict[str, Any]:
        """Call plugin to parse a document."""
        plugin_author, plugin_name = self._parse_plugin_id(plugin_id)
        binding = await self._target_binding(plugin_author, plugin_name)
        with self.handler.installation_scope(binding):
            return await self.handler.parse_document(plugin_author, plugin_name, context_data, file_bytes)
