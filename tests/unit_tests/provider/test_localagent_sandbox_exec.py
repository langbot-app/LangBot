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
                            name='exec',
                            arguments=json.dumps(
                                {'command': ("python - <<'PY'\nnums = [1, 2, 3, 4]\nprint(sum(nums) / len(nums))\nPY")}
                            ),
                        ),
                    )
                ],
            )

        tool_result = json.loads(messages[-1].content)
        return provider_message.Message(
            role='assistant',
            content=f'The average is {tool_result["stdout"]}.',
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
                                name='exec',
                                arguments=json.dumps({'command': "python -c 'print(1)'"}),
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


class ActivationProvider:
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
                content='[ACTIVATE_SKILL: demo]\nI will use the skill.',
            )
        return provider_message.Message(
            role='assistant',
            content='final answer after activation',
        )


class FailingActivationProvider:
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
                content='[ACTIVATE_SKILL: demo]\nI will use the skill.',
            )
        raise RuntimeError('activation failed')


class ActivationStreamProvider:
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
                    content='[ACTIVATE_SKILL: demo]\nI will use the skill.',
                    is_final=True,
                )
                return

            yield provider_message.MessageChunk(
                role='assistant',
                content='final answer after activation',
                is_final=True,
            )

        return _stream()


def make_skill_manager():
    skill_data = {
        'uuid': 'skill-demo',
        'name': 'demo',
        'instructions': 'Do the demo task.',
        'type': 'skill',
        'package_root': '/tmp/demo-skill',
        'sandbox_timeout_sec': 120,
        'sandbox_network': False,
    }
    return SimpleNamespace(
        SKILL_ACTIVATION_MARKER='[ACTIVATE_SKILL:',
        detect_skill_activations=Mock(
            side_effect=lambda content: ['demo'] if '[ACTIVATE_SKILL: demo]' in (content or '') else []
        ),
        build_activation_prompt_for_skills=Mock(return_value='skill prompt'),
        get_skill_by_name=Mock(side_effect=lambda name: skill_data if name == 'demo' else None),
        remove_activation_marker=Mock(side_effect=lambda content: (content or '').replace('[ACTIVATE_SKILL: demo]\n', '')),
    )


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
        use_funcs=[SimpleNamespace(name='exec')],
        use_llm_model_uuid='test-model-uuid',
        variables={},
    )


@pytest.mark.asyncio
async def test_localagent_uses_exec_for_exact_calculation():
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
        box_service=SimpleNamespace(
            get_system_guidance=Mock(
                return_value=(
                    'When the exec tool is available, use it for exact calculations, statistics, '
                    'structured data parsing, and code execution instead of estimating mentally. '
                    'Unless the user explicitly asks for the script, code, or implementation details, '
                    'do not include the generated script in the final answer. '
                    'A default workspace is mounted at /workspace for file tasks.'
                )
            ),
        ),
        skill_mgr=SimpleNamespace(
            get_skills_for_pipeline=AsyncMock(return_value=[]),
            detect_skill_activation=AsyncMock(return_value=None),
            build_activation_prompt=Mock(return_value=None),
        ),
    )

    runner = LocalAgentRunner(app, pipeline_config={})
    query = make_query()

    results = [message async for message in runner.run(query)]

    assert [message.role for message in results] == ['assistant', 'tool', 'assistant']
    assert results[-1].content == 'The average is 2.5.'

    tool_manager.execute_func_call.assert_awaited_once()
    tool_name, tool_parameters = tool_manager.execute_func_call.await_args.args[:2]
    assert tool_name == 'exec'
    assert 'print(sum(nums) / len(nums))' in tool_parameters['command']

    first_request = provider.requests[0]
    assert any(
        message.role == 'system'
        and 'exec' in str(message.content)
        and 'exact calculations' in str(message.content)
        and 'Unless the user explicitly asks for the script' in str(message.content)
        and '/workspace' in str(message.content)
        for message in first_request['messages']
    )
    assert [tool.name for tool in first_request['funcs']] == ['exec']


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
        box_service=SimpleNamespace(
            get_system_guidance=Mock(return_value='sandbox guidance'),
        ),
        skill_mgr=SimpleNamespace(
            get_skills_for_pipeline=AsyncMock(return_value=[]),
            detect_skill_activation=AsyncMock(return_value=None),
            build_activation_prompt=Mock(return_value=None),
        ),
    )

    runner = LocalAgentRunner(app, pipeline_config={})

    results = [message async for message in runner.run(query)]

    assert all(isinstance(message, provider_message.MessageChunk) for message in results)
    assert any(message.role == 'tool' and message.content == 'err: boom' for message in results)


@pytest.mark.asyncio
async def test_localagent_hides_activation_marker_before_follow_up_request():
    provider = ActivationProvider()
    model = SimpleNamespace(
        provider=provider,
        model_entity=SimpleNamespace(
            uuid='test-model-uuid',
            name='test-model',
            abilities=['func_call'],
            extra_args={},
        ),
    )

    app = SimpleNamespace(
        logger=Mock(),
        model_mgr=SimpleNamespace(get_model_by_uuid=AsyncMock(return_value=model)),
        tool_mgr=SimpleNamespace(execute_func_call=AsyncMock()),
        rag_mgr=SimpleNamespace(),
        box_service=SimpleNamespace(get_system_guidance=Mock(return_value='sandbox guidance')),
        skill_mgr=make_skill_manager(),
    )

    runner = LocalAgentRunner(app, pipeline_config={})
    query = make_query()
    query.use_funcs = []

    results = [message async for message in runner.run(query)]

    assert [(message.role, message.content) for message in results] == [
        ('assistant', 'final answer after activation')
    ]
    assert len(provider.requests) == 2
    assert provider.requests[1]['messages'][-2].content == 'I will use the skill.'
    assert '[ACTIVATE_SKILL:' not in provider.requests[1]['messages'][-2].content


@pytest.mark.asyncio
async def test_localagent_activation_failure_rolls_back_query_state_and_sanitizes_response():
    provider = FailingActivationProvider()
    model = SimpleNamespace(
        provider=provider,
        model_entity=SimpleNamespace(
            uuid='test-model-uuid',
            name='test-model',
            abilities=['func_call'],
            extra_args={},
        ),
    )

    app = SimpleNamespace(
        logger=Mock(),
        model_mgr=SimpleNamespace(get_model_by_uuid=AsyncMock(return_value=model)),
        tool_mgr=SimpleNamespace(execute_func_call=AsyncMock()),
        rag_mgr=SimpleNamespace(),
        box_service=SimpleNamespace(get_system_guidance=Mock(return_value='sandbox guidance')),
        skill_mgr=make_skill_manager(),
    )

    runner = LocalAgentRunner(app, pipeline_config={})
    query = make_query()
    query.use_funcs = []

    results = [message async for message in runner.run(query)]

    assert [(message.role, message.content) for message in results] == [
        ('assistant', 'I will use the skill.')
    ]
    assert query.use_funcs == []
    assert query.variables == {}


@pytest.mark.asyncio
async def test_localagent_streaming_activation_does_not_leak_marker():
    provider = ActivationStreamProvider()
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

    app = SimpleNamespace(
        logger=Mock(),
        model_mgr=SimpleNamespace(get_model_by_uuid=AsyncMock(return_value=model)),
        tool_mgr=SimpleNamespace(execute_func_call=AsyncMock()),
        rag_mgr=SimpleNamespace(),
        box_service=SimpleNamespace(get_system_guidance=Mock(return_value='sandbox guidance')),
        skill_mgr=make_skill_manager(),
    )

    runner = LocalAgentRunner(app, pipeline_config={})
    query = make_query()
    query.adapter = adapter
    query.use_funcs = []

    results = [message async for message in runner.run(query)]

    assert all(isinstance(message, provider_message.MessageChunk) for message in results)
    assert [message.content for message in results] == ['final answer after activation']
