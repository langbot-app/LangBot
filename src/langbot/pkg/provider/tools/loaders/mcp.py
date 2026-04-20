from __future__ import annotations

import enum
import typing
from contextlib import AsyncExitStack
import traceback
from langbot_plugin.api.entities.events import pipeline_query
import sqlalchemy
import asyncio
import httpx

import uuid as uuid_module
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client

from .. import loader
from ....core import app
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
import langbot_plugin.api.entities.builtin.provider.message as provider_message
from ....entity.persistence import mcp as persistence_mcp
from .mcp_stdio import BoxStdioSessionRuntime, MCPSessionErrorPhase


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

    session: ClientSession | None

    exit_stack: AsyncExitStack

    functions: list[resource_tool.LLMTool] = []

    enable: bool

    # connected: bool
    status: MCPSessionStatus

    _lifecycle_task: asyncio.Task | None

    _shutdown_event: asyncio.Event

    _ready_event: asyncio.Event

    error_message: str | None = None

    error_phase: MCPSessionErrorPhase | None = None

    retry_count: int = 0

    _box_stdio_runtime: BoxStdioSessionRuntime

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

        self._box_stdio_runtime = BoxStdioSessionRuntime(self)
        self.box_config = self._box_stdio_runtime.config

    async def _init_stdio_python_server(self):
        if self._uses_box_stdio():
            await self._box_stdio_runtime.initialize()
            return

        server_params = StdioServerParameters(
            command=self.server_config['command'],
            args=self.server_config['args'],
            env=self.server_config['env'],
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))

        stdio, write = stdio_transport

        self.session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))

        await self.session.initialize()

    async def _init_box_stdio_server(self):
        await self._box_stdio_runtime.initialize()

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

    async def _init_streamable_http_server(self):
        transport = await self.exit_stack.enter_async_context(
            streamable_http_client(
                self.server_config['url'],
                http_client=httpx.AsyncClient(
                    headers=self.server_config.get('headers', {}),
                    timeout=self.server_config.get('timeout', 10),
                    follow_redirects=True,
                ),
            )
        )

        read, write, _ = transport

        self.session = await self.exit_stack.enter_async_context(ClientSession(read, write))

        await self.session.initialize()

    _MAX_RETRIES = 3
    _RETRY_DELAYS = [2, 4, 8]

    async def _lifecycle_loop(self):
        """Manage the full MCP session lifecycle in a background task."""
        try:
            if self.server_config['mode'] == 'stdio':
                await self._init_stdio_python_server()
            elif self.server_config['mode'] == 'sse':
                await self._init_sse_server()
            elif self.server_config['mode'] == 'http':
                await self._init_streamable_http_server()
            else:
                raise ValueError(f'Unknown MCP server mode: {self.server_name}: {self.server_config}')

            await self.refresh()

            self.status = MCPSessionStatus.CONNECTED

            # Notify start() that connection is established
            self._ready_event.set()

            # Wait for shutdown signal, with optional health monitoring for Box stdio
            if self._uses_box_stdio():
                monitor_task = asyncio.create_task(self._box_stdio_runtime.monitor_process_health())
                shutdown_task = asyncio.create_task(self._shutdown_event.wait())
                done, pending = await asyncio.wait(
                    [shutdown_task, monitor_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                for task in done:
                    if task is monitor_task and not self._shutdown_event.is_set():
                        self.error_phase = MCPSessionErrorPhase.RUNTIME
                        raise Exception('Box managed process exited unexpectedly')
            else:
                await self._shutdown_event.wait()

        except Exception as e:
            self.status = MCPSessionStatus.ERROR
            self.error_message = str(e)
            self.ap.logger.error(f'Error in MCP session lifecycle {self.server_name}: {e}\n{traceback.format_exc()}')
            # Do NOT set _ready_event here — let _lifecycle_loop_with_retry
            # handle retries first. It will set the event when all retries
            # are exhausted or on success.
            raise  # Re-raise so _lifecycle_loop_with_retry can catch it
        finally:
            # Clean up all resources in the same task
            try:
                if self.exit_stack:
                    await self.exit_stack.aclose()
                    self.exit_stack = AsyncExitStack()
                self.functions.clear()
                self.session = None
            except Exception as e:
                self.ap.logger.error(f'Error cleaning up MCP session {self.server_name}: {e}\n{traceback.format_exc()}')
            finally:
                await self._cleanup_box_stdio_session()

    async def _lifecycle_loop_with_retry(self):
        """Wrap _lifecycle_loop with retry and exponential backoff."""
        for attempt in range(self._MAX_RETRIES + 1):
            try:
                await self._lifecycle_loop()
                return  # Normal shutdown, don't retry
            except Exception as e:
                self.retry_count = attempt + 1
                if self._shutdown_event.is_set():
                    return  # Shutdown requested, don't retry
                if attempt >= self._MAX_RETRIES:
                    self.status = MCPSessionStatus.ERROR
                    self.error_message = f'Failed after {self._MAX_RETRIES + 1} attempts: {e}'
                    self._ready_event.set()
                    return
                delay = self._RETRY_DELAYS[attempt]
                self.ap.logger.warning(
                    f'MCP session {self.server_name} failed (attempt {attempt + 1}), retrying in {delay}s: {e}'
                )
                await self._cleanup_box_stdio_session()
                # Reset status for retry
                self.status = MCPSessionStatus.CONNECTING
                self.error_message = None
                self.error_phase = None
                await asyncio.sleep(delay)

    _MONITOR_POLL_INTERVAL = 5
    _MONITOR_MAX_CONSECUTIVE_ERRORS = 3

    async def _monitor_box_process_health(self):
        await self._box_stdio_runtime.monitor_process_health()

    async def start(self):
        if not self.enable:
            return

        # Create background task for lifecycle management with retry
        self._lifecycle_task = asyncio.create_task(self._lifecycle_loop_with_retry())

        # Wait for connection or failure (with timeout)
        startup_timeout = self.box_config.startup_timeout_sec if self._uses_box_stdio() else 30.0
        try:
            await asyncio.wait_for(self._ready_event.wait(), timeout=startup_timeout)
        except asyncio.TimeoutError:
            self.status = MCPSessionStatus.ERROR
            raise Exception(f'Connection timeout after {startup_timeout} seconds')

        # Check for errors
        if self.status == MCPSessionStatus.ERROR:
            raise Exception('Connection failed, please check URL')

    async def refresh(self):
        if not self.session:
            return

        self.functions.clear()

        tools = await self.session.list_tools()

        self.ap.logger.debug(f'Refresh MCP tools: {tools}')

        for tool in tools.tools:

            async def func(*, _tool=tool, **kwargs):
                if not self.session:
                    raise Exception('MCP session is not connected')

                result = await self.session.call_tool(_tool.name, kwargs)
                if result.isError:
                    error_texts = []
                    for content in result.content:
                        if content.type == 'text':
                            error_texts.append(content.text)
                    raise Exception('\n'.join(error_texts) if error_texts else 'Unknown error from MCP tool')

                result_contents: list[provider_message.ContentElement] = []
                for content in result.content:
                    if content.type == 'text':
                        result_contents.append(provider_message.ContentElement.from_text(content.text))
                    elif content.type == 'image':
                        result_contents.append(provider_message.ContentElement.from_image_base64(content.image_base64))
                    elif content.type == 'resource':
                        # TODO: Handle resource content
                        pass

                return result_contents

            func.__name__ = tool.name

            self.functions.append(
                resource_tool.LLMTool(
                    name=tool.name,
                    human_desc=tool.description or '',
                    description=tool.description or '',
                    parameters=tool.inputSchema,
                    func=func,
                )
            )

    def get_tools(self) -> list[resource_tool.LLMTool]:
        return self.functions

    def get_runtime_info_dict(self) -> dict:
        info = {
            'status': self.status.value,
            'error_message': self.error_message,
            'error_phase': self.error_phase.value if self.error_phase else None,
            'retry_count': self.retry_count,
            'tool_count': len(self.get_tools()),
            'tools': [
                {
                    'name': tool.name,
                    'description': tool.description,
                }
                for tool in self.get_tools()
            ],
        }
        if self._uses_box_stdio():
            info['box_session_id'] = self._build_box_session_id()
            info['box_process_id'] = self._box_stdio_runtime.process_id
            info['box_enabled'] = True
        return info

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

    def _uses_box_stdio(self) -> bool:
        return self._box_stdio_runtime.uses_box_stdio()

    def _build_box_session_id(self) -> str:
        return 'mcp-shared'

    def _rewrite_path(self, path: str, host_path: str | None) -> str:
        return self._box_stdio_runtime.rewrite_path(path, host_path)

    def _infer_host_path(self) -> str | None:
        return self._box_stdio_runtime.infer_host_path()

    @staticmethod
    def _unwrap_venv_path(directory: str) -> str:
        return BoxStdioSessionRuntime.unwrap_venv_path(directory)

    def _resolve_host_path(self) -> str | None:
        return self._box_stdio_runtime.resolve_host_path()

    @staticmethod
    def _detect_install_command(host_path: str) -> str | None:
        return BoxStdioSessionRuntime.detect_install_command(host_path)

    def _build_box_session_payload(self, session_id: str, host_path: str | None = None) -> dict:
        return self._box_stdio_runtime.build_box_session_payload(session_id, host_path)

    def _build_box_process_payload(self, host_path: str | None = None) -> dict:
        return self._box_stdio_runtime.build_box_process_payload(host_path)

    def _rewrite_venv_command(self, command: str, host_path: str) -> str:
        return self._box_stdio_runtime.rewrite_venv_command(command, host_path)

    async def _cleanup_box_stdio_session(self) -> None:
        await self._box_stdio_runtime.cleanup_session()


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
                - mode: 连接模式 (stdio/sse/http)
                - enable: 是否启用
                - extra_args: 额外的配置参数 (可选)
        """
        uuid_ = server_config.get('uuid')
        if not uuid_:
            self.ap.logger.warning('Server UUID is None for MCP server, maybe testing in the config page.')
            uuid_ = str(uuid_module.uuid4())
            server_config['uuid'] = uuid_

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

    async def invoke_tool(self, name: str, parameters: dict, query: pipeline_query.Query) -> typing.Any:
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
            tools = session.get_tools()
            info[server_name] = {
                'name': server_name,
                'mode': session.server_config.get('mode'),
                'enable': session.enable,
                'tools_count': len(tools),
                'tool_names': [f.name for f in tools],
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
