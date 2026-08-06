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
    requester_name: str | None = None,
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
            requester=requester_name or request.requester_cfg.get('requester_name') or 'custom-requester',
            base_url='https://example.com',
            api_keys=[],
        ),
        requester=request,
        token_mgr=SimpleNamespace(),
    )
    return requester.RuntimeLLMModel(execution_context, entity, provider)


def _requester(provider: str = '', requester_name: str = '') -> LiteLLMRequester:
    return LiteLLMRequester(
        SimpleNamespace(),
        {
            'custom_llm_provider': provider,
            'requester_name': requester_name,
        },
    )


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
    assert reasoning.find_reasoning_arg_conflicts(
        {
            'enable_thinking': True,
            'extra_body': {'reasoning_effort': 'high'},
        }
    ) == ['enable_thinking', 'extra_body.reasoning_effort']


def test_manual_reasoning_model_without_known_protocol_stays_conservative(monkeypatch):
    request = _requester()
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)

    capabilities = request.get_reasoning_capabilities(_runtime_model(request))

    assert capabilities == {
        'supported': True,
        'levels': ['provider_default'],
        'source': 'manual',
    }


def test_openai_protocol_does_not_mark_unknown_models_as_reasoning(monkeypatch):
    request = _requester('openai', 'openai-chat-completions')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)

    capabilities = request.get_reasoning_capabilities(
        _runtime_model(request, name='future-reasoning-model', abilities=[])
    )

    assert capabilities == {
        'supported': False,
        'levels': ['provider_default'],
        'source': 'unknown',
    }


def test_unknown_unmarked_model_without_provider_stays_safe(monkeypatch):
    request = _requester()
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)

    capabilities = request.get_reasoning_capabilities(_runtime_model(request, name='unknown-model', abilities=[]))

    assert capabilities == {
        'supported': False,
        'levels': ['provider_default'],
        'source': 'unknown',
    }


def test_mimo_exposes_off_on_without_fake_effort_levels(monkeypatch):
    request = _requester('openai', 'mimo-chat-completions')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)

    capabilities = request.get_reasoning_capabilities(_runtime_model(request, name='mimo-v2.5', abilities=[]))

    assert capabilities == {
        'supported': True,
        'levels': ['provider_default', 'disabled', 'enabled'],
        'source': 'provider',
    }


def test_openai_reasoning_levels_follow_litellm_metadata(monkeypatch):
    request = _requester('openai', 'openai-chat-completions')
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


def test_anthropic_adaptive_and_always_on_profiles(monkeypatch):
    request = _requester('anthropic', 'anthropic-messages')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)

    adaptive = request.get_reasoning_capabilities(_runtime_model(request, name='claude-sonnet-4-6', abilities=[]))
    assert adaptive['levels'] == [
        'provider_default',
        'disabled',
        'low',
        'medium',
        'high',
        'xhigh',
        'max',
    ]

    always_on = request.get_reasoning_capabilities(_runtime_model(request, name='claude-fable-5', abilities=[]))
    assert 'disabled' not in always_on['levels']

    legacy = request.get_reasoning_capabilities(_runtime_model(request, name='claude-3-5-sonnet', abilities=[]))
    assert legacy['levels'] == ['provider_default', 'low', 'medium', 'high']


def test_deepseek_profiles_match_model_generation(monkeypatch):
    request = _requester('deepseek', 'deepseek-chat-completions')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)

    assert request.get_reasoning_capabilities(_runtime_model(request, name='deepseek-v4-flash', abilities=[]))[
        'levels'
    ] == ['provider_default', 'disabled', 'low', 'high', 'xhigh', 'max']
    assert request.get_reasoning_capabilities(_runtime_model(request, name='deepseek-chat', abilities=[]))[
        'levels'
    ] == ['provider_default', 'disabled', 'enabled']
    assert request.get_reasoning_capabilities(_runtime_model(request, name='deepseek-r1', abilities=[]))['levels'] == [
        'provider_default'
    ]


@pytest.mark.parametrize(
    ('model_name', 'expected_levels'),
    [
        ('kimi-k3', ['provider_default', 'low', 'high', 'max']),
        ('kimi-k2.7-code', ['provider_default']),
        ('kimi-k2.6', ['provider_default', 'disabled', 'enabled']),
        ('kimi-k2.5', ['provider_default', 'disabled', 'enabled']),
    ],
)
def test_kimi_profiles(model_name, expected_levels, monkeypatch):
    request = _requester('openai', 'moonshot-chat-completions')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)

    capabilities = request.get_reasoning_capabilities(_runtime_model(request, name=model_name, abilities=[]))

    assert capabilities['levels'] == expected_levels


def test_qwen_mixed_and_dedicated_thinking_profiles(monkeypatch):
    request = _requester('openai', 'bailian-chat-completions')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)

    mixed = request.get_reasoning_capabilities(_runtime_model(request, name='qwen-plus', abilities=[]))
    dedicated = request.get_reasoning_capabilities(
        _runtime_model(request, name='qwen3-235b-a22b-thinking-2507', abilities=[])
    )

    assert mixed['levels'] == ['provider_default', 'disabled', 'enabled']
    assert dedicated['levels'] == ['provider_default', 'low', 'medium', 'high']


def test_qwen3_exposes_budget_based_reasoning_levels(monkeypatch):
    request = _requester('openai', 'bailian-chat-completions')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)

    mixed = request.get_reasoning_capabilities(_runtime_model(request, name='qwen3.8-max', abilities=[]))
    dedicated = request.get_reasoning_capabilities(
        _runtime_model(request, name='qwen3.7-max-preview', abilities=[])
    )

    assert mixed['levels'] == ['provider_default', 'disabled', 'low', 'medium', 'high']
    assert mixed['legacy_levels'] == ['enabled']
    assert dedicated['levels'] == ['provider_default', 'low', 'medium', 'high']


def test_qwen3_legacy_enabled_config_remains_supported(monkeypatch):
    request = _requester('openai', 'bailian-chat-completions')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)

    assert request._build_reasoning_args(_runtime_model(request, 'enabled', name='qwen3.8-max')) == {
        'extra_body': {'enable_thinking': True}
    }


@pytest.mark.parametrize(
    ('level', 'budget'),
    [('low', 1024), ('medium', 4096), ('high', 8192)],
)
def test_qwen3_reasoning_levels_translate_to_thinking_budget(level, budget, monkeypatch):
    request = _requester('openai', 'bailian-chat-completions')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)

    assert request._build_reasoning_args(_runtime_model(request, level, name='qwen3.8-max')) == {
        'extra_body': {
            'enable_thinking': True,
            'thinking_budget': budget,
        }
    }


@pytest.mark.parametrize('model_name', ['qwen3.7-max-preview', 'qwen3.7-max-2026-05-17'])
def test_qwen_dedicated_thinking_release_models_are_not_toggleable(model_name, monkeypatch):
    request = _requester('openai', 'bailian-chat-completions')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)

    capabilities = request.get_reasoning_capabilities(_runtime_model(request, name=model_name, abilities=[]))

    assert capabilities['levels'] == ['provider_default', 'low', 'medium', 'high']


@pytest.mark.parametrize(
    ('model_name', 'expected_levels'),
    [
        ('kimi-k2.6', ['provider_default', 'disabled', 'enabled']),
        ('kimi-k2.5', ['provider_default', 'disabled', 'enabled']),
        ('kimi-k2.7-code', ['provider_default']),
        ('kimi-k2-thinking', ['provider_default']),
    ],
)
def test_bailian_kimi_profiles_use_kimi_model_rules(model_name, expected_levels, monkeypatch):
    request = _requester('openai', 'bailian-chat-completions')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)

    capabilities = request.get_reasoning_capabilities(_runtime_model(request, name=model_name, abilities=[]))

    assert capabilities['levels'] == expected_levels


def test_bailian_kimi_uses_thinking_protocol_instead_of_qwen_protocol(monkeypatch):
    request = _requester('openai', 'bailian-chat-completions')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)

    assert request._build_reasoning_args(_runtime_model(request, 'disabled', name='kimi-k2.6')) == {
        'extra_body': {'thinking': {'type': 'disabled'}}
    }


def test_doubao_exposes_documented_effort_range(monkeypatch):
    request = _requester('openai', 'doubao-chat-completions')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)

    capabilities = request.get_reasoning_capabilities(
        _runtime_model(request, name='doubao-seed-2-1-pro-260628', abilities=[])
    )

    assert capabilities['levels'] == ['provider_default', 'disabled', 'low', 'medium', 'high']


@pytest.mark.parametrize(
    ('model_name', 'expected_levels'),
    [
        ('gpt-5', ['provider_default', 'low', 'medium', 'high']),
        (
            'claude-sonnet-4-6',
            ['provider_default', 'disabled', 'low', 'medium', 'high', 'xhigh', 'max'],
        ),
        ('deepseek-v4-flash', ['provider_default', 'disabled', 'low', 'high', 'xhigh', 'max']),
        ('kimi-k2.6', ['provider_default', 'disabled', 'enabled']),
        ('qwen-plus', ['provider_default', 'disabled', 'enabled']),
        ('doubao-seed-2-1-pro-260628', ['provider_default', 'disabled', 'low', 'medium', 'high']),
        ('mimo-v2.5', ['provider_default', 'disabled', 'enabled']),
    ],
)
def test_new_api_infers_upstream_protocol_from_model_name(model_name, expected_levels, monkeypatch):
    request = _requester('openai', 'new-api-chat-completions')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)
    monkeypatch.setattr(request, '_safe_model_info', lambda _: {})

    capabilities = request.get_reasoning_capabilities(_runtime_model(request, name=model_name, abilities=[]))

    assert capabilities['levels'] == expected_levels


@pytest.mark.parametrize(
    ('provider', 'requester_name', 'model_name'),
    [
        ('openai', 'openai-chat-completions', 'gpt-5'),
        ('anthropic', 'anthropic-messages', 'claude-sonnet-4-6'),
        ('deepseek', 'deepseek-chat-completions', 'deepseek-v4-flash'),
        ('openai', 'mimo-chat-completions', 'mimo-v2.5'),
        ('openai', 'moonshot-chat-completions', 'kimi-k2.6'),
        ('openai', 'bailian-chat-completions', 'qwen-plus'),
        ('openai', 'doubao-chat-completions', 'doubao-seed-2-1-pro-260628'),
        ('openai', 'new-api-chat-completions', 'deepseek-v4-flash'),
    ],
)
def test_scanned_known_models_gain_reasoning_ability(provider, requester_name, model_name, monkeypatch):
    request = _requester(provider, requester_name)
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)
    monkeypatch.setattr(request, '_supports_function_calling', lambda _: False)
    monkeypatch.setattr(request, '_supports_vision', lambda _: False)
    monkeypatch.setattr(request, '_safe_context_length', lambda _: None)

    scanned = request._enrich_scanned_model(model_name)

    assert scanned['abilities'] == ['reasoning']


def test_new_api_unknown_alias_stays_conservative(monkeypatch):
    request = _requester('openai', 'new-api-chat-completions')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)

    capabilities = request.get_reasoning_capabilities(
        _runtime_model(request, name='company-internal-alias', abilities=[])
    )

    assert capabilities == {
        'supported': False,
        'levels': ['provider_default'],
        'source': 'unknown',
    }


def test_reasoning_argument_translation(monkeypatch):
    openai_request = _requester('openai', 'openai-chat-completions')
    monkeypatch.setattr(openai_request, '_supports_reasoning', lambda _: True)
    monkeypatch.setattr(openai_request, '_safe_model_info', lambda _: {'supports_none_reasoning_effort': True})
    assert openai_request._build_reasoning_args(_runtime_model(openai_request, 'disabled', name='gpt-5')) == {
        'reasoning_effort': 'none'
    }

    anthropic_request = _requester('anthropic', 'anthropic-messages')
    assert anthropic_request._build_reasoning_args(
        _runtime_model(anthropic_request, 'disabled', name='claude-sonnet-4-6')
    ) == {'thinking': {'type': 'disabled'}}

    deepseek_request = _requester('deepseek', 'deepseek-chat-completions')
    assert deepseek_request._build_reasoning_args(
        _runtime_model(deepseek_request, 'high', name='deepseek-v4-flash')
    ) == {
        'extra_body': {
            'thinking': {'type': 'enabled'},
            'reasoning_effort': 'high',
        }
    }

    kimi_request = _requester('openai', 'moonshot-chat-completions')
    assert kimi_request._build_reasoning_args(_runtime_model(kimi_request, 'enabled', name='kimi-k2.6')) == {
        'extra_body': {'thinking': {'type': 'enabled'}}
    }
    assert kimi_request._build_reasoning_args(_runtime_model(kimi_request, 'high', name='kimi-k3')) == {
        'reasoning_effort': 'high'
    }

    qwen_request = _requester('openai', 'bailian-chat-completions')
    assert qwen_request._build_reasoning_args(_runtime_model(qwen_request, 'disabled', name='qwen-plus')) == {
        'extra_body': {'enable_thinking': False}
    }

    doubao_request = _requester('openai', 'doubao-chat-completions')
    assert doubao_request._build_reasoning_args(
        _runtime_model(doubao_request, 'high', name='doubao-seed-2-1-pro-260628')
    ) == {'reasoning_effort': 'high'}

    mimo_request = _requester('openai', 'mimo-chat-completions')
    assert mimo_request._build_reasoning_args(_runtime_model(mimo_request, 'disabled', name='mimo-v2.5')) == {
        'extra_body': {'thinking': {'type': 'disabled'}}
    }


def test_pipeline_reasoning_override_takes_precedence(monkeypatch):
    request = _requester('openai', 'openai-chat-completions')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: True)
    monkeypatch.setattr(request, '_safe_model_info', lambda _: {})
    model = _runtime_model(request, 'high', name='gpt-5')

    model.reasoning_config_override = {'level': 'provider_default'}
    assert request._build_reasoning_args(model) == {}

    model.reasoning_config_override = {'level': 'low'}
    assert request._build_reasoning_args(model) == {'reasoning_effort': 'low'}


def test_always_on_reasoning_models_do_not_offer_disabled(monkeypatch):
    deepseek_request = _requester('deepseek', 'deepseek-chat-completions')
    monkeypatch.setattr(deepseek_request, '_supports_reasoning', lambda _: True)
    monkeypatch.setattr(deepseek_request, '_safe_model_info', lambda _: {})
    deepseek_capabilities = deepseek_request.get_reasoning_capabilities(
        _runtime_model(deepseek_request, name='deepseek-r1')
    )
    assert deepseek_capabilities['levels'] == ['provider_default']

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


def test_non_target_provider_capabilities_remain_supported(monkeypatch):
    ollama_request = _requester('ollama', 'ollama')
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

    volcengine_request = _requester('volcengine', 'volcark-chat-completions')
    monkeypatch.setattr(volcengine_request, '_supports_reasoning', lambda _: False)
    monkeypatch.setattr(volcengine_request, '_safe_model_info', lambda _: {})
    assert volcengine_request._build_reasoning_args(
        _runtime_model(volcengine_request, 'disabled', name='doubao-seed')
    ) == {'extra_body': {'thinking': {'type': 'disabled'}}}


def test_explicit_unsupported_level_raises(monkeypatch):
    request = _requester()
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)
    monkeypatch.setattr(request, '_safe_model_info', lambda _: {})

    with pytest.raises(errors.RequesterError, match='Available levels: provider_default'):
        request._build_reasoning_args(_runtime_model(request, 'high', abilities=[]))


def test_provider_inference_rejects_levels_outside_conservative_profile(monkeypatch):
    request = _requester('openai', 'openai-chat-completions')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)
    monkeypatch.setattr(request, '_safe_model_info', lambda _: {})

    with pytest.raises(errors.RequesterError, match='Available levels: provider_default, low, medium, high'):
        request._build_reasoning_args(_runtime_model(request, 'xhigh', name='gpt-5', abilities=[]))


@pytest.mark.asyncio
async def test_completion_args_reject_reasoning_extra_arg_conflicts(monkeypatch):
    request = _requester('openai', 'openai-chat-completions')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: True)
    monkeypatch.setattr(request, '_safe_model_info', lambda _: {})
    model = _runtime_model(request, 'high', name='gpt-5')
    model.model_entity.extra_args = {'reasoning_effort': 'low'}
    model.provider.token_mgr.get_token = lambda: 'test-token'

    with pytest.raises(errors.RequesterError, match='conflicts with advanced parameters'):
        await request._build_completion_args(model, [])


@pytest.mark.asyncio
async def test_openai_compatible_reasoning_effort_is_explicitly_allowed(monkeypatch):
    request = _requester('openai', 'moonshot-chat-completions')
    model = _runtime_model(request, 'high', name='kimi-k3')
    model.model_entity.extra_args = {'allowed_openai_params': ['custom_extension']}
    model.provider.token_mgr.get_token = lambda: 'test-token'

    args = await request._build_completion_args(model, [])

    assert args['reasoning_effort'] == 'high'
    assert args['allowed_openai_params'] == ['custom_extension', 'reasoning_effort']


@pytest.mark.asyncio
async def test_provider_default_does_not_allow_or_send_reasoning_effort():
    request = _requester('openai', 'new-api-chat-completions')
    model = _runtime_model(request, 'provider_default', name='deepseek-v4-flash')
    model.provider.token_mgr.get_token = lambda: 'test-token'

    args = await request._build_completion_args(model, [])

    assert 'reasoning_effort' not in args
    assert 'allowed_openai_params' not in args


@pytest.mark.asyncio
async def test_deepseek_disabled_thinking_is_merged_into_extra_body(monkeypatch):
    request = _requester('deepseek', 'deepseek-chat-completions')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)
    model = _runtime_model(request, 'disabled', name='deepseek-chat')
    model.model_entity.extra_args = {'extra_body': {'custom_extension': True}}
    model.provider.token_mgr.get_token = lambda: 'test-token'

    args = await request._build_completion_args(model, [])

    assert args['extra_body'] == {
        'custom_extension': True,
        'thinking': {'type': 'disabled'},
    }


@pytest.mark.asyncio
async def test_openai_compatible_reasoning_history_is_promoted_for_tool_continuity():
    request = _requester('openai', 'mimo-chat-completions')
    model = _runtime_model(request, 'enabled', name='mimo-v2.5')
    model.provider.token_mgr.get_token = lambda: 'test-token'
    history = [
        provider_message.Message(
            role='assistant',
            content='<think>\nprior reasoning\n</think>\nanswer',
            provider_specific_fields={'reasoning_content': 'prior reasoning'},
        )
    ]

    args = await request._build_completion_args(model, history)

    assert args['messages'][0]['reasoning_content'] == 'prior reasoning'
    assert args['messages'][0]['content'] == 'answer'
    assert 'provider_specific_fields' not in args['messages'][0]


@pytest.mark.asyncio
async def test_disabling_reasoning_removes_previous_reasoning_context():
    request = _requester('openai', 'mimo-chat-completions')
    model = _runtime_model(request, 'disabled', name='mimo-v2.5')
    model.provider.token_mgr.get_token = lambda: 'test-token'
    history = [
        provider_message.Message(
            role='assistant',
            content='answer',
            provider_specific_fields={'reasoning_content': 'prior reasoning'},
        )
    ]

    args = await request._build_completion_args(model, history)

    assert 'reasoning_content' not in args['messages'][0]
    assert 'provider_specific_fields' not in args['messages'][0]


@pytest.mark.asyncio
async def test_anthropic_history_promotes_thinking_blocks_instead_of_reasoning_content():
    request = _requester('anthropic', 'anthropic-messages')
    model = _runtime_model(request, 'high', name='claude-sonnet-4-6')
    model.provider.token_mgr.get_token = lambda: 'test-token'
    thinking_blocks = [{'type': 'thinking', 'thinking': 'prior reasoning', 'signature': 'sig'}]
    history = [
        provider_message.Message(
            role='assistant',
            content='',
            provider_specific_fields={
                'reasoning_content': 'prior reasoning',
                'thinking_blocks': thinking_blocks,
            },
        )
    ]

    args = await request._build_completion_args(model, history)

    assert args['messages'][0]['thinking_blocks'] == thinking_blocks
    assert 'reasoning_content' not in args['messages'][0]
    assert 'provider_specific_fields' not in args['messages'][0]


@pytest.mark.asyncio
async def test_non_stream_anthropic_thinking_blocks_are_preserved(monkeypatch):
    request = _requester('anthropic', 'anthropic-messages')
    request._build_completion_args = AsyncMock(return_value={})
    thinking_blocks = [{'type': 'thinking', 'thinking': 'private reasoning', 'signature': 'sig'}]
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=_Dumpable(
                    {
                        'role': 'assistant',
                        'content': 'answer',
                        'thinking_blocks': thinking_blocks,
                    }
                )
            )
        ],
        usage=None,
    )
    monkeypatch.setattr(litellmchat, 'acompletion', AsyncMock(return_value=response))

    message, _ = await request.invoke_llm(None, _runtime_model(request, 'high', name='claude-sonnet-4-6'), [])

    assert message.content == '<think>\nprivate reasoning\n</think>\nanswer'
    assert message.provider_specific_fields == {'thinking_blocks': thinking_blocks}


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


@pytest.mark.asyncio
async def test_stream_reasoning_content_is_wrapped_for_display(monkeypatch):
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
    accumulator = _StreamAccumulator(remove_think=False)
    emitted: provider_message.MessageChunk | None = None

    async for chunk in request.invoke_llm_stream(
        None,
        _runtime_model(request),
        [],
        remove_think=False,
    ):
        emitted = accumulator.add(chunk) or emitted

    assert emitted is not None
    assert emitted.content == '<think>\nprivate \n</think>\nanswer'
    assert emitted.provider_specific_fields == {'reasoning_content': 'private '}


@pytest.mark.asyncio
async def test_stream_anthropic_thinking_blocks_are_preserved(monkeypatch):
    request = _requester('anthropic', 'anthropic-messages')
    request._build_completion_args = AsyncMock(return_value={})
    thinking_blocks = [{'type': 'thinking', 'thinking': 'private ', 'signature': 'sig'}]

    async def chunks():
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=_Dumpable({'role': 'assistant', 'thinking_blocks': thinking_blocks}),
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
    accumulator = _StreamAccumulator(remove_think=False)
    emitted: provider_message.MessageChunk | None = None

    async for chunk in request.invoke_llm_stream(
        None,
        _runtime_model(request, 'high', name='claude-sonnet-4-6'),
        [],
        remove_think=False,
    ):
        emitted = accumulator.add(chunk) or emitted

    assert emitted is not None
    assert emitted.content == '<think>\nprivate \n</think>\nanswer'
    assert emitted.provider_specific_fields == {'thinking_blocks': thinking_blocks}


@pytest.mark.asyncio
async def test_hidden_thinking_does_not_drop_same_delta_tool_call(monkeypatch):
    request = _requester('openai', 'openai-chat-completions')
    request._build_completion_args = AsyncMock(return_value={})

    async def chunks():
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=_Dumpable(
                        {
                            'content': '<think>hidden</think>',
                            'tool_calls': [
                                {
                                    'index': 0,
                                    'id': 'call_1',
                                    'type': 'function',
                                    'function': {'name': 'lookup', 'arguments': '{}'},
                                }
                            ],
                        }
                    ),
                    finish_reason='tool_calls',
                )
            ],
            usage=None,
        )

    monkeypatch.setattr(litellmchat, 'acompletion', AsyncMock(return_value=chunks()))
    collected = [
        chunk
        async for chunk in request.invoke_llm_stream(
            None,
            _runtime_model(request, 'provider_default'),
            [],
            remove_think=True,
        )
    ]

    assert len(collected) == 1
    assert collected[0].tool_calls[0].id == 'call_1'
