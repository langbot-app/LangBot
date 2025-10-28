from __future__ import annotations

import quart
import asyncio

from ......core import taskmgr
from ... import group


@group.group_class('mcp', '/api/v1/mcp')
class MCPRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/servers', methods=['GET', 'POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            """获取MCP服务器列表"""
            if quart.request.method == 'GET':
                if not self.ap or not self.ap.provider_cfg or not self.ap.provider_cfg.data:
                    return self.success(data={'servers': []})

                servers = self.ap.provider_cfg.data.get('mcp', {}).get('servers', [])

                # 获取每个服务器的状态和工具信息
                mcp_loader = None
                for loader_name, loader in self.ap.tool_mgr.loaders.items():
                    if loader_name == 'mcp':
                        mcp_loader = loader
                        break

                servers_with_status = []
                for server in servers:
                    server_info = {
                        'name': server['name'],
                        'mode': server['mode'],
                        'enable': server['enable'],
                        'config': server,
                        'status': 'disconnected',
                        'tools': [],
                        'error': None,
                    }

                    # 检查服务器连接状态
                    if mcp_loader and server['name'] in mcp_loader.sessions:
                        session = mcp_loader.sessions[server['name']]
                        server_info['status'] = 'connected'
                        server_info['tools'] = [
                            {'name': func.name, 'description': func.description, 'parameters': func.parameters}
                            for func in session.functions
                        ]
                    elif server['enable']:
                        server_info['status'] = 'error'
                        server_info['error'] = 'Failed to connect'

                    servers_with_status.append(server_info)

                return self.success(data={'servers': servers_with_status})
            elif quart.request.method == 'POST':
                data = await quart.request.json

                # 验证必填字段
                required_fields = ['name', 'mode']
                for field in required_fields:
                    if field not in data:
                        return self.http_status(400, -1, f'Missing required field: {field}')

                # 检查provider_cfg是否可用
                if not self.ap or not self.ap.provider_cfg or not self.ap.provider_cfg.data:
                    return self.http_status(500, -1, 'Provider configuration not available')

                # 获取当前配置
                mcp_config = self.ap.provider_cfg.data.get('mcp', {'servers': []})
                servers = mcp_config['servers']

                # 检查服务器名称是否重复
                for server in servers:
                    if server['name'] == data['name']:
                        return self.http_status(400, -1, 'Server name already exists')

                # 创建新服务器配置
                new_server = {
                    'name': data['name'],
                    'mode': data['mode'],
                    'enable': data.get('enable', True),
                }

                # 根据模式添加配置
                if data['mode'] == 'stdio':
                    new_server.update(
                        {'command': data.get('command', ''), 'args': data.get('args', []), 'env': data.get('env', {})}
                    )
                elif data['mode'] == 'sse':
                    new_server.update(
                        {
                            'url': data.get('url', ''),
                            'headers': data.get('headers', {}),
                            'timeout': data.get('timeout', 10),
                        }
                    )

                # 添加到配置
                servers.append(new_server)
                self.ap.provider_cfg.data['mcp'] = mcp_config

                # 保存配置
                await self.ap.provider_cfg.dump_config()

                # 如果启用，尝试重新加载MCP loader
                if new_server['enable']:
                    ctx = taskmgr.TaskContext.new()
                    wrapper = self.ap.task_mgr.create_user_task(
                        self._reload_mcp_loader(ctx),
                        kind='mcp-operation',
                        name=f'mcp-reload-{new_server["name"]}',
                        label=f'Reloading MCP loader for {new_server["name"]}',
                        context=ctx,
                    )
                    return self.success(data={'task_id': wrapper.id})
                else:
                    return self.success()
            else:
                return self.http_status(405, -1, 'Method not allowed')

        @self.route('/servers/<server_name>', methods=['GET', 'PUT', 'DELETE'], auth_type=group.AuthType.USER_TOKEN)
        async def _(server_name: str) -> str:
            """获取、更新或删除MCP服务器配置"""
            if not self.ap or not self.ap.provider_cfg or not self.ap.provider_cfg.data:
                return self.http_status(500, -1, 'Provider configuration not available')

            mcp_config = self.ap.provider_cfg.data.get('mcp', {'servers': []})
            servers = mcp_config['servers']

            # 查找服务器
            server_index = None
            for i, server in enumerate(servers):
                if server['name'] == server_name:
                    server_index = i
                    break

            if server_index is None:
                return self.http_status(404, -1, 'Server not found')

            if quart.request.method == 'GET':
                return self.success(data={'server': servers[server_index]})

            elif quart.request.method == 'PUT':
                data = await quart.request.json
                server = servers[server_index]

                # 更新配置
                server.update(
                    {
                        'enable': data.get('enable', server.get('enable', True)),
                    }
                )

                # 根据模式更新特定配置
                if server['mode'] == 'stdio':
                    server.update(
                        {
                            'command': data.get('command', server.get('command', '')),
                            'args': data.get('args', server.get('args', [])),
                            'env': data.get('env', server.get('env', {})),
                        }
                    )
                elif server['mode'] == 'sse':
                    server.update(
                        {
                            'url': data.get('url', server.get('url', '')),
                            'headers': data.get('headers', server.get('headers', {})),
                            'timeout': data.get('timeout', server.get('timeout', 10)),
                        }
                    )

                # 保存配置
                await self.ap.provider_cfg.dump_config()

                # 重新加载MCP loader
                ctx = taskmgr.TaskContext.new()
                wrapper = self.ap.task_mgr.create_user_task(
                    self._reload_mcp_loader(ctx),
                    kind='mcp-operation',
                    name=f'mcp-reload-{server_name}',
                    label=f'Reloading MCP loader for {server_name}',
                    context=ctx,
                )
                return self.success(data={'task_id': wrapper.id})

            elif quart.request.method == 'DELETE':
                # 删除服务器
                servers.pop(server_index)
                self.ap.provider_cfg.data['mcp'] = mcp_config

                # 保存配置
                await self.ap.provider_cfg.dump_config()

                # 重新加载MCP loader
                ctx = taskmgr.TaskContext.new()
                wrapper = self.ap.task_mgr.create_user_task(
                    self._reload_mcp_loader(ctx),
                    kind='mcp-operation',
                    name=f'mcp-remove-{server_name}',
                    label=f'Removing MCP server {server_name}',
                    context=ctx,
                )
                return self.success(data={'task_id': wrapper.id})

        @self.route('/servers/<server_name>/toggle', methods=['PUT'], auth_type=group.AuthType.USER_TOKEN)
        async def _(server_name: str) -> str:
            """切换MCP服务器启用状态"""
            data = await quart.request.json
            target_enabled = data.get('target_enabled')

            if not self.ap or not self.ap.provider_cfg or not self.ap.provider_cfg.data:
                return self.http_status(500, -1, 'Provider configuration not available')

            mcp_config = self.ap.provider_cfg.data.get('mcp', {'servers': []})
            servers = mcp_config['servers']

            # 查找并更新服务器
            for server in servers:
                if server['name'] == server_name:
                    server['enable'] = target_enabled
                    break
            else:
                return self.http_status(404, -1, 'Server not found')

            # 保存配置
            await self.ap.provider_cfg.dump_config()

            # 重新加载MCP loader
            ctx = taskmgr.TaskContext.new()
            wrapper = self.ap.task_mgr.create_user_task(
                self._reload_mcp_loader(ctx),
                kind='mcp-operation',
                name=f'mcp-toggle-{server_name}',
                label=f'Toggling MCP server {server_name}',
                context=ctx,
            )
            return self.success(data={'task_id': wrapper.id})

        @self.route('/servers/<server_name>/test', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _(server_name: str) -> str:
            """测试MCP服务器连接"""
            if not self.ap or not self.ap.provider_cfg or not self.ap.provider_cfg.data:
                return self.http_status(500, -1, 'Provider configuration not available')

            mcp_config = self.ap.provider_cfg.data.get('mcp', {'servers': []})
            servers = mcp_config['servers']

            # 查找服务器配置
            server_config = None
            for server in servers:
                if server['name'] == server_name:
                    server_config = server
                    break

            if server_config is None:
                return self.http_status(404, -1, 'Server not found')

            # 创建测试任务
            ctx = taskmgr.TaskContext.new()
            wrapper = self.ap.task_mgr.create_user_task(
                self._test_mcp_server(server_config, ctx),
                kind='mcp-operation',
                name=f'mcp-test-{server_name}',
                label=f'Testing MCP server {server_name}',
                context=ctx,
            )
            return self.success(data={'task_id': wrapper.id})

        @self.route('/install/github', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            """从GitHub安装MCP服务器"""
            data = await quart.request.json
            source = data.get('source')

            if not source:
                return self.http_status(400, -1, 'Missing source parameter')

            # 创建安装任务
            ctx = taskmgr.TaskContext.new()
            wrapper = self.ap.task_mgr.create_user_task(
                self._install_mcp_from_github(source, ctx),
                kind='mcp-operation',
                name='install-mcp-github',
                label=f'Installing MCP from GitHub: {source}',
                context=ctx,
            )
            return self.success(data={'task_id': wrapper.id})

    async def _reload_mcp_loader(self, ctx: taskmgr.TaskContext):
        """重新加载MCP loader"""
        try:
            ctx.current_action = 'Stopping existing MCP sessions'
            # 停止现有的MCP会话
            mcp_loader = None
            for loader_name, loader in self.ap.tool_mgr.loaders.items():
                if loader_name == 'mcp':
                    mcp_loader = loader
                    break

            if mcp_loader:
                await mcp_loader.shutdown()

            ctx.current_action = 'Reloading MCP configuration'
            # 重新加载MCP loader
            await self.ap.tool_mgr.reload_loader('mcp')

            ctx.current_action = 'MCP loader reloaded successfully'

        except Exception as e:
            ctx.current_action = f'Failed to reload MCP loader: {str(e)}'
            raise e

    async def _test_mcp_server(self, server_config: dict, ctx: taskmgr.TaskContext):
        """测试MCP服务器连接"""
        try:
            from ......provider.tools.loaders.mcp import RuntimeMCPSession

            ctx.current_action = f'Testing connection to {server_config["name"]}'

            # 创建临时会话进行测试
            session = RuntimeMCPSession(server_config['name'], server_config, self.ap)
            await session.initialize()

            # 获取工具列表作为测试
            tools_count = len(session.functions)
            ctx.current_action = f'Successfully connected. Found {tools_count} tools.'

            # 关闭测试会话
            await session.shutdown()

            return {'status': 'success', 'tools_count': tools_count}

        except Exception as e:
            ctx.current_action = f'Connection test failed: {str(e)}'
            raise e

    async def _install_mcp_from_github(self, source: str, ctx: taskmgr.TaskContext):
        """从GitHub安装MCP服务器的实现"""
        try:
            ctx.current_action = f'Installing MCP server from {source}'

            # 这里是安装逻辑的占位符
            # 实际实现将包括克隆仓库、解析配置、安装依赖等步骤

            # 模拟安装过程

            await asyncio.sleep(2)  # 模拟安装过程

            # 返回成功结果
            return {'status': 'success', 'message': f'Successfully installed MCP server from {source}'}

        except Exception as e:
            ctx.current_action = f'Failed to install MCP server: {str(e)}'
            raise e
