"""Tests for provider test doubles used by integration paths."""

from __future__ import annotations

import pytest

from langbot.pkg.entity.persistence import model as persistence_model
from langbot.pkg.provider.modelmgr import requester
from langbot_plugin.api.entities.builtin.provider import message as provider_message
from langbot_plugin.api.entities.builtin.resource import tool as resource_tool


@pytest.mark.asyncio
async def test_fake_requester_counts_messages_and_tools(runtime_provider):
    """Fake requester should support token-free AgentRunner context budgeting."""
    runtime_model = requester.RuntimeLLMModel(
        model_entity=persistence_model.LLMModel(
            uuid='fake-count-model',
            name='fake-count-model',
            provider_uuid=runtime_provider.provider_entity.uuid,
            abilities=['func_call'],
            extra_args={},
        ),
        provider=runtime_provider,
    )

    async def _placeholder_func(**kwargs):
        return kwargs

    messages = [
        provider_message.Message(role='system', content='You are a test assistant.'),
        provider_message.Message(
            role='user',
            content=[
                provider_message.ContentElement(type='text', text='hello'),
                provider_message.ContentElement(type='text', text=' world'),
            ],
        ),
    ]
    tools = [
        resource_tool.LLMTool(
            name='lookup',
            human_desc='Lookup',
            description='Lookup a value',
            parameters={'type': 'object', 'properties': {'query': {'type': 'string'}}},
            func=_placeholder_func,
        )
    ]

    requester_inst = runtime_provider.requester
    message_tokens = await requester_inst.count_tokens(runtime_model, messages, funcs=[])
    message_and_tool_tokens = await requester_inst.count_tokens(runtime_model, messages, funcs=tools)

    assert message_tokens > 0
    assert message_and_tool_tokens > message_tokens
    assert requester_inst._last_count_tokens_payload[-1]['name'] == 'lookup'
    assert requester_inst._last_count_tokens_payload[1]['content'] == 'hello world'
