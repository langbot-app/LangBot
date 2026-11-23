import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import yaml
from langbot_plugin.api.entities.builtin.provider.message import Message

from langbot.pkg.provider.modelmgr import errors
from langbot.pkg.provider.modelmgr.requesters import litellmchat, minimax


@pytest.fixture
def provider():
    manifest = yaml.safe_load(Path(litellmchat.__file__).with_name('minimaxchatcmpl.yaml').read_text())
    settings = {option['name']: option['default'] for option in manifest['spec']['config']}
    settings.update(custom_llm_provider='openai', requester_name=manifest['metadata']['name'])
    tool = {'type': 'function', 'function': {'name': 'lookup', 'parameters': {'type': 'object'}}}
    app = SimpleNamespace(tool_mgr=SimpleNamespace(generate_tools_for_openai=AsyncMock(return_value=[tool])))
    return litellmchat.LiteLLMRequester(app, settings)


def runtime(provider, name='MiniMax-M3.1-Flash', level='provider_default'):
    return SimpleNamespace(
        provider=SimpleNamespace(
            provider_entity=SimpleNamespace(requester=provider.requester_cfg['requester_name']),
            token_mgr=SimpleNamespace(get_token=lambda: 'synthetic-minimax-test'),
        ),
        model_entity=SimpleNamespace(
            name=name, abilities=['reasoning'], reasoning_config={'level': level}, extra_args={}
        ),
    )


def completion(message=None):
    return {
        'id': 'protocol-test',
        'created': 1,
        'model': 'MiniMax-M3.1-Flash',
        'object': 'chat.completion',
        'choices': [
            {'index': 0, 'message': message or {'role': 'assistant', 'content': 'ok'}, 'finish_reason': 'stop'}
        ],
    }


@pytest.fixture
def wire(monkeypatch):
    captured = []
    queued = []

    async def send(client, request, **kwargs):
        captured.append((request, json.loads(request.content) if request.content else None))
        response = queued.pop(0) if queued else httpx.Response(200, json=completion())
        response.request = request
        return response

    monkeypatch.setattr(httpx.AsyncClient, 'send', send)
    return captured, queued


@pytest.mark.asyncio
@pytest.mark.parametrize('name', [*minimax.RECOMMENDED_MODELS, 'MiniMax-M2.7', 'private-deployment'])
@pytest.mark.parametrize(
    'base_url', [None, 'https://api.minimax.chat/v1', 'https://api.minimaxi.com/v1', 'https://proxy.test/v1']
)
async def test_saved_endpoint_and_model_are_not_migrated(provider, wire, name, base_url):
    if base_url:
        provider.requester_cfg['base_url'] = base_url
    await provider.invoke_llm(None, runtime(provider, name), [Message(role='user', content='hello')])
    request, body = wire[0][-1]
    assert str(request.url) == f'{base_url or "https://api.minimax.io/v1"}/chat/completions'
    assert body['model'] == name
    assert body['messages'] == [{'role': 'user', 'content': 'hello'}]
    assert not {'thinking', 'reasoning_effort', 'reasoning_split', 'service_tier'}.intersection(body)


@pytest.mark.asyncio
@pytest.mark.parametrize('level', ['enabled', 'low', 'medium', 'high', 'xhigh', 'max'])
async def test_flash_effort_is_serialized_without_changing_input(provider, wire, level):
    content = [
        {'type': 'text', 'text': 'inspect'},
        {'type': 'image_url', 'image_url': {'url': 'https://image.test/a.png'}},
    ]
    await provider.invoke_llm(None, runtime(provider, level=level), [Message(role='user', content=content)])
    body = wire[0][-1][1]
    assert body['messages'][0]['content'] == content
    if level == 'enabled':
        assert body['thinking'] == {'type': 'adaptive'}
        assert 'reasoning_effort' not in body
    else:
        assert body['reasoning_effort'] == level
        assert 'thinking' not in body


@pytest.mark.asyncio
@pytest.mark.parametrize('level,expected', [('enabled', 'adaptive'), ('disabled', 'disabled')])
async def test_m3_thinking_switch(provider, wire, level, expected):
    await provider.invoke_llm(None, runtime(provider, 'MiniMax-M3', level), [])
    assert wire[0][-1][1]['thinking'] == {'type': expected}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'name,level', [('MiniMax-M3.1-Flash', 'disabled'), ('MiniMax-M3', 'max'), ('MiniMax-M2.7', 'disabled')]
)
async def test_unsupported_thinking_rejected_before_http(provider, wire, name, level):
    with pytest.raises(errors.RequesterError):
        await provider.invoke_llm(None, runtime(provider, name, level), [])
    assert wire[0] == []


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [200, 404])
async def test_direct_discovery_fallback_preserves_custom_and_nontext_models(provider, wire, status):
    names = ['MiniMax-M2.7', 'MiniMax-01', 'abab6.5-chat', 'speech-02-hd', 'embo-01', 'private-deployment']
    wire[1].append(httpx.Response(status, json={'data': [{'id': name} for name in names]}))
    models = (await provider.scan_models('synthetic-minimax-test'))['models']
    assert [model['id'] for model in models[:2]] == list(minimax.RECOMMENDED_MODELS)
    assert all(model['context_length'] == 1_000_000 for model in models[:2])
    assert all(set(model['abilities']) == {'func_call', 'vision', 'reasoning'} for model in models[:2])
    assert {model['id'] for model in models[2:]} == (set(names[3:]) if status == 200 else set())


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [401, 403, 429, 500])
async def test_catalog_errors_are_not_hidden_by_recommendations(provider, wire, status):
    wire[1].append(httpx.Response(status, json={'error': 'fixture'}))
    with pytest.raises(errors.RequesterError, match=str(status)):
        await provider.scan_models()


@pytest.mark.asyncio
async def test_gateway_keeps_all_advertised_current_variants_and_metadata(provider, wire):
    provider.requester_cfg.update(requester_name='openrouter-chat-completions', base_url='https://openrouter.ai/api/v1')
    names = [
        'other/minimax-m2',
        'minimax/minimax-m3',
        'minimax/minimax-m3.1-flash',
        'minimax/minimax-m3.1-flash:free',
        'minimax/minimax-m4',
        'minimax/minimax-m2.7',
        'minimax/speech-02-hd',
    ]
    wire[1].append(httpx.Response(200, json={'data': [{'id': name, 'context_length': 12345} for name in names]}))
    models = (await provider.scan_models())['models']
    assert [model['id'] for model in models[:3]] == [names[2], names[3], names[1]]
    assert {model['id'] for model in models} == set(names) - {names[5]}
    assert all(model.get('context_length') == 12345 for model in models if model['type'] == 'llm')
    wire[1].append(httpx.Response(200, json={'data': []}))
    assert await provider.scan_models() == {'models': []}


@pytest.mark.asyncio
@pytest.mark.parametrize('stream', [False, True])
@pytest.mark.parametrize('hide_thinking', [False, True])
@pytest.mark.parametrize('name,level', [('MiniMax-M3.1-Flash', 'provider_default'), ('MiniMax-M3', 'disabled')])
async def test_tool_followup_replays_original_assistant_not_rendered_text(
    provider, wire, stream, hide_thinking, name, level
):
    tool_call = {'id': 'lookup-1', 'type': 'function', 'function': {'name': 'lookup', 'arguments': '{}'}}
    original = {
        'role': 'assistant',
        'content': '<think>private</think>answer',
        'reasoning_content': 'plan',
        'tool_calls': [tool_call],
    }
    model = runtime(provider, name, level)
    if stream:
        deltas = [
            {'role': 'assistant', 'reasoning_content': 'pl'},
            {'reasoning_content': 'an'},
            {'content': '<thi'},
            {'content': 'nk>private</think>'},
            {'content': 'answer'},
            {'tool_calls': [{'index': 0, **tool_call}]},
        ]
        events = []
        for index, delta in enumerate([*deltas, {}]):
            event = completion()
            event.update(object='chat.completion.chunk')
            event['choices'] = [
                {'index': 0, 'delta': delta, 'finish_reason': 'tool_calls' if index == len(deltas) else None}
            ]
            events.append('data: ' + json.dumps(event) + '\n\n')
        wire[1].append(
            httpx.Response(
                200, content=''.join(events) + 'data: [DONE]\n\n', headers={'content-type': 'text/event-stream'}
            )
        )
        chunks = [chunk async for chunk in provider.invoke_llm_stream(None, model, [], remove_think=hide_thinking)]
        fields = {}
        calls = []
        for chunk in chunks:
            for key, value in (chunk.provider_specific_fields or {}).items():
                fields[key] = fields.get(key, '') + value if key == 'reasoning_content' else value
            if chunk.tool_calls:
                calls = chunk.tool_calls
        response = Message(
            role='assistant',
            content=''.join(chunk.content or '' for chunk in chunks),
            provider_specific_fields=fields,
            tool_calls=calls,
        )
    else:
        wire[1].append(httpx.Response(200, json=completion(original)))
        response, _ = await provider.invoke_llm(None, model, [], remove_think=hide_thinking)
    if hide_thinking:
        assert response.content == 'answer'
    assert response.provider_specific_fields[minimax.RAW_CONTENT_FIELD] == original['content']
    saved = Message.model_validate_json(response.model_dump_json())
    await provider.invoke_llm(
        None, model, [saved, Message(role='tool', tool_call_id='lookup-1', content='result')], funcs=[object()]
    )
    followup = wire[0][-1][1]
    assert {key: followup['messages'][0][key] for key in original} == original
    assert minimax.RAW_CONTENT_FIELD not in json.dumps(followup)
    assert followup['messages'][1]['tool_call_id'] == 'lookup-1'
    assert followup['tools'][0]['function']['name'] == 'lookup'


def test_private_replay_field_does_not_leak_when_switching_provider(provider):
    message = Message(
        role='assistant', content='visible', provider_specific_fields={minimax.RAW_CONTENT_FIELD: 'private'}
    )
    assert provider._convert_messages([message], reasoning_family='openai') == [
        {'role': 'assistant', 'content': 'visible'}
    ]
    assert message.provider_specific_fields == {minimax.RAW_CONTENT_FIELD: 'private'}


def test_direct_catalog_does_not_overwrite_advertised_context_or_drop_nontext():
    advertised = [
        {'id': 'MiniMax-M3', 'name': 'MiniMax-M3', 'type': 'llm', 'context_length': 54321},
        {'id': 'minimax-m2-embedding', 'name': 'embedding', 'type': 'text-embedding'},
    ]
    models = minimax.arrange_catalog(advertised, direct=True)
    assert len(models) == 3
    assert models[1]['context_length'] == 54321
    assert models[2] == advertised[1]
    assert 'abilities' not in advertised[0]


@pytest.mark.asyncio
@pytest.mark.parametrize('requester_name', ['openai-chat-completions', 'openrouter-chat-completions'])
async def test_other_providers_do_not_get_minimax_404_fallback(provider, wire, requester_name):
    provider.requester_cfg['requester_name'] = requester_name
    wire[1].append(httpx.Response(404, json={}))
    with pytest.raises(errors.RequesterError, match='404'):
        await provider.scan_models()


@pytest.mark.asyncio
@pytest.mark.parametrize('content', ['<think>hidden</think>', '<think>hidden</think>answer'])
async def test_stream_without_finish_reason_flushes_one_complete_history_snapshot(provider, wire, content):
    events = []
    for fragment in [content[:5], content[5:]]:
        event = completion()
        event['object'] = 'chat.completion.chunk'
        event['choices'] = [{'index': 0, 'delta': {'content': fragment}, 'finish_reason': None}]
        events.append('data: ' + json.dumps(event) + '\n\n')
    wire[1].append(
        httpx.Response(200, content=''.join(events) + 'data: [DONE]\n\n', headers={'content-type': 'text/event-stream'})
    )
    chunks = [chunk async for chunk in provider.invoke_llm_stream(None, runtime(provider), [], remove_think=True)]
    snapshots = [
        chunk.provider_specific_fields[minimax.RAW_CONTENT_FIELD]
        for chunk in chunks
        if minimax.RAW_CONTENT_FIELD in (chunk.provider_specific_fields or {})
    ]
    assert snapshots == [content]
