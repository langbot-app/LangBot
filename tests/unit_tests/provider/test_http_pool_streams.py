import asyncio
import json
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from aiohttp import web

from langbot.pkg.provider.modelmgr.http_pool import _CompletedSSEStream, RequesterHTTPPool
from langbot.pkg.provider.modelmgr.errors import RequesterError
from langbot.pkg.provider.modelmgr.requesters.litellmchat import LiteLLMRequester
from langbot.pkg.provider.modelmgr.request_policy import CallState, RequestPolicy, current_call
from tests.unit_tests.provider.test_reasoning_control import _runtime_model
from scripts.llm_latency_probe import SSEMeter, cache_tokens


def test_request_timing_uses_high_resolution_monotonic_clock(monkeypatch):
    from langbot.pkg.provider.modelmgr import request_policy

    ticks = iter([100.0, 100.0004])
    monkeypatch.setattr(request_policy.time, 'perf_counter', lambda: next(ticks))
    state = CallState(RequestPolicy())
    state.mark('request_prepared_ms')
    assert state.metrics['request_prepared_ms'] == 0.4


def test_meter_accepts_split_utf8_and_usage_without_content():
    meter = SSEMeter()
    event = {'choices': [{'delta': {'content': '你好'}}]}
    data = ('data: ' + json.dumps(event, ensure_ascii=False) + '\r\n\r\n').encode()
    for byte in data:
        meter.feed(bytes([byte]), 1)
    meter.feed(b'data: {"choices":[],"usage":{"prompt_tokens_details":{"cached_tokens":12}}}\n\n', 2)
    meter.feed(b'data: [DONE]\n\n', 3)
    assert meter.first_content == 1 and meter.content_chars == 2
    assert cache_tokens(meter.usage) == 12 and meter.done
    assert cache_tokens(None) is None


@pytest.mark.asyncio
@pytest.mark.parametrize('provider,name', [('openai', 'gpt-4o'), ('openrouter', 'openai/gpt-4o')])
@pytest.mark.parametrize('drain', [False, True])
async def test_real_stream_reuses_socket_and_preserves_late_usage(monkeypatch, provider, name, drain):
    monkeypatch.setenv('NO_PROXY', '127.0.0.1,localhost')
    sockets = []

    async def handle(request):
        await request.read()
        sockets.append(request.transport)
        response = web.StreamResponse(headers={'Content-Type': 'text/event-stream'})
        await response.prepare(request)
        events = [
            {'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': 'hello'}, 'finish_reason': None}]},
            {'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]},
            {
                'choices': [],
                'usage': {
                    'prompt_tokens': 14,
                    'completion_tokens': 1,
                    'total_tokens': 15,
                    'prompt_tokens_details': {'cached_tokens': 12},
                },
            },
        ]
        for event in events:
            await response.write(
                (
                    'data: '
                    + json.dumps(
                        {
                            'id': 'r',
                            'object': 'chat.completion.chunk',
                            'created': 1,
                            'model': name,
                            **event,
                        }
                    )
                    + '\n\n'
                ).encode()
            )
            await asyncio.sleep(0.02)
        await response.write(b'data: [DO')
        await response.write(b'NE]\n\n')
        await response.write_eof()
        return response

    app = web.Application()
    app.router.add_post('/chat/completions', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    adapter = LiteLLMRequester(
        SimpleNamespace(logger=Mock()),
        {
            'custom_llm_provider': provider,
            'base_url': f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}',
        },
    )
    await adapter.initialize()
    adapter._http_pool.drain_sse = drain
    model = _runtime_model(adapter, name=name)
    model.provider.token_mgr.get_token = lambda: 'test'
    try:
        for _ in range(2):
            state = CallState(RequestPolicy())
            token = current_call.set(state)
            try:
                chunks = [chunk async for chunk in adapter.invoke_llm_stream(None, model, [])]
                assert ''.join(chunk.content or '' for chunk in chunks) == 'hello'
                assert state.usage['prompt_tokens_details']['cached_tokens'] == 12
            finally:
                current_call.reset(token)
        # OpenRouter's generic HTTP adapter already consumes EOF; the OpenAI
        # SDK path is the regression that needs terminal draining.
        assert (sockets[0] is sockets[1]) == (drain or provider == 'openrouter')
    finally:
        await adapter.aclose()
        await runner.cleanup()


@pytest.mark.asyncio
async def test_terminal_drain_is_bounded_but_early_close_does_not_drain():
    class Stream(httpx.AsyncByteStream):
        def __init__(self, terminal):
            self.terminal = terminal
            self.tail_read = False
            self.closed = False

        async def __aiter__(self):
            yield b'data: [DONE]\n\n' if self.terminal else b'data: {"choices":[]}\n\n'
            self.tail_read = True
            await asyncio.Event().wait()

        async def aclose(self):
            self.closed = True

    for terminal in (False, True):
        raw = Stream(terminal)
        wrapped = _CompletedSSEStream(raw)
        iterator = wrapped.__aiter__()
        async with asyncio.timeout(1):
            await anext(iterator)
        await wrapped.aclose()
        await iterator.aclose()
        assert raw.closed and raw.tail_read == terminal


@pytest.mark.asyncio
async def test_cancellation_during_terminal_drain_is_not_swallowed():
    reading = asyncio.Event()

    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: [DONE]\n\n'
            reading.set()
            await asyncio.Event().wait()

        async def aclose(self):
            pass

    wrapped = _CompletedSSEStream(Stream())
    iterator = wrapped.__aiter__()
    pending = asyncio.create_task(anext(iterator))
    await reading.wait()
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    await iterator.aclose()
    await wrapped.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize('retire', [False, True])
async def test_concurrent_pool_initialization_loads_tls_once_off_loop(monkeypatch, retire):
    context = httpx.create_ssl_context()
    entered, release = threading.Event(), threading.Event()
    main_thread = threading.get_ident()
    calls = []

    def load():
        assert threading.get_ident() != main_thread
        calls.append(True)
        entered.set()
        assert release.wait(2)
        return context

    monkeypatch.setattr(httpx, 'create_ssl_context', load)
    pool = RequesterHTTPPool()

    async def lease():
        async with pool.lease() as client:
            return client

    first, second = asyncio.create_task(lease()), asyncio.create_task(lease())
    await asyncio.to_thread(entered.wait, 2)
    if retire:
        await pool.aclose()
    release.set()
    results = await asyncio.gather(first, second, return_exceptions=True)
    assert len(calls) == 1
    if retire:
        assert all(isinstance(result, RequesterError) for result in results)
        assert pool.client is None
    else:
        assert results[0] is results[1] is pool.client
        assert not pool.client.is_closed
    await pool.aclose()


@pytest.mark.asyncio
async def test_cancelling_tls_initialization_leaks_no_http_client(monkeypatch):
    context = httpx.create_ssl_context()
    entered, release = threading.Event(), threading.Event()

    def load():
        entered.set()
        assert release.wait(2)
        return context

    monkeypatch.setattr(httpx, 'create_ssl_context', load)
    pool = RequesterHTTPPool()

    async def lease():
        async with pool.lease():
            pytest.fail('Cancelled initializer must not publish a client')

    pending = asyncio.create_task(lease())
    await asyncio.to_thread(entered.wait, 2)
    pending.cancel()
    try:
        with pytest.raises(asyncio.CancelledError):
            await pending
        await pool.aclose()
        assert pool.client is None and pool.active == 0
    finally:
        release.set()


@pytest.mark.asyncio
async def test_real_openai_stream_close_disconnects_upstream(monkeypatch):
    monkeypatch.setenv('NO_PROXY', '127.0.0.1,localhost')
    disconnected = asyncio.Event()

    async def handle(request):
        await request.read()
        response = web.StreamResponse(headers={'Content-Type': 'text/event-stream'})
        await response.prepare(request)
        await response.write(
            b'data: {"id":"r","object":"chat.completion.chunk","created":1,"model":"gpt-4o","choices":[{"index":0,"delta":{"content":"hello"},"finish_reason":null}]}\n\n'
        )
        for _ in range(100):
            if request.transport is None or request.transport.is_closing():
                disconnected.set()
                break
            await asyncio.sleep(0.02)
        return response

    app = web.Application()
    app.router.add_post('/chat/completions', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    adapter = LiteLLMRequester(
        SimpleNamespace(logger=Mock()),
        {
            'custom_llm_provider': 'openai',
            'base_url': f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}',
        },
    )
    await adapter.initialize()
    model = _runtime_model(adapter, name='gpt-4o')
    model.provider.token_mgr.get_token = lambda: 'test'
    stream = adapter.invoke_llm_stream(None, model, [])
    try:
        assert (await anext(stream)).content == 'hello'
        await stream.aclose()
        await asyncio.wait_for(disconnected.wait(), 3)
    finally:
        await stream.aclose()
        await adapter.aclose()
        await runner.cleanup()
