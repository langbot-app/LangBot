"""Replay synthetic HTTP/SSE traffic through the real Codex requester."""

import json
import asyncio
from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import langbot_plugin.api.entities.builtin.provider.message as pm

from langbot.pkg.provider.modelmgr.requesters.codex import CodexRequester, sse_events


TOKENS = {'access_token': 'access-secret', 'account_id': 'account', 'connection_id': 'connection'}
MODEL = SimpleNamespace(model_entity=SimpleNamespace(name='codex-test', extra_args={}, reasoning_config=None))


@pytest.mark.asyncio
async def test_response_headers_obey_host_first_event_deadline(monkeypatch):
    from langbot.pkg.provider.modelmgr.errors import RequesterError
    from langbot.pkg.provider.modelmgr.request_policy import CallState, RequestPolicy, current_call

    cancelled = asyncio.Event()

    async def handler(request):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()

    obj = requester(monkeypatch, handler)
    state = CallState(RequestPolicy(first_event_timeout=0.02))
    token = current_call.set(state)
    try:
        with pytest.raises(RequesterError) as caught:
            await obj.invoke_llm(None, MODEL, [])
    finally:
        current_call.reset(token)
    assert caught.value.code == 'timeout'
    assert caught.value.phase == 'first_event'
    assert cancelled.is_set()


def requester(monkeypatch, handler):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs)
    )
    obj = CodexRequester(SimpleNamespace(), {})
    obj.workspace, obj.provider = 'w', 'p'
    obj._replay = OrderedDict()
    obj.auth = SimpleNamespace(access=AsyncMock(return_value=TOKENS))
    return obj


def stream(events):
    return httpx.Response(200, content=''.join('data: ' + json.dumps(event) + '\r\n\r\n' for event in events))


@pytest.mark.asyncio
async def test_text_tools_usage_and_scoped_opaque_replay(monkeypatch):
    call = {'type': 'function_call', 'call_id': 'call_1', 'name': 'lookup', 'arguments': '{"q":"test"}'}
    output = [
        {'type': 'reasoning', 'encrypted_content': 'opaque-secret'},
        call,
        {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'Hello'}]},
    ]
    requests = []

    def handler(request):
        requests.append(request)
        return stream(
            [
                {'type': 'response.created', 'response': {'id': 'resp_1'}},
                {'type': 'response.output_text.delta', 'delta': 'Hel'},
                {'type': 'response.output_text.delta', 'delta': 'lo'},
                {'type': 'response.function_call_arguments.delta', 'delta': '{broken'},
                {'type': 'response.output_item.done', 'item': call, 'output_index': 1},
                {
                    'type': 'response.completed',
                    'response': {
                        'id': 'resp_1',
                        'status': 'completed',
                        'output': output,
                        'usage': {'input_tokens': 4, 'output_tokens': 3, 'input_tokens_details': {'cached_tokens': 2}},
                    },
                },
            ]
        )

    obj = requester(monkeypatch, handler)
    query = SimpleNamespace(query_id='q', variables=None)
    messages = [pm.Message(role='system', content='Be brief'), pm.Message(role='user', content='Hi')]
    message, usage = await obj.invoke_llm(query, MODEL, messages)
    assert message.content == 'Hello'
    assert len(message.tool_calls) == 1
    assert message.tool_calls[0].function.arguments == '{"q":"test"}'
    assert usage['total_tokens'] == 7
    assert query.variables['_stream_usage'] == usage
    assert 'opaque-secret' not in message.model_dump_json()
    body = json.loads(requests[0].content)
    assert body['store'] is False and body['stream'] is True
    assert body['instructions'] == 'Be brief'
    assert requests[0].url.path.endswith('/codex/responses')
    assert requests[0].headers['authorization'] == 'Bearer access-secret'
    assert requests[0].headers['originator'] == 'langbot'
    same = obj._body(query, MODEL, [message], None, None, TOKENS)
    assert same['input'] == output
    other = obj._body(SimpleNamespace(query_id='q'), MODEL, [message], None, None, TOKENS)
    assert 'opaque-secret' not in json.dumps(other)
    rotated = obj._body(query, MODEL, [message], None, None, {**TOKENS, 'connection_id': 'new'})
    assert 'opaque-secret' not in json.dumps(rotated)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'events',
    [
        [{'type': 'response.failed', 'error': 'access-secret'}],
        [{'type': 'response.incomplete'}],
        [{'type': 'error'}],
        [{'type': 'response.output_text.delta', 'delta': 'partial'}],
        [],
    ],
)
async def test_failure_and_truncated_stream_never_succeed(monkeypatch, events):
    obj = requester(monkeypatch, lambda request: stream(events))
    with pytest.raises(ValueError) as caught:
        await obj.invoke_llm(None, MODEL, [])
    assert 'access-secret' not in str(caught.value)


@pytest.mark.asyncio
async def test_terminal_only_text_stream_and_usage(monkeypatch):
    obj = requester(
        monkeypatch,
        lambda request: stream(
            [
                {
                    'type': 'response.done',
                    'response': {
                        'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'done'}]}],
                        'usage': {'input_tokens': 2, 'output_tokens': 1},
                    },
                }
            ]
        ),
    )
    query = SimpleNamespace(query_id='q', variables={})
    chunks = [chunk async for chunk in obj.invoke_llm_stream(query, MODEL, [])]
    assert ''.join(chunk.content or '' for chunk in chunks) == 'done'
    assert chunks[-1].is_final
    assert query.variables['_stream_usage']['total_tokens'] == 3


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [401, 403, 429, 500])
async def test_http_error_secrecy_and_bounded_401_retry(monkeypatch, status):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status, text='access-secret refresh-secret')

    obj = requester(monkeypatch, handler)
    with pytest.raises(ValueError) as caught:
        await obj.invoke_llm(None, MODEL, [])
    assert 'secret' not in str(caught.value)
    assert len(requests) == (2 if status == 401 else 1)
    if status == 401:
        assert obj.auth.access.call_args.kwargs == {'rejected_token': 'access-secret'}


@pytest.mark.asyncio
async def test_catalog_mapping_filtering_and_deduplication(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                'models': [
                    {'slug': 'a', 'input_modalities': ['text', 'image'], 'supported_reasoning_levels': ['low']},
                    {'slug': 'hidden', 'visibility': 'hide'},
                    {'slug': 'a', 'input_modalities': ['text', 'image'], 'supported_reasoning_levels': ['low']},
                ]
            },
        )

    obj = requester(monkeypatch, handler)
    catalog = await obj.scan_models()
    assert len(catalog['models']) == 1
    assert catalog['models'][0]['abilities'] == ['func_call', 'vision', 'reasoning']
    assert catalog['debug'] is None
    assert requests[0].url.path.endswith('/codex/models')
    assert 'client_version' in requests[0].url.params


@pytest.mark.asyncio
@pytest.mark.parametrize('payload', [{'models': ['secret']}, [], {'models': None}])
async def test_catalog_malformed_safe(monkeypatch, payload):
    obj = requester(monkeypatch, lambda request: httpx.Response(200, json=payload))
    with pytest.raises(ValueError, match='invalid model catalog'):
        await obj.scan_models()


@pytest.mark.asyncio
async def test_sse_multiline_crlf_comments_and_chunk_boundaries():
    class Bytes(httpx.AsyncByteStream):
        async def __aiter__(self):
            for value in b': comment\r\nevent: test\r\ndata: {"type":\r\ndata: "test"}\r\n\r\ndata: [DONE]\r\n\r\n':
                yield bytes([value])

    response = httpx.Response(200, stream=Bytes())
    assert [event async for event in sse_events(response)] == [{'type': 'test'}]


@pytest.mark.parametrize(
    'key', ['base_url', 'headers', 'api_key', 'store', 'stream', 'previous_response_id', 'temperature']
)
def test_advanced_parameters_cannot_override_transport(monkeypatch, key):
    obj = requester(monkeypatch, lambda request: httpx.Response(200))
    with pytest.raises(ValueError, match='Unsupported Codex advanced'):
        obj._body(None, MODEL, [], None, {key: 'secret'}, TOKENS)


@pytest.mark.asyncio
async def test_early_close_releases_nested_http_stream(monkeypatch):
    closed = asyncio.Event()

    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {"type":"response.output_text.delta","delta":"first"}\n\n'
            await asyncio.Event().wait()

        async def aclose(self):
            closed.set()

    obj = requester(monkeypatch, lambda request: httpx.Response(200, stream=Body()))
    stream = obj.invoke_llm_stream(None, MODEL, [])
    assert (await anext(stream)).content == 'first'
    await stream.aclose()
    assert closed.is_set()


@pytest.mark.asyncio
async def test_host_deadline_does_not_cancel_suspended_consumer(monkeypatch, runtime_provider, runtime_llm_model):
    from langbot.pkg.provider.modelmgr.errors import RequesterError
    from tests.unit_tests.provider.conftest import TEST_EXECUTION_CONTEXT

    runtime_provider.requester = requester(
        monkeypatch,
        lambda request: stream(
            [
                {'type': 'response.output_text.delta', 'delta': 'first'},
                {'type': 'response.completed', 'response': {'status': 'completed', 'output': []}},
            ]
        ),
    )
    runtime_llm_model.model_entity.extra_args = {}
    result = runtime_provider.invoke_llm_stream(
        None,
        runtime_llm_model,
        [],
        extra_args={'request_policy': {'total_timeout': 0.05}},
        execution_context=TEST_EXECUTION_CONTEXT,
    )
    assert (await anext(result)).content == 'first'
    await asyncio.sleep(0.07)
    with pytest.raises(RequesterError) as caught:
        await anext(result)
    assert caught.value.phase == 'total'
