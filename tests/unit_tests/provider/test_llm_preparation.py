"""Connection ownership, preparation reuse and provider-specific request policy."""

import asyncio
import copy
import threading
import json
from pathlib import Path
from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
import yaml
from aiohttp import web

from langbot.pkg.provider.modelmgr import reasoning
from langbot.pkg.provider.modelmgr.errors import RequesterError
from langbot.pkg.provider.modelmgr.http_pool import RequesterHTTPPool
from langbot.pkg.provider.modelmgr.prompt_caching import apply_prompt_caching
from langbot.pkg.provider.modelmgr.request_policy import CallState, RequestPolicy, current_call
from langbot.pkg.provider.modelmgr.requesters.litellmchat import LiteLLMRequester
from langbot.pkg.provider.modelmgr.requesters.litellmchat import _LeasedHTTPHandler
from langbot.pkg.provider.modelmgr.requesters import codex
from langbot_plugin.api.entities.builtin.provider.message import Message
from tests.unit_tests.provider.test_reasoning_control import _runtime_model, _requester


@pytest.mark.asyncio
async def test_pool_retirement_waits_for_stream_lease():
    pool = RequesterHTTPPool()
    async with pool.lease() as first:
        async with pool.lease() as second:
            assert first is second
            await pool.aclose()
            assert not first.is_closed
            with pytest.raises(RequesterError, match='retired'):
                async with pool.lease():
                    pass
        assert not first.is_closed
    assert first.is_closed
    await pool.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize('provider,name', [('openai', 'gpt-4o'), ('openrouter', 'openai/gpt-4o')])
async def test_real_http_reuses_socket_with_rotating_key_and_timeout(monkeypatch, provider, name):
    monkeypatch.setenv('NO_PROXY', '127.0.0.1,localhost')
    sockets, headers, bodies = [], [], []

    async def handle(request):
        sockets.append(request.transport)
        headers.append(request.headers['Authorization'])
        bodies.append(await request.json())
        return web.json_response(
            {
                'id': 'r',
                'object': 'chat.completion',
                'created': 1,
                'model': 'gpt-4o',
                'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'ok'}, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2},
            }
        )

    app = web.Application()
    app.router.add_post('/v1/chat/completions', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    adapter = LiteLLMRequester(Mock(), {'custom_llm_provider': provider, 'base_url': f'http://127.0.0.1:{port}/v1'})
    await adapter.initialize()
    model = _runtime_model(adapter, name=name)
    model.provider.token_mgr.get_token = Mock(side_effect=['first-key', 'second-key'])
    try:
        for seconds in (10, 20):
            state = CallState(RequestPolicy(read_timeout=seconds), 'lb-scoped')
            token = current_call.set(state)
            try:
                message, _ = await adapter.invoke_llm(
                    None,
                    model,
                    [Message(role='user', content='Hi')],
                    extra_args={'prompt_caching': {'mode': 'openai', 'retention': 'in_memory'}},
                )
                assert message.content == 'ok'
            finally:
                current_call.reset(token)
        assert sockets[0] is sockets[1]
        assert headers == ['Bearer first-key', 'Bearer second-key']
        assert bodies[0]['prompt_cache_key'] == bodies[1]['prompt_cache_key']
        assert bodies[0]['prompt_cache_retention'] == 'in_memory'
        assert all('prompt_caching' not in body and 'reasoning_config' not in body for body in bodies)
    finally:
        await adapter.aclose()
        await runner.cleanup()


@pytest.mark.asyncio
@pytest.mark.parametrize('cancel', [False, True])
async def test_stream_holds_pool_lease_until_consumer_close(cancel):
    adapter = _requester('openai')
    await adapter.initialize()
    model = _runtime_model(adapter, name='gpt-4o')
    model.provider.token_mgr.get_token = Mock(return_value='test')
    closed = asyncio.Event()

    async def raw():
        try:
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(delta=SimpleNamespace(model_dump=lambda: {'content': 'hi'}), finish_reason=None)
                ]
            )
            await asyncio.Event().wait()
        finally:
            closed.set()

    with patch('langbot.pkg.provider.modelmgr.requesters.litellmchat.acompletion', new=AsyncMock(return_value=raw())):
        stream = adapter.invoke_llm_stream(None, model, [])
        await anext(stream)
        client = adapter._http_pool.client
        await adapter.aclose()
        assert not client.is_closed
        if cancel:
            pending = asyncio.create_task(anext(stream))
            await asyncio.sleep(0)
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
        else:
            await stream.aclose()
        assert closed.is_set() and client.is_closed


@pytest.mark.asyncio
async def test_preparation_reused_only_within_call_and_is_not_mutated():
    adapter = _requester('openai')
    adapter.ap.tool_mgr = SimpleNamespace(
        generate_tools_for_openai=AsyncMock(
            return_value=[{'type': 'function', 'function': {'name': 'tool', 'parameters': {'type': 'object'}}}]
        )
    )
    model = _runtime_model(adapter, name='gpt-4o')
    model.provider.token_mgr.get_token = Mock(side_effect=['key-1', 'key-2', 'key-3'])
    messages, funcs = [Message(role='user', content='original')], [object()]
    state = CallState(RequestPolicy(retries=1))
    with patch.object(adapter, '_convert_messages', wraps=adapter._convert_messages) as convert:
        token = current_call.set(state)
        try:
            first = await adapter._build_completion_args(model, messages, funcs)
            first['messages'][0]['content'] = 'mutated'
            first['tools'][0]['function']['name'] = 'mutated'
            second = await adapter._build_completion_args(model, messages, funcs)
        finally:
            current_call.reset(token)
        assert convert.call_count == 1
        assert adapter.ap.tool_mgr.generate_tools_for_openai.await_count == 1
        assert second['messages'][0]['content'] == 'original'
        assert second['tools'][0]['function']['name'] == 'tool'
        assert second['api_key'] == 'key-2'
        await adapter._build_completion_args(model, messages, funcs)
        assert convert.call_count == 2
    assert messages[0].content == 'original'


@pytest.mark.asyncio
async def test_token_counter_runs_off_event_loop():
    adapter = _requester('openai')
    model = _runtime_model(adapter, name='gpt-4o')
    model.provider.token_mgr.get_token = Mock(return_value='test')
    main_thread = threading.get_ident()

    def count(**kwargs):
        assert threading.get_ident() != main_thread
        return 12

    with patch('litellm.token_counter', new=count):
        assert await adapter.count_tokens(model, []) == 12


def test_metadata_cache_is_bounded_and_returns_copies():
    adapter = _requester('openai')
    compute = Mock(return_value={'levels': ['low']})
    first = adapter._cached_metadata('model', compute)
    first['levels'].append('bad')
    assert adapter._cached_metadata('model', compute) == {'levels': ['low']}
    assert compute.call_count == 1
    for index in range(150):
        adapter._cached_metadata(index, lambda: index)
    assert len(adapter._metadata_cache) == 128


@pytest.mark.parametrize(
    'config',
    [
        {'budget_tokens': True},
        {'budget_tokens': 0},
        {'budget_tokens': -1},
        {'budget_tokens': 1.5},
        {'level': 'high', 'budget_tokens': 1024},
        {'level': 'disabled', 'budget_tokens': 1024},
    ],
)
def test_invalid_reasoning_budget(config):
    with pytest.raises(ValueError):
        reasoning.normalize_reasoning_config(config)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'provider,name,budget,expected',
    [
        ('anthropic', 'claude-sonnet-4-5', 2048, {'thinking': {'type': 'enabled', 'budget_tokens': 2048}}),
        ('openai', 'qwen3-32b', 2048, {'extra_body': {'enable_thinking': True, 'thinking_budget': 2048}}),
        ('gemini', 'gemini-2.5-flash', 2048, {'thinking': {'type': 'enabled', 'budget_tokens': 2048}}),
        ('openrouter', 'anthropic/claude-sonnet-4.5', 2048, {'extra_body': {'reasoning': {'max_tokens': 2048}}}),
    ],
)
async def test_budget_mapping_through_existing_extra_args(provider, name, budget, expected):
    adapter = _requester(provider)
    model = _runtime_model(adapter, name=name)
    model.provider.token_mgr.get_token = Mock(return_value='test')
    args = await adapter._build_completion_args(
        model, [], extra_args={'reasoning_config': {'budget_tokens': budget}, 'max_tokens': 4096}
    )
    for key, value in expected.items():
        assert args[key] == value
    assert 'reasoning_config' not in args
    assert model.reasoning_config_override is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'provider,name,budget',
    [
        ('openai', 'gpt-5', 2048),
        ('anthropic', 'claude-opus-4-7', 2048),
        ('anthropic', 'claude-sonnet-4-5', 512),
        ('gemini', 'gemini-2.5-flash', 30000),
        ('gemini', 'gemini-2.5-flash-lite', 128),
    ],
)
async def test_budget_not_silently_dropped_on_unsupported_model(provider, name, budget):
    adapter = _requester(provider)
    model = _runtime_model(adapter, name=name)
    model.provider.token_mgr.get_token = Mock(return_value='test')
    with pytest.raises(RequesterError, match='budget'):
        await adapter._build_completion_args(model, [], extra_args={'reasoning_config': {'budget_tokens': budget}})


def test_runner_level_replaces_call_and_model_budget():
    adapter = _requester('anthropic')
    model = _runtime_model(adapter, name='claude-sonnet-4-5')
    model.model_entity.reasoning_config = {'budget_tokens': 2048}
    call = {'reasoning_config': {'budget_tokens': 4096}}
    assert reasoning.resolve_reasoning_config(model, call)['budget_tokens'] == 4096
    model.reasoning_config_override = {'level': 'low'}
    assert reasoning.resolve_reasoning_config(model, call) == {'level': 'low'}


def test_anthropic_cache_boundary_stable_and_input_unchanged():
    messages = [{'role': 'system', 'content': 'stable instructions'}, {'role': 'user', 'content': 'first'}]
    original = copy.deepcopy(messages)
    args = {'messages': messages, 'prompt_caching': {'mode': 'anthropic', 'ttl': '1h'}}
    apply_prompt_caching(args, None, provider='anthropic', family='anthropic')
    prefix = args['messages'][0]
    assert prefix['content'][-1]['cache_control'] == {'type': 'ephemeral', 'ttl': '1h'}
    assert messages == original
    assert 'cache_control' not in args['messages'][1]
    args['messages'].append({'role': 'user', 'content': 'second'})
    args['prompt_caching'] = {'mode': 'anthropic'}
    apply_prompt_caching(args, None, provider='anthropic', family='anthropic')
    assert args['messages'][0] == prefix


def test_explicit_cache_settings_win_and_default_does_nothing():
    args = {
        'model': 'openai/gpt-4o',
        'extra_body': {'prompt_cache_key': 'explicit', 'prompt_cache_retention': '24h'},
        'prompt_caching': {'mode': 'openai', 'retention': 'in_memory'},
    }
    apply_prompt_caching(args, CallState(RequestPolicy(), 'lb-scoped'), provider='openai', family='openai')
    assert 'prompt_cache_key' not in args and 'prompt_cache_retention' not in args
    args = {'messages': [{'role': 'system', 'content': 'same'}], 'prompt_caching': {'mode': 'provider_default'}}
    apply_prompt_caching(args, None, provider='anthropic', family='anthropic')
    assert args == {'messages': [{'role': 'system', 'content': 'same'}]}


def test_native_cache_options_bypass_model_filter_without_legacy_hints():
    args = {
        'model': 'openai/gpt-test',
        'prompt_cache_options': {'mode': 'implicit', 'ttl': '30m'},
        'prompt_caching': {'mode': 'openai', 'retention': '24h'},
    }
    apply_prompt_caching(args, CallState(RequestPolicy(), 'lb-scoped'), provider='openai', family='openai')
    assert args == {
        'model': 'openai/gpt-test',
        'extra_body': {'prompt_cache_options': {'mode': 'implicit', 'ttl': '30m'}},
    }


@pytest.mark.parametrize(
    'config',
    [
        {'mode': 'typo'},
        {'mode': 'anthropic', 'ttl': '24h'},
        {'mode': 'openai', 'retention': 'forever'},
        {'mode': 'provider_default', 'ttl': '1h'},
    ],
)
def test_invalid_cache_config(config):
    with pytest.raises(RequesterError):
        apply_prompt_caching(
            {'model': 'test', 'messages': [], 'prompt_caching': config}, None, provider='openai', family='openai'
        )


@pytest.mark.asyncio
async def test_gateway_transport_never_retries_or_closes_borrowed_client():
    calls = 0

    async def fail(request):
        nonlocal calls
        calls += 1
        raise httpx.ConnectError('unavailable', request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as client:
        handler = _LeasedHTTPHandler(client, 10)
        with pytest.raises(httpx.ConnectError):
            await handler.post('https://example.com', json={})
        await handler.close()
        assert calls == 1 and not client.is_closed


@pytest.mark.asyncio
@pytest.mark.parametrize('provider', ['anthropic', 'openrouter', 'openrouter-metadata'])
async def test_anthropic_cache_and_budget_reach_upstream(provider):
    bodies = []

    async def handle(request):
        bodies.append(json.loads(request.content))
        if provider == 'anthropic':
            payload = {
                'id': 'msg_test',
                'type': 'message',
                'role': 'assistant',
                'model': 'claude-sonnet-4-5',
                'content': [{'type': 'text', 'text': 'ok'}],
                'stop_reason': 'end_turn',
                'usage': {'input_tokens': 1, 'output_tokens': 1, 'cache_read_input_tokens': 50},
            }
        else:
            payload = {
                'id': 'r',
                'object': 'chat.completion',
                'created': 1,
                'model': 'anthropic/claude-sonnet-4.5',
                'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'ok'}, 'finish_reason': 'stop'}],
                'usage': {
                    'prompt_tokens': 51,
                    'completion_tokens': 1,
                    'total_tokens': 52,
                    'prompt_tokens_details': {'cached_tokens': 50},
                },
            }
        return httpx.Response(200, json=payload)

    adapter = _requester('openai' if provider == 'openrouter-metadata' else provider)
    if provider == 'openrouter-metadata':
        metadata = yaml.safe_load(
            (
                Path(__file__).parents[3] / 'src/langbot/pkg/provider/modelmgr/requesters/openrouterchatcmpl.yaml'
            ).read_text(encoding='utf-8')
        )
        adapter.requester_cfg.update(
            requester_name=metadata['metadata']['name'], custom_llm_provider=metadata['spec']['litellm_provider']
        )
    name = 'claude-sonnet-4-5' if provider == 'anthropic' else 'anthropic/claude-sonnet-4.5'
    model = _runtime_model(adapter, name=name)
    model.provider.token_mgr.get_token = Mock(return_value='test')
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result, usage = await adapter.invoke_llm(
            None,
            model,
            [
                Message(role='system', content='stable'),
                Message(role='user', content='hello'),
            ],
            extra_args={
                'client': _LeasedHTTPHandler(client, 10),
                'reasoning_config': {'budget_tokens': 2048},
                'max_tokens': 4096,
                'prompt_caching': {'mode': 'anthropic', 'ttl': '1h'},
            },
        )
    assert result.content == 'ok'
    assert usage
    body = bodies[0]
    if provider == 'anthropic':
        assert body['system'][-1]['cache_control'] == {'type': 'ephemeral', 'ttl': '1h'}
        assert body['thinking']['budget_tokens'] == 2048
    else:
        assert body['messages'][0]['content'][-1]['cache_control'] == {'type': 'ephemeral', 'ttl': '1h'}
        assert body['reasoning']['max_tokens'] == 2048
    assert 'reasoning_config' not in body and 'prompt_caching' not in body


@pytest.mark.asyncio
async def test_codex_reuses_real_connection(monkeypatch):
    monkeypatch.setenv('NO_PROXY', '127.0.0.1,localhost')
    sockets = []

    async def handle(request):
        sockets.append(request.transport)
        await request.read()
        events = [
            {'type': 'response.output_text.delta', 'delta': 'ok'},
            {'type': 'response.completed', 'response': {'id': 'r', 'status': 'completed', 'output': []}},
        ]
        return web.Response(
            text=''.join('data: ' + json.dumps(event) + '\n\n' for event in events), content_type='text/event-stream'
        )

    app = web.Application()
    app.router.add_post('/responses', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    monkeypatch.setattr(codex, 'BASE_URL', f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}')
    adapter = object.__new__(codex.CodexRequester)
    adapter.workspace, adapter.provider = 'w', 'p'
    adapter._replay = OrderedDict()
    adapter._http_pool = RequesterHTTPPool()
    adapter.auth = SimpleNamespace(
        access=AsyncMock(
            return_value={
                'access_token': 'test',
                'account_id': 'a',
                'connection_id': 'c',
            }
        )
    )
    model = SimpleNamespace(model_entity=SimpleNamespace(name='test', extra_args={}, reasoning_config=None))
    try:
        for _ in range(2):
            message, _ = await adapter.invoke_llm(None, model, [])
            assert message.content == 'ok'
        assert sockets[0] is sockets[1]
    finally:
        await adapter.aclose()
        await runner.cleanup()


@pytest.mark.asyncio
async def test_explicit_client_and_redirected_provider_are_preserved():
    adapter = _requester('openai')
    await adapter.initialize()
    explicit = object()
    for args in ({'model': 'openai/gpt-4o', 'client': explicit}, {'model': 'anthropic/claude-sonnet-4-5'}):
        async with adapter._client_args(args) as result:
            assert result is args
    assert adapter._http_pool.client is None
    await adapter.aclose()


@pytest.mark.asyncio
async def test_codex_terminal_tail_is_bounded_and_releases_stream():
    closed = asyncio.Event()

    class HangingTail(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {"type":"response.completed"}\n\n'
            await asyncio.Event().wait()

        async def aclose(self):
            closed.set()

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=HangingTail()))
    ) as client:
        async with client.stream('GET', 'https://example.com') as response:
            events = [event async for event in codex.sse_events(response)]
            assert events == [{'type': 'response.completed'}]
    assert closed.is_set()


@pytest.mark.asyncio
async def test_custom_tls_keeps_litellm_transport(monkeypatch):
    import litellm

    adapter = _requester('openai')
    await adapter.initialize()
    monkeypatch.setattr(litellm, 'ssl_verify', '/custom/ca.pem')
    args = {'model': 'openai/gpt-4o'}
    async with adapter._client_args(args) as result:
        assert result is args
    assert adapter._http_pool.client is None
    await adapter.aclose()


@pytest.mark.asyncio
async def test_pooled_sdk_preserves_environment_fallbacks(monkeypatch):
    monkeypatch.setenv('OPENAI_BASE_URL', 'https://gateway.example/v1')
    monkeypatch.setenv('OPENAI_API_KEY', 'env-test-key')
    adapter = _requester('openai')
    await adapter.initialize()
    try:
        async with adapter._client_args({'model': 'openai/gpt-4o', 'api_key': ''}) as args:
            assert str(args['client'].base_url) == 'https://gateway.example/v1/'
            assert args['client'].api_key == 'env-test-key'
    finally:
        await adapter.aclose()
