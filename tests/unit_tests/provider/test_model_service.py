from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.session as provider_session

from langbot.pkg.api.http.service.model import _runtime_model_data
from langbot.pkg.entity.persistence import model as persistence_model
from langbot.pkg.pipeline.preproc.preproc import PreProcessor
from langbot.pkg.provider.modelmgr import requester
from langbot.pkg.provider.modelmgr.modelmgr import ModelManager
from langbot.pkg.provider.runners.localagent import LocalAgentRunner


def test_runtime_llm_model_data_preserves_uuid_after_update_payload_uuid_removed():
    update_payload = {
        'name': 'Qwen3.5-27B',
        'provider_uuid': 'provider-uuid',
        'abilities': [],
        'extra_args': {},
    }

    runtime_entity = persistence_model.LLMModel(**_runtime_model_data('model-uuid', update_payload))

    assert runtime_entity.uuid == 'model-uuid'
    assert runtime_entity.name == 'Qwen3.5-27B'


def test_runtime_embedding_model_data_preserves_uuid_after_update_payload_uuid_removed():
    update_payload = {
        'name': 'embedding-model',
        'provider_uuid': 'provider-uuid',
        'extra_args': {},
    }

    runtime_entity = persistence_model.EmbeddingModel(**_runtime_model_data('embedding-uuid', update_payload))

    assert runtime_entity.uuid == 'embedding-uuid'
    assert runtime_entity.name == 'embedding-model'


def test_runtime_rerank_model_data_preserves_uuid_after_update_payload_uuid_removed():
    update_payload = {
        'name': 'rerank-model',
        'provider_uuid': 'provider-uuid',
        'extra_args': {},
    }

    runtime_entity = persistence_model.RerankModel(**_runtime_model_data('rerank-uuid', update_payload))

    assert runtime_entity.uuid == 'rerank-uuid'
    assert runtime_entity.name == 'rerank-model'


@pytest.mark.asyncio
async def test_updated_llm_model_is_immediately_usable_by_local_agent_pipeline():
    from langbot.pkg.api.http.service.model import LLMModelsService

    model_uuid = 'qwen-model-uuid'
    provider_uuid = 'ollama-provider-uuid'

    ap = SimpleNamespace()
    ap.logger = Mock()
    ap.persistence_mgr = SimpleNamespace(execute_async=AsyncMock())
    ap.tool_mgr = SimpleNamespace(get_all_tools=AsyncMock(return_value=[]))
    ap.plugin_connector = SimpleNamespace(
        emit_event=AsyncMock(return_value=SimpleNamespace(event=SimpleNamespace(default_prompt=[], prompt=[])))
    )

    ap.model_mgr = ModelManager(ap)
    runtime_provider = Mock()
    ap.model_mgr.provider_dict = {provider_uuid: runtime_provider}
    ap.model_mgr.llm_models = [
        requester.RuntimeLLMModel(
            model_entity=persistence_model.LLMModel(
                uuid=model_uuid,
                name='old-qwen-name',
                provider_uuid=provider_uuid,
                abilities=[],
                extra_args={},
            ),
            provider=runtime_provider,
        )
    ]

    await LLMModelsService(ap).update_llm_model(
        model_uuid,
        {
            'name': 'Qwen3.5-27B',
            'provider_uuid': provider_uuid,
            'abilities': [],
            'extra_args': {},
        },
    )

    runtime_model = await ap.model_mgr.get_model_by_uuid(model_uuid)
    assert runtime_model.model_entity.uuid == model_uuid
    assert runtime_model.model_entity.name == 'Qwen3.5-27B'

    session = SimpleNamespace(
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id=12345,
    )
    conversation = SimpleNamespace(
        uuid='conversation-uuid',
        create_time=None,
        update_time=None,
        prompt=SimpleNamespace(messages=[], copy=Mock(return_value=SimpleNamespace(messages=[]))),
        messages=[],
    )
    ap.sess_mgr = SimpleNamespace(
        get_session=AsyncMock(return_value=session),
        get_conversation=AsyncMock(return_value=conversation),
    )

    message_chain = platform_message.MessageChain([platform_message.Plain(text='hello')])
    sender = platform_entities.Friend(id=12345, nickname='Tester', remark=None)
    message_event = platform_events.FriendMessage(
        type='FriendMessage',
        sender=sender,
        message_chain=message_chain,
        time=1710000000,
    )
    pipeline_config = {
        'ai': {
            'runner': {'runner': 'local-agent'},
            'local-agent': {
                'model': {'primary': model_uuid, 'fallbacks': []},
                'prompt': [],
                'knowledge-bases': [],
            },
        },
        'trigger': {'misc': {'combine-quote-message': False}},
        'output': {'misc': {'remove-think': False}},
    }
    query = pipeline_query.Query.model_construct(
        query_id='query-id',
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id=12345,
        sender_id=12345,
        message_chain=message_chain,
        message_event=message_event,
        adapter=AsyncMock(),
        pipeline_uuid='pipeline-uuid',
        bot_uuid='bot-uuid',
        pipeline_config=pipeline_config,
        session=None,
        prompt=None,
        messages=[],
        user_message=None,
        use_funcs=[],
        use_llm_model_uuid=None,
        variables={},
        resp_messages=[],
        resp_message_chain=None,
        current_stage_name=None,
    )

    result = await PreProcessor(ap).process(query, 'PreProcessor')
    processed_query = result.new_query

    assert processed_query.use_llm_model_uuid == model_uuid

    candidates = await LocalAgentRunner(ap, pipeline_config)._get_model_candidates(processed_query)

    assert [model.model_entity.uuid for model in candidates] == [model_uuid]
