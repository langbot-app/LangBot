from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.session as provider_session

from langbot.pkg.api.http.service.model import _runtime_model_data
from langbot.pkg.api.http.service.provider import ModelProviderService
from langbot.pkg.entity.persistence import model as persistence_model
from langbot.pkg.pipeline.preproc.preproc import PreProcessor
from langbot.pkg.provider.modelmgr import requester
from langbot.pkg.provider.modelmgr.modelmgr import ModelManager
from langbot.pkg.provider.modelmgr.token import TokenManager
from langbot.pkg.provider.runners.localagent import LocalAgentRunner
from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.workspace.entities import WorkspaceExecutionBinding


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


def test_normalize_space_provider_api_keys_filters_blank_values():
    assert ModelProviderService._normalize_api_keys('space-key') == ['space-key']
    assert ModelProviderService._normalize_api_keys('  trimmed-key  ') == ['trimmed-key']
    assert ModelProviderService._normalize_api_keys('') == []
    assert ModelProviderService._normalize_api_keys('   ') == []
    assert ModelProviderService._normalize_api_keys(None) == []
    assert ModelProviderService._normalize_api_keys([' first-key ', '', 'first-key', 'second-key']) == [
        'first-key',
        'second-key',
    ]


def test_token_manager_filters_blank_and_duplicate_tokens():
    token_mgr = TokenManager('provider-uuid', ['  first-key  ', '', 'first-key', 'second-key', '   '])

    assert token_mgr.tokens == ['first-key', 'second-key']
    assert token_mgr.get_token() == 'first-key'


def test_token_manager_next_token_ignores_empty_token_list():
    token_mgr = TokenManager('provider-uuid', [])

    token_mgr.next_token()

    assert token_mgr.get_token() == ''
    assert token_mgr.using_token_index == 0


@pytest.mark.asyncio
async def test_model_manager_initialize_skips_space_sync_after_timeout():
    ap = SimpleNamespace()
    ap.discover = SimpleNamespace(get_components_by_kind=Mock(return_value=[]))
    ap.instance_config = SimpleNamespace(data={'space': {'models_sync_timeout': 0.01}})
    ap.logger = Mock()
    binding = WorkspaceExecutionBinding(
        instance_uuid='instance-test',
        workspace_uuid='workspace-test',
        placement_generation=1,
        write_fenced=False,
        state='active',
    )
    ap.workspace_service = SimpleNamespace(
        get_local_execution_binding=AsyncMock(return_value=binding),
        get_execution_binding=AsyncMock(return_value=binding),
    )

    mgr = ModelManager(ap)
    mgr.load_models_from_db = AsyncMock()

    async def slow_sync(_context):
        await asyncio.sleep(1)

    mgr.sync_new_models_from_space = AsyncMock(side_effect=slow_sync)

    await mgr.initialize()

    mgr.load_models_from_db.assert_awaited_once()
    mgr.sync_new_models_from_space.assert_awaited_once()
    ap.logger.warning.assert_any_call('LangBot Space model sync timed out after 0.01s, skipping startup sync.')


@pytest.mark.asyncio
async def test_updated_llm_model_is_immediately_usable_by_local_agent_pipeline():
    from langbot.pkg.api.http.service.model import LLMModelsService

    model_uuid = 'qwen-model-uuid'
    provider_uuid = 'ollama-provider-uuid'
    workspace_uuid = 'workspace-test'
    execution_context = ExecutionContext(
        instance_uuid='instance-test',
        workspace_uuid=workspace_uuid,
        placement_generation=1,
        bot_uuid='bot-uuid',
        pipeline_uuid='pipeline-uuid',
    )

    ap = SimpleNamespace()
    ap.logger = Mock()
    ap.persistence_mgr = SimpleNamespace(execute_async=AsyncMock())
    ap.tool_mgr = SimpleNamespace(get_all_tools=AsyncMock(return_value=[]))
    ap.skill_mgr = None  # PreProcessor only uses skill_mgr for the local-agent skill-binding branch
    ap.plugin_connector = SimpleNamespace(
        emit_event=AsyncMock(return_value=SimpleNamespace(event=SimpleNamespace(default_prompt=[], prompt=[])))
    )
    binding = WorkspaceExecutionBinding(
        instance_uuid='instance-test',
        workspace_uuid=workspace_uuid,
        placement_generation=1,
        write_fenced=False,
        state='active',
    )
    ap.workspace_service = SimpleNamespace(get_execution_binding=AsyncMock(return_value=binding))

    ap.model_mgr = ModelManager(ap)
    runtime_provider = Mock(
        execution_context=execution_context,
        provider_entity=persistence_model.ModelProvider(
            workspace_uuid=workspace_uuid,
            uuid=provider_uuid,
            name='Ollama',
            requester='ollama',
            base_url='http://localhost:11434',
            api_keys=[],
        ),
    )
    cache_key = ('instance-test', workspace_uuid, 1, provider_uuid)
    ap.model_mgr.provider_dict = {cache_key: runtime_provider}
    runtime_model = requester.RuntimeLLMModel(
        execution_context=execution_context,
        model_entity=persistence_model.LLMModel(
            workspace_uuid=workspace_uuid,
            uuid=model_uuid,
            name='old-qwen-name',
            provider_uuid=provider_uuid,
            abilities=[],
            extra_args={},
        ),
        provider=runtime_provider,
    )
    ap.model_mgr.llm_model_dict = {
        ('instance-test', workspace_uuid, 1, model_uuid): runtime_model,
    }

    ap.provider_service = SimpleNamespace(
        get_provider=AsyncMock(return_value={'uuid': provider_uuid, 'workspace_uuid': workspace_uuid})
    )
    model_service = LLMModelsService(ap)
    model_service.get_llm_model = AsyncMock(
        return_value={
            'uuid': model_uuid,
            'workspace_uuid': workspace_uuid,
            'name': 'old-qwen-name',
            'provider_uuid': provider_uuid,
            'abilities': [],
            'context_length': None,
            'extra_args': {},
            'prefered_ranking': 0,
        }
    )
    await model_service.update_llm_model(
        workspace_uuid,
        model_uuid,
        {
            'name': 'Qwen3.5-27B',
            'provider_uuid': provider_uuid,
            'abilities': [],
            'extra_args': {},
        },
    )

    runtime_model = await ap.model_mgr.get_model_by_uuid(execution_context, model_uuid)
    assert runtime_model.model_entity.uuid == model_uuid
    assert runtime_model.model_entity.name == 'Qwen3.5-27B'

    session = provider_session.Session(
        instance_uuid='instance-test',
        workspace_uuid=workspace_uuid,
        placement_generation=1,
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id=12345,
        bot_uuid='bot-uuid',
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
        instance_uuid='instance-test',
        workspace_uuid=workspace_uuid,
        placement_generation=1,
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
    object.__setattr__(query, '_execution_context', execution_context)

    result = await PreProcessor(ap).process(query, 'PreProcessor')
    processed_query = result.new_query

    assert processed_query.use_llm_model_uuid == model_uuid

    runner = SimpleNamespace(ap=ap, pipeline_config=pipeline_config)
    candidates = await LocalAgentRunner._get_model_candidates(runner, processed_query)

    assert [model.model_entity.uuid for model in candidates] == [model_uuid]
