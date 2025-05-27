from __future__ import annotations

import typing
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

from .. import loader, entities as tools_entities
from ....core import app, entities as core_entities


class RuntimeMCPSession:
    """运行时 MCP 会话"""

    ap: app.Application

    server_name: str

    server_config: dict

    session: ClientSession

    exit_stack: AsyncExitStack

    functions: list[tools_entities.LLMFunction] = []

    def __init__(self, server_name: str, server_config: dict, ap: app.Application):
        self.server_name = server_name
        self.server_config = server_config
        self.ap = ap

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

            async def func(query: core_entities.Query, *, _tool=tool, **kwargs):
                result = await self.session.call_tool(_tool.name, kwargs)
                if result.isError:
                    raise Exception(result.content[0].text)
                return result.content[0].text

            func.__name__ = tool.name

            self.functions.append(
                tools_entities.LLMFunction(
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

    _last_listed_functions: list[tools_entities.LLMFunction] = []

    def __init__(self, ap: app.Application):
        super().__init__(ap)
        self.sessions = {}
        self._last_listed_functions = []

    async def initialize(self):
        for server_config in self.ap.instance_config.data.get('mcp', {}).get('servers', []):
            if not server_config['enable']:
                continue
            session = RuntimeMCPSession(server_config['name'], server_config, self.ap)
            await session.initialize()
            # self.ap.event_loop.create_task(session.initialize())
            self.sessions[server_config['name']] = session

    async def get_tools(self, enabled: bool = True) -> list[tools_entities.LLMFunction]:
        all_functions = []

        for session in self.sessions.values():
            all_functions.extend(session.functions)

        self._last_listed_functions = all_functions

        return all_functions

    async def has_tool(self, name: str) -> bool:
        return name in [f.name for f in self._last_listed_functions]

    async def invoke_tool(self, query: core_entities.Query, name: str, parameters: dict) -> typing.Any:
        for server_name, session in self.sessions.items():
            for function in session.functions:
                if function.name == name:
                    return await function.func(query, **parameters)

        raise ValueError(f'未找到工具: {name}')

    async def shutdown(self):
        """关闭工具"""
        for session in self.sessions.values():
            await session.shutdown()
