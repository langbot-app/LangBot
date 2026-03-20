from __future__ import annotations

import langbot_plugin.api.entities.builtin.provider.message as provider_message

from langbot.pkg.pipeline.process.logging_utils import format_result_log


def cut_str(s: str) -> str:
    s0 = s.split('\n')[0]
    if len(s0) > 20 or '\n' in s:
        s0 = s0[:20] + '...'
    return s0


def test_chat_handler_formats_tool_call_request_log():
    result = provider_message.Message(
        role='assistant',
        content='',
        tool_calls=[
            provider_message.ToolCall(
                id='call-1',
                type='function',
                function=provider_message.FunctionCall(name='sandbox_exec', arguments='{}'),
            )
        ],
    )

    summary = format_result_log(result, cut_str)

    assert summary == 'assistant: requested tools: sandbox_exec'


def test_chat_handler_formats_tool_result_log():
    result = provider_message.Message(
        role='tool',
        content='{"status":"completed","exit_code":0,"backend":"podman","stdout":"42\\n"}',
        tool_call_id='call-1',
    )

    summary = format_result_log(result, cut_str)

    assert summary == 'tool result: status=completed exit_code=0 backend=podman stdout=42'


def test_chat_handler_formats_tool_error_log():
    result = provider_message.MessageChunk(
        role='tool',
        content='err: host_path must point to an existing directory on the host',
        tool_call_id='call-1',
        is_final=True,
    )

    summary = format_result_log(result, cut_str)

    assert summary is not None
    assert summary.startswith('tool error: err: host_path must')
    assert summary.endswith('...')


def test_chat_handler_skips_empty_assistant_log():
    result = provider_message.Message(role='assistant', content='')

    summary = format_result_log(result, cut_str)

    assert summary is None
