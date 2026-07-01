"""Unit tests for provider_specific_fields round-trip in LiteLLMRequester.

This tests the fix for GitHub issue #1899: Gemini requires thought_signature
to be preserved across tool call rounds for function calls to work correctly.
"""

import langbot_plugin.api.entities.builtin.provider.message as provider_message

from langbot.pkg.provider.modelmgr.requesters.litellmchat import LiteLLMRequester


def _make_requester() -> LiteLLMRequester:
    # _convert_messages and _normalize_stream_tool_calls do not touch instance config.
    return LiteLLMRequester.__new__(LiteLLMRequester)


def test_convert_messages_preserves_tool_call_provider_specific_fields():
    """Tool calls should retain provider_specific_fields through _convert_messages."""
    req = _make_requester()
    msg = provider_message.Message(
        role='assistant',
        content=None,
        tool_calls=[
            provider_message.ToolCall(
                id='call_123',
                type='function',
                function=provider_message.FunctionCall(
                    name='search',
                    arguments='{"query": "test"}',
                ),
                provider_specific_fields={
                    'thought_signature': 'c2tpcF90aG91Z2h0X3NpZ25hdHVyZQ==',
                },
            ),
        ],
    )
    out = req._convert_messages([msg])
    assert len(out) == 1
    assert out[0]['tool_calls'] is not None
    assert len(out[0]['tool_calls']) == 1

    tc = out[0]['tool_calls'][0]
    assert tc['id'] == 'call_123'
    assert tc['function']['name'] == 'search'
    assert 'provider_specific_fields' in tc
    assert tc['provider_specific_fields']['thought_signature'] == 'c2tpcF90aG91Z2h0X3NpZ25hdHVyZQ=='


def test_convert_messages_preserves_message_provider_specific_fields():
    """Messages should retain provider_specific_fields through _convert_messages."""
    req = _make_requester()
    msg = provider_message.Message(
        role='assistant',
        content='Hello',
        provider_specific_fields={
            'thought_signatures': ['sig1', 'sig2'],
        },
    )
    out = req._convert_messages([msg])
    assert len(out) == 1
    assert 'provider_specific_fields' in out[0]
    assert out[0]['provider_specific_fields']['thought_signatures'] == ['sig1', 'sig2']


def test_normalize_stream_tool_calls_preserves_provider_specific_fields():
    """Streaming tool calls should retain provider_specific_fields."""
    req = _make_requester()
    tool_call_state: dict[int, dict] = {}

    # Simulate first chunk with id and type
    raw_tool_calls_1 = [
        {
            'index': 0,
            'id': 'call_abc',
            'type': 'function',
            'function': {
                'name': 'get_weather',
                'arguments': '',
            },
            'provider_specific_fields': {
                'thought_signature': 'dGVzdF9zaWduYXR1cmU=',
            },
        },
    ]
    result_1 = req._normalize_stream_tool_calls(raw_tool_calls_1, tool_call_state)
    assert result_1 is not None
    assert len(result_1) == 1
    assert result_1[0]['provider_specific_fields']['thought_signature'] == 'dGVzdF9zaWduYXR1cmU='

    # Simulate second chunk without provider_specific_fields (should be retained from state)
    raw_tool_calls_2 = [
        {
            'index': 0,
            'function': {
                'arguments': '{"city": "Tokyo"}',
            },
        },
    ]
    result_2 = req._normalize_stream_tool_calls(raw_tool_calls_2, tool_call_state)
    assert result_2 is not None
    assert len(result_2) == 1
    # Should retain the provider_specific_fields from the first chunk
    assert result_2[0]['provider_specific_fields']['thought_signature'] == 'dGVzdF9zaWduYXR1cmU='
    assert result_2[0]['function']['arguments'] == '{"city": "Tokyo"}'


def test_normalize_stream_tool_calls_merges_function_level_psf():
    """Function-level provider_specific_fields should be merged into tool-level."""
    req = _make_requester()
    tool_call_state: dict[int, dict] = {}

    raw_tool_calls = [
        {
            'index': 0,
            'id': 'call_xyz',
            'type': 'function',
            'function': {
                'name': 'search',
                'arguments': '{}',
                'provider_specific_fields': {
                    'thought_signature': 'ZnVuY19sZXZlbF9zaWc=',
                },
            },
        },
    ]
    result = req._normalize_stream_tool_calls(raw_tool_calls, tool_call_state)
    assert result is not None
    assert result[0]['provider_specific_fields']['thought_signature'] == 'ZnVuY19sZXZlbF9zaWc='


def test_tool_call_roundtrip_through_message_entity():
    """Full round-trip: LiteLLM response dict -> Message entity -> _convert_messages."""
    # Simulate what LiteLLM returns for a Gemini tool call response
    message_data = {
        'role': 'assistant',
        'content': None,
        'tool_calls': [
            {
                'id': 'call_gemini_123',
                'type': 'function',
                'function': {
                    'name': 'web_search',
                    'arguments': '{"query": "test"}',
                },
                'provider_specific_fields': {
                    'thought_signature': 'Z2VtaW5pX3NpZ25hdHVyZQ==',
                },
            },
        ],
        'provider_specific_fields': {
            'thought_signatures': ['Z2VtaW5pX3NpZ25hdHVyZQ=='],
        },
    }

    # Parse into Message entity (this is what invoke_llm does)
    msg = provider_message.Message(**message_data)

    # Verify the entity has the fields
    assert msg.tool_calls is not None
    assert len(msg.tool_calls) == 1
    assert msg.tool_calls[0].provider_specific_fields is not None
    assert msg.tool_calls[0].provider_specific_fields['thought_signature'] == 'Z2VtaW5pX3NpZ25hdHVyZQ=='
    assert msg.provider_specific_fields is not None
    assert msg.provider_specific_fields['thought_signatures'] == ['Z2VtaW5pX3NpZ25hdHVyZQ==']

    # Convert back to dict for LiteLLM (this is what _convert_messages does)
    req = _make_requester()
    out = req._convert_messages([msg])

    # Verify the fields are preserved in the output
    assert out[0]['tool_calls'][0]['provider_specific_fields']['thought_signature'] == 'Z2VtaW5pX3NpZ25hdHVyZQ=='
    assert out[0]['provider_specific_fields']['thought_signatures'] == ['Z2VtaW5pX3NpZ25hdHVyZQ==']
