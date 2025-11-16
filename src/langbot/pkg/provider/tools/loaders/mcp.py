from __future__ import annotations

import enum
import typing
from contextlib import AsyncExitStack
import traceback
import sqlalchemy
import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

from .. import loader
from ....core import app
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
from ....entity.persistence import mcp as persistence_mcp


class MCPSessionStatus(enum.Enum):
    CONNECTING = 'connecting'
    CONNECTED = 'connected'
    ERROR = 'error'


class RuntimeMCPSession:
    """运行时 MCP 会话"""

    ap: app.Application

    server_name: str

    server_uuid: str

    server_config: dict

    session: ClientSession

    exit_stack: AsyncExitStack

    functions: list[resource_tool.LLMTool] = []

    enable: bool

    # connected: bool
    status: MCPSessionStatus

    _lifecycle_task: asyncio.Task | None

    _shutdown_event: asyncio.Event

    _ready_event: asyncio.Event

    def __init__(self, server_name: str, server_config: dict, enable: bool, ap: app.Application):
        self.server_name = server_name
        self.server_uuid = server_config.get('uuid', '')
        self.server_config = server_config
        self.ap = ap
        self.enable = enable
        self.session = None

        self.exit_stack = AsyncExitStack()
        self.functions = []

        self.status = MCPSessionStatus.CONNECTING

        self._lifecycle_task = None
        self._shutdown_event = asyncio.Event()
        self._ready_event = asyncio.Event()

    async def _init_stdio_python_server(self):
        server_params = StdioServerParameters(
            command=self.server_config['command'],
            args=self.server_config['args'],
            env=self.server_config['env'],
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))

        stdio, write = stdio_transport

        self.session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))

        await self.session.initialize()

    async def _init_sse_server(self):
        sse_transport = await self.exit_stack.enter_async_context(
            sse_client(
                self.server_config['url'],
                headers=self.server_config.get('headers', {}),
                timeout=self.server_config.get('timeout', 10),
                sse_read_timeout=self.server_config.get('ssereadtimeout', 30),
            )
        )

        sseio, write = sse_transport

        self.session = await self.exit_stack.enter_async_context(ClientSession(sseio, write))

        await self.session.initialize()

    async def _lifecycle_loop(self):
        """在后台任务中管理整个MCP会话的生命周期"""
        try:
            if self.server_config['mode'] == 'stdio':
                await self._init_stdio_python_server()
            elif self.server_config['mode'] == 'sse':
                await self._init_sse_server()
            else:
                raise ValueError(f'无法识别 MCP 服务器类型: {self.server_name}: {self.server_config}')

            await self.refresh()

            self.status = MCPSessionStatus.CONNECTED

            # 通知start()方法连接已建立
            self._ready_event.set()

            # 等待shutdown信号
            await self._shutdown_event.wait()

        except Exception as e:
            self.status = MCPSessionStatus.ERROR
            self.ap.logger.error(f'Error in MCP session lifecycle {self.server_name}: {e}\n{traceback.format_exc()}')
            # 即使出错也要设置ready事件，让start()方法知道初始化已完成
            self._ready_event.set()
        finally:
            # 在同一个任务中清理所有资源
            try:
                if self.exit_stack:
                    await self.exit_stack.aclose()
                self.functions.clear()
                self.session = None
            except Exception as e:
                self.ap.logger.error(f'Error cleaning up MCP session {self.server_name}: {e}\n{traceback.format_exc()}')

    async def start(self):
        if not self.enable:
            return

        # 创建后台任务来管理生命周期
        self._lifecycle_task = asyncio.create_task(self._lifecycle_loop())

        # 等待连接建立或失败（带超时）
        try:
            await asyncio.wait_for(self._ready_event.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            self.status = MCPSessionStatus.ERROR
            raise Exception('Connection timeout after 30 seconds')

        # 检查是否有错误
        if self.status == MCPSessionStatus.ERROR:
            raise Exception('Connection failed, please check URL')

    async def refresh(self):
        self.functions.clear()

        tools = await self.session.list_tools()

        self.ap.logger.debug(f'Refresh MCP tools: {tools}')

        for tool in tools.tools:

            async def func(*, _tool=tool, **kwargs):
                result = await self.session.call_tool(_tool.name, kwargs)
                if result.isError:
                    raise Exception(result.content[0].text)
                return result.content[0].text

            func.__name__ = tool.name

            self.functions.append(
                resource_tool.LLMTool(
                    name=tool.name,
                    human_desc=tool.description,
                    description=tool.description,
                    parameters=tool.inputSchema,
                    func=func,
                )
            )

    def get_tools(self) -> list[resource_tool.LLMTool]:
        return self.functions

    def get_runtime_info_dict(self) -> dict:
        return {
            'status': self.status.value,
            'tool_count': len(self.get_tools()),
            'tools': [
                {
                    'name': tool.name,
                    'description': tool.description,
                }
                for tool in self.get_tools()
            ],
        }

    async def shutdown(self):
        """关闭会话并清理资源"""
        try:
            # 设置shutdown事件，通知lifecycle任务退出
            self._shutdown_event.set()

            # 等待lifecycle任务完成（带超时）
            if self._lifecycle_task and not self._lifecycle_task.done():
                try:
                    await asyncio.wait_for(self._lifecycle_task, timeout=5.0)
                except asyncio.TimeoutError:
                    self.ap.logger.warning(f'MCP session {self.server_name} shutdown timeout, cancelling task')
                    self._lifecycle_task.cancel()
                    try:
                        await self._lifecycle_task
                    except asyncio.CancelledError:
                        pass

            self.ap.logger.info(f'MCP session {self.server_name} shutdown complete')
        except Exception as e:
            self.ap.logger.error(f'Error shutting down MCP session {self.server_name}: {e}\n{traceback.format_exc()}')


# @loader.loader_class('mcp')
class MCPLoader(loader.ToolLoader):
    """MCP 工具加载器。

    在此加载器中管理所有与 MCP Server 的连接。
    """

    sessions: dict[str, RuntimeMCPSession]

    _last_listed_functions: list[resource_tool.LLMTool]

    _hosted_mcp_tasks: list[asyncio.Task]

    def __init__(self, ap: app.Application):
        super().__init__(ap)
        self.sessions = {}
        self._last_listed_functions = []
        self._hosted_mcp_tasks = []

    async def initialize(self):
        await self.load_mcp_servers_from_db()

    async def load_mcp_servers_from_db(self):
        self.ap.logger.info('Loading MCP servers from db...')

        self.sessions = {}

        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_mcp.MCPServer))
        servers = result.all()

        for server in servers:
            config = self.ap.persistence_mgr.serialize_model(persistence_mcp.MCPServer, server)

            task = asyncio.create_task(self.host_mcp_server(config))
            self._hosted_mcp_tasks.append(task)

    async def host_mcp_server(self, server_config: dict):
        self.ap.logger.debug(f'Loading MCP server {server_config}')
        try:
            session = await self.load_mcp_server(server_config)
            self.sessions[server_config['name']] = session
        except Exception as e:
            self.ap.logger.error(
                f'Failed to load MCP server from db: {server_config["name"]}({server_config["uuid"]}): {e}\n{traceback.format_exc()}'
            )
            return

        self.ap.logger.debug(f'Starting MCP server {server_config["name"]}({server_config["uuid"]})')
        try:
            await session.start()
        except Exception as e:
            self.ap.logger.error(
                f'Failed to start MCP server {server_config["name"]}({server_config["uuid"]}): {e}\n{traceback.format_exc()}'
            )
            return

        self.ap.logger.debug(f'Started MCP server {server_config["name"]}({server_config["uuid"]})')

    async def load_mcp_server(self, server_config: dict) -> RuntimeMCPSession:
        """加载 MCP 服务器到运行时

        Args:
            server_config: 服务器配置字典，必须包含:
                - name: 服务器名称
                - mode: 连接模式 (stdio/sse)
                - enable: 是否启用
                - extra_args: 额外的配置参数 (可选)
        """

        name = server_config['name']
        uuid = server_config['uuid']
        mode = server_config['mode']
        enable = server_config['enable']
        extra_args = server_config.get('extra_args', {})

        mixed_config = {
            'name': name,
            'uuid': uuid,
            'mode': mode,
            'enable': enable,
            **extra_args,
        }

        session = RuntimeMCPSession(name, mixed_config, enable, self.ap)

        return session

    async def get_tools(self, bound_mcp_servers: list[str] | None = None) -> list[resource_tool.LLMTool]:
        all_functions = []

        for session in self.sessions.values():
            # If bound_mcp_servers is specified, only include tools from those servers
            if bound_mcp_servers is not None:
                if session.server_uuid in bound_mcp_servers:
                    all_functions.extend(session.get_tools())
            else:
                # If no bound servers specified, include all tools
                all_functions.extend(session.get_tools())

        self._last_listed_functions = all_functions

        return all_functions

    async def has_tool(self, name: str) -> bool:
        """检查工具是否存在"""
        for session in self.sessions.values():
            for function in session.get_tools():
                if function.name == name:
                    return True
        return False

    async def invoke_tool(self, name: str, parameters: dict) -> typing.Any:
        """执行工具调用"""
        for session in self.sessions.values():
            for function in session.get_tools():
                if function.name == name:
                    self.ap.logger.debug(f'Invoking MCP tool: {name} with parameters: {parameters}')
                    try:
                        result = await function.func(**parameters)
                        self.ap.logger.debug(f'MCP tool {name} executed successfully')
                        return result
                    except Exception as e:
                        self.ap.logger.error(f'Error invoking MCP tool {name}: {e}\n{traceback.format_exc()}')
                        raise

        raise ValueError(f'Tool not found: {name}')

    async def remove_mcp_server(self, server_name: str):
        """移除 MCP 服务器"""
        if server_name not in self.sessions:
            self.ap.logger.warning(f'MCP server {server_name} not found in sessions, skipping removal')
            return

        session = self.sessions.pop(server_name)
        await session.shutdown()
        self.ap.logger.info(f'Removed MCP server: {server_name}')

    def get_session(self, server_name: str) -> RuntimeMCPSession | None:
        """获取指定名称的 MCP 会话"""
        return self.sessions.get(server_name)

    def has_session(self, server_name: str) -> bool:
        """检查是否存在指定名称的 MCP 会话"""
        return server_name in self.sessions

    def get_all_server_names(self) -> list[str]:
        """获取所有已加载的 MCP 服务器名称"""
        return list(self.sessions.keys())

    def get_server_tool_count(self, server_name: str) -> int:
        """获取指定服务器的工具数量"""
        session = self.get_session(server_name)
        return len(session.get_tools()) if session else 0

    def get_all_servers_info(self) -> dict[str, dict]:
        """获取所有服务器的信息"""
        info = {}
        for server_name, session in self.sessions.items():
            info[server_name] = {
                'name': server_name,
                'mode': session.server_config.get('mode'),
                'enable': session.enable,
                'tools_count': len(session.get_tools()),
                'tool_names': [f.name for f in session.get_tools()],
            }
        return info

    async def shutdown(self):
        """关闭所有工具"""
        self.ap.logger.info('Shutting down all MCP sessions...')
        for server_name, session in list(self.sessions.items()):
            try:
                await session.shutdown()
                self.ap.logger.debug(f'Shutdown MCP session: {server_name}')
            except Exception as e:
                self.ap.logger.error(f'Error shutting down MCP session {server_name}: {e}\n{traceback.format_exc()}')
        self.sessions.clear()
        self.ap.logger.info('All MCP sessions shutdown complete')
