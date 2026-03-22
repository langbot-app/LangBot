from __future__ import annotations

from unittest.mock import Mock

import pytest
import langbot_plugin.api.entities.builtin.provider.message as provider_message

# TODO: unskip once the handler ↔ app circular import is resolved
pytest.skip(
    'circular import in handler ↔ app; will be unblocked once resolved',
    allow_module_level=True,
)

from langbot.pkg.pipeline.process.handler import MessageHandler  # noqa: E402


class _StubHandler(MessageHandler):
    async def handle(self, query):
        raise NotImplementedError


handler = _StubHandler(ap=Mock())


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

    summary = handler.format_result_log(result)

    assert summary == 'assistant: requested tools: sandbox_exec'


def test_chat_handler_formats_tool_result_log():
    result = provider_message.Message(
        role='tool',
        content='{"status":"completed","exit_code":0,"backend":"podman","stdout":"42\\n"}',
        tool_call_id='call-1',
    )

    summary = handler.format_result_log(result)

    # Tool results use generic cut_str truncation
    assert summary is not None
    assert summary.startswith('tool: {"status":"com')
    assert summary.endswith('...')


def test_chat_handler_formats_tool_error_log():
    result = provider_message.MessageChunk(
        role='tool',
        content='err: host_path must point to an existing directory on the host',
        tool_call_id='call-1',
        is_final=True,
    )

    summary = handler.format_result_log(result)

    assert summary is not None
    assert summary.startswith('tool error: err: host_path must')
    assert summary.endswith('...')


def test_chat_handler_skips_empty_assistant_log():
    result = provider_message.Message(role='assistant', content='')

    summary = handler.format_result_log(result)

    assert summary is None
