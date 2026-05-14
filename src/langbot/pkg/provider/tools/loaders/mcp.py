from __future__ import annotations

import base64
import enum
import json
import typing
from contextlib import AsyncExitStack
import traceback
from langbot_plugin.api.entities.events import pipeline_query
import sqlalchemy
import asyncio
import httpx

import uuid as uuid_module
from mcp import ClientSession, StdioServerParameters, types as mcp_types
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client
from pydantic import AnyUrl

from .. import loader
from ....core import app
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
import langbot_plugin.api.entities.builtin.provider.message as provider_message
from ....entity.persistence import mcp as persistence_mcp

# Synthesized LLM tools for MCP resources (not from server tools/list).
# Dispatched in MCPLoader.invoke_tool; placeholder func on LLMTool is never used.
# Prefixed with langbot_ to avoid clashing with MCP server tool names.
MCP_TOOL_LIST_RESOURCES = 'langbot_mcp_list_resources'
MCP_TOOL_READ_RESOURCE = 'langbot_mcp_read_resource'

MCP_LIST_RESOURCES_SCHEMA: dict[str, typing.Any] = {
    'type': 'object',
    'properties': {
        'server_name': {
            'type': 'string',
            'description': 'MCP server name as configured in LangBot (see admin / pipeline bindings).',
        }
    },
    'required': ['server_name'],
}

MCP_READ_RESOURCE_SCHEMA: dict[str, typing.Any] = {
    'type': 'object',
    'properties': {
        'server_name': {
            'type': 'string',
            'description': 'MCP server name as configured in LangBot.',
        },
        'uri': {
            'type': 'string',
            'description': 'Resource URI from langbot_mcp_list_resources output, or from MCP documentation.',
        },
    },
    'required': ['server_name', 'uri'],
}


async def _mcp_resource_tool_placeholder(**kwargs: typing.Any) -> list[provider_message.ContentElement]:
    """LLMTool requires a func; real execution goes through MCPLoader.invoke_tool."""
    raise RuntimeError('MCP resource tool execution must be routed through MCPLoader.invoke_tool')


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

    resources: list[dict] = []

    enable: bool

    # connected: bool
    status: MCPSessionStatus

    _lifecycle_task: asyncio.Task | None

    _shutdown_event: asyncio.Event

    _ready_event: asyncio.Event

    error_message: str | None = None

    def __init__(self, server_name: str, server_config: dict, enable: bool, ap: app.Application):
        self.server_name = server_name
        self.server_uuid = server_config.get('uuid', '')
        self.server_config = server_config
        self.ap = ap
        self.enable = enable
        self.session = None

        self.exit_stack = AsyncExitStack()
        self.functions = []
        self.resources = []

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

    async def _lifecycle_loop(self):
        """在后台任务中管理整个MCP会话的生命周期"""
        try:
            if self.server_config['mode'] == 'stdio':
                await self._init_stdio_python_server()
            elif self.server_config['mode'] == 'sse':
                await self._init_sse_server()
            elif self.server_config['mode'] == 'http':
                await self._init_streamable_http_server()
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
            self.error_message = str(e)
            self.ap.logger.error(f'Error in MCP session lifecycle {self.server_name}: {e}\n{traceback.format_exc()}')
            # 即使出错也要设置ready事件，让start()方法知道初始化已完成
            self._ready_event.set()
        finally:
            # 在同一个任务中清理所有资源
            try:
                if self.exit_stack:
                    await self.exit_stack.aclose()
                self.functions.clear()
                self.resources.clear()
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
        if not self.session:
            return

        self.functions.clear()
        self.resources.clear()

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
                        if isinstance(content.resource, mcp_types.TextResourceContents):
                            result_contents.append(provider_message.ContentElement.from_text(content.resource.text))
                        elif isinstance(content.resource, mcp_types.BlobResourceContents):
                            decoded = base64.b64decode(content.resource.blob)
                            result_contents.append(provider_message.ContentElement.from_text(decoded.decode('utf-8', errors='replace')))

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

        try:
            resources_result = await self.session.list_resources()
            for resource in resources_result.resources:
                self.resources.append({
                    'uri': str(resource.uri),
                    'name': resource.name,
                    'description': resource.description or '',
                    'mime_type': resource.mimeType or '',
                })
            self.ap.logger.debug(f'Refresh MCP resources: {len(self.resources)} resources found')
        except Exception as e:
            self.ap.logger.debug(f'MCP server {self.server_name} does not support resources or failed to list: {e}')

    def get_tools(self) -> list[resource_tool.LLMTool]:
        return self.functions

    def get_resources(self) -> list[dict]:
        return self.resources

    async def read_resource(self, uri: str) -> list[dict]:
        """Read a resource by URI and return its contents."""
        if not self.session:
            raise Exception('MCP session is not connected')

        result = await self.session.read_resource(AnyUrl(uri))
        contents = []
        for content in result.contents:
            if isinstance(content, mcp_types.TextResourceContents):
                contents.append({
                    'uri': str(content.uri),
                    'mime_type': content.mimeType or '',
                    'type': 'text',
                    'text': content.text,
                })
            elif isinstance(content, mcp_types.BlobResourceContents):
                contents.append({
                    'uri': str(content.uri),
                    'mime_type': content.mimeType or '',
                    'type': 'blob',
                    'blob': content.blob,
                })
        return contents

    def get_runtime_info_dict(self) -> dict:
        return {
            'status': self.status.value,
            'error_message': self.error_message,
            'tool_count': len(self.get_tools()),
            'tools': [
                {
                    'name': tool.name,
                    'description': tool.description,
                }
                for tool in self.get_tools()
            ],
            'resource_count': len(self.get_resources()),
            'resources': self.get_resources(),
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

    @staticmethod
    def _get_bound_mcp_from_query(query: pipeline_query.Query) -> list[str] | None:
        v = getattr(query, 'variables', None) or {}
        return v.get('_pipeline_bound_mcp_servers', None)

    def _eligible_sessions_for_bound(self, bound_mcp_servers: list[str] | None) -> list[RuntimeMCPSession]:
        out: list[RuntimeMCPSession] = []
        for session in self.sessions.values():
            if not session.enable:
                continue
            if session.status != MCPSessionStatus.CONNECTED:
                continue
            if session.session is None:
                continue
            if bound_mcp_servers is not None and session.server_uuid not in bound_mcp_servers:
                continue
            out.append(session)
        return out

    @staticmethod
    def _mcp_synthetic_resource_tools() -> list[resource_tool.LLMTool]:
        return [
            resource_tool.LLMTool(
                name=MCP_TOOL_LIST_RESOURCES,
                human_desc='List MCP resource URIs for a server (MCP resources/list).',
                description=(
                    'Lists static resources (URI, name, description, mime type) exposed by the MCP server. '
                    'Call langbot_mcp_read_resource with a URI to fetch content. '
                    'Use the server name from LangBot pipeline MCP bindings or admin configuration.'
                ),
                parameters=MCP_LIST_RESOURCES_SCHEMA,
                func=_mcp_resource_tool_placeholder,
            ),
            resource_tool.LLMTool(
                name=MCP_TOOL_READ_RESOURCE,
                human_desc='Read a single MCP resource by URI (MCP resources/read).',
                description=(
                    'Fetches the body of a resource. Discover URIs via langbot_mcp_list_resources or MCP docs. '
                    'The businessId, env, and other parameters in downstream tools must match the selected environment.'
                ),
                parameters=MCP_READ_RESOURCE_SCHEMA,
                func=_mcp_resource_tool_placeholder,
            ),
        ]

    async def _invoke_mcp_list_resources(self, parameters: dict, query: pipeline_query.Query) -> typing.Any:
        server_name = parameters.get('server_name') if parameters else None
        if not server_name or not isinstance(server_name, str):
            return [provider_message.ContentElement.from_text('Error: "server_name" (string) is required.')]

        bound = self._get_bound_mcp_from_query(query)
        allowed = {s.server_name for s in self._eligible_sessions_for_bound(bound)}
        if server_name not in allowed:
            return [
                provider_message.ContentElement.from_text(
                    f'Error: MCP server {server_name!r} is not available for this query. '
                    f'Allowed server names: {sorted(allowed)}. '
                    'Check pipeline MCP server bindings and that the server is connected.'
                )
            ]

        session = self.get_session(server_name)
        if session is None or session.status != MCPSessionStatus.CONNECTED:
            return [provider_message.ContentElement.from_text(f'Error: MCP server not connected: {server_name!r}')]

        data = session.get_resources()
        body = {
            'server_name': server_name,
            'resource_count': len(data),
            'resources': data,
        }
        return [provider_message.ContentElement.from_text(json.dumps(body, ensure_ascii=False, indent=2))]

    async def _invoke_mcp_read_resource(self, parameters: dict, query: pipeline_query.Query) -> typing.Any:
        server_name = parameters.get('server_name') if parameters else None
        uri = parameters.get('uri') if parameters else None
        if not server_name or not isinstance(server_name, str):
            return [provider_message.ContentElement.from_text('Error: "server_name" (string) is required.')]
        if not uri or not isinstance(uri, str):
            return [provider_message.ContentElement.from_text('Error: "uri" (string) is required.')]

        bound = self._get_bound_mcp_from_query(query)
        allowed = {s.server_name for s in self._eligible_sessions_for_bound(bound)}
        if server_name not in allowed:
            return [
                provider_message.ContentElement.from_text(
                    f'Error: MCP server {server_name!r} is not available for this query. '
                    f'Allowed server names: {sorted(allowed)}.'
                )
            ]

        session = self.get_session(server_name)
        if session is None or session.status != MCPSessionStatus.CONNECTED:
            return [provider_message.ContentElement.from_text(f'Error: MCP server not connected: {server_name!r}')]

        try:
            parts = await session.read_resource(uri)
        except Exception as e:
            self.ap.logger.error(f'read_resource {uri!r} on {server_name}: {e}\n{traceback.format_exc()}')
            return [provider_message.ContentElement.from_text(f'Error reading resource: {e!s}')]

        out_chunks: list[str] = []
        for item in parts:
            if not isinstance(item, dict):
                continue
            t = item.get('type', '')
            if t == 'text' and 'text' in item:
                out_chunks.append(typing.cast(str, item['text']))
            elif t == 'blob' and 'blob' in item:
                try:
                    raw = base64.b64decode(typing.cast(str, item['blob']))
                    out_chunks.append(raw.decode('utf-8', errors='replace'))
                except Exception as be:
                    out_chunks.append(f'[Binary decode error: {be}]')
        if not out_chunks:
            return [
                provider_message.ContentElement.from_text(
                    json.dumps({'uri': uri, 'contents': parts}, ensure_ascii=False, indent=2)
                )
            ]
        return [provider_message.ContentElement.from_text('\n\n'.join(out_chunks))]

    async def get_tools(self, bound_mcp_servers: list[str] | None = None) -> list[resource_tool.LLMTool]:
        all_functions: list[resource_tool.LLMTool] = []

        for session in self.sessions.values():
            # If bound_mcp_servers is specified, only include tools from those servers
            if bound_mcp_servers is not None:
                if session.server_uuid in bound_mcp_servers:
                    all_functions.extend(session.get_tools())
            else:
                # If no bound servers specified, include all tools
                all_functions.extend(session.get_tools())

        if self._eligible_sessions_for_bound(bound_mcp_servers):
            all_functions.extend(self._mcp_synthetic_resource_tools())

        self._last_listed_functions = all_functions

        return all_functions

    async def has_tool(self, name: str) -> bool:
        """检查工具是否存在"""
        if name in (MCP_TOOL_LIST_RESOURCES, MCP_TOOL_READ_RESOURCE):
            return bool(self._eligible_sessions_for_bound(None))
        for session in self.sessions.values():
            for function in session.get_tools():
                if function.name == name:
                    return True
        return False

    async def invoke_tool(self, name: str, parameters: dict, query: pipeline_query.Query) -> typing.Any:
        """执行工具调用"""
        if name == MCP_TOOL_LIST_RESOURCES:
            return await self._invoke_mcp_list_resources(parameters, query)
        if name == MCP_TOOL_READ_RESOURCE:
            return await self._invoke_mcp_read_resource(parameters, query)

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

    async def get_resources(self, server_name: str) -> list[dict]:
        """Get resources from a specific MCP server."""
        session = self.get_session(server_name)
        if session is None:
            raise ValueError(f'MCP server not found: {server_name}')
        return session.get_resources()

    async def read_resource(self, server_name: str, uri: str) -> list[dict]:
        """Read a resource from a specific MCP server."""
        session = self.get_session(server_name)
        if session is None:
            raise ValueError(f'MCP server not found: {server_name}')
        return await session.read_resource(uri)

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
