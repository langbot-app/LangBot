from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.builtin.provider.session as provider_session

from langbot.pkg.provider.runners.localagent import LocalAgentRunner


class RecordingProvider:
    """Non-streaming provider that returns a tool-call on round 1 and plain text on round 2."""

    def __init__(self):
        self.requests: list[dict] = []

    async def invoke_llm(self, query, model, messages, funcs, extra_args=None, remove_think=None):
        self.requests.append(
            {
                'messages': list(messages),
                'funcs': list(funcs),
                'remove_think': remove_think,
            }
        )

        if len(self.requests) == 1:
            return provider_message.Message(
                role='assistant',
                content='Let me check that.',
                tool_calls=[
                    provider_message.ToolCall(
                        id='call-1',
                        type='function',
                        function=provider_message.FunctionCall(
                            name='exec',
                            arguments=json.dumps({'command': "python -c 'print(42)'"}),
                        ),
                    )
                ],
            )

        return provider_message.Message(
            role='assistant',
            content='The result is 42.',
        )


class RecordingStreamProvider:
    """Streaming provider that returns a tool-call on round 1 and plain text on round 2."""

    def __init__(self):
        self.stream_requests: list[dict] = []

    def invoke_llm_stream(self, query, model, messages, funcs, extra_args=None, remove_think=None):
        self.stream_requests.append(
            {
                'messages': list(messages),
                'funcs': list(funcs),
                'remove_think': remove_think,
            }
        )

        async def _stream():
            if len(self.stream_requests) == 1:
                yield provider_message.MessageChunk(
                    role='assistant',
                    content='Let me check that.',
                    tool_calls=[
                        provider_message.ToolCall(
                            id='call-1',
                            type='function',
                            function=provider_message.FunctionCall(
                                name='exec',
                                arguments=json.dumps({'command': "python -c 'print(42)'"}),
                            ),
                        )
                    ],
                    is_final=True,
                )
                return

            yield provider_message.MessageChunk(
                role='assistant',
                content='The result is 42.',
                is_final=True,
            )

        return _stream()


def make_query() -> pipeline_query.Query:
    adapter = AsyncMock()
    adapter.is_stream_output_supported = AsyncMock(return_value=False)

    return pipeline_query.Query.model_construct(
        query_id='no-dup-query',
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id=12345,
        sender_id=12345,
        message_chain=[],
        message_event=None,
        adapter=adapter,
        pipeline_uuid='pipeline-uuid',
        bot_uuid='bot-uuid',
        pipeline_config={
            'ai': {
                'runner': {'runner': 'local-agent'},
                'local-agent': {'model': {'primary': 'test-model-uuid', 'fallbacks': []}, 'prompt': 'test-prompt'},
            },
            'output': {'misc': {'remove-think': False}},
        },
        prompt=SimpleNamespace(messages=[]),
        messages=[],
        user_message=provider_message.Message(
            role='user',
            content='What is the answer?',
        ),
        use_funcs=[SimpleNamespace(name='exec')],
        use_llm_model_uuid='test-model-uuid',
        variables={},
    )


def _make_app(provider) -> SimpleNamespace:
    model = SimpleNamespace(
        provider=provider,
        model_entity=SimpleNamespace(
            uuid='test-model-uuid',
            name='test-model',
            abilities=['func_call'],
            extra_args={},
        ),
    )
    return SimpleNamespace(
        logger=Mock(),
        model_mgr=SimpleNamespace(get_model_by_uuid=AsyncMock(return_value=model)),
        tool_mgr=SimpleNamespace(
            execute_func_call=AsyncMock(
                return_value={
                    'session_id': 'no-dup-query',
                    'backend': 'podman',
                    'status': 'completed',
                    'ok': True,
                    'exit_code': 0,
                    'stdout': '42',
                    'stderr': '',
                    'duration_ms': 10,
                }
            )
        ),
        rag_mgr=SimpleNamespace(),
        box_service=SimpleNamespace(
            get_system_guidance=Mock(return_value='sandbox guidance'),
        ),
        skill_mgr=SimpleNamespace(
            get_skills_for_pipeline=AsyncMock(return_value=[]),
            detect_skill_activation=AsyncMock(return_value=None),
            build_activation_prompt=Mock(return_value=None),
        ),
    )


@pytest.mark.asyncio
async def test_localagent_non_streaming_no_duplicate():
    """Non-streaming: round-2 content must not contain round-1 text."""
    provider = RecordingProvider()
    app = _make_app(provider)

    runner = LocalAgentRunner(app, pipeline_config={})
    query = make_query()

    results = [message async for message in runner.run(query)]

    # Expect: assistant (tool call) -> tool -> assistant (final answer)
    assert [message.role for message in results] == ['assistant', 'tool', 'assistant']

    final_message = results[-1]
    assert final_message.content == 'The result is 42.'
    assert 'Let me check that.' not in final_message.content


@pytest.mark.asyncio
async def test_localagent_streaming_no_duplicate():
    """Streaming: round-2 content must not be re-seeded with round-1 text.

    Regression test for the bug where _StreamAccumulator was initialized with
    initial_content=first_content, causing every subsequent round to repeat
    the entire opening line.
    """
    provider = RecordingStreamProvider()
    app = _make_app(provider)

    adapter = AsyncMock()
    adapter.is_stream_output_supported = AsyncMock(return_value=True)

    query = make_query()
    query.adapter = adapter

    runner = LocalAgentRunner(app, pipeline_config={})

    results = [message async for message in runner.run(query)]

    # All yielded messages should be MessageChunk in streaming mode
    assert all(isinstance(message, provider_message.MessageChunk) for message in results)

    # The last assistant chunk is the final answer for round 2
    assistant_chunks = [m for m in results if m.role == 'assistant']
    assert len(assistant_chunks) >= 2

    final_chunk = assistant_chunks[-1]
    assert final_chunk.content == 'The result is 42.'
    assert 'Let me check that.' not in final_chunk.content
