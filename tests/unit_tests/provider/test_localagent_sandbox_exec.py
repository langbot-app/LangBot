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
                content='Let me calculate that exactly.',
                tool_calls=[
                    provider_message.ToolCall(
                        id='call-1',
                        type='function',
                        function=provider_message.FunctionCall(
                            name='sandbox_exec',
                            arguments=json.dumps(
                                {
                                    'cmd': (
                                        "python - <<'PY'\n"
                                        "nums = [1, 2, 3, 4]\n"
                                        'print(sum(nums) / len(nums))\n'
                                        'PY'
                                    )
                                }
                            ),
                        ),
                    )
                ],
            )

        tool_result = json.loads(messages[-1].content)
        return provider_message.Message(
            role='assistant',
            content=f"The average is {tool_result['stdout']}.",
        )


class RecordingStreamProvider:
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
                    tool_calls=[
                        provider_message.ToolCall(
                            id='call-1',
                            type='function',
                            function=provider_message.FunctionCall(
                                name='sandbox_exec',
                                arguments=json.dumps({'cmd': "python -c 'print(1)'"}),
                            ),
                        )
                    ],
                    is_final=True,
                )
                return

            yield provider_message.MessageChunk(
                role='assistant',
                content='Tool execution failed.',
                is_final=True,
            )

        return _stream()


def make_query() -> pipeline_query.Query:
    adapter = AsyncMock()
    adapter.is_stream_output_supported = AsyncMock(return_value=False)

    return pipeline_query.Query.model_construct(
        query_id='avg-query',
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
            content='Please calculate the average of 1, 2, 3, and 4.',
        ),
        use_funcs=[SimpleNamespace(name='sandbox_exec')],
        use_llm_model_uuid='test-model-uuid',
        variables={},
    )


@pytest.mark.asyncio
async def test_localagent_uses_sandbox_exec_for_exact_calculation():
    provider = RecordingProvider()
    model = SimpleNamespace(
        provider=provider,
        model_entity=SimpleNamespace(
            uuid='test-model-uuid',
            name='test-model',
            abilities=['func_call'],
            extra_args={},
        ),
    )

    tool_manager = SimpleNamespace(
        execute_func_call=AsyncMock(
            return_value={
                'session_id': 'avg-query',
                'backend': 'podman',
                'status': 'completed',
                'ok': True,
                'exit_code': 0,
                'stdout': '2.5',
                'stderr': '',
                'duration_ms': 18,
            }
        )
    )

    app = SimpleNamespace(
        logger=Mock(),
        model_mgr=SimpleNamespace(get_model_by_uuid=AsyncMock(return_value=model)),
        tool_mgr=tool_manager,
        rag_mgr=SimpleNamespace(),
        instance_config=SimpleNamespace(
            data={
                'box': {
                    'default_host_workspace': '/home/yhh/workspace/box-demo',
                }
            }
        ),
    )

    runner = LocalAgentRunner(app, pipeline_config={})
    query = make_query()

    results = [message async for message in runner.run(query)]

    assert [message.role for message in results] == ['assistant', 'tool', 'assistant']
    assert results[-1].content == 'The average is 2.5.'

    tool_manager.execute_func_call.assert_awaited_once()
    tool_name, tool_parameters = tool_manager.execute_func_call.await_args.args[:2]
    assert tool_name == 'sandbox_exec'
    assert "print(sum(nums) / len(nums))" in tool_parameters['cmd']

    first_request = provider.requests[0]
    assert any(
        message.role == 'system'
        and 'sandbox_exec' in str(message.content)
        and 'exact calculations' in str(message.content)
        and 'Unless the user explicitly asks for the script' in str(message.content)
        and '/workspace' in str(message.content)
        for message in first_request['messages']
    )
    assert [tool.name for tool in first_request['funcs']] == ['sandbox_exec']


@pytest.mark.asyncio
async def test_localagent_streaming_tool_error_yields_message_chunks():
    provider = RecordingStreamProvider()
    model = SimpleNamespace(
        provider=provider,
        model_entity=SimpleNamespace(
            uuid='test-model-uuid',
            name='test-model',
            abilities=['func_call'],
            extra_args={},
        ),
    )

    adapter = AsyncMock()
    adapter.is_stream_output_supported = AsyncMock(return_value=True)

    query = make_query()
    query.adapter = adapter

    app = SimpleNamespace(
        logger=Mock(),
        model_mgr=SimpleNamespace(get_model_by_uuid=AsyncMock(return_value=model)),
        tool_mgr=SimpleNamespace(execute_func_call=AsyncMock(side_effect=RuntimeError('boom'))),
        rag_mgr=SimpleNamespace(),
        instance_config=SimpleNamespace(data={'box': {'default_host_workspace': '/home/yhh/workspace/box-demo'}}),
    )

    runner = LocalAgentRunner(app, pipeline_config={})

    results = [message async for message in runner.run(query)]

    assert all(isinstance(message, provider_message.MessageChunk) for message in results)
    assert any(message.role == 'tool' and message.content == 'err: boom' for message in results)
