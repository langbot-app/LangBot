from __future__ import annotations

import quart
import traceback


from ... import group


@group.group_class('mcp', '/api/v1/mcp')
class MCPRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/servers', methods=['GET', 'POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            """获取MCP服务器列表"""
            if quart.request.method == 'GET':
                servers = await self.ap.mcp_service.get_mcp_servers(contain_runtime_info=True)

                return self.success(data={'servers': servers})

            elif quart.request.method == 'POST':
                data = await quart.request.json

                try:
                    uuid = await self.ap.mcp_service.create_mcp_server(data)
                    return self.success(data={'uuid': uuid})
                except Exception as e:
                    traceback.print_exc()
                    return self.http_status(500, -1, f'Failed to create MCP server: {str(e)}')

        @self.route('/servers/<server_name>', methods=['GET', 'PUT', 'DELETE'], auth_type=group.AuthType.USER_TOKEN)
        async def _(server_name: str) -> str:
            """获取、更新或删除MCP服务器配置"""

            server_data = await self.ap.mcp_service.get_mcp_server_by_name(server_name)
            if server_data is None:
                return self.http_status(404, -1, 'Server not found')

            if quart.request.method == 'GET':
                return self.success(data={'server': server_data})

            elif quart.request.method == 'PUT':
                data = await quart.request.json
                try:
                    await self.ap.mcp_service.update_mcp_server(server_data['uuid'], data)
                    return self.success()
                except Exception as e:
                    return self.http_status(500, -1, f'Failed to update MCP server: {str(e)}')

            elif quart.request.method == 'DELETE':
                try:
                    await self.ap.mcp_service.delete_mcp_server(server_data['uuid'])
                    return self.success()
                except Exception as e:
                    return self.http_status(500, -1, f'Failed to delete MCP server: {str(e)}')

        @self.route('/servers/<server_name>/test', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _(server_name: str) -> str:
            """测试MCP服务器连接"""
            server_data = await quart.request.json
            task_id = await self.ap.mcp_service.test_mcp_server(server_name=server_name, server_data=server_data)
            return self.success(data={'task_id': task_id})
