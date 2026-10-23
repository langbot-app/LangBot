"""Real resource services and SQLite; only external runtime caches are stubbed."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa

from langbot.pkg.api.application import ApplicationAPIException
from langbot.pkg.api.authz import Permission
from langbot.pkg.api.http.service.knowledge import KnowledgeService
from langbot.pkg.api.http.service.model import EmbeddingModelsService, LLMModelsService, RerankModelsService
from langbot.pkg.api.http.service.pipeline import PipelineService
from langbot.pkg.api.http.service.provider import ModelProviderService
from langbot.pkg.entity.persistence.model import EmbeddingModel, LLMModel, ModelProvider, RerankModel
from langbot.pkg.entity.persistence.pipeline import LegacyPipeline
from langbot.pkg.entity.persistence.rag import KnowledgeBase
from langbot.pkg.rag.knowledge.kbmgr import RAGManager
from tests.integration.api.test_application_foundation import context, foundation  # noqa: F401


@pytest.fixture
async def resources(foundation):  # noqa: F811 - pytest resolves the imported fixture by name.
    api, ap, engine = foundation
    runtime_provider = SimpleNamespace(provider_entity=SimpleNamespace(requester='test-requester'))
    ap.model_mgr = SimpleNamespace(
        load_provider=AsyncMock(return_value=runtime_provider),
        cache_provider=AsyncMock(),
        reload_provider=AsyncMock(),
        get_provider_by_uuid=AsyncMock(return_value=runtime_provider),
        get_available_requester_manifest_by_name=lambda name: SimpleNamespace(
            spec={'support_type': ['llm', 'text-embedding', 'rerank']}
        ),
        llm_model_dict={},
    )
    for family in ('llm', 'embedding', 'rerank'):
        setattr(ap.model_mgr, f'load_{family}_model_with_provider', AsyncMock())
        setattr(ap.model_mgr, f'cache_{family}_model', AsyncMock())
        setattr(ap.model_mgr, f'remove_{family}_model', AsyncMock())
    ap.provider_service = ModelProviderService(ap)
    ap.llm_model_service = LLMModelsService(ap)
    ap.embedding_models_service = EmbeddingModelsService(ap)
    ap.rerank_models_service = RerankModelsService(ap)
    ap.pipeline_service = PipelineService(ap)
    ap.pipeline_mgr = SimpleNamespace(load_pipeline=AsyncMock(), remove_pipeline=AsyncMock())
    ap.ver_mgr = SimpleNamespace(get_current_version=lambda: 'test-foundation')
    ap.sess_mgr = SimpleNamespace(session_list=[])
    ap.plugin_connector = SimpleNamespace(is_enable_plugin=False)
    ap.rag_mgr = RAGManager(ap)
    ap.knowledge_service = KnowledgeService(ap)
    return api, ap, engine


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('family', 'table'), [('llm', LLMModel), ('embedding', EmbeddingModel), ('rerank', RerankModel)]
)
async def test_provider_models_sql_ownership_and_secret_round_trip(resources, family, table):
    api, _, engine = resources
    provider = await api.execute(
        'provider.create',
        context(),
        {
            'provider_data': {
                'name': 'provider',
                'requester': 'test-requester',
                'base_url': 'https://example.test/v1',
                'api_keys': ['secret-key'],
                'workspace_uuid': 'workspace-b',
            }
        },
    )
    model = await api.execute(
        f'model.{family}.create',
        context(),
        {
            'model_data': {
                'name': 'model',
                'provider_uuid': provider,
                'extra_args': {'api_key': 'model-secret'},
                'workspace_uuid': 'workspace-b',
            }
        },
    )
    reader = context(permissions={Permission.RESOURCE_VIEW})
    visible = await api.execute(f'model.{family}.get', reader, {'model_uuid': model})
    assert visible['extra_args']['api_key'] == '***'
    assert visible['provider']['api_keys'] == ['***']
    with pytest.raises(ApplicationAPIException) as denied:
        await api.execute(f'model.{family}.get', reader, {'model_uuid': model, 'include_secret': True})
    assert denied.value.error.code == 'permission_denied'
    for operation, payload in (
        (f'model.{family}.get', {'model_uuid': model}),
        (f'model.{family}.update', {'model_uuid': model, 'model_data': {'name': 'stolen'}}),
        (f'model.{family}.create', {'model_data': {'name': 'foreign-provider', 'provider_uuid': provider}}),
        ('provider.update', {'provider_uuid': provider, 'provider_data': {'name': 'stolen'}}),
    ):
        with pytest.raises(ApplicationAPIException) as missing:
            await api.execute(operation, context('workspace-b'), payload)
        assert missing.value.error.code == 'resource_not_found'
    await api.execute(
        'provider.update',
        context(),
        {'provider_uuid': provider, 'provider_data': {'name': 'renamed', 'api_keys': ['***']}},
    )
    await api.execute(
        f'model.{family}.update',
        context(),
        {'model_uuid': model, 'model_data': {'name': 'renamed-model', 'extra_args': {'api_key': '***'}}},
    )
    async with engine.connect() as connection:
        stored_provider = (
            (await connection.execute(sa.select(ModelProvider).where(ModelProvider.uuid == provider))).mappings().one()
        )
        stored_model = (await connection.execute(sa.select(table).where(table.uuid == model))).mappings().one()
        assert stored_provider['workspace_uuid'] == stored_model['workspace_uuid'] == 'workspace-a'
        assert stored_provider['api_keys'] == ['secret-key']
        assert stored_provider['name'] == 'renamed'
        assert stored_model['extra_args']['api_key'] == 'model-secret'
        assert stored_model['name'] == 'renamed-model'
        assert (await connection.execute(sa.select(sa.func.count()).select_from(table))).scalar_one() == 1
    await api.execute(f'model.{family}.delete', context(), {'model_uuid': model})
    assert await api.execute(f'model.{family}.list', context(), {}) == []


@pytest.mark.asyncio
async def test_pipeline_copy_update_and_isolation_use_real_persistence(resources):
    api, _, engine = resources
    config = {'ai': {'api_key': 'pipeline-secret'}}
    pipeline = await api.execute(
        'pipeline.create', context(), {'pipeline_data': {'name': 'pipeline', 'config': config}}
    )
    copied = await api.execute('pipeline.copy', context(), {'pipeline_uuid': pipeline})
    assert copied != pipeline
    await api.execute(
        'pipeline.update',
        context(),
        {
            'pipeline_uuid': pipeline,
            'pipeline_data': {
                'name': 'updated',
                'workspace_uuid': 'workspace-b',
                'config': {'ai': {'api_key': '***'}},
            },
        },
    )
    viewer = context(permissions={Permission.RESOURCE_VIEW})
    assert (await api.execute('pipeline.get', viewer, {'pipeline_uuid': pipeline}))['config']['ai']['api_key'] == '***'
    with pytest.raises(ApplicationAPIException):
        await api.execute('pipeline.copy', context('workspace-b'), {'pipeline_uuid': pipeline})
    with pytest.raises(ApplicationAPIException):
        await api.execute('pipeline.delete', context('workspace-b'), {'pipeline_uuid': pipeline})
    async with engine.connect() as connection:
        rows = (await connection.execute(sa.select(LegacyPipeline))).mappings().all()
        assert len(rows) == 2
        assert {row['workspace_uuid'] for row in rows} == {'workspace-a'}
        assert {row['config']['ai']['api_key'] for row in rows} == {'pipeline-secret'}
        assert {row['name'] for row in rows} == {'updated', 'pipeline (Copy)'}
    await api.execute('pipeline.delete', context(), {'pipeline_uuid': copied})
    assert len(await api.execute('pipeline.list', context(), {})) == 1


@pytest.mark.asyncio
async def test_knowledge_draft_crud_and_secret_projection_with_real_rag_manager(resources):
    api, _, engine = resources
    kb = await api.execute(
        'knowledge.base.create',
        context(),
        {
            'kb_data': {
                'name': 'draft',
                'knowledge_engine_plugin_id': 'test/engine',
                'defer_initialization': True,
                'creation_settings': {'api_key': 'knowledge-secret'},
                'workspace_uuid': 'workspace-b',
            }
        },
    )
    visible = await api.execute('knowledge.base.get', context(permissions={Permission.RESOURCE_VIEW}), {'kb_uuid': kb})
    assert visible['creation_settings']['api_key'] == '***'
    assert visible['initialized'] is False
    await api.execute(
        'knowledge.base.update',
        context(),
        {'kb_uuid': kb, 'kb_data': {'name': 'updated', 'workspace_uuid': 'workspace-b'}},
    )
    for operation, payload in (
        ('knowledge.base.get', {'kb_uuid': kb}),
        ('knowledge.base.update', {'kb_uuid': kb, 'kb_data': {'name': 'stolen'}}),
        ('knowledge.base.delete', {'kb_uuid': kb}),
    ):
        with pytest.raises(ApplicationAPIException) as missing:
            await api.execute(operation, context('workspace-b'), payload)
        assert missing.value.error.code == 'resource_not_found'
    async with engine.connect() as connection:
        row = (await connection.execute(sa.select(KnowledgeBase).where(KnowledgeBase.uuid == kb))).mappings().one()
        assert row['workspace_uuid'] == 'workspace-a'
        assert row['name'] == 'updated'
        assert row['creation_settings']['api_key'] == 'knowledge-secret'
    await api.execute('knowledge.base.delete', context(), {'kb_uuid': kb})
    async with engine.connect() as connection:
        assert (await connection.execute(sa.select(sa.func.count()).select_from(KnowledgeBase))).scalar_one() == 0


@pytest.mark.asyncio
async def test_chat_management_uses_scoped_history_and_real_connection_queues(resources, monkeypatch):
    from langbot.pkg.api.application import ApplicationAPI
    from langbot.pkg.api.application.connection_operations import operations
    from langbot.pkg.platform.sources import websocket_manager
    from langbot.pkg.platform.sources.websocket_adapter import WebSocketAdapter, WebSocketMessage, WebSocketSession

    api, ap, _ = resources
    pipeline = await api.execute(
        'pipeline.create', context(), {'pipeline_data': {'name': 'chat', 'config': {'ai': {}}}}
    )
    api = ApplicationAPI(ap, operations=operations())
    manager = websocket_manager.WebSocketConnectionManager()
    monkeypatch.setattr(websocket_manager, 'ws_connection_manager', manager)
    owned = await manager.add_connection(
        None, websocket_manager.WebSocketScope.from_context(context()), pipeline, 'person'
    )
    foreign = await manager.add_connection(
        None, websocket_manager.WebSocketScope.from_context(context('workspace-b')), pipeline, 'person'
    )
    stale = await manager.add_connection(
        None, websocket_manager.WebSocketScope('foundation-instance', 'workspace-a', 2), pipeline, 'person'
    )
    visible = await api.execute('pipeline.chat.connections', context(), {'pipeline_uuid': pipeline})
    assert [row['connection_id'] for row in visible['connections']] == [owned.connection_id]
    await api.execute('pipeline.chat.broadcast', context(), {'pipeline_uuid': pipeline, 'message': '你好'})
    assert owned.send_queue.get_nowait()['message'] == '你好'
    assert foreign.send_queue.empty()
    assert stale.send_queue.empty()
    with pytest.raises(ApplicationAPIException):
        await api.execute(
            'pipeline.chat.broadcast', context('workspace-b'), {'pipeline_uuid': pipeline, 'message': 'stolen'}
        )
    assert owned.send_queue.empty()

    adapter = WebSocketAdapter.model_construct(
        ap=ap,
        websocket_person_session=WebSocketSession(id='person'),
        websocket_group_session=WebSocketSession(id='group'),
    )
    message = WebSocketMessage(id=1, role='user', content='history', message_chain=[], timestamp='2026-10-24')
    adapter.websocket_person_session.append_message(pipeline, message)
    adapter.websocket_group_session.append_message(pipeline, message)
    ap.platform_mgr = SimpleNamespace(get_websocket_proxy_bot=AsyncMock(return_value=SimpleNamespace(adapter=adapter)))
    assert (
        await api.execute('pipeline.chat.history', context(), {'pipeline_uuid': pipeline, 'session_type': 'person'})
    )[0]['content'] == 'history'
    await api.execute('pipeline.chat.reset', context(), {'pipeline_uuid': pipeline, 'session_type': 'person'})
    assert (
        await api.execute('pipeline.chat.history', context(), {'pipeline_uuid': pipeline, 'session_type': 'person'})
        == []
    )
    assert len(adapter.websocket_group_session.message_lists[pipeline]) == 1
