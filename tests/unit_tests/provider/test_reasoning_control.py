from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import langbot_plugin.api.entities.builtin.provider.message as provider_message
from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.entity.persistence import model as persistence_model
from langbot.pkg.provider.modelmgr import errors, reasoning, requester
from langbot.pkg.provider.modelmgr.requesters import litellmchat
from langbot.pkg.provider.modelmgr.requesters.litellmchat import LiteLLMRequester
from langbot.pkg.provider.runners.localagent import _StreamAccumulator


def _runtime_model(
    request: LiteLLMRequester,
    level: str = 'provider_default',
    name: str = 'reasoning-model',
    abilities: list[str] | None = None,
) -> requester.RuntimeLLMModel:
    execution_context = ExecutionContext(
        instance_uuid='instance-test',
        workspace_uuid='workspace-test',
        placement_generation=1,
    )
    entity = persistence_model.LLMModel(
        workspace_uuid='workspace-test',
        uuid='reasoning-model',
        name=name,
        provider_uuid='provider-test',
        abilities=abilities if abilities is not None else ['reasoning'],
        reasoning_config={'level': level},
        extra_args={},
    )
    provider = SimpleNamespace(
        execution_context=execution_context,
        provider_entity=persistence_model.ModelProvider(
            workspace_uuid='workspace-test',
            uuid='provider-test',
            name='provider',
            requester='openai',
            base_url='https://example.com',
            api_keys=[],
        ),
        requester=request,
        token_mgr=SimpleNamespace(),
    )
    return requester.RuntimeLLMModel(execution_context, entity, provider)


def _requester(provider: str = '') -> LiteLLMRequester:
    return LiteLLMRequester(SimpleNamespace(), {'custom_llm_provider': provider})


def test_reasoning_config_normalization_and_conflicts():
    assert reasoning.normalize_reasoning_config(None) == {'level': 'provider_default'}
    assert reasoning.normalize_reasoning_config({}) == {'level': 'provider_default'}
    assert reasoning.validate_reasoning_config(
        {'level': 'high'},
        ['reasoning'],
        {},
    ) == {'level': 'high'}

    with pytest.raises(ValueError, match='Unsupported reasoning level'):
        reasoning.normalize_reasoning_config({'level': 'turbo'})
    with pytest.raises(ValueError, match='reasoning ability'):
        reasoning.validate_reasoning_config({'level': 'low'}, [], {})
    with pytest.raises(ValueError, match='extra_body.thinking_budget'):
        reasoning.validate_reasoning_config(
            {'level': 'low'},
            ['reasoning'],
            {'extra_body': {'thinking_budget': 1024}},
        )


def test_manual_reasoning_model_exposes_conservative_effort_levels(monkeypatch):
    request = _requester()
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)
    monkeypatch.setattr(request, '_safe_model_info', lambda _: {})

    capabilities = request.get_reasoning_capabilities(_runtime_model(request))

    assert capabilities == {
        'supported': True,
        'levels': ['provider_default', 'low', 'medium', 'high'],
        'source': 'manual',
    }


def test_provider_protocol_exposes_reasoning_for_unknown_model(monkeypatch):
    request = _requester('openai')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)
    monkeypatch.setattr(request, '_safe_model_info', lambda _: pytest.fail('metadata should not be queried'))

    capabilities = request.get_reasoning_capabilities(
        _runtime_model(request, name='future-reasoning-model', abilities=[])
    )

    assert capabilities == {
        'supported': True,
        'levels': ['provider_default', 'low', 'medium', 'high'],
        'source': 'provider',
    }


def test_unknown_unmarked_model_without_provider_stays_safe(monkeypatch):
    request = _requester()
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)

    capabilities = request.get_reasoning_capabilities(
        _runtime_model(request, name='unknown-model', abilities=[])
    )

    assert capabilities == {
        'supported': False,
        'levels': ['provider_default'],
        'source': 'unknown',
    }


def test_mimo_native_model_uses_known_equivalent_litellm_metadata(monkeypatch):
    request = _requester('openai')

    def supports_reasoning(model: str, custom_llm_provider: str | None = None) -> bool:
        return model == 'openrouter/xiaomi/mimo-v2.5'

    def get_model_info(model: str) -> dict:
        if model == 'openrouter/xiaomi/mimo-v2.5':
            return {'supports_reasoning': True}
        raise ValueError('unknown model')

    monkeypatch.setattr(litellmchat.litellm, 'supports_reasoning', supports_reasoning)
    monkeypatch.setattr(litellmchat.litellm, 'get_model_info', get_model_info)

    capabilities = request.get_reasoning_capabilities(
        _runtime_model(request, name='mimo-v2.5', abilities=[])
    )

    assert capabilities == {
        'supported': True,
        'levels': ['provider_default', 'minimal', 'low', 'medium', 'high'],
        'source': 'litellm',
    }


def test_openai_reasoning_levels_follow_litellm_metadata(monkeypatch):
    request = _requester('openai')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: True)
    monkeypatch.setattr(
        request,
        '_safe_model_info',
        lambda _: {
            'supports_none_reasoning_effort': True,
            'supports_minimal_reasoning_effort': False,
            'supports_low_reasoning_effort': True,
            'supports_xhigh_reasoning_effort': True,
        },
    )

    capabilities = request.get_reasoning_capabilities(_runtime_model(request, name='gpt-5'))

    assert capabilities['source'] == 'litellm'
    assert capabilities['levels'] == [
        'provider_default',
        'disabled',
        'low',
        'medium',
        'high',
        'xhigh',
    ]


def test_reasoning_argument_translation(monkeypatch):
    openai_request = _requester('openai')
    monkeypatch.setattr(openai_request, '_supports_reasoning', lambda _: True)
    monkeypatch.setattr(
        openai_request,
        '_safe_model_info',
        lambda _: {'supports_none_reasoning_effort': True},
    )

    assert openai_request._build_reasoning_args(_runtime_model(openai_request, 'provider_default')) == {}
    assert openai_request._build_reasoning_args(_runtime_model(openai_request, 'disabled')) == {
        'reasoning_effort': 'none'
    }
    assert openai_request._build_reasoning_args(_runtime_model(openai_request, 'high')) == {'reasoning_effort': 'high'}

    deepseek_request = _requester('deepseek')
    monkeypatch.setattr(deepseek_request, '_supports_reasoning', lambda _: False)
    monkeypatch.setattr(deepseek_request, '_safe_model_info', lambda _: {})
    assert deepseek_request._build_reasoning_args(
        _runtime_model(deepseek_request, 'enabled', name='deepseek-chat')
    ) == {'thinking': {'type': 'enabled'}}


def test_pipeline_reasoning_override_takes_precedence(monkeypatch):
    request = _requester('openai')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: True)
    monkeypatch.setattr(request, '_safe_model_info', lambda _: {})
    model = _runtime_model(request, 'high', name='gpt-5')

    model.reasoning_config_override = {'level': 'provider_default'}
    assert request._build_reasoning_args(model) == {}

    model.reasoning_config_override = {'level': 'low'}
    assert request._build_reasoning_args(model) == {'reasoning_effort': 'low'}


def test_deepseek_provider_is_inferred_from_model_name(monkeypatch):
    request = _requester()
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: True)
    monkeypatch.setattr(request, '_safe_model_info', lambda _: {})

    capabilities = request.get_reasoning_capabilities(_runtime_model(request, name='deepseek-chat'))

    assert capabilities['levels'] == ['provider_default', 'disabled', 'enabled']


def test_always_on_reasoning_models_do_not_offer_disabled(monkeypatch):
    deepseek_request = _requester('deepseek')
    monkeypatch.setattr(deepseek_request, '_supports_reasoning', lambda _: True)
    monkeypatch.setattr(deepseek_request, '_safe_model_info', lambda _: {})
    deepseek_capabilities = deepseek_request.get_reasoning_capabilities(
        _runtime_model(deepseek_request, name='deepseek-r1')
    )
    assert deepseek_capabilities['levels'] == ['provider_default', 'enabled']

    gemini_request = _requester('gemini')
    monkeypatch.setattr(gemini_request, '_supports_reasoning', lambda _: True)
    monkeypatch.setattr(
        gemini_request,
        '_safe_model_info',
        lambda _: {'supports_none_reasoning_effort': True},
    )
    gemini_capabilities = gemini_request.get_reasoning_capabilities(_runtime_model(gemini_request, name='gemini-3-pro'))
    assert 'disabled' not in gemini_capabilities['levels']
    with pytest.raises(errors.RequesterError, match='not supported'):
        gemini_request._build_reasoning_args(_runtime_model(gemini_request, 'disabled', name='gemini-3-pro'))


def test_toggle_and_effort_provider_capabilities(monkeypatch):
    ollama_request = _requester('ollama')
    monkeypatch.setattr(ollama_request, '_supports_reasoning', lambda _: False)
    monkeypatch.setattr(ollama_request, '_safe_model_info', lambda _: {})

    toggle_capabilities = ollama_request.get_reasoning_capabilities(_runtime_model(ollama_request, name='qwen3'))
    assert toggle_capabilities['levels'] == [
        'provider_default',
        'disabled',
        'enabled',
    ]
    assert ollama_request._build_reasoning_args(_runtime_model(ollama_request, 'enabled', name='qwen3')) == {
        'reasoning_effort': 'low'
    }

    effort_capabilities = ollama_request.get_reasoning_capabilities(_runtime_model(ollama_request, name='gpt-oss:20b'))
    assert effort_capabilities['levels'] == [
        'provider_default',
        'disabled',
        'low',
        'medium',
        'high',
    ]
    assert ollama_request._build_reasoning_args(_runtime_model(ollama_request, 'high', name='gpt-oss:20b')) == {
        'reasoning_effort': 'high'
    }

    volcengine_request = _requester('volcengine')
    monkeypatch.setattr(volcengine_request, '_supports_reasoning', lambda _: False)
    monkeypatch.setattr(volcengine_request, '_safe_model_info', lambda _: {})
    assert volcengine_request._build_reasoning_args(
        _runtime_model(volcengine_request, 'disabled', name='doubao-seed')
    ) == {'thinking': {'type': 'disabled'}}


def test_explicit_unsupported_level_raises(monkeypatch):
    request = _requester()
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)
    monkeypatch.setattr(request, '_safe_model_info', lambda _: {})

    with pytest.raises(errors.RequesterError, match='Available levels: provider_default'):
        request._build_reasoning_args(_runtime_model(request, 'high', abilities=[]))


def test_provider_inference_rejects_levels_outside_conservative_profile(monkeypatch):
    request = _requester('openai')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)

    with pytest.raises(errors.RequesterError, match='Available levels: provider_default, low, medium, high'):
        request._build_reasoning_args(_runtime_model(request, 'xhigh', abilities=[]))


@pytest.mark.asyncio
async def test_completion_args_reject_reasoning_extra_arg_conflicts(monkeypatch):
    request = _requester('openai')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: True)
    monkeypatch.setattr(request, '_safe_model_info', lambda _: {})
    model = _runtime_model(request, 'high')
    model.model_entity.extra_args = {'reasoning_effort': 'low'}
    model.provider.token_mgr.get_token = lambda: 'test-token'

    with pytest.raises(errors.RequesterError, match='conflicts with advanced parameters'):
        await request._build_completion_args(model, [])


@pytest.mark.asyncio
async def test_openai_compatible_reasoning_effort_is_explicitly_allowed(monkeypatch):
    request = _requester('openai')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: True)
    monkeypatch.setattr(request, '_safe_model_info', lambda _: {})
    model = _runtime_model(request, 'high', name='deepseek-v4-flash')
    model.model_entity.extra_args = {'allowed_openai_params': ['custom_extension']}
    model.provider.token_mgr.get_token = lambda: 'test-token'

    args = await request._build_completion_args(model, [])

    assert args['reasoning_effort'] == 'high'
    assert args['allowed_openai_params'] == ['custom_extension', 'reasoning_effort']


@pytest.mark.asyncio
async def test_provider_default_does_not_allow_or_send_reasoning_effort():
    request = _requester('openai')
    model = _runtime_model(request, 'provider_default', name='deepseek-v4-flash')
    model.provider.token_mgr.get_token = lambda: 'test-token'

    args = await request._build_completion_args(model, [])

    assert 'reasoning_effort' not in args
    assert 'allowed_openai_params' not in args


class _Dumpable:
    def __init__(self, data: dict):
        self.data = data

    def model_dump(self) -> dict:
        return dict(self.data)


@pytest.mark.asyncio
async def test_non_stream_reasoning_content_is_preserved(monkeypatch):
    request = _requester('deepseek')
    request._build_completion_args = AsyncMock(return_value={})
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=_Dumpable(
                    {
                        'role': 'assistant',
                        'content': 'answer',
                        'reasoning_content': 'private reasoning',
                    }
                )
            )
        ],
        usage=None,
    )
    monkeypatch.setattr(litellmchat, 'acompletion', AsyncMock(return_value=response))

    message, _ = await request.invoke_llm(None, _runtime_model(request), [], remove_think=True)

    assert message.content == 'answer'
    assert message.provider_specific_fields == {'reasoning_content': 'private reasoning'}


@pytest.mark.asyncio
async def test_stream_reasoning_round_trip_with_hidden_display(monkeypatch):
    request = _requester('deepseek')
    request._build_completion_args = AsyncMock(return_value={})

    async def chunks():
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=_Dumpable({'role': 'assistant', 'reasoning_content': 'private '}),
                    finish_reason=None,
                )
            ],
            usage=None,
        )
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=_Dumpable({'content': 'answer'}),
                    finish_reason='stop',
                )
            ],
            usage=None,
        )

    monkeypatch.setattr(litellmchat, 'acompletion', AsyncMock(return_value=chunks()))
    accumulator = _StreamAccumulator(remove_think=True)
    emitted: provider_message.MessageChunk | None = None

    async for chunk in request.invoke_llm_stream(
        None,
        _runtime_model(request),
        [],
        remove_think=True,
    ):
        emitted = accumulator.add(chunk) or emitted

    assert emitted is not None
    assert emitted.content == 'answer'
    assert emitted.provider_specific_fields == {'reasoning_content': 'private '}
