from __future__ import annotations

import asyncio
import quart

from ...authz import Permission
from ...context import RequestContext
from ...service.secrets import redact_secrets
from .. import group


@group.group_class('extensions', '/api/v1/extensions')
class ExtensionsRouterGroup(group.RouterGroup):
    """Unified API for installed extensions (plugins, MCP servers, skills)."""

    async def initialize(self) -> None:
        @self.route(
            '',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> quart.Response:
            if self.ap.plugin_connector.is_enable_plugin:
                await self.ap.plugin_connector.require_workspace_context(request_context)

            async def read_in_task_scope(operation):
                tenant_scope = getattr(getattr(self.ap, 'persistence_mgr', None), 'tenant_scope', None)
                if callable(tenant_scope):
                    async with tenant_scope(request_context.workspace_uuid):
                        return await operation()
                return await operation()

            plugins, mcp_servers, skills = await asyncio.gather(
                read_in_task_scope(self.ap.plugin_connector.list_plugins),
                read_in_task_scope(
                    lambda: self.ap.mcp_service.get_mcp_servers(request_context, contain_runtime_info=True)
                ),
                read_in_task_scope(lambda: self.ap.skill_service.list_skills(request_context)),
                return_exceptions=True,
            )

            def _sort_key(item: dict) -> str:
                if item['type'] == 'plugin':
                    return (
                        item['plugin']
                        .get('manifest', {})
                        .get('manifest', {})
                        .get('metadata', {})
                        .get('name', '')
                        .lower()
                    )
                if item['type'] == 'mcp':
                    return (item['server'].get('name') or '').lower()
                if item['type'] == 'skill':
                    return (item['skill'].get('display_name') or item['skill'].get('name') or '').lower()
                return ''

            extensions: list[dict] = []
            if isinstance(plugins, list):
                for plugin in plugins:
                    extensions.append({'type': 'plugin', 'plugin': redact_secrets(plugin)})
            if isinstance(mcp_servers, list):
                for server in mcp_servers:
                    extensions.append({'type': 'mcp', 'server': server})
            if isinstance(skills, list):
                for skill in skills:
                    extensions.append({'type': 'skill', 'skill': skill})

            extensions.sort(key=_sort_key)

            return self.success(data={'extensions': extensions})
