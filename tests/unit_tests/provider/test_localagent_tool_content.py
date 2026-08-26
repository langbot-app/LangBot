"""Regression tests for tool-message content serialization (#2457).

MCP tools return ``list[ContentElement]`` from ``execute_func_call``.
The runner must serialize that list to a string before placing it in a
``role='tool'`` message, because the OpenAI chat-completions spec
requires tool-message content to be a string. Sending the raw list
causes OpenAI-compatible endpoints to return HTTP 500.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.builtin.provider.session as provider_session

from langbot.pkg.api.http.context import ExecutionContext, PrincipalContext, PrincipalType
from langbot.pkg.provider.runners.localagent import LocalAgentRunner


class _ToolCallProvider:
    """Non-streaming provider: round 1 issues a tool call, round 2 returns text."""

    def __init__(self):
        self.requests: list[dict] = []

    async def invoke_llm(self, query, model, messages, funcs, extra_args=None, remove_think=None):
        self.requests.append({'messages': list(messages)})

        if len(self.requests) == 1:
            return provider_message.Message(
                role='assistant',
                content='Let me search that.',
                tool_calls=[
                    provider_message.ToolCall(
                        id='call-mcp-1',
                        type='function',
                        function=provider_message.FunctionCall(
                            name='duckduckgo_search',
                            arguments=json.dumps({'query': 'swift'}),
                        ),
                    )
                ],
            )

        return provider_message.Message(role='assistant', content='Done.')


class _ToolCallStreamProvider:
    """Streaming variant of _ToolCallProvider."""

    def __init__(self):
        self.requests: list[dict] = []

    def invoke_llm_stream(self, query, model, messages, funcs, extra_args=None, remove_think=None):
        self.requests.append({'messages': list(messages)})

        async def _stream():
            if len(self.requests) == 1:
                yield provider_message.MessageChunk(
                    role='assistant',
                    content='Let me search that.',
                    tool_calls=[
                        provider_message.ToolCall(
                            id='call-mcp-1',
                            type='function',
                            function=provider_message.FunctionCall(
                                name='duckduckgo_search',
                                arguments=json.dumps({'query': 'swift'}),
                            ),
                        )
                    ],
                    is_final=True,
                )
                return

            yield provider_message.MessageChunk(
                role='assistant',
                content='Done.',
                is_final=True,
            )

        return _stream()


def _make_query(stream: bool = False) -> pipeline_query.Query:
    adapter = AsyncMock()
    adapter.is_stream_output_supported = AsyncMock(return_value=stream)

    query = pipeline_query.Query.model_construct(
        query_id='mcp-tool-query',
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
        user_message=provider_message.Message(role='user', content='search swift'),
        use_funcs=[SimpleNamespace(name='duckduckgo_search')],
        use_llm_model_uuid='test-model-uuid',
        variables={},
    )
    object.__setattr__(
        query,
        '_execution_context',
        ExecutionContext(
            instance_uuid='instance-test',
            workspace_uuid='workspace-test',
            placement_generation=1,
            trigger_principal=PrincipalContext(PrincipalType.SYSTEM),
        ),
    )
    return query


def _make_app(provider, func_ret) -> SimpleNamespace:
    """Build a minimal app whose tool_mgr returns *func_ret*."""
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
        tool_mgr=SimpleNamespace(execute_func_call=AsyncMock(return_value=func_ret)),
        rag_mgr=SimpleNamespace(),
        box_service=SimpleNamespace(get_system_guidance=Mock(return_value='sandbox guidance')),
        skill_mgr=SimpleNamespace(
            get_skills_for_pipeline=AsyncMock(return_value=[]),
            detect_skill_activation=AsyncMock(return_value=None),
            build_activation_prompt=Mock(return_value=None),
        ),
    )


# The actual shape returned by MCP tools: a list of ContentElement objects.
_MCP_FUNC_RET = [
    provider_message.ContentElement.from_text('Title: Swift - Wikipedia\nURL: https://en.wikipedia.org/wiki/Swift'),
    provider_message.ContentElement.from_text('Title: Swift Programming Language\nURL: https://swift.org'),
]


@pytest.mark.asyncio
async def test_tool_message_content_is_string_not_list():
    """Non-streaming: tool message content must be a string (#2457).

    Before the fix, ``func_ret`` (a ``list[ContentElement]``) was assigned
    to ``tool_content`` as-is, so the tool message carried a list instead
    of a string, causing OpenAI-compatible APIs to return 500.
    """
    provider = _ToolCallProvider()
    app = _make_app(provider, _MCP_FUNC_RET)
    runner = LocalAgentRunner(app, pipeline_config={})
    query = _make_query(stream=False)

    results = [msg async for msg in runner.run(query)]

    tool_msgs = [m for m in results if m.role == 'tool']
    assert len(tool_msgs) == 1

    # The content must be a string, not a list.
    assert isinstance(tool_msgs[0].content, str), (
        f'tool message content should be str, got {type(tool_msgs[0].content).__name__}'
    )
    # And it should contain the text of both ContentElements.
    assert 'Swift - Wikipedia' in tool_msgs[0].content
    assert 'Swift Programming Language' in tool_msgs[0].content


@pytest.mark.asyncio
async def test_tool_message_content_is_string_in_stream():
    """Streaming: same regression check for the streaming path (#2457)."""
    provider = _ToolCallStreamProvider()
    app = _make_app(provider, _MCP_FUNC_RET)
    runner = LocalAgentRunner(app, pipeline_config={})
    query = _make_query(stream=True)

    results = [msg async for msg in runner.run(query)]

    tool_msgs = [m for m in results if m.role == 'tool']
    assert len(tool_msgs) == 1

    assert isinstance(tool_msgs[0].content, str), (
        f'tool message content should be str, got {type(tool_msgs[0].content).__name__}'
    )
    assert 'Swift - Wikipedia' in tool_msgs[0].content
    assert 'Swift Programming Language' in tool_msgs[0].content
