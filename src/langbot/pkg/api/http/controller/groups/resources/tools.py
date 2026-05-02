from __future__ import annotations

from ... import group


@group.group_class('tools', '/api/v1/tools')
class ToolsRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            """获取所有可用工具列表"""
            tools = await self.ap.tool_mgr.get_all_tools()

            tool_list = []
            for tool in tools:
                tool_list.append(
                    {
                        'name': tool.name,
                        'description': tool.description,
                        'human_desc': tool.human_desc,
                        'parameters': tool.parameters,
                    }
                )

            return self.success(data={'tools': tool_list})

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
