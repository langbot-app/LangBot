from __future__ import annotations

import quart

from ... import group
from ......pipeline.extension_preferences import normalize_extension_preferences


@group.group_class('tools', '/api/v1/tools')
class ToolsRouterGroup(group.RouterGroup):
    async def _get_scoped_tool_catalog(self) -> list[dict] | None:
        pipeline_uuid = quart.request.args.get('pipeline_uuid') or quart.request.args.get('pipeline_id')
        bound_plugins: list[str] | None = None
        bound_mcp_servers: list[str] | None = None

        if pipeline_uuid:
            pipeline = await self.ap.pipeline_service.get_pipeline(pipeline_uuid)
            if pipeline is None:
                return None

            extensions_prefs = normalize_extension_preferences(pipeline.get('extensions_preferences'))
            if not extensions_prefs['enable_all_plugins']:
                bound_plugins = [f'{plugin["author"]}/{plugin["name"]}' for plugin in extensions_prefs['plugins']]
            if not extensions_prefs['enable_all_mcp_servers']:
                bound_mcp_servers = extensions_prefs['mcp_servers']

        return await self.ap.tool_mgr.get_resolved_tool_catalog(
            bound_plugins,
            bound_mcp_servers,
            include_skill_authoring=True,
        )

    async def initialize(self) -> None:
        @self.route('', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            """获取所有可用工具列表"""
            catalog = await self._get_scoped_tool_catalog()
            if catalog is None:
                return self.http_status(404, -1, 'pipeline not found')
            return self.success(data={'tools': catalog})

        @self.route('/<path:tool_name>', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _(tool_name: str) -> str:
            """获取特定工具详情"""
            catalog = await self._get_scoped_tool_catalog()
            if catalog is None:
                return self.http_status(404, -1, 'pipeline not found')

            for tool in catalog:
                if tool.get('name') == tool_name:
                    return self.success(
                        data={
                            'tool': {
                                'name': tool['name'],
                                'description': tool.get('description') or '',
                                'human_desc': tool.get('human_desc') or '',
                                'parameters': tool.get('parameters') or {},
                                'source': tool.get('source'),
                                'source_name': tool.get('source_name'),
                                'source_id': tool.get('source_id'),
                            }
                        }
                    )

            return self.http_status(404, -1, f'Tool not found: {tool_name}')
