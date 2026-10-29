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
            plugins, mcp_servers, skills = await asyncio.gather(
                self.call_application('plugin.list', request_context, {}),
                self.call_application('mcp.server.list', request_context, {'contain_runtime_info': True}),
                self.call_application('skill.list', request_context, {}),
                return_exceptions=True,
            )
            if isinstance(plugins, dict):
                plugins = plugins['plugins']

            def _sort_key(item: dict) -> tuple[int, str]:
                is_debug = 0 if (item.get('type') == 'plugin' and item.get('plugin', {}).get('debug')) else 1
                name = ''
                if item['type'] == 'plugin':
                    name = (
                        item['plugin']
                        .get('manifest', {})
                        .get('manifest', {})
                        .get('metadata', {})
                        .get('name', '')
                        .lower()
                    )
                elif item['type'] == 'mcp':
                    name = (item['server'].get('name') or '').lower()
                elif item['type'] == 'skill':
                    name = (item['skill'].get('display_name') or item['skill'].get('name') or '').lower()
                return (is_debug, name)

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
