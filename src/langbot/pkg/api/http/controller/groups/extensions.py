from __future__ import annotations

import asyncio
import quart

from .. import group


@group.group_class('extensions', '/api/v1/extensions')
class ExtensionsRouterGroup(group.RouterGroup):
    """Unified API for installed extensions (plugins, MCP servers, skills)."""

    async def initialize(self) -> None:
        @self.route('', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> quart.Response:
            plugins, mcp_servers, skills = await asyncio.gather(
                self.ap.plugin_connector.list_plugins(),
                self.ap.mcp_service.get_mcp_servers(contain_runtime_info=True),
                self.ap.skill_service.list_skills(),
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
                    extensions.append({'type': 'plugin', 'plugin': plugin})
            if isinstance(mcp_servers, list):
                for server in mcp_servers:
                    extensions.append({'type': 'mcp', 'server': server})
            if isinstance(skills, list):
                for skill in skills:
                    extensions.append({'type': 'skill', 'skill': skill})

            extensions.sort(key=_sort_key)

            return self.success(data={'extensions': extensions})
