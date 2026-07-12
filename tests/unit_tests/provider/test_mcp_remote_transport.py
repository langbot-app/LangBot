from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from aiohttp import web
from mcp import types as mcp_types

from langbot.pkg.provider.tools.loaders.mcp import RuntimeMCPSession


@pytest.fixture(autouse=True)
def _isolate_loopback_transport_from_proxy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep real loopback transport tests independent of workstation proxies."""
    for variable in (
        'ALL_PROXY',
        'all_proxy',
        'HTTP_PROXY',
        'http_proxy',
        'HTTPS_PROXY',
        'https_proxy',
    ):
        monkeypatch.delenv(variable, raising=False)


class _TransportProbe:
    def __init__(self, streamable_status: int | None) -> None:
        self.streamable_status = streamable_status
        self.streamable_posts = 0
        self.streamable_messages: list[str] = []
        self.sse_gets = 0
        self.sse_messages: list[str] = []
        self.streamable_request_started = asyncio.Event()
        self.release_streamable_request = asyncio.Event()
        self._sse_response: web.StreamResponse | None = None

    async def handle_mcp_endpoint(self, request: web.Request) -> web.StreamResponse:
        if request.method == 'POST':
            self.streamable_posts += 1
            self.streamable_request_started.set()
            if self.streamable_status is None:
                await self.release_streamable_request.wait()
                return web.Response(status=204)
            if self.streamable_status == 200:
                message = await request.json()
                method = message.get('method', '')
                self.streamable_messages.append(method)
                if method == 'initialize':
                    return web.json_response(
                        {
                            'jsonrpc': '2.0',
                            'id': message['id'],
                            'result': {
                                'protocolVersion': mcp_types.LATEST_PROTOCOL_VERSION,
                                'capabilities': {'tools': {}},
                                'serverInfo': {'name': 'streamable-test', 'version': '1.0.0'},
                            },
                        }
                    )
                if method == 'tools/list':
                    return web.json_response(
                        {
                            'jsonrpc': '2.0',
                            'id': message['id'],
                            'result': {
                                'tools': [
                                    {
                                        'name': 'echo',
                                        'description': 'Echo test input',
                                        'inputSchema': {'type': 'object'},
                                    }
                                ]
                            },
                        }
                    )
                return web.Response(status=202)
            return web.Response(status=self.streamable_status)

        self.sse_gets += 1
        response = web.StreamResponse(
            status=200,
            headers={
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
            },
        )
        await response.prepare(request)
        self._sse_response = response
        await response.write(b'event: endpoint\ndata: /messages?session_id=test-session\n\n')
        try:
            while request.transport is not None and not request.transport.is_closing():
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            raise
        return response

    async def handle_sse_message(self, request: web.Request) -> web.Response:
        message = await request.json()
        method = message.get('method', '')
        self.sse_messages.append(method)

        if method == 'initialize':
            response_message = {
                'jsonrpc': '2.0',
                'id': message['id'],
                'result': {
                    'protocolVersion': mcp_types.LATEST_PROTOCOL_VERSION,
                    'capabilities': {},
                    'serverInfo': {'name': 'legacy-sse-test', 'version': '1.0.0'},
                },
            }
            assert self._sse_response is not None
            payload = json.dumps(response_message, separators=(',', ':'))
            await self._sse_response.write(f'event: message\ndata: {payload}\n\n'.encode())

        return web.Response(status=202)


@asynccontextmanager
async def _transport_server(streamable_status: int | None):
    probe = _TransportProbe(streamable_status)
    application = web.Application()
    application.router.add_route('*', '/mcp', probe.handle_mcp_endpoint)
    application.router.add_post('/messages', probe.handle_sse_message)
    runner = web.AppRunner(application, shutdown_timeout=0.1)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    server = cast(asyncio.Server, site._server)
    port = server.sockets[0].getsockname()[1]
    try:
        yield probe, f'http://127.0.0.1:{port}/mcp'
    finally:
        await runner.cleanup()


def _session(url: str, *, timeout: float = 2) -> RuntimeMCPSession:
    app = cast(Any, SimpleNamespace(logger=Mock()))
    return RuntimeMCPSession(
        'remote-transport-test',
        {'uuid': 'srv-1', 'mode': 'remote', 'url': url, 'timeout': timeout},
        True,
        app,
    )


def _contains_http_status(exc: BaseException, status_code: int) -> bool:
    return any(
        isinstance(leaf, httpx.HTTPStatusError) and leaf.response.status_code == status_code
        for leaf in RuntimeMCPSession._iter_exception_leaves(exc)
    )


async def _close_session(session: RuntimeMCPSession) -> None:
    await session.exit_stack.aclose()


@pytest.mark.asyncio
async def test_remote_transport_real_streamable_http_success_keeps_session_usable():
    async with _transport_server(200) as (probe, url):
        session = _session(url)
        try:
            await session._init_remote_server()
            assert session.session is not None
            tools = await session.session.list_tools()
            assert [tool.name for tool in tools.tools] == ['echo']
            assert probe.streamable_posts >= 2
            assert probe.streamable_messages[:2] == ['initialize', 'notifications/initialized']
            assert 'tools/list' in probe.streamable_messages
            assert probe.sse_gets == 0
        finally:
            await _close_session(session)


@pytest.mark.asyncio
@pytest.mark.parametrize('status_code', [400, 404, 405])
async def test_remote_transport_real_streamable_http_error_falls_back_to_legacy_sse(status_code: int):
    async with _transport_server(status_code) as (probe, url):
        session = _session(url)
        try:
            await session._init_remote_server()
            assert session.session is not None
            assert probe.streamable_posts == 1
            assert probe.sse_gets == 1
            assert 'initialize' in probe.sse_messages
        finally:
            await _close_session(session)


@pytest.mark.asyncio
@pytest.mark.parametrize('status_code', [401, 403, 406, 415, 429, 500])
async def test_remote_transport_real_non_compatibility_error_does_not_fallback(status_code: int):
    async with _transport_server(status_code) as (probe, url):
        session = _session(url)
        try:
            with pytest.raises(BaseException) as exc_info:
                await session._init_remote_server()
            assert _contains_http_status(exc_info.value, status_code)
            assert probe.streamable_posts == 1
            assert probe.sse_gets == 0
        finally:
            await _close_session(session)


@pytest.mark.asyncio
async def test_remote_transport_real_timeout_does_not_fallback():
    async with _transport_server(None) as (probe, url):
        session = _session(url, timeout=0.05)
        try:
            with pytest.raises(BaseException) as exc_info:
                await session._init_remote_server()
            assert any(
                isinstance(leaf, httpx.TimeoutException)
                for leaf in RuntimeMCPSession._iter_exception_leaves(exc_info.value)
            )
            assert probe.streamable_posts == 1
            assert probe.sse_gets == 0
        finally:
            probe.release_streamable_request.set()
            await _close_session(session)


@pytest.mark.asyncio
@pytest.mark.parametrize('error_type', [httpx.ConnectError, httpx.ConnectTimeout])
async def test_remote_transport_connection_errors_do_not_fallback(error_type: type[httpx.RequestError]):
    request = httpx.Request('POST', 'https://unreachable.invalid/mcp')
    error = error_type('connection failed', request=request)
    session = _session(str(request.url))
    session._init_streamable_http_server = AsyncMock(side_effect=error)
    session._init_sse_server = AsyncMock()

    with pytest.raises(type(error)) as exc_info:
        await session._init_remote_server()

    assert exc_info.value is error
    session._init_sse_server.assert_not_awaited()


@pytest.mark.asyncio
async def test_remote_transport_external_cancellation_is_not_converted_to_sse_fallback():
    async with _transport_server(None) as (probe, url):
        session = _session(url)
        task = asyncio.create_task(session._init_remote_server())
        await asyncio.wait_for(probe.streamable_request_started.wait(), timeout=2)
        task.cancel()
        try:
            with pytest.raises(asyncio.CancelledError):
                await task
            assert probe.sse_gets == 0
        finally:
            probe.release_streamable_request.set()
            await _close_session(session)
