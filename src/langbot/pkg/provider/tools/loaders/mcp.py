from __future__ import annotations

import base64
import enum
import json
import re
import time
import typing
from contextlib import AsyncExitStack, asynccontextmanager
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
from mcp.shared.exceptions import McpError
from pydantic import AnyUrl

from .. import loader
from ..errors import ToolExecutionDeniedError
from ....core import app
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
import langbot_plugin.api.entities.builtin.provider.message as provider_message
from ....entity.persistence import mcp as persistence_mcp
from .mcp_stdio import BoxStdioSessionRuntime, MCPServerBoxConfig, MCPSessionErrorPhase, _ColdStartRetry  # noqa: F401

# Synthesized LLM tools for MCP resources (not from server tools/list).
# Dispatched in MCPLoader.invoke_tool; placeholder func on LLMTool is never used.
# Prefixed with langbot_ to avoid clashing with MCP server tool names.
MCP_TOOL_LIST_RESOURCES = 'langbot_mcp_list_resources'
MCP_TOOL_READ_RESOURCE = 'langbot_mcp_read_resource'

MCP_RESOURCE_DISCOVERY_MAX_PAGES = 20
MCP_RESOURCE_CACHE_TTL_SECONDS = 30
MCP_RESOURCE_PREVIEW_MAX_BYTES = 64 * 1024
MCP_RESOURCE_AGENT_READ_MAX_BYTES = 64 * 1024
MCP_RESOURCE_AGENT_READ_MAX_TOKENS = 12000
MCP_RESOURCE_CONTEXT_MAX_TOKENS = 8000
MCP_RESOURCE_CONTEXT_MAX_BYTES = 96 * 1024
MCP_RESOURCE_TRACE_QUERY_KEY = '_mcp_resource_reads'
MCP_RESOURCE_LINKS_QUERY_KEY = '_mcp_resource_links'
MCP_RESOURCE_CONTEXT_QUERY_KEY = '_mcp_resource_context'
MCP_TRANSPORT_CLEANUP_TIMEOUT_SECONDS = 5.0

TEXT_LIKE_MIME_TYPES = {
    'application/json',
    'application/ld+json',
    'application/xml',
    'application/yaml',
    'application/x-yaml',
    'application/toml',
    'application/javascript',
    'application/typescript',
    'application/sql',
    'application/graphql',
}

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
            'description': 'Resource URI from langbot_mcp_list_resources output or a listed resource template.',
        },
    },
    'required': ['server_name', 'uri'],
}


def _mcp_model_dump(obj: typing.Any) -> typing.Any:
    if obj is None:
        return None
    if hasattr(obj, 'model_dump'):
        return obj.model_dump(mode='json', by_alias=True, exclude_none=True)
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [_mcp_model_dump(item) for item in obj]
    if isinstance(obj, dict):
        return {str(k): _mcp_model_dump(v) for k, v in obj.items()}
    return str(obj)


def _truncate_text(text: str, max_bytes: int, max_tokens: int | None = None) -> tuple[str, bool, int]:
    raw = text.encode('utf-8')
    original_bytes = len(raw)
    truncated = False

    if max_bytes > 0 and len(raw) > max_bytes:
        raw = raw[:max_bytes]
        text = raw.decode('utf-8', errors='ignore')
        truncated = True

    if max_tokens is not None and max_tokens > 0:
        max_chars = max_tokens * 4
        if len(text) > max_chars:
            text = text[:max_chars]
            truncated = True

    return text, truncated, original_bytes


def _blob_size(blob: str) -> int:
    try:
        return len(base64.b64decode(blob, validate=False))
    except Exception:
        return len(blob.encode('utf-8', errors='ignore'))


def _resource_to_dict(resource: mcp_types.Resource | mcp_types.ResourceLink) -> dict:
    return {
        'uri': str(resource.uri),
        'name': resource.name,
        'title': resource.title or '',
        'description': resource.description or '',
        'mime_type': resource.mimeType or '',
        'size': resource.size,
        'icons': _mcp_model_dump(resource.icons) or [],
        'annotations': _mcp_model_dump(resource.annotations) or {},
        '_meta': _mcp_model_dump(getattr(resource, 'meta', None)) or {},
    }


def _resource_template_to_dict(resource_template: mcp_types.ResourceTemplate) -> dict:
    return {
        'uri_template': resource_template.uriTemplate,
        'name': resource_template.name,
        'title': resource_template.title or '',
        'description': resource_template.description or '',
        'mime_type': resource_template.mimeType or '',
        'icons': _mcp_model_dump(resource_template.icons) or [],
        'annotations': _mcp_model_dump(resource_template.annotations) or {},
        '_meta': _mcp_model_dump(getattr(resource_template, 'meta', None)) or {},
    }


def _is_text_like_mime(mime_type: str) -> bool:
    if not mime_type:
        return False
    normalized = mime_type.split(';', 1)[0].strip().lower()
    return normalized.startswith('text/') or normalized in TEXT_LIKE_MIME_TYPES or normalized.endswith('+json')


def _uri_matches_template(uri: str, uri_template: str) -> bool:
    if uri_template == uri:
        return True
    if not uri_template or '{' not in uri_template:
        return False

    pattern_parts: list[str] = []
    pos = 0
    for match in re.finditer(r'\{[^{}]+\}', uri_template):
        pattern_parts.append(re.escape(uri_template[pos : match.start()]))
        pattern_parts.append(r'[^\s]+')
        pos = match.end()
    pattern_parts.append(re.escape(uri_template[pos:]))
    return re.fullmatch(''.join(pattern_parts), uri) is not None


async def _mcp_resource_tool_placeholder(**kwargs: typing.Any) -> list[provider_message.ContentElement]:
    """LLMTool requires a func; real execution goes through MCPLoader.invoke_tool."""
    raise RuntimeError('MCP resource tool execution must be routed through MCPLoader.invoke_tool')


class MCPSessionStatus(enum.Enum):
    CONNECTING = 'connecting'
    CONNECTED = 'connected'
    ERROR = 'error'


class _TransportReconnect(Exception):
    """Internal signal: the Box stdio WS transport dropped but the managed
    process is still alive. Triggers a lightweight transport reconnect that
    reuses the live process, instead of a full process rebuild.

    Reconnect attempts are NOT counted toward the fatal retry budget, so a
    long-lived session can survive arbitrarily many transient drops.
    """


class _CallerReconnect(Exception):
    """Internal signal: a tool/resource call hit a server-expired session
    (e.g. a UDP/HTTP MCP server's own session timeout) and asked the owning
    lifecycle loop to rebuild the connection.

    Like _TransportReconnect, this does NOT consume the fatal retry budget —
    the server-side timeout is expected, recurring behavior, not a failure.
    """


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

    resource_templates: list[dict] = []

    resource_capabilities: dict = {}

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

        # Transient test sessions (created from the config page "test" button,
        # which carry no persisted server UUID) must NOT share the live
        # "mcp-shared" Box session. Otherwise a failing test churns the shared
        # session and tears down healthy, already-connected servers. Callers
        # flag these via server_config['_transient'] = True.
        self.is_transient = bool(server_config.get('_transient', False))

        self.exit_stack = AsyncExitStack()
        self.functions = []
        self.resources = []
        self.resource_templates = []
        self.resource_capabilities = {}
        self._resource_cache: dict[tuple[str, int, int | None, bool], dict] = {}

        self.status = MCPSessionStatus.CONNECTING

        self._lifecycle_task = None
        self._shutdown_event = asyncio.Event()
        self._ready_event = asyncio.Event()
        # Signaled by callers (invoke_mcp_tool / read_resource_envelope) when
        # they see a server-expired session; the lifecycle loop reconnects and
        # sets _reconnected_event so all callers waiting on this cycle resume
        # together, instead of each racing to rebuild the session itself.
        self._reconnect_event = asyncio.Event()
        self._reconnected_event: asyncio.Event | None = None
        self._connection_generation = 0
        # Set transiently when a WS transport drop should NOT stop the managed
        # process (it will be re-attached on the next initialize()).
        self._preserve_managed_process = False

        # Log buffer for capturing stderr from Box managed process (maxlen=500 keeps
        # recent lines without unbounded memory growth)
        import collections as _collections

        self._log_buffer: _collections.deque = _collections.deque(maxlen=500)
        self._last_stderr_text: str = ''

        self._box_stdio_runtime = BoxStdioSessionRuntime(self)
        self.box_config = self._box_stdio_runtime.config

    async def _init_stdio_python_server(self):
        if self._uses_box_stdio():
            await self._box_stdio_runtime.initialize()
            return

        # Box is configured (ap.box_service exists) but currently unavailable
        # (disabled by config or connection failed). Refuse stdio MCP rather
        # than silently falling through to host-stdio — the operator asked
        # for the sandbox and the failure mode should be visible.
        #
        # Set ``error_phase = BOX_UNAVAILABLE`` BEFORE raising so the retry
        # wrapper can short-circuit (retrying is pointless when Box is
        # deliberately off) and the frontend can render a localized,
        # actionable message instead of this raw RuntimeError. Keep the
        # message itself short — the frontend ignores it for this phase.
        box_service = getattr(self.ap, 'box_service', None)
        if box_service is not None and not getattr(box_service, 'available', False):
            self.error_phase = MCPSessionErrorPhase.BOX_UNAVAILABLE
            if not getattr(box_service, 'enabled', True):
                raise RuntimeError('box_disabled_in_config')
            raise RuntimeError('box_unavailable')

        # Legacy: no box_service installed at all (pre-Box dev mode). Fall
        # through to host-stdio for backward compatibility.
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

    @asynccontextmanager
    async def _streamable_http_session(self) -> typing.AsyncIterator[ClientSession]:
        """Enter a fully initialized Streamable HTTP session as one context.

        Initialization must happen inside the same context manager that owns the
        MCP transport. The SDK reports request failures by cancelling the host
        task and raises the real HTTP error from its TaskGroup during context
        exit. Keeping these nested contexts together guarantees a failed
        ``__aenter__`` unwinds immediately, so callers see the HTTPStatusError
        instead of a detached CancelledError. It also owns the injected HTTPX
        client, which the MCP SDK deliberately does not close for callers.
        """
        async with httpx.AsyncClient(
            headers=self.server_config.get('headers', {}),
            timeout=self.server_config.get('timeout', 10),
            follow_redirects=True,
        ) as http_client:
            async with streamable_http_client(
                self.server_config['url'],
                http_client=http_client,
            ) as transport:
                read, write, _ = transport
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session

    async def _init_streamable_http_server(self):
        self.session = await self.exit_stack.enter_async_context(self._streamable_http_session())

    async def _init_remote_server(self):
        """Connect to a remote MCP server, auto-detecting the transport.

        The user only supplies a URL ("remote" mode); they should not have to
        know whether the server speaks the modern Streamable HTTP transport or
        the legacy HTTP+SSE transport. Following the MCP backwards-compatibility
        guidance, we try Streamable HTTP first and fall back to SSE when it
        fails (e.g. the endpoint returns 4xx to the initialize POST).
        """
        try:
            await self._init_streamable_http_server()
            return
        except Exception as e:
            if not self._should_fallback_to_sse(e):
                self.ap.logger.info(
                    f'MCP server {self.server_name}: Streamable HTTP transport failed '
                    f'({self._describe_exception(e)}); not falling back to SSE'
                )
                raise
            self.ap.logger.info(
                f'MCP server {self.server_name}: Streamable HTTP initialize failed with a compatible HTTP status '
                f'({self._describe_exception(e)}), falling back to legacy SSE'
            )

        # The Streamable HTTP attempt may have partially entered the transport /
        # session into the exit stack before failing. Tear it down and start
        # from a clean stack before trying SSE so we do not leak connections.
        try:
            await self.exit_stack.aclose()
        except Exception as cleanup_err:
            self.ap.logger.debug(f'MCP server {self.server_name}: error cleaning up before SSE fallback: {cleanup_err}')
        self.exit_stack = AsyncExitStack()
        self.session = None

        await self._init_sse_server()

    _MAX_RETRIES = 3
    _RETRY_DELAYS = [2, 4, 8]

    async def _lifecycle_loop(self):
        """Manage the full MCP session lifecycle in a background task."""
        wait_tasks: list[asyncio.Task] = []
        try:
            if self.server_config['mode'] == 'stdio':
                await self._init_stdio_python_server()
            elif self.server_config['mode'] == 'remote':
                await self._init_remote_server()
            elif self.server_config['mode'] == 'sse':
                await self._init_sse_server()
            elif self.server_config['mode'] == 'http':
                await self._init_streamable_http_server()
            else:
                raise ValueError(f'Unknown MCP server mode: {self.server_name}: {self.server_config}')

            await self.refresh()

            self.status = MCPSessionStatus.CONNECTED
            self._connection_generation += 1

            # Notify start() that connection is established
            self._ready_event.set()

            # Wait for shutdown signal, with optional health monitoring for Box stdio
            if self._uses_box_stdio():
                monitor_task = asyncio.create_task(self._box_stdio_runtime.monitor_process_health())
                shutdown_task = asyncio.create_task(self._shutdown_event.wait())
                reconnect_task = asyncio.create_task(self._reconnect_event.wait())
                wait_tasks = [shutdown_task, monitor_task, reconnect_task]
                done, pending = await asyncio.wait(
                    wait_tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                if reconnect_task in done and not self._shutdown_event.is_set():
                    self._reconnect_event.clear()
                    self.ap.logger.info(
                        f'MCP session {self.server_name}: caller requested reconnect (server session expired)'
                    )
                    raise _CallerReconnect('Caller requested reconnect after session expiry')
                for task in done:
                    if task is monitor_task and not self._shutdown_event.is_set():
                        # The monitor completed. This is EITHER the managed
                        # process actually exiting OR just the WS transport
                        # dropping while the process stays alive in the Box
                        # runtime. Re-check the real process state so a
                        # transient transport drop reconnects (reusing the live
                        # process) instead of tearing the process down and
                        # running a full rebuild+backoff cycle.
                        process_still_running = False
                        try:
                            process_still_running = await self._box_stdio_runtime._managed_process_is_running()
                        except Exception:
                            process_still_running = False
                        if process_still_running:
                            self.ap.logger.info(
                                f'MCP server {self.server_name}: transport dropped but '
                                f'managed process is still running; reconnecting transport'
                            )
                            self.error_phase = MCPSessionErrorPhase.RELAY_CONNECT
                            # Preserve the live process across the finally-block
                            # cleanup: only the WS transport should be torn down.
                            self._preserve_managed_process = True
                            raise _TransportReconnect('Box managed process transport dropped; reconnecting')
                        self.error_phase = MCPSessionErrorPhase.RUNTIME
                        raise Exception('Box managed process exited unexpectedly')
            else:
                shutdown_task = asyncio.create_task(self._shutdown_event.wait())
                reconnect_task = asyncio.create_task(self._reconnect_event.wait())
                done, pending = await asyncio.wait(
                    [shutdown_task, reconnect_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                if reconnect_task in done and not self._shutdown_event.is_set():
                    self._reconnect_event.clear()
                    self.ap.logger.info(
                        f'MCP session {self.server_name}: caller requested reconnect (server session expired)'
                    )
                    raise _CallerReconnect('Caller requested reconnect after session expiry')

        except _ColdStartRetry:
            # Cold-start in progress: set the preserve flag BEFORE the finally
            # block runs so it does not stop the live managed process. The outer
            # _lifecycle_loop_with_retry will reuse it on the next attempt.
            self._preserve_managed_process = True
            raise
        except Exception as e:
            self.status = MCPSessionStatus.ERROR
            self.error_message = str(e)
            self.ap.logger.error(f'Error in MCP session lifecycle {self.server_name}: {e}\n{traceback.format_exc()}')
            # Do NOT set _ready_event here — let _lifecycle_loop_with_retry
            # handle retries first. It will set the event when all retries
            # are exhausted or on success.
            raise  # Re-raise so _lifecycle_loop_with_retry can catch it
        finally:
            for task in wait_tasks:
                if not task.done():
                    task.cancel()
            # AsyncExitStack contains AnyIO cancel scopes that must exit in
            # the same task where their contexts were entered.
            await self._cleanup_lifecycle_attempt()

    async def _lifecycle_loop_with_retry(self):
        """Wrap _lifecycle_loop with retry and exponential backoff."""
        attempt = 0
        while attempt <= self._MAX_RETRIES:
            connection_generation_before = self._connection_generation
            try:
                lifecycle_task = asyncio.create_task(self._lifecycle_loop())
                try:
                    await lifecycle_task
                except asyncio.CancelledError as exc:
                    if self._shutdown_event.is_set():
                        return
                    if not self._uses_box_stdio():
                        raise
                    error = self._prepare_box_transport_retry('Box MCP transport task was cancelled unexpectedly')
                    raise error from exc
                if self._uses_box_stdio() and not self._shutdown_event.is_set():
                    raise self._prepare_box_transport_retry('Box MCP lifecycle ended unexpectedly')
                return  # Normal shutdown, don't retry
            except _TransportReconnect as e:
                # Transient WS transport drop while the managed process is still
                # alive. Reconnect promptly WITHOUT consuming the fatal retry
                # budget and WITHOUT stopping the process — initialize() will
                # re-attach to the live process. This is what lets a long-lived
                # stdio MCP survive repeated brief event-loop stalls / pings.
                if self._shutdown_event.is_set():
                    return
                self.ap.logger.info(
                    f'MCP session {self.server_name}: reconnecting transport ({self._describe_exception(e)})'
                )
                self.status = MCPSessionStatus.CONNECTING
                self.error_message = None
                self.error_phase = None
                await asyncio.sleep(1)
                continue
            except _CallerReconnect:
                # A tool/resource call hit a server-expired session and asked us
                # to rebuild the connection. Same treatment as _TransportReconnect:
                # reconnect immediately WITHOUT consuming the fatal retry budget.
                # Wake any callers waiting in _trigger_reconnect() regardless of
                # outcome so they don't block for the full timeout.
                reconnected_event = self._reconnected_event
                if self._shutdown_event.is_set():
                    if reconnected_event is not None:
                        reconnected_event.set()
                    return
                self.status = MCPSessionStatus.CONNECTING
                self.error_message = None
                self.error_phase = None
                try:
                    if self.server_config['mode'] == 'stdio':
                        await self._init_stdio_python_server()
                    elif self.server_config['mode'] == 'remote':
                        await self._init_remote_server()
                    elif self.server_config['mode'] == 'sse':
                        await self._init_sse_server()
                    elif self.server_config['mode'] == 'http':
                        await self._init_streamable_http_server()
                    await self.refresh()
                    self.status = MCPSessionStatus.CONNECTED
                    self.ap.logger.info(f'MCP session {self.server_name} reconnected successfully after session expiry')
                except Exception as reconnect_err:
                    self.status = MCPSessionStatus.ERROR
                    self.error_message = str(reconnect_err)
                    self.ap.logger.error(
                        f'MCP session {self.server_name}: reconnect after session expiry failed: '
                        f'{self._describe_exception(reconnect_err)}'
                    )
                finally:
                    if reconnected_event is not None:
                        reconnected_event.set()
                continue
            except _ColdStartRetry as e:
                # The managed process is alive but still cold-starting (e.g.
                # `npx -y <pkg>` is still installing) and cannot yet answer the
                # handshake. Reuse the live process and retry the attach WITHOUT
                # consuming the fatal retry budget or stopping the process, so a
                # slow cold start is waited out instead of failing. Preserve the
                # process across the finally-block cleanup.
                if self._shutdown_event.is_set():
                    return
                self._preserve_managed_process = True
                self.ap.logger.debug(
                    f'MCP session {self.server_name}: waiting for cold start ({self._describe_exception(e)})'
                )
                self.status = MCPSessionStatus.CONNECTING
                self.error_message = None
                self.error_phase = None
                await asyncio.sleep(2)
                continue
            except Exception as e:
                self.retry_count += 1
                if self._shutdown_event.is_set():
                    return  # Shutdown requested, don't retry
                # A lifecycle that reached CONNECTED proved its preceding
                # startup attempt was healthy. Give a later runtime failure a
                # fresh consecutive-startup retry budget instead of exhausting
                # the budget across the entire process lifetime.
                if self._connection_generation > connection_generation_before:
                    attempt = 0
                # BOX_UNAVAILABLE is a deliberate refusal, not a transient
                # failure — retrying produces log spam and a misleading
                # "Failed after N attempts" message. Surface it immediately.
                if self.error_phase == MCPSessionErrorPhase.BOX_UNAVAILABLE:
                    self.status = MCPSessionStatus.ERROR
                    self.error_message = str(e)
                    self._ready_event.set()
                    return
                if attempt >= self._MAX_RETRIES:
                    self.status = MCPSessionStatus.ERROR
                    self.error_message = f'Failed after {self._MAX_RETRIES + 1} attempts: {self._describe_exception(e)}'
                    self._ready_event.set()
                    return
                delay = self._RETRY_DELAYS[attempt]
                self.ap.logger.warning(
                    f'MCP session {self.server_name} failed (attempt {attempt + 1}), '
                    f'retrying in {delay}s: {self._describe_exception(e)}'
                )
                # Reset status for retry
                self.status = MCPSessionStatus.CONNECTING
                self.error_message = None
                self.error_phase = None
                await asyncio.sleep(delay)
                attempt += 1

    def _prepare_box_transport_retry(self, message: str) -> RuntimeError:
        error = RuntimeError(message)
        self.status = MCPSessionStatus.ERROR
        self.error_message = str(error)
        self.error_phase = MCPSessionErrorPhase.RELAY_CONNECT
        self.ap.logger.error(f'Error in MCP session lifecycle {self.server_name}: {error}')
        self.functions.clear()
        self.resources.clear()
        self.resource_templates.clear()
        self.resource_capabilities = {}
        self._resource_cache.clear()
        self.session = None
        return error

    async def _cleanup_lifecycle_attempt(self) -> None:
        stale_exit_stack = self.exit_stack
        self.exit_stack = AsyncExitStack()
        try:
            async with asyncio.timeout(MCP_TRANSPORT_CLEANUP_TIMEOUT_SECONDS):
                await stale_exit_stack.aclose()
        except TimeoutError:
            self.ap.logger.warning(
                f'Timed out cleaning up MCP transport for {self.server_name}; continuing lifecycle recovery'
            )
        except asyncio.CancelledError:
            self.ap.logger.warning(
                f'MCP transport cleanup was cancelled for {self.server_name}; continuing lifecycle recovery'
            )
        except Exception as e:
            self.ap.logger.warning(
                f'Error cleaning up MCP transport for {self.server_name}; '
                f'continuing lifecycle recovery: {self._describe_exception(e)}'
            )

        self.functions.clear()
        self.resources.clear()
        self.resource_templates.clear()
        self.resource_capabilities = {}
        self._resource_cache.clear()
        self.session = None
        if self._preserve_managed_process:
            self._preserve_managed_process = False
            return
        try:
            await asyncio.wait_for(
                self._cleanup_box_stdio_session(),
                timeout=MCP_TRANSPORT_CLEANUP_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            self.ap.logger.warning(
                f'Timed out cleaning up MCP managed process for {self.server_name}; continuing lifecycle recovery'
            )

    @staticmethod
    def _describe_exception(exc: BaseException) -> str:
        """Flatten an exception into its underlying leaf messages.

        anyio / the MCP client wrap real failures in a TaskGroup, whose own
        message is the unhelpful "unhandled errors in a TaskGroup (N
        sub-exception)". Recurse into ExceptionGroups so the actual cause
        (e.g. ``httpx.HTTPStatusError: Client error '410 Gone'``) is surfaced.
        """
        leaves: list[str] = []

        def visit(e: BaseException) -> None:
            sub = getattr(e, 'exceptions', None)
            if sub:  # ExceptionGroup / BaseExceptionGroup
                for child in sub:
                    visit(child)
            else:
                leaves.append(f'{type(e).__name__}: {e}')

        visit(exc)
        seen: set[str] = set()
        unique = [m for m in leaves if not (m in seen or seen.add(m))]
        return '; '.join(unique) if unique else f'{type(exc).__name__}: {exc}'

    @staticmethod
    def _iter_exception_leaves(exc: BaseException) -> typing.Iterator[BaseException]:
        sub = getattr(exc, 'exceptions', None)
        if sub:  # ExceptionGroup / BaseExceptionGroup
            for child in sub:
                yield from RuntimeMCPSession._iter_exception_leaves(child)
        else:
            yield exc

    @staticmethod
    def _should_fallback_to_sse(exc: BaseException) -> bool:
        """Whether a Streamable HTTP failure matches legacy-SSE fallback.

        Only protocol-compatibility responses trigger fallback. Authentication,
        authorization, throttling, and server failures must remain visible
        instead of being retried against a different transport.

        MCP SDK 1.26 translates an HTTP 404 initialize response into a synthetic
        ``McpError(32600, 'Session terminated')`` rather than preserving the
        HTTPStatusError, so recognize that exact SDK sentinel as 404-compatible.
        """
        fallback_statuses = {400, 404, 405}
        for leaf in RuntimeMCPSession._iter_exception_leaves(exc):
            if isinstance(leaf, httpx.HTTPStatusError):
                if leaf.response.status_code in fallback_statuses:
                    return True
            elif isinstance(leaf, McpError) and leaf.error.code == 32600 and leaf.error.message == 'Session terminated':
                return True
        return False

    @staticmethod
    def _is_session_terminated(exc: BaseException) -> bool:
        """Whether exc indicates the server-side session expired.

        Long-lived MCP servers (notably UDP/HTTP transports) commonly enforce
        their own session timeout (e.g. ~30 minutes); once it fires, any call
        on the cached session raises this rather than a transport-level error.
        """
        for leaf in RuntimeMCPSession._iter_exception_leaves(exc):
            msg = str(leaf).lower()
            if 'session terminated' in msg or 'session expired' in msg:
                return True
        return False

    _RECONNECT_WAIT_TIMEOUT = 30.0

    async def _trigger_reconnect(self) -> bool:
        """Ask the owning lifecycle loop to rebuild the session and wait for it.

        Concurrent callers that hit the timeout at the same time all signal
        the same _reconnect_event and await the same _reconnected_event, so
        the lifecycle loop reconnects once and every caller resumes together
        — instead of each caller racing to rebuild the session itself.

        Returns True if reconnection succeeded within the timeout.
        """
        if self._shutdown_event.is_set():
            return False

        if self._reconnected_event is None or self._reconnected_event.is_set():
            self._reconnected_event = asyncio.Event()
        reconnected_event = self._reconnected_event
        self._reconnect_event.set()

        try:
            await asyncio.wait_for(reconnected_event.wait(), timeout=self._RECONNECT_WAIT_TIMEOUT)
            return self.status == MCPSessionStatus.CONNECTED
        except asyncio.TimeoutError:
            self.ap.logger.warning(f'MCP session {self.server_name} reconnect timed out')
            return False

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
        startup_timeout = (self.box_config.startup_timeout_sec + 30) if self._uses_box_stdio() else 30.0
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
        self.resources.clear()
        self.resource_templates.clear()
        self._resource_cache.clear()

        try:
            capabilities = self.session.get_server_capabilities()
            self.resource_capabilities = _mcp_model_dump(getattr(capabilities, 'resources', None)) or {}
        except Exception:
            self.resource_capabilities = {}

        tools = await self.session.list_tools()

        self.ap.logger.debug(f'Refresh MCP tools: {tools}')

        for tool in tools.tools:

            async def func(*, _tool=tool, **kwargs):
                return await self.invoke_mcp_tool(_tool.name, kwargs)

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

        await self._refresh_resources()

    async def _refresh_resources(self):
        if not self.session:
            return

        try:
            cursor: str | None = None
            for _ in range(MCP_RESOURCE_DISCOVERY_MAX_PAGES):
                resources_result = await self.session.list_resources(cursor)
                for resource in resources_result.resources:
                    self.resources.append(_resource_to_dict(resource))
                cursor = getattr(resources_result, 'nextCursor', None)
                if not cursor:
                    break
            self.ap.logger.debug(f'Refresh MCP resources: {len(self.resources)} resources found')
        except Exception as e:
            self.ap.logger.debug(f'MCP server {self.server_name} does not support resources or failed to list: {e}')

        try:
            cursor = None
            for _ in range(MCP_RESOURCE_DISCOVERY_MAX_PAGES):
                templates_result = await self.session.list_resource_templates(cursor)
                for template in templates_result.resourceTemplates:
                    self.resource_templates.append(_resource_template_to_dict(template))
                cursor = getattr(templates_result, 'nextCursor', None)
                if not cursor:
                    break
            self.ap.logger.debug(f'Refresh MCP resource templates: {len(self.resource_templates)} templates found')
        except Exception as e:
            self.ap.logger.debug(
                f'MCP server {self.server_name} does not support resource templates or failed to list: {e}'
            )

    def _record_query_resource_link(
        self,
        query: pipeline_query.Query | None,
        resource_link: dict,
        source_tool: str,
    ) -> None:
        if query is None:
            return
        try:
            link = {
                **resource_link,
                'server_name': self.server_name,
                'server_uuid': self.server_uuid,
                'source_tool': source_tool,
            }
            query.variables.setdefault(MCP_RESOURCE_LINKS_QUERY_KEY, []).append(link)
        except Exception:
            pass

    def _content_to_provider_elements(
        self,
        content: typing.Any,
        *,
        query: pipeline_query.Query | None = None,
        source_tool: str = '',
    ) -> list[provider_message.ContentElement]:
        content_type = getattr(content, 'type', '')
        if content_type == 'text':
            return [provider_message.ContentElement.from_text(content.text)]

        if content_type == 'image':
            image_data = getattr(content, 'data', None) or getattr(content, 'image_base64', None)
            if image_data:
                return [provider_message.ContentElement.from_image_base64(image_data)]
            return []

        if content_type == 'audio':
            return [
                provider_message.ContentElement.from_text(
                    json.dumps(
                        {
                            'type': 'audio',
                            'mime_type': getattr(content, 'mimeType', ''),
                            'message': 'Audio content returned by MCP tool is available to the host but not inlined.',
                        },
                        ensure_ascii=False,
                    )
                )
            ]

        if content_type == 'resource_link':
            resource_link = _resource_to_dict(content)
            self._record_query_resource_link(query, resource_link, source_tool)
            return [
                provider_message.ContentElement.from_text(
                    json.dumps(
                        {
                            'type': 'resource_link',
                            'server_name': self.server_name,
                            'server_uuid': self.server_uuid,
                            'resource': resource_link,
                            'message': 'Resource link captured. Read it only if the task needs this additional context.',
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            ]

        if content_type == 'resource':
            resource = getattr(content, 'resource', None)
            if isinstance(resource, mcp_types.TextResourceContents):
                text, truncated, original_bytes = _truncate_text(
                    resource.text,
                    MCP_RESOURCE_AGENT_READ_MAX_BYTES,
                    MCP_RESOURCE_AGENT_READ_MAX_TOKENS,
                )
                header = {
                    'type': 'embedded_resource',
                    'server_name': self.server_name,
                    'server_uuid': self.server_uuid,
                    'uri': str(resource.uri),
                    'mime_type': resource.mimeType or '',
                    'bytes': original_bytes,
                    'truncated': truncated,
                }
                return [provider_message.ContentElement.from_text(f'{json.dumps(header, ensure_ascii=False)}\n{text}')]
            if isinstance(resource, mcp_types.BlobResourceContents):
                return [
                    provider_message.ContentElement.from_text(
                        json.dumps(
                            {
                                'type': 'embedded_resource',
                                'server_name': self.server_name,
                                'server_uuid': self.server_uuid,
                                'uri': str(resource.uri),
                                'mime_type': resource.mimeType or '',
                                'bytes': _blob_size(resource.blob),
                                'binary_omitted': True,
                            },
                            ensure_ascii=False,
                        )
                    )
                ]

        return []

    async def invoke_mcp_tool(
        self,
        tool_name: str,
        arguments: dict,
        query: pipeline_query.Query | None = None,
    ) -> list[provider_message.ContentElement]:
        for attempt in range(2):
            if not self.session:
                raise Exception('MCP session is not connected')

            try:
                result = await self.session.call_tool(tool_name, arguments)
            except Exception as e:
                if attempt == 0 and self._is_session_terminated(e):
                    self.ap.logger.warning(
                        f'MCP tool {tool_name} on {self.server_name} got session terminated, triggering reconnect...'
                    )
                    if await self._trigger_reconnect():
                        continue
                raise

            if result.isError:
                error_texts = []
                for content in result.content:
                    if getattr(content, 'type', '') == 'text':
                        error_texts.append(content.text)
                raise Exception('\n'.join(error_texts) if error_texts else 'Unknown error from MCP tool')

            result_contents: list[provider_message.ContentElement] = []
            for content in result.content:
                result_contents.extend(self._content_to_provider_elements(content, query=query, source_tool=tool_name))
            return result_contents

        raise Exception('MCP session is not connected')

    def get_tools(self) -> list[resource_tool.LLMTool]:
        return self.functions

    def get_resources(self) -> list[dict]:
        return self.resources

    def get_resource_templates(self) -> list[dict]:
        return self.resource_templates

    def has_resource_support(self) -> bool:
        return bool(self.resources or self.resource_templates or self.resource_capabilities)

    def invalidate_resource_cache(self, uri: str | None = None) -> None:
        if uri is None:
            self._resource_cache.clear()
            return
        for key in list(self._resource_cache.keys()):
            if key[0] == uri:
                self._resource_cache.pop(key, None)

    def resource_uri_allowed(self, uri: str) -> bool:
        if any(item.get('uri') == uri for item in self.resources):
            return True

        for template in self.resource_templates:
            uri_template = template.get('uri_template', '')
            if _uri_matches_template(uri, uri_template):
                return True

        return False

    async def read_resource_envelope(
        self,
        uri: str,
        *,
        max_bytes: int = MCP_RESOURCE_PREVIEW_MAX_BYTES,
        max_tokens: int | None = None,
        include_blob: bool = False,
        source: str = 'api',
        query: pipeline_query.Query | None = None,
    ) -> dict:
        """Read a resource by URI with safety limits and audit metadata."""
        if not self.session:
            raise Exception('MCP session is not connected')

        if not self.resource_uri_allowed(uri):
            raise ValueError(
                f'Resource URI is not available from MCP server {self.server_name!r}: {uri!r}. '
                'Use listed resources or resource templates.'
            )

        cache_key = (uri, max_bytes, max_tokens, include_blob)
        now = time.time()
        cached = self._resource_cache.get(cache_key)
        if cached and now - cached.get('cached_at', 0) <= MCP_RESOURCE_CACHE_TTL_SECONDS:
            envelope = {
                **cached['envelope'],
                'cache_hit': True,
                'source': source,
            }
            self._record_resource_read_trace(query, envelope)
            return envelope

        result = None
        for attempt in range(2):
            if not self.session:
                raise Exception('MCP session is not connected')
            try:
                result = await self.session.read_resource(AnyUrl(uri))
                break
            except Exception as e:
                if attempt == 0 and self._is_session_terminated(e):
                    self.ap.logger.warning(
                        f'MCP resource read on {self.server_name} got session terminated, triggering reconnect...'
                    )
                    if await self._trigger_reconnect():
                        continue
                raise
        contents: list[dict] = []
        total_bytes = 0
        truncated_any = False
        warnings: list[str] = []
        remaining_bytes = max_bytes if max_bytes > 0 else None
        remaining_tokens = max_tokens if max_tokens is not None and max_tokens > 0 else None

        for content in result.contents:
            if isinstance(content, mcp_types.TextResourceContents):
                if (remaining_bytes is not None and remaining_bytes <= 0) or (
                    remaining_tokens is not None and remaining_tokens <= 0
                ):
                    text = ''
                    truncated = True
                    original_bytes = len(content.text.encode('utf-8'))
                else:
                    text, truncated, original_bytes = _truncate_text(
                        content.text,
                        remaining_bytes if remaining_bytes is not None else 0,
                        remaining_tokens,
                    )
                total_bytes += original_bytes
                truncated_any = truncated_any or truncated
                if remaining_bytes is not None:
                    remaining_bytes = max(0, remaining_bytes - len(text.encode('utf-8')))
                if remaining_tokens is not None:
                    remaining_tokens = max(0, remaining_tokens - (max(1, len(text) // 4) if text else 0))
                contents.append(
                    {
                        'uri': str(content.uri),
                        'mime_type': content.mimeType or '',
                        'type': 'text',
                        'text': text,
                        'bytes': original_bytes,
                        'truncated': truncated,
                        '_meta': _mcp_model_dump(getattr(content, 'meta', None)) or {},
                    }
                )
            elif isinstance(content, mcp_types.BlobResourceContents):
                original_bytes = _blob_size(content.blob)
                total_bytes += original_bytes
                include_this_blob = include_blob and (remaining_bytes is None or original_bytes <= remaining_bytes)
                if not include_this_blob:
                    truncated_any = True
                    warnings.append('Binary resource content omitted from response.')
                elif remaining_bytes is not None:
                    remaining_bytes = max(0, remaining_bytes - original_bytes)
                contents.append(
                    {
                        'uri': str(content.uri),
                        'mime_type': content.mimeType or '',
                        'type': 'blob',
                        'blob': content.blob if include_this_blob else None,
                        'bytes': original_bytes,
                        'truncated': not include_this_blob,
                        'binary_omitted': not include_this_blob,
                        '_meta': _mcp_model_dump(getattr(content, 'meta', None)) or {},
                    }
                )

        envelope = {
            'server_name': self.server_name,
            'server_uuid': self.server_uuid,
            'uri': uri,
            'source': source,
            'contents': contents,
            'bytes': total_bytes,
            'truncated': truncated_any,
            'cache_hit': False,
            'warnings': warnings,
        }
        self._resource_cache[cache_key] = {'cached_at': now, 'envelope': envelope}
        self._record_resource_read_trace(query, envelope)
        return envelope

    def _record_resource_read_trace(self, query: pipeline_query.Query | None, envelope: dict) -> None:
        if query is None:
            return
        try:
            from langbot.pkg.telemetry import features as telemetry_features

            telemetry_features.increment(query, 'mcp_resource_reads', envelope.get('source') or 'unknown')
            query.variables.setdefault(MCP_RESOURCE_TRACE_QUERY_KEY, []).append(
                {
                    'server_name': envelope.get('server_name'),
                    'server_uuid': envelope.get('server_uuid'),
                    'uri': envelope.get('uri'),
                    'source': envelope.get('source'),
                    'bytes': envelope.get('bytes', 0),
                    'truncated': envelope.get('truncated', False),
                    'cache_hit': envelope.get('cache_hit', False),
                    'content_types': [item.get('type') for item in envelope.get('contents', [])],
                }
            )
        except Exception:
            pass

    async def read_resource(self, uri: str) -> list[dict]:
        """Read a resource by URI and return its capped contents."""
        envelope = await self.read_resource_envelope(uri)
        return envelope['contents']

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
                    'parameters': tool.parameters,
                }
                for tool in self.get_tools()
            ],
            'resource_count': len(self.get_resources()),
            'resources': self.get_resources(),
            'resource_template_count': len(self.get_resource_templates()),
            'resource_templates': self.get_resource_templates(),
            'resource_capabilities': self.resource_capabilities,
        }
        if self._uses_box_stdio():
            info['box_session_id'] = self._build_box_session_id()
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
        # Both live servers and transient config-page tests share ONE Box
        # session ('mcp-shared'). A test therefore reuses the already-running
        # container (and, for an existing server, its live managed process)
        # instead of paying a full per-test session cold-start + dependency
        # bootstrap. Isolation between a test and the live servers is provided
        # at the *process* level: each server/test has its own process_id and a
        # test only ever stops its own process_id (see cleanup_session), so it
        # never disturbs another server's process or the shared session itself.
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
        is_transient = False
        if not uuid_:
            self.ap.logger.warning('Server UUID is None for MCP server, maybe testing in the config page.')
            uuid_ = str(uuid_module.uuid4())
            server_config['uuid'] = uuid_
            # No persisted UUID => this is a throwaway "test" session from the
            # config page. Isolate it from the shared live Box session.
            is_transient = True

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
            '_transient': is_transient,
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

    def _eligible_resource_sessions_for_bound(self, bound_mcp_servers: list[str] | None) -> list[RuntimeMCPSession]:
        return [
            session
            for session in self._eligible_sessions_for_bound(bound_mcp_servers)
            if session.has_resource_support()
        ]

    @staticmethod
    def _mcp_synthetic_resource_tools() -> list[resource_tool.LLMTool]:
        return [
            resource_tool.LLMTool(
                name=MCP_TOOL_LIST_RESOURCES,
                human_desc='List MCP resource URIs for a server (MCP resources/list).',
                description=(
                    'Lists resources and resource templates exposed by an MCP server. '
                    'Call langbot_mcp_read_resource with a listed resource URI or a URI constructed from a listed template. '
                    'Use the server name from LangBot pipeline MCP bindings or admin configuration.'
                ),
                parameters=MCP_LIST_RESOURCES_SCHEMA,
                func=_mcp_resource_tool_placeholder,
            ),
            resource_tool.LLMTool(
                name=MCP_TOOL_READ_RESOURCE,
                human_desc='Read a single MCP resource by URI (MCP resources/read).',
                description=(
                    'Fetches capped text content for a resource. Binary resources return metadata only. '
                    'Only read URIs exposed by langbot_mcp_list_resources for the bound server.'
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
        allowed = {s.server_name for s in self._eligible_resource_sessions_for_bound(bound)}
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
        templates = session.get_resource_templates()
        body = {
            'server_name': server_name,
            'resource_count': len(data),
            'resources': data,
            'resource_template_count': len(templates),
            'resource_templates': templates,
            'resource_capabilities': session.resource_capabilities,
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
        allowed = {s.server_name for s in self._eligible_resource_sessions_for_bound(bound)}
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
            envelope = await session.read_resource_envelope(
                uri,
                max_bytes=MCP_RESOURCE_AGENT_READ_MAX_BYTES,
                max_tokens=MCP_RESOURCE_AGENT_READ_MAX_TOKENS,
                include_blob=False,
                source='agent_tool',
                query=query,
            )
        except Exception as e:
            self.ap.logger.error(f'read_resource {uri!r} on {server_name}: {e}\n{traceback.format_exc()}')
            return [provider_message.ContentElement.from_text(f'Error reading resource: {e!s}')]

        out_chunks: list[str] = []
        for item in envelope.get('contents', []):
            if not isinstance(item, dict):
                continue
            t = item.get('type', '')
            if t == 'text' and 'text' in item:
                header = {
                    'uri': item.get('uri'),
                    'mime_type': item.get('mime_type', ''),
                    'bytes': item.get('bytes', 0),
                    'truncated': item.get('truncated', False),
                }
                out_chunks.append(f'{json.dumps(header, ensure_ascii=False)}\n{typing.cast(str, item["text"])}')
            elif t == 'blob':
                out_chunks.append(
                    json.dumps(
                        {
                            'uri': item.get('uri'),
                            'mime_type': item.get('mime_type', ''),
                            'bytes': item.get('bytes', 0),
                            'binary_omitted': True,
                        },
                        ensure_ascii=False,
                    )
                )
        if not out_chunks:
            return [provider_message.ContentElement.from_text(json.dumps(envelope, ensure_ascii=False, indent=2))]
        suffix = ''
        if envelope.get('truncated'):
            suffix = '\n\n[LangBot: resource content was truncated by configured byte/token limits.]'
        return [provider_message.ContentElement.from_text('\n\n'.join(out_chunks) + suffix)]

    async def get_tools(
        self,
        bound_mcp_servers: list[str] | None = None,
        *,
        include_resource_tools: bool = True,
    ) -> list[resource_tool.LLMTool]:
        all_functions: list[resource_tool.LLMTool] = []

        for session in self.sessions.values():
            # If bound_mcp_servers is specified, only include tools from those servers
            if bound_mcp_servers is not None:
                if session.server_uuid in bound_mcp_servers:
                    all_functions.extend(session.get_tools())
            else:
                # If no bound servers specified, include all tools
                all_functions.extend(session.get_tools())

        if include_resource_tools and self._eligible_resource_sessions_for_bound(bound_mcp_servers):
            all_functions.extend(self._mcp_synthetic_resource_tools())

        self._last_listed_functions = all_functions

        return all_functions

    async def get_tool_catalog(
        self,
        bound_mcp_servers: list[str] | None = None,
        *,
        include_resource_tools: bool = False,
    ) -> list[dict[str, typing.Any]]:
        items: list[dict[str, typing.Any]] = []

        for session in self.sessions.values():
            if bound_mcp_servers is not None and session.server_uuid not in bound_mcp_servers:
                continue
            for tool in session.get_tools():
                items.append(
                    {
                        'name': tool.name,
                        'description': tool.description,
                        'human_desc': tool.human_desc,
                        'parameters': tool.parameters,
                        'source': 'mcp',
                        'source_name': session.server_name,
                        'source_id': session.server_uuid,
                    }
                )

        if include_resource_tools and self._eligible_resource_sessions_for_bound(bound_mcp_servers):
            for tool in self._mcp_synthetic_resource_tools():
                items.append(
                    {
                        'name': tool.name,
                        'description': tool.description,
                        'human_desc': tool.human_desc,
                        'parameters': tool.parameters,
                        'source': 'mcp',
                        'source_name': 'MCP resources',
                        'source_id': '',
                    }
                )

        return items

    def _session_by_source_id(self, source_id: str) -> RuntimeMCPSession | None:
        return next(
            (session for session in self.sessions.values() if session.server_uuid == source_id),
            None,
        )

    async def has_tool(self, name: str, source_id: str | None = None) -> bool:
        """检查工具是否存在"""
        if source_id is None and name in (MCP_TOOL_LIST_RESOURCES, MCP_TOOL_READ_RESOURCE):
            return bool(self._eligible_resource_sessions_for_bound(None))
        sessions = [self._session_by_source_id(source_id)] if source_id is not None else list(self.sessions.values())
        for session in sessions:
            if session is None:
                continue
            for function in session.get_tools():
                if function.name == name:
                    return True
        return False

    async def get_tool(
        self,
        name: str,
        source_id: str | None = None,
    ) -> resource_tool.LLMTool | None:
        if source_id is None and name in (MCP_TOOL_LIST_RESOURCES, MCP_TOOL_READ_RESOURCE):
            if not self._eligible_resource_sessions_for_bound(None):
                return None
            return next(
                (tool for tool in self._mcp_synthetic_resource_tools() if tool.name == name),
                None,
            )
        sessions = [self._session_by_source_id(source_id)] if source_id is not None else list(self.sessions.values())
        for session in sessions:
            if session is None:
                continue
            for function in session.get_tools():
                if function.name == name:
                    return function
        return None

    async def invoke_tool(
        self,
        name: str,
        parameters: dict,
        query: pipeline_query.Query,
        source_id: str | None = None,
    ) -> typing.Any:
        """执行工具调用"""
        if source_id is None and name == MCP_TOOL_LIST_RESOURCES:
            if getattr(query, 'variables', {}).get('_pipeline_mcp_resource_agent_read_enabled', True) is not True:
                raise ToolExecutionDeniedError(name, 'MCP resource agent reads are disabled')
            return await self._invoke_mcp_list_resources(parameters, query)
        if source_id is None and name == MCP_TOOL_READ_RESOURCE:
            if getattr(query, 'variables', {}).get('_pipeline_mcp_resource_agent_read_enabled', True) is not True:
                raise ToolExecutionDeniedError(name, 'MCP resource agent reads are disabled')
            return await self._invoke_mcp_read_resource(parameters, query)

        sessions = [self._session_by_source_id(source_id)] if source_id is not None else list(self.sessions.values())
        for session in sessions:
            if session is None:
                continue
            for function in session.get_tools():
                if function.name == name:
                    self.ap.logger.debug(f'Invoking MCP tool: {name} with parameters: {parameters}')
                    try:
                        result = await session.invoke_mcp_tool(name, parameters, query=query)
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

    async def get_resource_templates(self, server_name: str) -> list[dict]:
        """Get resource templates from a specific MCP server."""
        session = self.get_session(server_name)
        if session is None:
            raise ValueError(f'MCP server not found: {server_name}')
        return session.get_resource_templates()

    async def read_resource_envelope(
        self,
        server_name: str,
        uri: str,
        *,
        max_bytes: int = MCP_RESOURCE_PREVIEW_MAX_BYTES,
        max_tokens: int | None = None,
        include_blob: bool = False,
        source: str = 'api',
        query: pipeline_query.Query | None = None,
    ) -> dict:
        """Read a resource from a specific MCP server and return metadata plus contents."""
        session = self.get_session(server_name)
        if session is None:
            raise ValueError(f'MCP server not found: {server_name}')
        return await session.read_resource_envelope(
            uri,
            max_bytes=max_bytes,
            max_tokens=max_tokens,
            include_blob=include_blob,
            source=source,
            query=query,
        )

    async def read_resource(self, server_name: str, uri: str) -> list[dict]:
        """Read a resource from a specific MCP server."""
        envelope = await self.read_resource_envelope(server_name, uri)
        return envelope['contents']

    def get_session_by_uuid(self, server_uuid: str) -> RuntimeMCPSession | None:
        for session in self.sessions.values():
            if session.server_uuid == server_uuid:
                return session
        return None

    def _resolve_attachment_session(self, attachment: dict) -> RuntimeMCPSession | None:
        server_uuid = attachment.get('server_uuid') or attachment.get('server_id')
        server_name = attachment.get('server_name')
        if server_uuid:
            return self.get_session_by_uuid(server_uuid)
        if server_name:
            return self.get_session(server_name)
        return None

    async def build_resource_context_for_query(
        self,
        query: pipeline_query.Query,
        *,
        default_max_tokens: int = MCP_RESOURCE_CONTEXT_MAX_TOKENS,
        default_max_bytes: int = MCP_RESOURCE_CONTEXT_MAX_BYTES,
    ) -> str:
        """Build host-controlled MCP resource context for the current query."""
        if getattr(query, 'variables', {}).get('_pipeline_mcp_resource_agent_read_enabled', True) is not True:
            return ''

        attachments = (query.variables or {}).get('_pipeline_mcp_resource_attachments', [])
        if not isinstance(attachments, list) or not attachments:
            return ''

        bound = self._get_bound_mcp_from_query(query)
        eligible = self._eligible_resource_sessions_for_bound(bound)
        eligible_by_uuid = {session.server_uuid: session for session in eligible}
        eligible_by_name = {session.server_name: session for session in eligible}

        blocks: list[str] = []
        remaining_tokens = default_max_tokens

        for raw_attachment in attachments:
            if remaining_tokens <= 0:
                break
            if not isinstance(raw_attachment, dict) or raw_attachment.get('enabled', True) is not True:
                continue

            attachment = raw_attachment.copy()
            mode = attachment.get('mode', 'pinned')
            if mode not in ('pinned', 'manual', 'auto'):
                continue

            uri = attachment.get('uri')
            if not uri or not isinstance(uri, str):
                continue

            session = self._resolve_attachment_session(attachment)
            if session is None:
                continue
            if session.server_uuid not in eligible_by_uuid and session.server_name not in eligible_by_name:
                continue

            raw_max_tokens = attachment.get('max_tokens')
            raw_max_bytes = attachment.get('max_bytes')
            if raw_max_tokens is None:
                max_tokens = remaining_tokens
            elif isinstance(raw_max_tokens, bool) or not isinstance(raw_max_tokens, int) or raw_max_tokens <= 0:
                self.ap.logger.warning(f'Ignoring MCP resource {uri!r}: max_tokens must be a positive integer')
                continue
            else:
                max_tokens = min(raw_max_tokens, remaining_tokens)

            if raw_max_bytes is None:
                max_bytes = default_max_bytes
            elif isinstance(raw_max_bytes, bool) or not isinstance(raw_max_bytes, int) or raw_max_bytes <= 0:
                self.ap.logger.warning(f'Ignoring MCP resource {uri!r}: max_bytes must be a positive integer')
                continue
            else:
                max_bytes = raw_max_bytes

            try:
                envelope = await session.read_resource_envelope(
                    uri,
                    max_bytes=max_bytes,
                    max_tokens=max_tokens,
                    include_blob=False,
                    source='preloaded',
                    query=query,
                )
            except Exception as e:
                self.ap.logger.warning(f'Failed to preload MCP resource {uri!r} from {session.server_name!r}: {e}')
                continue

            for item in envelope.get('contents', []):
                if item.get('type') != 'text':
                    continue
                mime_type = item.get('mime_type', '')
                text = item.get('text') or ''
                if not text:
                    continue
                approx_tokens = max(1, len(text) // 4)
                remaining_tokens -= approx_tokens
                header_attrs = {
                    'server': session.server_name,
                    'server_uuid': session.server_uuid,
                    'uri': item.get('uri') or uri,
                    'mime_type': mime_type,
                    'bytes': item.get('bytes', 0),
                    'truncated': item.get('truncated', False),
                    'mode': mode,
                }
                attr_text = ' '.join(f'{k}={json.dumps(v, ensure_ascii=False)}' for k, v in header_attrs.items())
                blocks.append(f'<mcp_resource {attr_text}>\n{text}\n</mcp_resource>')
                if remaining_tokens <= 0:
                    break

        context = '\n\n'.join(blocks)
        if context:
            try:
                query.variables[MCP_RESOURCE_CONTEXT_QUERY_KEY] = {
                    'resource_count': len(blocks),
                    'max_tokens': default_max_tokens,
                    'traces': query.variables.get(MCP_RESOURCE_TRACE_QUERY_KEY, []),
                }
            except Exception:
                pass
        return context

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
