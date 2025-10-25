from __future__ import annotations
import time
import traceback
import uuid

import quart
import asyncio

import sqlalchemy

from pkg.entity.persistence.mcp import MCPServer

from .....core import taskmgr
from .. import group

from sqlalchemy import insert

@group.group_class('mcp', '/api/v1/mcp')
class MCPRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/servers', methods=['GET', 'POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            """获取MCP服务器列表"""
            if quart.request.method == 'GET':
                result = await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.select(MCPServer).order_by(MCPServer.created_at.desc())
                )
                raw_results = result.all()
                servers = [self.ap.persistence_mgr.serialize_model(MCPServer, row) for row in raw_results]

                servers_with_status = []
                # 获取MCP工具加载器
                mcp_loader = None
                for loader in self.ap.tool_mgr.loaders:
                    if loader.__class__.__name__ == 'MCPLoader':
                        mcp_loader = loader
                        break

                for server in servers:
                    # 设置状态
                    if server['enable']:
                        status = 'enabled'
                    else:
                        status = 'disabled'

                    # 构建 config 对象 (前端期望的格式)
                    extra_args = server.get('extra_args', {})
                    config = {
                        'name': server['name'],
                        'mode': server['mode'],
                        'enable': server['enable'],
                    }

                    # 根据模式添加相应的配置
                    if server['mode'] == 'sse':
                        config['url'] = extra_args.get('url', '')
                        config['headers'] = extra_args.get('headers', {})
                        config['timeout'] = extra_args.get('timeout', 60)
                    elif server['mode'] == 'stdio':
                        config['command'] = extra_args.get('command', '')
                        config['args'] = extra_args.get('args', [])
                        config['env'] = extra_args.get('env', {})

                    # 从运行中的会话获取工具数量
                    tools_count = 0
                    if mcp_loader and hasattr(mcp_loader, 'sessions') and server['name'] in mcp_loader.sessions:
                        session = mcp_loader.sessions[server['name']]
                        tools_count = len(session.functions)

                    server_info = {
                        'name': server['name'],
                        'mode': server['mode'],
                        'enable': server['enable'],
                        'status': status,
                        'tools': tools_count,  # 从运行中的会话获取工具数量
                        'config': config,
                    }
                    servers_with_status.append(server_info)

                return self.success(data={'servers': servers_with_status})
            
            elif quart.request.method == 'POST':
                data = await quart.request.json
                data = data['source']
                try:
                # 检查服务器名称是否重复
                    result = await self.ap.persistence_mgr.execute_async(
                        sqlalchemy.select(MCPServer).where(MCPServer.name == data['name'])
                    )
                    if result.first() is not None:
                        return self.http_status(400, -1, 'Server name already exists')
                    
                    # 创建新服务器配置
                    new_server = {
                        'uuid': str(uuid.uuid4()),
                        'name': data['name'],
                        'mode': 'sse',
                        'enable': data.get('enable', False),
                        'extra_args': {
                            'url':data.get('url',''),
                            'headers':data.get('headers',{}),
                            'timeout':data.get('timeout',60),
                            'ssereadtimeout':data.get('ssereadtimeout',300),
                        },
                    }

                    await self.ap.persistence_mgr.execute_async(
                        sqlalchemy.insert(MCPServer).values(new_server)
                    )

                    return self.success()
                
                except Exception:
                    print(traceback.format_exc())

        @self.route('/servers/<server_name>', methods=['GET', 'PUT', 'DELETE'], auth_type=group.AuthType.USER_TOKEN)
        async def _(server_name: str) -> str:
            """获取、更新或删除MCP服务器配置"""
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(MCPServer).where(MCPServer.name == server_name)
            )
            server = result.first()
            if server is None:
                return self.http_status(404, -1, 'Server not found')
            
            if quart.request.method == 'GET':
                server_data = self.ap.persistence_mgr.serialize_model(MCPServer, server)
                return self.success(data={'server': server_data})
            
            elif quart.request.method == 'PUT':
                data = await quart.request.json
                update_data = {
                    'enable': data.get('enable', server.enable),
                }

                extra_args = server.extra_args or {}
                if server.mode == 'sse':
                    extra_args.update({
                        'url': data.get('url', extra_args.get('url','')),
                        'headers': data.get('headers', extra_args.get('headers',{})),
                        'timeout': data.get('timeout', extra_args.get('timeout',60)),
                        'ssereadtimeout': data.get('ssereadtimeout', extra_args.get('ssereadtimeout',300)),
                    })
                update_data['extra_args'] = extra_args

                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.update(MCPServer).where(MCPServer.name == server_name).values(update_data)
                )

                return self.success()
            
            elif quart.request.method == 'DELETE':
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.delete(MCPServer).where(MCPServer.name == server_name)
                )
                return self.success()
            
        @self.route('/servers/<server_name>/test', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _(server_name: str) -> str:
            """测试MCP服务器连接"""
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(MCPServer).where(MCPServer.name == server_name)
            )
            server = result.first()
            if server is None:
                return self.http_status(404, -1, 'Server not found')
            
            # 创建测试任务
            ctx = taskmgr.TaskContext.new()
            wrapper = self.ap.task_mgr.create_user_task(
                self._test_mcp_server(server, ctx),
                kind='mcp-operation',
                name=f'mcp-test-{server_name}',
                label=f'Testing MCP server {server_name}',
                context=ctx,
            )
            return self.success(data={'task_id': wrapper.id})
            
    async def _test_mcp_server(self, server: MCPServer, ctx: taskmgr.TaskContext):
        """测试MCP服务器连接"""
        try:
            from .....provider.tools.loaders.mcp import RuntimeMCPSession

            ctx.current_action = f'Testing connection to {server.name}'
            print(server)
            # 创建临时会话进行测试
            session = RuntimeMCPSession(server.name, {
            'name': server.name,
            'mode': server.mode,
            'enable': server.enable,
            'url': server.extra_args.get('url',''),
            'headers': server.extra_args.get('headers',{}),
            'timeout': server.extra_args.get('timeout',60),
            },enable=True, ap=self.ap)
            await session.start()

            # 获取工具列表作为测试
            tools_count = len(session.functions)

            tool_name_list = []
            for function in session.functions:
                tool_name_list.append(function.name)
            ctx.current_action = f'Successfully connected. Found {tools_count} tools.'

            # 关闭测试会话
            await session.shutdown()

            return {'status': 'success', 'tools_count': tools_count,'tools_names_lists':tool_name_list}

        except Exception as e:
            print(traceback.format_exc())
            ctx.current_action = f'Connection test failed: {str(e)}'
            raise e
        
    
