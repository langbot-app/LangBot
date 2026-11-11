"""Input counting is independent of generation reasoning policy."""

from unittest.mock import Mock

import pytest
from langbot_plugin.api.entities.builtin.provider.message import Message

from langbot.pkg.provider.modelmgr import errors
from langbot.pkg.provider.modelmgr.requesters import litellmchat
from tests.unit_tests.provider.test_reasoning_control import _requester, _runtime_model


@pytest.mark.asyncio
@pytest.mark.parametrize('abilities', [[], ['reasoning']])
async def test_count_ignores_unsupported_reasoning_without_reading_credentials(monkeypatch, abilities):
    request = _requester('anthropic')
    model = _runtime_model(request, name='claude-sonnet-5', abilities=abilities)
    model.reasoning_config_override = {'level': 'minimal'}
    model.provider.token_mgr.get_token = Mock(side_effect=AssertionError('Counting does not need credentials'))
    counter = Mock(return_value=13)
    monkeypatch.setattr(litellmchat.litellm, 'token_counter', counter)

    assert await request.count_tokens(model, [Message(role='user', content='hello')]) == 13
    assert counter.call_args.kwargs == {
        'model': 'anthropic/claude-sonnet-5',
        'messages': [{'role': 'user', 'content': 'hello'}],
    }
    with pytest.raises(errors.RequesterError):
        request._build_reasoning_args(model)


@pytest.mark.asyncio
async def test_count_preserves_input_overrides(monkeypatch):
    request = _requester('openai')
    model = _runtime_model(request, name='gpt-4o')
    tools = [{'type': 'function', 'function': {'name': 'search', 'parameters': {'type': 'object'}}}]
    model.model_entity.extra_args = {'tools': tools, 'tool_choice': 'auto', 'temperature': 0.2}
    counter = Mock(return_value=37)
    monkeypatch.setattr(litellmchat.litellm, 'token_counter', counter)

    assert await request.count_tokens(model, [], extra_args={'tool_choice': 'none'}) == 37
    assert counter.call_args.kwargs == {'model': 'openai/gpt-4o', 'messages': [], 'tools': tools, 'tool_choice': 'none'}
