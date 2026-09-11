from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.builtin.provider.session as provider_session

from langbot.pkg.api.http.context import ExecutionContext
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
        return provider_message.Message(role='assistant', content='fallback answer')


def _make_query(policy: str | None = None) -> pipeline_query.Query:
    adapter = AsyncMock()
    adapter.is_stream_output_supported = AsyncMock(return_value=False)

    local_agent_config = {
        'model': {'primary': 'test-model-uuid', 'fallbacks': []},
        'prompt': 'test-prompt',
    }
    if policy is not None:
        local_agent_config['knowledge-retrieval-error-policy'] = policy

    query = pipeline_query.Query.model_construct(
        query_id='knowledge-fallback-query',
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
                'local-agent': local_agent_config,
            },
            'output': {'misc': {'remove-think': False}},
        },
        prompt=SimpleNamespace(messages=[]),
        messages=[],
        user_message=provider_message.Message(
            role='user',
            content=[provider_message.ContentElement.from_text('hello knowledge')],
        ),
        use_funcs=[],
        use_llm_model_uuid='test-model-uuid',
        variables={'_knowledge_base_uuids': ['kb-1']},
        session=SimpleNamespace(
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=12345,
        ),
    )
    object.__setattr__(
        query,
        '_execution_context',
        ExecutionContext(
            instance_uuid='instance-test',
            workspace_uuid='workspace-test',
            placement_generation=1,
            bot_uuid='bot-uuid',
            pipeline_uuid='pipeline-uuid',
            query_uuid='query-knowledge-fallback',
        ),
    )
    object.__setattr__(query, 'query_uuid', 'query-knowledge-fallback')
    return query


def _make_app(provider: RecordingProvider) -> SimpleNamespace:
    model = SimpleNamespace(
        provider=provider,
        model_entity=SimpleNamespace(
            uuid='test-model-uuid',
            name='test-model',
            abilities=[],
            extra_args={},
        ),
    )
    kb = SimpleNamespace(
        get_knowledge_engine_plugin_id=Mock(return_value='langbot-team/LangRAG'),
        retrieve=AsyncMock(side_effect=RuntimeError('embedding unavailable')),
    )
    return SimpleNamespace(
        logger=Mock(),
        model_mgr=SimpleNamespace(get_model_by_uuid=AsyncMock(return_value=model)),
        tool_mgr=SimpleNamespace(),
        rag_mgr=SimpleNamespace(get_knowledge_base_by_uuid=AsyncMock(return_value=kb)),
        box_service=None,
        skill_mgr=SimpleNamespace(
            get_skills_for_pipeline=AsyncMock(return_value=[]),
            detect_skill_activation=AsyncMock(return_value=None),
            build_activation_prompt=Mock(return_value=None),
        ),
    )


@pytest.mark.asyncio
async def test_localagent_knowledge_retrieval_error_fails_by_default():
    provider = RecordingProvider()
    app = _make_app(provider)
    runner = LocalAgentRunner(app, pipeline_config={})
    query = _make_query()

    with pytest.raises(RuntimeError, match='embedding unavailable'):
        [message async for message in runner.run(query)]

    assert provider.requests == []


@pytest.mark.asyncio
async def test_localagent_can_continue_when_knowledge_retrieval_fails():
    provider = RecordingProvider()
    app = _make_app(provider)
    runner = LocalAgentRunner(app, pipeline_config={})
    query = _make_query(policy='continue')

    results = [message async for message in runner.run(query)]

    assert [message.content for message in results] == ['fallback answer']
    app.logger.warning.assert_called_once()
    request_user_message = provider.requests[0]['messages'][-1]
    assert request_user_message.content[0].text == 'hello knowledge'
