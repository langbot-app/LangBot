"""Explicit model call options preserve legacy defaults and shared state."""

from __future__ import annotations

import pytest
from langbot.pkg.provider.modelmgr import errors, reasoning
from tests.unit_tests.provider.test_reasoning_control import _requester, _runtime_model

PRIMARY = '00000000-0000-4000-8000-000000000011'
FALLBACK = '00000000-0000-4000-8000-000000000012'
OTHER = '00000000-0000-4000-8000-000000000013'


def test_request_local_clone_preserves_shared_model_and_absent_default():
    model = _runtime_model(_requester('openai'), 'high', name='gpt-5')
    assert reasoning.model_with_reasoning_level(model, None) is model
    assert reasoning.model_with_reasoning_level(model, None) is model
    clone = reasoning.model_with_reasoning_level(model, 'provider_default')
    assert clone is not model
    assert clone.provider is model.provider
    assert clone.model_entity is model.model_entity
    assert clone.reasoning_config_override == {'level': 'provider_default'}
    clone.reasoning_config_override['level'] = 'disabled'
    assert model.reasoning_config_override is None
    assert model.model_entity.reasoning_config == {'level': 'high'}


@pytest.mark.parametrize(
    ('provider', 'name', 'expected'),
    [
        ('openai', 'gpt-5', {'reasoning_effort': 'high'}),
        ('anthropic', 'claude-sonnet-4-6', {'reasoning_effort': 'high'}),
        ('gemini', 'gemini-3-pro', {'reasoning_effort': 'high'}),
    ],
)
def test_real_requester_reasoning_boundary(provider, name, expected, monkeypatch):
    request = _requester(provider)
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: True)
    monkeypatch.setattr(request, '_safe_model_info', lambda _: {})
    model = _runtime_model(request, 'low', name=name)
    clone = reasoning.model_with_reasoning_level(model, 'high')
    assert request._build_reasoning_args(clone) == expected
    clone.reasoning_config_override = {'level': 'provider_default'}
    assert request._build_reasoning_args(clone) == {}
    assert model.model_entity.reasoning_config == {'level': 'low'}


@pytest.mark.parametrize(
    ('name', 'abilities', 'level'), [('gpt-5', [], 'high'), ('gemini-3-pro', ['reasoning'], 'disabled')]
)
def test_real_requester_still_rejects_ability_and_capability_mismatches(name, abilities, level, monkeypatch):
    request = _requester('gemini' if name.startswith('gemini') else 'openai')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: True)
    monkeypatch.setattr(request, '_safe_model_info', lambda _: {})
    model = _runtime_model(request, name=name, abilities=abilities)
    if not abilities:
        with pytest.raises(ValueError, match='reasoning ability'):
            reasoning.model_with_reasoning_level(model, level)
    else:
        clone = reasoning.model_with_reasoning_level(model, level)
        with pytest.raises(errors.RequesterError):
            request._build_reasoning_args(clone)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('provider', 'name', 'level', 'expected'),
    [
        ('openai', 'gpt-5', 'high', {'reasoning_effort': 'high'}),
        ('anthropic', 'claude-sonnet-4-6', 'disabled', {'thinking': {'type': 'disabled'}}),
        ('gemini', 'gemini-3-pro', 'low', {'reasoning_effort': 'low'}),
    ],
)
async def test_real_completion_and_count_tokens_build_boundary(provider, name, level, expected, monkeypatch):
    from unittest.mock import AsyncMock
    from langbot_plugin.api.entities.builtin.provider import message as provider_message
    from langbot.pkg.provider.modelmgr.requesters import litellmchat

    request = _requester(provider)
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: True)
    monkeypatch.setattr(request, '_safe_model_info', lambda _: {})
    model = _runtime_model(request, name=name)
    model.provider.token_mgr.get_token = lambda: 'test-only-not-a-secret'
    clone = reasoning.model_with_reasoning_level(model, level)
    messages = [provider_message.Message(role='user', content='hello')]
    for stream in (False, True):
        built = await request._build_completion_args(clone, messages, extra_args={'temperature': 0.7}, stream=stream)
        for key, value in expected.items():
            assert built[key] == value
        assert 'model_reasoning_overrides' not in built
        assert 'reasoning_config_override' not in built
        assert built['temperature'] == 0.7
        assert built.get('stream', False) is stream
    build = AsyncMock(wraps=request._build_completion_args)
    monkeypatch.setattr(request, '_build_completion_args', build)
    # Only the tokenizer is stubbed; count_tokens and completion construction are real.
    monkeypatch.setattr(litellmchat.litellm, 'token_counter', lambda **kwargs: 37)
    assert await request.count_tokens(clone, messages) == 37
    assert build.await_args.args[0] is clone
    assert model.reasoning_config_override is None


@pytest.mark.asyncio
async def test_real_requester_rejects_caller_reasoning_conflicts(monkeypatch):
    from langbot_plugin.api.entities.builtin.provider import message as provider_message

    request = _requester('openai')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: True)
    monkeypatch.setattr(request, '_safe_model_info', lambda _: {})
    model = _runtime_model(request, name='gpt-5')
    model.provider.token_mgr.get_token = lambda: 'test-only-not-a-secret'
    clone = reasoning.model_with_reasoning_level(model, 'high')
    with pytest.raises(errors.RequesterError, match='conflicts with advanced parameters'):
        await request._build_completion_args(
            clone, [provider_message.Message(role='user', content='hello')], extra_args={'reasoning_effort': 'low'}
        )


@pytest.mark.asyncio
@pytest.mark.parametrize('stream', [False, True])
async def test_space_detected_reasoning_without_catalog_flag_reaches_completion(stream, monkeypatch):
    from langbot_plugin.api.entities.builtin.provider import message as provider_message

    request = _requester('openai', 'space-chat-completions')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: True)
    monkeypatch.setattr(request, '_safe_model_info', lambda _: {})
    model = _runtime_model(request, name='gpt-5.6-sol', abilities=['vision', 'func_call'])
    model.provider.token_mgr.get_token = lambda: 'test-only-not-a-secret'
    scoped = reasoning.model_with_reasoning_level(model, 'medium')
    built = await request._build_completion_args(
        scoped, [provider_message.Message(role='user', content='hello')], stream=stream
    )
    assert built['reasoning_effort'] == 'medium'
    assert built.get('stream', False) is stream
    assert model.model_entity.abilities == ['vision', 'func_call']
    assert model.reasoning_config_override is None


def test_space_unknown_model_does_not_gain_reasoning(monkeypatch):
    request = _requester('openai', 'space-chat-completions')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: False)
    monkeypatch.setattr(request, '_safe_model_info', lambda _: {})
    model = _runtime_model(request, name='unknown-model', abilities=[])
    with pytest.raises(ValueError, match='reasoning ability'):
        reasoning.model_with_reasoning_level(model, 'medium')


def test_space_detected_reasoning_still_validates_conflicting_parameters(monkeypatch):
    request = _requester('openai', 'space-chat-completions')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: True)
    model = _runtime_model(request, name='gpt-5.6-sol', abilities=[])
    model.model_entity.extra_args = {'reasoning_effort': 'low'}
    with pytest.raises(ValueError, match='conflicts with advanced parameters'):
        reasoning.model_with_reasoning_level(model, 'medium')
