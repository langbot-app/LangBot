from __future__ import annotations

import quart

from ... import group


@group.group_class('tools', '/api/v1/tools')
class ToolsRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            """获取所有可用工具列表"""
            pipeline_uuid = quart.request.args.get('pipeline_uuid') or quart.request.args.get('pipeline_id')
            bound_plugins: list[str] | None = None
            bound_mcp_servers: list[str] | None = None

            if pipeline_uuid:
                pipeline = await self.ap.pipeline_service.get_pipeline(pipeline_uuid)
                if pipeline is None:
                    return self.http_status(404, -1, 'pipeline not found')

                extensions_prefs = pipeline.get('extensions_preferences', {}) or {}
                if not extensions_prefs.get('enable_all_plugins', True):
                    bound_plugins = [
                        f'{plugin.get("author", "")}/{plugin.get("name", "")}'
                        for plugin in extensions_prefs.get('plugins', [])
                        if isinstance(plugin, dict) and plugin.get('name')
                    ]
                if not extensions_prefs.get('enable_all_mcp_servers', True):
                    bound_mcp_servers = [
                        server for server in (extensions_prefs.get('mcp_servers', []) or []) if isinstance(server, str)
                    ]

            return self.success(
                data={
                    'tools': await self.ap.tool_mgr.get_tool_catalog(
                        bound_plugins,
                        bound_mcp_servers,
                        include_skill_authoring=True,
                    )
                }
            )

        @self.route('/<tool_name>', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _(tool_name: str) -> str:
            """获取特定工具详情"""
            tools = await self.ap.tool_mgr.get_all_tools()

            for tool in tools:
                if tool.name == tool_name:
                    return self.success(
                        data={
                            'tool': {
                                'name': tool.name,
                                'description': tool.description,
                                'human_desc': tool.human_desc,
                                'parameters': tool.parameters,
                            }
                        }
                    )

            return self.http_status(404, -1, f'Tool not found: {tool_name}')
