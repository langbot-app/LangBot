from __future__ import annotations

import asyncio
import copy
import re
import uuid

import sqlalchemy

from ....core import app, taskmgr
from ....entity.persistence import mcp as persistence_mcp
from ....entity.persistence import plugin as persistence_plugin
from ....provider.tools.loaders.mcp import MCPSessionStatus, RuntimeMCPSession
from ....provider.tools.loaders.mcp_policy import require_stdio_mcp_enabled
from ....workspace.errors import WorkspaceNotFoundError
from ..context import ExecutionContext
from .secrets import is_url_key, redact_url_secrets, restore_url_secret_placeholders
from .tenant import TenantContext, require_workspace_uuid, scope_statement


_SECRET_MASK = '***'
_MISSING_SECRET = object()
_SENSITIVE_CONFIG_NAMES = frozenset(
    {
        'api_key',
        'apikey',
        'auth',
        'authorization',
        'cookie',
        'credentials',
        'database_url',
        'dsn',
        'key',
        'proxy_authorization',
        'set_cookie',
    }
)
_SENSITIVE_CONFIG_TOKENS = frozenset(
    {
        'credential',
        'credentials',
        'passwd',
        'password',
        'secret',
        'token',
    }
)
_SENSITIVE_KEY_QUALIFIERS = frozenset(
    {
        'access',
        'api',
        'auth',
        'bearer',
        'client',
        'debug',
        'encryption',
        'private',
        'signing',
    }
)


def _normalize_config_key(key: object) -> str:
    value = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', str(key or ''))
    return re.sub(r'[^a-zA-Z0-9]+', '_', value).strip('_').lower()


def _is_sensitive_config_key(key: object) -> bool:
    normalized = _normalize_config_key(key)
    if normalized in _SENSITIVE_CONFIG_NAMES:
        return True
    tokens = frozenset(token for token in normalized.split('_') if token)
    if tokens & _SENSITIVE_CONFIG_TOKENS:
        return True
    return 'key' in tokens and bool(tokens & _SENSITIVE_KEY_QUALIFIERS)


def _mask_secret_structure(value):
    if isinstance(value, dict):
        return {key: _mask_secret_structure(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_mask_secret_structure(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_mask_secret_structure(item) for item in value)
    if value is None or value == '':
        return value
    return _SECRET_MASK


def redact_mcp_secrets(value):
    """Return a recursively redacted copy of MCP configuration data."""

    if isinstance(value, dict):
        return {
            key: (
                _mask_secret_structure(item)
                if _is_sensitive_config_key(key)
                else redact_url_secrets(item)
                if is_url_key(key)
                else redact_mcp_secrets(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_mcp_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_mcp_secrets(item) for item in value)
    return value


def restore_mcp_secret_placeholders(value, current_value=_MISSING_SECRET, *, sensitive: bool = False):
    """Restore masked leaves from the current MCP config before a write."""

    if sensitive and value == _SECRET_MASK:
        if current_value is _MISSING_SECRET:
            raise ValueError('Masked MCP secret has no existing value')
        return copy.deepcopy(current_value)
    if isinstance(value, dict):
        current_mapping = current_value if isinstance(current_value, dict) else {}
        return {
            key: (
                restore_url_secret_placeholders(
                    item,
                    current_mapping.get(key, _MISSING_SECRET),
                )
                if not sensitive and not _is_sensitive_config_key(key) and is_url_key(key)
                else restore_mcp_secret_placeholders(
                    item,
                    current_mapping.get(key, _MISSING_SECRET),
                    sensitive=sensitive or _is_sensitive_config_key(key),
                )
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        current_items = current_value if isinstance(current_value, (list, tuple)) else ()
        return [
            restore_mcp_secret_placeholders(
                item,
                current_items[index] if index < len(current_items) else _MISSING_SECRET,
                sensitive=sensitive,
            )
            for index, item in enumerate(value)
        ]
    if isinstance(value, tuple):
        current_items = current_value if isinstance(current_value, (list, tuple)) else ()
        return tuple(
            restore_mcp_secret_placeholders(
                item,
                current_items[index] if index < len(current_items) else _MISSING_SECRET,
                sensitive=sensitive,
            )
            for index, item in enumerate(value)
        )
    return value


class MCPService:
    """Workspace-scoped MCP configuration and runtime facade."""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def _execution_context(self, context: TenantContext) -> ExecutionContext:
        workspace_uuid = require_workspace_uuid(context)
        instance_uuid = str(getattr(context, 'instance_uuid', '') or '').strip()
        generation = getattr(context, 'placement_generation', None)
        if not instance_uuid or not isinstance(generation, int) or isinstance(generation, bool) or generation <= 0:
            raise ValueError('MCP operations require an explicit fenced execution context')
        binding = await self.ap.workspace_service.get_execution_binding(
            workspace_uuid,
            expected_generation=generation,
        )
        if binding.instance_uuid != instance_uuid:
            raise ValueError('MCP execution context belongs to another LangBot instance')
        return ExecutionContext(
            instance_uuid=instance_uuid,
            workspace_uuid=workspace_uuid,
            placement_generation=generation,
            bot_uuid=getattr(context, 'bot_uuid', None),
            pipeline_uuid=getattr(context, 'pipeline_uuid', None),
            query_uuid=getattr(context, 'query_uuid', None),
        )

    async def get_runtime_info(self, context: TenantContext, server_name: str) -> dict | None:
        execution_context = await self._execution_context(context)
        session = self.ap.tool_mgr.mcp_tool_loader.get_session(execution_context, server_name)
        return session.get_runtime_info_dict() if session else None

    async def get_mcp_servers(self, context: TenantContext, contain_runtime_info: bool = False) -> list[dict]:
        execution_context = await self._execution_context(context)
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(sqlalchemy.select(persistence_mcp.MCPServer), persistence_mcp.MCPServer, context)
        )
        serialized_servers = [
            redact_mcp_secrets(self.ap.persistence_mgr.serialize_model(persistence_mcp.MCPServer, server))
            for server in result.all()
        ]
        if contain_runtime_info:
            for server in serialized_servers:
                session = self.ap.tool_mgr.mcp_tool_loader.get_session(execution_context, server['name'])
                server['runtime_info'] = session.get_runtime_info_dict() if session else None
        return serialized_servers

    async def create_mcp_server(self, context: TenantContext, server_data: dict) -> str:
        execution_context = await self._execution_context(context)
        workspace_uuid = execution_context.workspace_uuid

        # This gate is independent of Box availability.  Cloud v2 disables
        # stdio MCP even though Box Runtime itself remains available.
        require_stdio_mcp_enabled(self.ap, server_data)

        limitation = self.ap.instance_config.data.get('system', {}).get('limitation', {})
        max_extensions = limitation.get('max_extensions', -1)
        if max_extensions >= 0:
            mcp_count_result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(sqlalchemy.func.count(persistence_mcp.MCPServer.uuid)).where(
                    persistence_mcp.MCPServer.workspace_uuid == workspace_uuid
                )
            )
            plugin_count_result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(sqlalchemy.func.count())
                .select_from(persistence_plugin.PluginSetting)
                .where(persistence_plugin.PluginSetting.workspace_uuid == workspace_uuid)
            )
            if (mcp_count_result.scalar() or 0) + (plugin_count_result.scalar() or 0) >= max_extensions:
                raise ValueError(f'Maximum number of extensions ({max_extensions}) reached')

        payload = dict(server_data)
        payload.pop('workspace_uuid', None)
        server_name = str(payload.get('name') or '').strip()
        if not server_name:
            raise ValueError('MCP server name is required')
        payload['name'] = server_name
        payload['workspace_uuid'] = workspace_uuid
        payload['uuid'] = str(uuid.uuid4())

        existing_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_mcp.MCPServer).where(
                persistence_mcp.MCPServer.workspace_uuid == workspace_uuid,
                persistence_mcp.MCPServer.name == server_name,
            )
        )
        if existing_result.first() is not None:
            raise ValueError(f'MCP server already exists: {server_name}')

        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_mcp.MCPServer).values(payload))
        created = await self._get_mcp_server_by_uuid_raw(execution_context, payload['uuid'])
        if created and self.ap.tool_mgr.mcp_tool_loader:
            task = asyncio.create_task(self.ap.tool_mgr.mcp_tool_loader.host_mcp_server(execution_context, created))
            self.ap.tool_mgr.mcp_tool_loader._hosted_mcp_tasks.append(task)
        return payload['uuid']

    async def get_mcp_server_by_uuid(self, context: TenantContext, server_uuid: str) -> dict | None:
        execution_context = await self._execution_context(context)
        server_data = await self._get_mcp_server_by_uuid_raw(execution_context, server_uuid)
        return redact_mcp_secrets(server_data) if server_data is not None else None

    async def _get_mcp_server_by_uuid_raw(
        self,
        execution_context: ExecutionContext,
        server_uuid: str,
    ) -> dict | None:
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_mcp.MCPServer).where(persistence_mcp.MCPServer.uuid == server_uuid),
                persistence_mcp.MCPServer,
                execution_context,
            )
        )
        server = result.first()
        return self.ap.persistence_mgr.serialize_model(persistence_mcp.MCPServer, server) if server else None

    async def get_mcp_server_by_name(self, context: TenantContext, server_name: str) -> dict | None:
        execution_context = await self._execution_context(context)
        server_data = await self._get_mcp_server_by_name_raw(execution_context, server_name)
        if server_data is None:
            return None
        session = self.ap.tool_mgr.mcp_tool_loader.get_session(execution_context, server_name)
        response_data = {
            **server_data,
            'runtime_info': session.get_runtime_info_dict() if session else None,
        }
        return redact_mcp_secrets(response_data)

    async def _get_mcp_server_by_name_raw(
        self,
        execution_context: ExecutionContext,
        server_name: str,
    ) -> dict | None:
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_mcp.MCPServer).where(persistence_mcp.MCPServer.name == server_name),
                persistence_mcp.MCPServer,
                execution_context,
            )
        )
        server = result.first()
        if server is None:
            return None
        return self.ap.persistence_mgr.serialize_model(persistence_mcp.MCPServer, server)

    async def update_mcp_server(self, context: TenantContext, server_uuid: str, server_data: dict) -> None:
        execution_context = await self._execution_context(context)
        old_server = await self._get_mcp_server_by_uuid_raw(execution_context, server_uuid)
        if old_server is None:
            raise WorkspaceNotFoundError('MCP server not found')

        payload = dict(server_data)
        payload.pop('uuid', None)
        payload.pop('workspace_uuid', None)
        payload = restore_mcp_secret_placeholders(payload, old_server)
        if 'name' in payload:
            payload['name'] = str(payload['name'] or '').strip()
            if not payload['name']:
                raise ValueError('MCP server name is required')
            duplicate = await self._get_mcp_server_by_name_raw(execution_context, payload['name'])
            if duplicate is not None and duplicate['uuid'] != server_uuid:
                raise ValueError(f'MCP server already exists: {payload["name"]}')

        effective_server = {**old_server, **payload}
        # Existing disabled rows remain readable/deletable.  Switching away
        # from stdio or explicitly disabling one is also allowed, but an
        # update may never leave a disabled stdio server enabled.
        if bool(effective_server.get('enable', True)):
            require_stdio_mcp_enabled(self.ap, effective_server)

        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.update(persistence_mcp.MCPServer)
                .where(persistence_mcp.MCPServer.uuid == server_uuid)
                .values(payload),
                persistence_mcp.MCPServer,
                execution_context,
            )
        )
        if getattr(result, 'rowcount', None) == 0:
            raise WorkspaceNotFoundError('MCP server not found')

        loader = self.ap.tool_mgr.mcp_tool_loader
        if loader is None:
            return
        old_name = old_server['name']
        old_enable = bool(old_server['enable'])
        updated = await self._get_mcp_server_by_uuid_raw(execution_context, server_uuid)
        if updated is None:
            raise WorkspaceNotFoundError('MCP server not found')
        new_enable = bool(updated['enable'])
        if old_enable and loader.has_session(execution_context, old_name):
            await loader.remove_mcp_server(execution_context, old_name)
        if new_enable:
            task = asyncio.create_task(loader.host_mcp_server(execution_context, updated))
            loader._hosted_mcp_tasks.append(task)

    async def delete_mcp_server(self, context: TenantContext, server_uuid: str) -> None:
        execution_context = await self._execution_context(context)
        server = await self._get_mcp_server_by_uuid_raw(execution_context, server_uuid)
        if server is None:
            raise WorkspaceNotFoundError('MCP server not found')
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.delete(persistence_mcp.MCPServer).where(persistence_mcp.MCPServer.uuid == server_uuid),
                persistence_mcp.MCPServer,
                execution_context,
            )
        )
        if getattr(result, 'rowcount', None) == 0:
            raise WorkspaceNotFoundError('MCP server not found')
        loader = self.ap.tool_mgr.mcp_tool_loader
        if loader and loader.has_session(execution_context, server['name']):
            await loader.remove_mcp_server(execution_context, server['name'])

    async def _require_server(self, context: TenantContext, server_name: str) -> tuple[ExecutionContext, dict]:
        execution_context = await self._execution_context(context)
        server = await self._get_mcp_server_by_name_raw(execution_context, server_name)
        if server is None:
            raise WorkspaceNotFoundError('MCP server not found')
        return execution_context, server

    async def get_mcp_server_resources(self, context: TenantContext, server_name: str) -> list[dict]:
        execution_context, _ = await self._require_server(context, server_name)
        return await self.ap.tool_mgr.mcp_tool_loader.get_resources(execution_context, server_name)

    async def get_mcp_server_resource_templates(self, context: TenantContext, server_name: str) -> list[dict]:
        execution_context, _ = await self._require_server(context, server_name)
        return await self.ap.tool_mgr.mcp_tool_loader.get_resource_templates(execution_context, server_name)

    async def read_mcp_server_resource_envelope(
        self,
        context: TenantContext,
        server_name: str,
        uri: str,
        *,
        max_bytes: int | None = None,
        include_blob: bool = False,
    ) -> dict:
        execution_context, _ = await self._require_server(context, server_name)
        kwargs = {'include_blob': include_blob, 'source': 'ui_preview'}
        if max_bytes is not None:
            kwargs['max_bytes'] = max_bytes
        return await self.ap.tool_mgr.mcp_tool_loader.read_resource_envelope(
            execution_context,
            server_name,
            uri,
            **kwargs,
        )

    async def read_mcp_server_resource(self, context: TenantContext, server_name: str, uri: str) -> list[dict]:
        execution_context, _ = await self._require_server(context, server_name)
        return await self.ap.tool_mgr.mcp_tool_loader.read_resource(execution_context, server_name, uri)

    async def test_mcp_server(self, context: TenantContext, server_name: str, server_data: dict) -> int:
        execution_context = await self._execution_context(context)
        runtime_mcp_session: RuntimeMCPSession | None = None
        ctx = taskmgr.TaskContext.new()

        if server_name != '_':
            _, persisted_server = await self._require_server(execution_context, server_name)
            require_stdio_mcp_enabled(self.ap, persisted_server)
            runtime_mcp_session = self.ap.tool_mgr.mcp_tool_loader.get_session(execution_context, server_name)
            if runtime_mcp_session is None:
                raise WorkspaceNotFoundError('MCP server not found')
            persisted_session = runtime_mcp_session

            async def _refresh_and_report() -> None:
                needs_start = persisted_session.status == MCPSessionStatus.ERROR or persisted_session.session is None
                if needs_start:
                    await persisted_session.start()
                else:
                    try:
                        await persisted_session.refresh()
                    except Exception:
                        await persisted_session.start()
                ctx.metadata['runtime_info'] = persisted_session.get_runtime_info_dict()

            coroutine = _refresh_and_report()
        else:
            payload = dict(server_data)
            payload.pop('workspace_uuid', None)
            payload['workspace_uuid'] = execution_context.workspace_uuid
            require_stdio_mcp_enabled(self.ap, payload)
            runtime_mcp_session = await self.ap.tool_mgr.mcp_tool_loader.load_mcp_server(
                execution_context,
                payload,
            )
            test_session = runtime_mcp_session

            async def _run_and_cleanup() -> None:
                try:
                    await test_session.start()
                    ctx.metadata['runtime_info'] = test_session.get_runtime_info_dict()
                finally:
                    try:
                        await test_session.shutdown()
                    except Exception as exc:
                        self.ap.logger.warning(
                            f'Failed to tear down transient MCP test session '
                            f'{test_session.server_name}: {type(exc).__name__}: {exc}'
                        )

            coroutine = _run_and_cleanup()

        wrapper = self.ap.task_mgr.create_user_task(
            coroutine,
            kind='mcp-operation',
            name=f'mcp-test-{execution_context.workspace_uuid}-{server_name}',
            label=f'Testing MCP server {server_name}',
            context=ctx,
            instance_uuid=execution_context.instance_uuid,
            workspace_uuid=execution_context.workspace_uuid,
            placement_generation=execution_context.placement_generation,
        )
        return wrapper.id

    async def get_mcp_server_logs(
        self,
        context: TenantContext,
        server_name: str,
        limit: int = 200,
        level: str | None = None,
    ) -> list[dict]:
        execution_context, _ = await self._require_server(context, server_name)
        session = self.ap.tool_mgr.mcp_tool_loader.get_session(execution_context, server_name)
        if not session:
            return []
        logs = list(session._log_buffer)
        if level:
            logs = [log for log in logs if log.get('level') == level]
        return logs[-limit:]
