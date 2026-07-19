"""Tests for Workspace-scoped RAG manager and runtime knowledge bases."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.entity.persistence.rag import KnowledgeBase
from langbot.pkg.rag.knowledge.kbmgr import RAGManager, RuntimeKnowledgeBase
from langbot.pkg.workspace.errors import WorkspaceNotFoundError


CONTEXT_A = ExecutionContext(
    instance_uuid='instance-a',
    workspace_uuid='workspace-a',
    placement_generation=5,
)
CONTEXT_B = ExecutionContext(
    instance_uuid='instance-a',
    workspace_uuid='workspace-b',
    placement_generation=5,
)


class _Result:
    def __init__(self, rows=(), *, first=None):
        self.rows = list(rows)
        self._first = first

    def all(self):
        return self.rows

    def first(self):
        return self._first


def _entity(*, kb_uuid='kb-a', workspace_uuid='workspace-a', plugin_id='author/engine'):
    return KnowledgeBase(
        uuid=kb_uuid,
        workspace_uuid=workspace_uuid,
        name='Test KB',
        description='description',
        knowledge_engine_plugin_id=plugin_id,
        collection_id=kb_uuid,
        creation_settings={},
        retrieval_settings={},
    )


def _app():
    return SimpleNamespace(
        logger=Mock(),
        persistence_mgr=SimpleNamespace(
            execute_async=AsyncMock(return_value=_Result()),
            serialize_model=Mock(
                side_effect=lambda _model, row: {
                    'uuid': row.uuid,
                    'workspace_uuid': row.workspace_uuid,
                    'name': row.name,
                    'description': row.description,
                    'knowledge_engine_plugin_id': row.knowledge_engine_plugin_id,
                    'collection_id': row.collection_id,
                    'creation_settings': row.creation_settings,
                    'retrieval_settings': row.retrieval_settings,
                }
            ),
        ),
        plugin_connector=SimpleNamespace(
            is_enable_plugin=True,
            require_workspace_context=AsyncMock(side_effect=lambda context: context),
            list_knowledge_engines=AsyncMock(
                return_value=[
                    {
                        'plugin_id': 'author/engine',
                        'name': {'en_US': 'Engine'},
                        'capabilities': ['doc_ingestion'],
                    }
                ]
            ),
            rag_on_kb_create=AsyncMock(),
            rag_on_kb_delete=AsyncMock(),
            call_rag_ingest=AsyncMock(return_value={'status': 'success'}),
            call_rag_retrieve=AsyncMock(return_value={'results': []}),
            call_rag_delete_document=AsyncMock(return_value=True),
            call_parser=AsyncMock(),
        ),
        workspace_service=SimpleNamespace(
            get_execution_binding=AsyncMock(
                side_effect=lambda workspace_uuid, **_kwargs: SimpleNamespace(
                    instance_uuid='instance-a',
                    workspace_uuid=workspace_uuid,
                    placement_generation=5,
                )
            )
        ),
        storage_mgr=SimpleNamespace(storage_provider=AsyncMock()),
        task_mgr=SimpleNamespace(create_user_task=Mock(return_value=SimpleNamespace(id='task-a'))),
    )


@pytest.mark.asyncio
async def test_create_binds_workspace_and_uses_tuple_runtime_key():
    app = _app()
    manager = RAGManager(app)

    kb = await manager.create_knowledge_base(
        CONTEXT_A,
        name='Created',
        knowledge_engine_plugin_id='author/engine',
        creation_settings={'model': 'embedding-a'},
    )

    assert kb.workspace_uuid == 'workspace-a'
    assert ('workspace-a', kb.uuid) in manager.knowledge_bases
    app.plugin_connector.rag_on_kb_create.assert_awaited_once_with(
        'author/engine',
        kb.uuid,
        {'model': 'embedding-a'},
    )


@pytest.mark.asyncio
async def test_create_rejects_unknown_engine_and_rolls_back_plugin_failure():
    app = _app()
    manager = RAGManager(app)
    app.plugin_connector.list_knowledge_engines.return_value = []
    with pytest.raises(ValueError, match='not found'):
        await manager.create_knowledge_base(
            CONTEXT_A,
            name='Unknown',
            knowledge_engine_plugin_id='missing/engine',
            creation_settings={},
        )

    app.plugin_connector.list_knowledge_engines.return_value = [{'plugin_id': 'author/engine'}]
    app.plugin_connector.rag_on_kb_create.side_effect = RuntimeError('plugin failed')
    with pytest.raises(RuntimeError, match='plugin failed'):
        await manager.create_knowledge_base(
            CONTEXT_A,
            name='Rollback',
            knowledge_engine_plugin_id='author/engine',
            creation_settings={},
        )
    assert manager.knowledge_bases == {}


@pytest.mark.asyncio
async def test_runtime_retrieve_carries_context_and_merges_settings_without_mutation():
    app = _app()
    entity = _entity()
    entity.retrieval_settings = {'top_k': 10, 'model': 'default'}
    app.plugin_connector.call_rag_retrieve.return_value = {
        'results': [
            {
                'id': 'entry-a',
                'content': [{'type': 'text', 'text': 'hello'}],
                'metadata': {},
                'distance': 0.2,
            }
        ]
    }
    runtime = RuntimeKnowledgeBase(app, entity, CONTEXT_A)
    overrides = {'top_k': 2, 'filters': {'file_id': 'file-a'}}

    results = await runtime.retrieve(CONTEXT_A, 'query', settings=overrides)

    assert results[0].id == 'entry-a'
    assert overrides == {'top_k': 2, 'filters': {'file_id': 'file-a'}}
    payload = app.plugin_connector.call_rag_retrieve.await_args.args[1]
    assert payload['knowledge_base_id'] == 'kb-a'
    assert payload['collection_id'] == 'kb-a'
    assert payload['retrieval_settings']['top_k'] == 2
    assert payload['filters'] == {'file_id': 'file-a'}


@pytest.mark.asyncio
async def test_runtime_rejects_cross_workspace_and_stale_contexts():
    app = _app()
    runtime = RuntimeKnowledgeBase(app, _entity(), CONTEXT_A)

    with pytest.raises(WorkspaceNotFoundError):
        await runtime.retrieve(CONTEXT_B, 'query')
    stale = CONTEXT_A.__class__(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=4,
    )
    with pytest.raises(WorkspaceNotFoundError):
        await runtime.retrieve(stale, 'query')
    app.plugin_connector.call_rag_retrieve.assert_not_awaited()


@pytest.mark.asyncio
async def test_runtime_retrieve_fails_before_bound_connector_on_generation_mismatch():
    app = _app()
    app.plugin_connector.require_workspace_context.side_effect = WorkspaceNotFoundError('Plugin resource not found')
    runtime = RuntimeKnowledgeBase(app, _entity(), CONTEXT_A)

    with pytest.raises(WorkspaceNotFoundError, match='Plugin resource not found'):
        await runtime.retrieve(CONTEXT_A, 'query')

    app.plugin_connector.call_rag_retrieve.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('operation', 'connector_method'),
    [
        ('create', 'rag_on_kb_create'),
        ('ingest', 'call_rag_ingest'),
        ('delete', 'call_rag_delete_document'),
    ],
)
async def test_runtime_plugin_mutations_fail_before_mismatched_connector(operation, connector_method):
    app = _app()
    app.plugin_connector.require_workspace_context.side_effect = WorkspaceNotFoundError('Plugin resource not found')
    runtime = RuntimeKnowledgeBase(app, _entity(), CONTEXT_A)

    with pytest.raises(WorkspaceNotFoundError, match='Plugin resource not found'):
        if operation == 'create':
            await runtime._on_kb_create(CONTEXT_A)
        elif operation == 'ingest':
            await runtime._ingest_document(CONTEXT_A, {'filename': 'document.pdf'}, 'storage/path')
        else:
            await runtime._delete_document(CONTEXT_A, 'file-a')

    getattr(app.plugin_connector, connector_method).assert_not_awaited()


@pytest.mark.asyncio
async def test_create_fails_before_engine_discovery_on_connector_workspace_mismatch():
    app = _app()
    app.plugin_connector.require_workspace_context.side_effect = WorkspaceNotFoundError('Plugin resource not found')
    manager = RAGManager(app)

    with pytest.raises(WorkspaceNotFoundError, match='Plugin resource not found'):
        await manager.create_knowledge_base(
            CONTEXT_A,
            name='Other workspace',
            knowledge_engine_plugin_id='author/engine',
            creation_settings={},
        )

    app.plugin_connector.list_knowledge_engines.assert_not_awaited()
    app.persistence_mgr.execute_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_ingestion_payload_uses_host_owned_kb_collection():
    app = _app()
    runtime = RuntimeKnowledgeBase(app, _entity(), CONTEXT_A)
    metadata = {'filename': 'document.pdf'}

    await runtime._ingest_document(CONTEXT_A, metadata, 'uploads/document.pdf')

    payload = app.plugin_connector.call_rag_ingest.await_args.args[1]
    assert payload['knowledge_base_id'] == 'kb-a'
    assert payload['collection_id'] == 'kb-a'
    assert payload['file_object']['metadata']['knowledge_base_id'] == 'kb-a'


@pytest.mark.asyncio
async def test_delete_file_checks_workspace_and_parent_before_plugin_call():
    app = _app()
    runtime = RuntimeKnowledgeBase(app, _entity(), CONTEXT_A)
    app.persistence_mgr.execute_async.return_value = _Result(first=('file-a',))

    await runtime.delete_file(CONTEXT_A, 'file-a')
    app.plugin_connector.call_rag_delete_document.assert_awaited_once_with(
        'author/engine',
        'file-a',
        'kb-a',
    )

    missing_app = _app()
    missing = RuntimeKnowledgeBase(missing_app, _entity(), CONTEXT_A)
    with pytest.raises(WorkspaceNotFoundError):
        await missing.delete_file(CONTEXT_A, 'file-other')
    missing_app.plugin_connector.call_rag_delete_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_manager_get_remove_and_delete_are_workspace_scoped():
    app = _app()
    manager = RAGManager(app)
    runtime = await manager.load_knowledge_base(CONTEXT_A, _entity())

    assert await manager.get_knowledge_base_by_uuid(CONTEXT_A, 'kb-a') is runtime
    assert await manager.get_knowledge_base_by_uuid(CONTEXT_B, 'kb-a') is None
    await manager.remove_knowledge_base_from_runtime(CONTEXT_B, 'kb-a')
    assert await manager.get_knowledge_base_by_uuid(CONTEXT_A, 'kb-a') is runtime
    await manager.delete_knowledge_base(CONTEXT_A, 'kb-a')
    app.plugin_connector.rag_on_kb_delete.assert_awaited_once()
    assert await manager.get_knowledge_base_by_uuid(CONTEXT_A, 'kb-a') is None


@pytest.mark.asyncio
async def test_details_queries_require_workspace_and_enrich_engine():
    app = _app()
    row_a = _entity()
    app.persistence_mgr.execute_async.return_value = _Result([row_a], first=row_a)
    manager = RAGManager(app)

    listed = await manager.get_all_knowledge_base_details(CONTEXT_A)
    fetched = await manager.get_knowledge_base_details(CONTEXT_A, 'kb-a')
    assert listed[0]['knowledge_engine']['plugin_id'] == 'author/engine'
    assert fetched['knowledge_engine']['capabilities'] == ['doc_ingestion']


@pytest.mark.asyncio
async def test_load_dict_filters_computed_fields_and_requires_matching_workspace():
    app = _app()
    manager = RAGManager(app)
    runtime = await manager.load_knowledge_base(
        CONTEXT_A,
        {
            'uuid': 'kb-a',
            'workspace_uuid': 'workspace-a',
            'name': 'KB',
            'description': '',
            'knowledge_engine_plugin_id': 'author/engine',
            'collection_id': 'kb-a',
            'creation_settings': {},
            'retrieval_settings': {},
            'knowledge_engine': {'computed': True},
        },
    )
    assert runtime.get_uuid() == 'kb-a'

    with pytest.raises(WorkspaceNotFoundError):
        await manager.load_knowledge_base(CONTEXT_B, _entity())


# Preserve the complete pre-tenancy RAG manager regression matrix.  Every
# runtime operation now carries the immutable ExecutionContext, and cache
# assertions use the Workspace + resource tuple key introduced for isolation.
class TestRAGManagerCreateKnowledgeBase:
    @pytest.mark.asyncio
    async def test_creates_kb_with_valid_engine(self):
        app = _app()
        manager = RAGManager(app)

        kb = await manager.create_knowledge_base(
            CONTEXT_A,
            name='Test KB',
            knowledge_engine_plugin_id='author/engine',
            creation_settings={'model': 'test'},
        )

        assert kb.name == 'Test KB'
        assert kb.workspace_uuid == CONTEXT_A.workspace_uuid
        assert kb.knowledge_engine_plugin_id == 'author/engine'

    @pytest.mark.asyncio
    async def test_raises_when_engine_not_found(self):
        app = _app()
        app.plugin_connector.list_knowledge_engines.return_value = []

        with pytest.raises(ValueError, match='not found'):
            await RAGManager(app).create_knowledge_base(
                CONTEXT_A,
                name='Test KB',
                knowledge_engine_plugin_id='unknown/engine',
                creation_settings={},
            )

    @pytest.mark.asyncio
    async def test_rollback_on_plugin_create_failure(self):
        app = _app()
        app.plugin_connector.rag_on_kb_create.side_effect = RuntimeError('Plugin error')
        manager = RAGManager(app)

        with pytest.raises(RuntimeError, match='Plugin error'):
            await manager.create_knowledge_base(
                CONTEXT_A,
                name='Test KB',
                knowledge_engine_plugin_id='author/engine',
                creation_settings={},
            )

        assert manager.knowledge_bases == {}
        assert app.persistence_mgr.execute_async.await_count == 2

    @pytest.mark.asyncio
    async def test_sets_default_retrieval_settings(self):
        app = _app()

        kb = await RAGManager(app).create_knowledge_base(
            CONTEXT_A,
            name='Test KB',
            knowledge_engine_plugin_id='author/engine',
            creation_settings={},
            retrieval_settings=None,
        )

        assert kb.retrieval_settings == {}

    @pytest.mark.asyncio
    async def test_skips_validation_when_plugin_disabled(self):
        app = _app()
        app.plugin_connector.is_enable_plugin = False

        kb = await RAGManager(app).create_knowledge_base(
            CONTEXT_A,
            name='Test KB',
            knowledge_engine_plugin_id='any/engine',
            creation_settings={},
        )

        assert kb.knowledge_engine_plugin_id == 'any/engine'
        app.plugin_connector.list_knowledge_engines.assert_not_awaited()


class TestRuntimeKnowledgeBaseOnKBCreate:
    @pytest.mark.asyncio
    async def test_calls_plugin_on_create(self):
        app = _app()
        entity = _entity()
        entity.creation_settings = {'model': 'test'}

        await RuntimeKnowledgeBase(app, entity, CONTEXT_A)._on_kb_create(CONTEXT_A)

        app.plugin_connector.rag_on_kb_create.assert_awaited_once_with(
            'author/engine',
            entity.uuid,
            {'model': 'test'},
        )

    @pytest.mark.asyncio
    async def test_skips_when_no_plugin_id(self):
        app = _app()

        await RuntimeKnowledgeBase(
            app,
            _entity(plugin_id=None),
            CONTEXT_A,
        )._on_kb_create(CONTEXT_A)

        app.plugin_connector.rag_on_kb_create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_raises_on_plugin_error(self):
        app = _app()
        app.plugin_connector.rag_on_kb_create.side_effect = RuntimeError('Plugin failed')

        with pytest.raises(RuntimeError, match='Plugin failed'):
            await RuntimeKnowledgeBase(app, _entity(), CONTEXT_A)._on_kb_create(CONTEXT_A)


class TestRuntimeKnowledgeBaseDeleteFile:
    @pytest.mark.asyncio
    async def test_delete_file_calls_plugin_and_db(self):
        app = _app()
        app.persistence_mgr.execute_async.return_value = _Result(first=('file-uuid',))

        await RuntimeKnowledgeBase(app, _entity(), CONTEXT_A).delete_file(
            CONTEXT_A,
            'file-uuid',
        )

        app.plugin_connector.call_rag_delete_document.assert_awaited_once_with(
            'author/engine',
            'file-uuid',
            'kb-a',
        )
        assert app.persistence_mgr.execute_async.await_count == 2


class TestRuntimeKnowledgeBaseIngestDocument:
    @pytest.mark.asyncio
    async def test_ingest_calls_plugin(self):
        app = _app()

        result = await RuntimeKnowledgeBase(app, _entity(), CONTEXT_A)._ingest_document(
            CONTEXT_A,
            {'filename': 'test.pdf'},
            'storage/path',
        )

        assert result == {'status': 'success'}
        app.plugin_connector.call_rag_ingest.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ingest_raises_when_no_plugin_id(self):
        app = _app()

        with pytest.raises(ValueError, match='Plugin ID required'):
            await RuntimeKnowledgeBase(
                app,
                _entity(plugin_id=None),
                CONTEXT_A,
            )._ingest_document(CONTEXT_A, {'filename': 'test.pdf'}, 'path')


class TestRAGManagerLoadKnowledgeBasesFromDB:
    @pytest.mark.asyncio
    async def test_loads_all_kbs_from_db(self):
        app = _app()
        kb1 = _entity(kb_uuid='kb-1')
        kb2 = _entity(kb_uuid='kb-2')
        app.persistence_mgr.execute_async.return_value = _Result([kb1, kb2])
        manager = RAGManager(app)

        await manager.load_knowledge_bases_from_db()

        assert set(manager.knowledge_bases) == {
            ('workspace-a', 'kb-1'),
            ('workspace-a', 'kb-2'),
        }

    @pytest.mark.asyncio
    async def test_handles_load_error_gracefully(self):
        app = _app()
        app.persistence_mgr.execute_async.return_value = _Result([_entity()])
        app.workspace_service.get_execution_binding.side_effect = RuntimeError('binding unavailable')
        manager = RAGManager(app)

        await manager.load_knowledge_bases_from_db()

        assert manager.knowledge_bases == {}
        app.logger.error.assert_called_once()


class TestRuntimeKnowledgeBaseGetters:
    def test_get_uuid_returns_entity_uuid(self):
        entity = _entity()

        assert RuntimeKnowledgeBase(_app(), entity, CONTEXT_A).get_uuid() == entity.uuid

    def test_get_name_returns_entity_name(self):
        entity = _entity()

        assert RuntimeKnowledgeBase(_app(), entity, CONTEXT_A).get_name() == entity.name

    def test_get_knowledge_engine_plugin_id_returns_plugin_id(self):
        runtime = RuntimeKnowledgeBase(_app(), _entity(), CONTEXT_A)

        assert runtime.get_knowledge_engine_plugin_id() == 'author/engine'

    def test_get_knowledge_engine_plugin_id_returns_empty_when_none(self):
        runtime = RuntimeKnowledgeBase(_app(), _entity(plugin_id=None), CONTEXT_A)

        assert runtime.get_knowledge_engine_plugin_id() == ''


class TestRuntimeKnowledgeBaseRetrieve:
    @pytest.mark.asyncio
    async def test_retrieve_merges_settings(self):
        app = _app()
        entity = _entity()
        entity.retrieval_settings = {'top_k': 10, 'model': 'default'}
        app.plugin_connector.call_rag_retrieve.return_value = {
            'results': [
                {
                    'id': 'doc1',
                    'content': [{'type': 'text', 'text': 'test content'}],
                    'metadata': {},
                    'distance': 0.1,
                }
            ]
        }

        results = await RuntimeKnowledgeBase(app, entity, CONTEXT_A).retrieve(
            CONTEXT_A,
            'query text',
            settings={'top_k': 20},
        )

        assert len(results) == 1
        payload = app.plugin_connector.call_rag_retrieve.await_args.args[1]
        assert payload['retrieval_settings'] == {'top_k': 20, 'model': 'default'}

    @pytest.mark.asyncio
    async def test_retrieve_adds_default_top_k(self):
        app = _app()

        await RuntimeKnowledgeBase(app, _entity(), CONTEXT_A).retrieve(
            CONTEXT_A,
            'query text',
        )

        payload = app.plugin_connector.call_rag_retrieve.await_args.args[1]
        assert payload['retrieval_settings']['top_k'] == 5

    @pytest.mark.asyncio
    async def test_retrieve_converts_dict_to_entry(self):
        app = _app()
        app.plugin_connector.call_rag_retrieve.return_value = {
            'results': [
                {
                    'id': 'doc1',
                    'content': [{'type': 'text', 'text': 'test content'}],
                    'metadata': {'source': 'file.pdf'},
                    'distance': 0.15,
                }
            ]
        }

        results = await RuntimeKnowledgeBase(app, _entity(), CONTEXT_A).retrieve(
            CONTEXT_A,
            'query',
        )

        assert len(results) == 1
        assert results[0].id == 'doc1'
        assert hasattr(results[0], 'content')


class TestRuntimeKnowledgeBaseDispose:
    @pytest.mark.asyncio
    async def test_dispose_calls_on_kb_delete(self):
        app = _app()

        await RuntimeKnowledgeBase(app, _entity(), CONTEXT_A).dispose(CONTEXT_A)

        app.plugin_connector.rag_on_kb_delete.assert_awaited_once_with(
            'author/engine',
            'kb-a',
        )

    @pytest.mark.asyncio
    async def test_dispose_skips_when_no_plugin_id(self):
        app = _app()

        await RuntimeKnowledgeBase(
            app,
            _entity(plugin_id=None),
            CONTEXT_A,
        ).dispose(CONTEXT_A)

        app.plugin_connector.rag_on_kb_delete.assert_not_awaited()


class TestRAGManagerInit:
    def test_init_stores_app_reference(self):
        app = _app()

        assert RAGManager(app).ap is app

    def test_init_creates_empty_knowledge_bases_dict(self):
        assert RAGManager(_app()).knowledge_bases == {}


class TestRAGManagerGetKnowledgeBase:
    @pytest.mark.asyncio
    async def test_get_knowledge_base_by_uuid_returns_runtime_kb(self):
        app = _app()
        manager = RAGManager(app)
        runtime = RuntimeKnowledgeBase(app, _entity(), CONTEXT_A)
        manager.knowledge_bases[('workspace-a', 'kb-a')] = runtime

        result = await manager.get_knowledge_base_by_uuid(CONTEXT_A, 'kb-a')

        assert result is runtime

    @pytest.mark.asyncio
    async def test_get_knowledge_base_by_uuid_returns_none_when_not_found(self):
        assert (
            await RAGManager(_app()).get_knowledge_base_by_uuid(
                CONTEXT_A,
                'nonexistent-uuid',
            )
            is None
        )

    @pytest.mark.asyncio
    async def test_remove_knowledge_base_from_runtime(self):
        app = _app()
        manager = RAGManager(app)
        manager.knowledge_bases[('workspace-a', 'kb-a')] = RuntimeKnowledgeBase(
            app,
            _entity(),
            CONTEXT_A,
        )

        await manager.remove_knowledge_base_from_runtime(CONTEXT_A, 'kb-a')

        assert ('workspace-a', 'kb-a') not in manager.knowledge_bases


class TestRAGManagerEnrichKB:
    def test_enrich_adds_engine_info_from_map(self):
        kb_dict = {'knowledge_engine_plugin_id': 'author/engine'}
        engine_map = {
            'author/engine': {
                'plugin_id': 'author/engine',
                'name': 'Test Engine',
                'capabilities': ['doc_ingestion', 'search'],
            }
        }

        RAGManager(_app())._enrich_kb_dict(kb_dict, engine_map)

        assert kb_dict['knowledge_engine']['plugin_id'] == 'author/engine'
        assert kb_dict['knowledge_engine']['capabilities'] == ['doc_ingestion', 'search']

    def test_enrich_uses_fallback_when_engine_not_in_map(self):
        kb_dict = {'knowledge_engine_plugin_id': 'unknown/engine'}

        RAGManager(_app())._enrich_kb_dict(kb_dict, {})

        assert kb_dict['knowledge_engine']['plugin_id'] == 'unknown/engine'
        assert kb_dict['knowledge_engine']['capabilities'] == []

    def test_enrich_uses_fallback_when_no_plugin_id(self):
        kb_dict = {}

        RAGManager(_app())._enrich_kb_dict(kb_dict, {})

        assert kb_dict['knowledge_engine']['plugin_id'] is None
        assert 'en_US' in kb_dict['knowledge_engine']['name']

    def test_enrich_converts_string_name_to_i18n(self):
        kb_dict = {'knowledge_engine_plugin_id': 'author/engine'}
        engine_map = {
            'author/engine': {
                'plugin_id': 'author/engine',
                'name': 'Simple Name',
                'capabilities': [],
            }
        }

        RAGManager(_app())._enrich_kb_dict(kb_dict, engine_map)

        assert kb_dict['knowledge_engine']['name'] == {
            'en_US': 'Simple Name',
            'zh_Hans': 'Simple Name',
        }


class TestRAGManagerDeleteKnowledgeBase:
    @pytest.mark.asyncio
    async def test_delete_removes_from_runtime_and_disposes(self):
        app = _app()
        manager = RAGManager(app)
        manager.knowledge_bases[('workspace-a', 'kb-a')] = RuntimeKnowledgeBase(
            app,
            _entity(),
            CONTEXT_A,
        )

        await manager.delete_knowledge_base(CONTEXT_A, 'kb-a')

        assert ('workspace-a', 'kb-a') not in manager.knowledge_bases
        app.plugin_connector.rag_on_kb_delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_logs_warning_when_not_in_runtime(self):
        app = _app()

        await RAGManager(app).delete_knowledge_base(CONTEXT_A, 'nonexistent-uuid')

        app.logger.warning.assert_called_once()


class TestRAGManagerGetAllDetails:
    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_kbs(self):
        assert await RAGManager(_app()).get_all_knowledge_base_details(CONTEXT_A) == []

    @pytest.mark.asyncio
    async def test_enriches_each_kb_with_engine_info(self):
        app = _app()
        app.persistence_mgr.execute_async.return_value = _Result([_entity()])

        result = await RAGManager(app).get_all_knowledge_base_details(CONTEXT_A)

        assert len(result) == 1
        assert result[0]['knowledge_engine']['plugin_id'] == 'author/engine'


class TestRAGManagerGetDetails:
    @pytest.mark.asyncio
    async def test_returns_none_when_kb_not_found(self):
        assert (
            await RAGManager(_app()).get_knowledge_base_details(
                CONTEXT_A,
                'nonexistent',
            )
            is None
        )

    @pytest.mark.asyncio
    async def test_returns_enriched_kb_dict(self):
        app = _app()
        app.persistence_mgr.execute_async.return_value = _Result(first=_entity())

        result = await RAGManager(app).get_knowledge_base_details(CONTEXT_A, 'kb-a')

        assert result is not None
        assert result['knowledge_engine']['plugin_id'] == 'author/engine'


class TestRAGManagerLoadKnowledgeBase:
    @pytest.mark.asyncio
    async def test_loads_kb_entity_into_runtime(self):
        manager = RAGManager(_app())

        result = await manager.load_knowledge_base(CONTEXT_A, _entity())

        assert ('workspace-a', 'kb-a') in manager.knowledge_bases
        assert result.get_uuid() == 'kb-a'

    @pytest.mark.asyncio
    async def test_load_handles_dict_entity(self):
        manager = RAGManager(_app())
        kb_dict = {
            'uuid': 'kb-uuid',
            'workspace_uuid': 'workspace-a',
            'name': 'Test',
            'description': '',
            'knowledge_engine_plugin_id': 'author/engine',
            'collection_id': 'kb-uuid',
            'creation_settings': {},
            'retrieval_settings': {},
            'knowledge_engine': {'name': 'should_be_filtered'},
        }

        await manager.load_knowledge_base(CONTEXT_A, kb_dict)

        assert ('workspace-a', 'kb-uuid') in manager.knowledge_bases
