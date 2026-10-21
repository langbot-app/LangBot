"""MiniMax discovery and real LiteLLM/OpenAI wire-contract regressions."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import yaml

from langbot_plugin.api.entities.builtin.provider.message import Message
from langbot.pkg.provider.modelmgr import errors
from langbot.pkg.provider.modelmgr.requesters.litellmchat import LiteLLMRequester


FLASH = 'MiniMax-M3.1-Flash'
M3 = 'MiniMax-M3'


def adapter(base_url=None, requester_name='minimax-chat-completions'):
    config = yaml.safe_load(
        (Path(__file__).parents[3] / 'src/langbot/pkg/provider/modelmgr/requesters/minimaxchatcmpl.yaml').read_text()
    )
    cfg = {item['name']: item['default'] for item in config['spec']['config']}
    cfg['custom_llm_provider'] = config['spec']['litellm_provider']
    cfg['requester_name'] = requester_name
    if base_url:
        cfg['base_url'] = base_url
    return LiteLLMRequester(SimpleNamespace(tool_mgr=SimpleNamespace(generate_tools_for_openai=AsyncMock())), cfg)


def model(request, name=FLASH, level='provider_default'):
    return SimpleNamespace(
        model_entity=SimpleNamespace(
            name=name, extra_args={}, abilities=['reasoning'], reasoning_config={'level': level}
        ),
        provider=SimpleNamespace(
            provider_entity=SimpleNamespace(requester=request.requester_cfg['requester_name']),
            token_mgr=SimpleNamespace(get_token=lambda: 'fixture-key'),
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [200, 404])
async def test_direct_discovery_recommends_current_models_without_dropping_nontext(monkeypatch, status):
    request = adapter()
    original_client = httpx.AsyncClient
    items = [FLASH, M3, 'MiniMax-M2.7', 'MiniMax-01', 'abab6.5s-chat', 'embo-01', 'speech-02-hd', 'other-chat']
    monkeypatch.setattr(
        httpx,
        'AsyncClient',
        lambda **kwargs: original_client(
            **kwargs,
            transport=httpx.MockTransport(
                lambda req: httpx.Response(status, json={'data': [{'id': x} for x in items]})
            ),
        ),
    )
    result = await request.scan_models('fixture-key')
    ids = [item['id'] for item in result['models']]
    assert ids[:2] == [FLASH, M3]
    assert 'MiniMax-M2.7' not in ids and 'abab6.5s-chat' not in ids
    assert result['models'][0]['context_length'] == 1000000
    assert result['models'][0]['abilities'] == ['func_call', 'vision', 'reasoning']
    if status == 200:
        assert set(ids[2:]) == {'embo-01', 'speech-02-hd', 'other-chat'}


@pytest.mark.asyncio
async def test_gateway_discovery_preserves_advertised_metadata_and_other_models(monkeypatch):
    request = adapter('https://openrouter.ai/api/v1', 'openrouter-chat-completions')
    original_client = httpx.AsyncClient
    data = [
        {'id': 'minimax/minimax-m3.1-flash:free', 'context_length': 123456},
        {'id': 'minimax/minimax-m3', 'context_length': 654321},
        {'id': 'minimax/minimax-m2.7'},
        {'id': 'minimax/minimax-01'},
        {'id': 'other/chat'},
        {'id': 'minimax/speech-02-hd'},
    ]
    monkeypatch.setattr(
        httpx,
        'AsyncClient',
        lambda **kwargs: original_client(
            **kwargs, transport=httpx.MockTransport(lambda req: httpx.Response(200, json={'data': data}))
        ),
    )
    result = await request.scan_models('fixture-key')
    assert [item['id'] for item in result['models']] == [
        data[0]['id'],
        data[1]['id'],
        'minimax/speech-02-hd',
        'other/chat',
    ]
    assert result['models'][0]['context_length'] == 123456
    assert result['models'][1]['context_length'] == 654321


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'base_url', [None, 'https://api.minimaxi.com/v1', 'https://api.minimax.chat/v1', 'https://custom.example/v1']
)
@pytest.mark.parametrize('name', [FLASH, M3, 'MiniMax-M2.7', 'custom-model'])
async def test_default_and_saved_ids_reach_real_sdk_http_unchanged(monkeypatch, base_url, name):
    request = adapter(base_url)
    captured = []

    async def send(client, wire, **kwargs):
        captured.append((str(wire.url), json.loads(wire.content)))
        return httpx.Response(
            200,
            request=wire,
            json={
                'id': 'fixture',
                'object': 'chat.completion',
                'created': 1,
                'model': name,
                'choices': [
                    {'index': 0, 'message': {'role': 'assistant', 'content': 'hello'}, 'finish_reason': 'stop'}
                ],
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, 'send', send)
    response, _ = await request.invoke_llm(None, model(request, name), [Message(role='user', content='hello')])
    assert response.content == 'hello'
    url, body = captured[-1]
    assert url == (base_url or 'https://api.minimax.io/v1') + '/chat/completions'
    assert body['model'] == name
    assert body['messages'] == [{'role': 'user', 'content': 'hello'}]
    assert 'service_tier' not in body and 'reasoning_split' not in body
    assert 'reasoning_effort' not in body and 'thinking' not in body


@pytest.mark.asyncio
@pytest.mark.parametrize('level', ['low', 'medium', 'high', 'xhigh', 'max', 'enabled'])
async def test_flash_reasoning_reaches_wire(monkeypatch, level):
    request = adapter()
    captured = []

    async def send(client, wire, **kwargs):
        captured.append(json.loads(wire.content))
        return httpx.Response(
            200,
            request=wire,
            json={
                'id': 'fixture',
                'object': 'chat.completion',
                'created': 1,
                'model': FLASH,
                'choices': [
                    {'index': 0, 'message': {'role': 'assistant', 'content': 'answer'}, 'finish_reason': 'stop'}
                ],
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, 'send', send)
    await request.invoke_llm(None, model(request, level=level), [Message(role='user', content='hello')])
    if level == 'enabled':
        assert captured[-1]['thinking'] == {'type': 'adaptive'}
    else:
        assert captured[-1]['reasoning_effort'] == level


@pytest.mark.asyncio
async def test_flash_rejects_disabled_but_m3_allows_it():
    request = adapter()
    with pytest.raises(errors.RequesterError):
        await request._build_completion_args(model(request, level='disabled'), [])
    args = await request._build_completion_args(model(request, name=M3, level='disabled'), [])
    assert args['extra_body']['thinking'] == {'type': 'disabled'}


@pytest.mark.asyncio
async def test_tool_history_preserves_raw_thinking_and_separate_reasoning(monkeypatch):
    request = adapter()
    captured = []
    tool_call = {'id': 'call_1', 'type': 'function', 'function': {'name': 'lookup', 'arguments': '{}'}}
    request.ap.tool_mgr.generate_tools_for_openai.return_value = [
        {'type': 'function', 'function': {'name': 'lookup', 'parameters': {'type': 'object', 'properties': {}}}}
    ]
    raw = '<think>original reasoning</think>answer'

    async def send(client, wire, **kwargs):
        captured.append(json.loads(wire.content))
        return httpx.Response(
            200,
            request=wire,
            json={
                'id': 'fixture',
                'object': 'chat.completion',
                'created': 1,
                'model': FLASH,
                'choices': [
                    {
                        'index': 0,
                        'message': {
                            'role': 'assistant',
                            'content': raw,
                            'reasoning_content': 'separate reasoning',
                            'tool_calls': [tool_call],
                        },
                        'finish_reason': 'tool_calls',
                    }
                ],
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, 'send', send)
    runtime = model(request)
    response, _ = await request.invoke_llm(None, runtime, [Message(role='user', content='lookup')], remove_think=True)
    assert response.content == 'answer'
    history = [response, Message(role='tool', content='result', tool_call_id='call_1')]
    await request.invoke_llm(None, runtime, history, funcs=[object()])
    assistant = captured[-1]['messages'][0]
    assert assistant['content'] == raw
    assert assistant['reasoning_content'] == 'separate reasoning'
    assert assistant['tool_calls'] == [tool_call]
    assert captured[-1]['messages'][1]['tool_call_id'] == 'call_1'
    assert captured[-1]['tools'][0]['function']['name'] == 'lookup'


@pytest.mark.asyncio
async def test_stream_preserves_reasoning_and_inline_content_for_followup(monkeypatch):
    request = adapter()
    captured = []
    deltas = [
        {'role': 'assistant', 'reasoning_content': 'separate '},
        {'reasoning_content': 'reasoning'},
        {'content': '<think>inline '},
        {'content': 'reasoning</think>answer'},
    ]

    async def send(client, wire, **kwargs):
        body = json.loads(wire.content)
        captured.append(body)
        if body.get('stream'):
            events = [
                {
                    'id': 'fixture',
                    'object': 'chat.completion.chunk',
                    'created': 1,
                    'model': FLASH,
                    'choices': [{'index': 0, 'delta': delta, 'finish_reason': None}],
                }
                for delta in deltas
            ]
            events.append(
                {
                    'id': 'fixture',
                    'object': 'chat.completion.chunk',
                    'created': 1,
                    'model': FLASH,
                    'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}],
                }
            )
            stream = ''.join('data: ' + json.dumps(event) + '\n\n' for event in events) + 'data: [DONE]\n\n'
            return httpx.Response(200, request=wire, content=stream, headers={'Content-Type': 'text/event-stream'})
        return httpx.Response(
            200,
            request=wire,
            json={
                'id': 'fixture',
                'object': 'chat.completion',
                'created': 1,
                'model': FLASH,
                'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'done'}, 'finish_reason': 'stop'}],
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, 'send', send)
    chunks = [
        chunk
        async for chunk in request.invoke_llm_stream(
            None, model(request), [Message(role='user', content='hello')], remove_think=True
        )
    ]
    accumulated = Message(
        role='assistant',
        content=''.join(chunk.content or '' for chunk in chunks),
        provider_specific_fields={
            key: ''.join((chunk.provider_specific_fields or {}).get(key, '') for chunk in chunks)
            for key in ('reasoning_content', 'minimax_content')
        },
    )
    assert accumulated.content == 'answer'
    assert accumulated.provider_specific_fields['reasoning_content'] == 'separate reasoning'
    assert accumulated.provider_specific_fields['minimax_content'] == '<think>inline reasoning</think>answer'
    await request.invoke_llm(None, model(request), [accumulated])
    assert captured[-1]['messages'][0]['reasoning_content'] == 'separate reasoning'
    assert captured[-1]['messages'][0]['content'] == '<think>inline reasoning</think>answer'
    assert captured[0]['stream_options']['include_usage'] is True


@pytest.mark.asyncio
async def test_multimodal_input_and_m3_disabled_reach_wire(monkeypatch):
    request = adapter()
    captured = []
    content = [
        {'type': 'text', 'text': 'Describe this image'},
        {'type': 'image_url', 'image_url': {'url': 'https://example.com/image.png'}},
    ]

    async def send(client, wire, **kwargs):
        captured.append(json.loads(wire.content))
        return httpx.Response(
            200,
            request=wire,
            json={
                'id': 'fixture',
                'object': 'chat.completion',
                'created': 1,
                'model': M3,
                'choices': [
                    {'index': 0, 'message': {'role': 'assistant', 'content': 'answer'}, 'finish_reason': 'stop'}
                ],
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, 'send', send)
    await request.invoke_llm(None, model(request, name=M3, level='disabled'), [Message(role='user', content=content)])
    assert captured[-1]['messages'][0]['content'] == content
    assert captured[-1]['thinking'] == {'type': 'disabled'}
