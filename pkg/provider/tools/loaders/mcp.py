from __future__ import annotations

import typing
from contextlib import AsyncExitStack
import traceback

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

from .. import loader
from ....core import app
from ....entity.persistence import mcp as persistence_mcp
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
import sqlalchemy


class RuntimeMCPSession:
    """运行时 MCP 会话"""

    ap: app.Application

    server_name: str

    server_config: dict

    session: ClientSession

    exit_stack: AsyncExitStack

    functions: list[resource_tool.LLMTool] = []

    enable: bool

    def __init__(self, server_name: str, server_config: dict, enable: bool, ap: app.Application):
        self.server_name = server_name
        self.server_config = server_config
        self.ap = ap
        self.enable = enable
        self.session = None

        self.exit_stack = AsyncExitStack()
        self.functions = []

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
            )
        )

        sseio, write = sse_transport

        self.session = await self.exit_stack.enter_async_context(ClientSession(sseio, write))

        await self.session.initialize()

    async def initialize(self):
        pass

    async def start(self):
        if not self.enable:
            return

        self.ap.logger.debug(f'初始化 MCP 会话: {self.server_name} {self.server_config}')

        if self.server_config['mode'] == 'stdio':
            await self._init_stdio_python_server()
        elif self.server_config['mode'] == 'sse':
            await self._init_sse_server()
        else:
            raise ValueError(f'无法识别 MCP 服务器类型: {self.server_name}: {self.server_config}')

        tools = await self.session.list_tools()

        self.ap.logger.debug(f'获取 MCP 工具: {tools}')

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

    async def shutdown(self):
        """关闭工具"""
        await self.session._exit_stack.aclose()


@loader.loader_class('mcp')
class MCPLoader(loader.ToolLoader):
    """MCP 工具加载器。

    在此加载器中管理所有与 MCP Server 的连接。
    """

    sessions: dict[str, RuntimeMCPSession] = {}

    _last_listed_functions: list[resource_tool.LLMTool] = []

    def __init__(self, ap: app.Application):
        super().__init__(ap)
        self.sessions = {}
        self._last_listed_functions = []

    async def initialize(self):
        await self.load_mcp_servers_from_db()

    async def load_mcp_servers_from_db(self):
        self.ap.logger.info('Loading MCP servers from db...')
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_mcp.MCPServer))
        servers = result.all()
        for server in servers:
            try:
                await self.load_mcp_server(server)
            except Exception as e:
                self.ap.logger.error(f'Failed to load MCP server {server.name}: {e}\n{traceback.format_exc()}')

    async def init_runtime_mcp_session(
        self,
        server_entity: persistence_mcp.MCPServer | sqlalchemy.Row[persistence_mcp.MCPServer] | dict,
    ):
        if isinstance(server_entity, sqlalchemy.Row):
            server_entity = persistence_mcp.MCPServer(**server_entity._mapping)
        elif isinstance(server_entity, dict):
            server_entity = persistence_mcp.MCPServer(**server_entity)

        mixed_config = {
            'name': server_entity.name,
            'mode': server_entity.mode,
            'enable': server_entity.enable,
            **server_entity.extra_args,
        }

        session = RuntimeMCPSession(server_entity.name, mixed_config, server_entity.enable, self.ap)
        await session.initialize()

        return session

    async def load_mcp_server(
        self,
        server_entity: persistence_mcp.MCPServer | sqlalchemy.Row[persistence_mcp.MCPServer] | dict,
    ):
        session = await self.init_runtime_mcp_session(server_entity)
        self.sessions[server_entity.name] = session

    async def get_tools(self) -> list[resource_tool.LLMTool]:
        all_functions = []

        for session in self.sessions.values():
            all_functions.extend(session.functions)

        self._last_listed_functions = all_functions

        return all_functions

    async def has_tool(self, name: str) -> bool:
        return name in [f.name for f in self._last_listed_functions]

    async def invoke_tool(self, name: str, parameters: dict) -> typing.Any:
        for server_name, session in self.sessions.items():
            for function in session.functions:
                if function.name == name:
                    return await function.func(**parameters)

        raise ValueError(f'Tool not found: {name}')

    async def remove_mcp_server(self, server_name: str):
        if server_name not in self.sessions:
            raise ValueError(f'MCP server {server_name} not found')

        session = self.sessions.pop(server_name)
        await session.shutdown()

    async def shutdown(self):
        """关闭工具"""
        for session in self.sessions.values():
            await session.shutdown()
