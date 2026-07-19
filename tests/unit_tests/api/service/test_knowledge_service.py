"""Tests for the tenant-aware knowledge service facade."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.authz import WorkspaceRequiredError
from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.api.http.service.knowledge import KnowledgeService
from langbot.pkg.workspace.errors import WorkspaceNotFoundError


CONTEXT = ExecutionContext(
    instance_uuid='instance-a',
    workspace_uuid='workspace-a',
    placement_generation=2,
)


class _Rows:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def all(self):
        return self.rows

    def __iter__(self):
        return iter(self.rows)


def _app():
    return SimpleNamespace(
        logger=Mock(),
        rag_mgr=SimpleNamespace(
            get_all_knowledge_base_details=AsyncMock(return_value=[]),
            get_knowledge_base_details=AsyncMock(return_value=None),
            create_knowledge_base=AsyncMock(),
            remove_knowledge_base_from_runtime=AsyncMock(),
            load_knowledge_base=AsyncMock(),
            get_knowledge_base_by_uuid=AsyncMock(return_value=None),
            delete_knowledge_base=AsyncMock(),
        ),
        persistence_mgr=SimpleNamespace(
            execute_async=AsyncMock(return_value=_Rows()),
            serialize_model=Mock(return_value={}),
        ),
        plugin_connector=SimpleNamespace(
            is_enable_plugin=True,
            require_workspace_context=AsyncMock(side_effect=lambda context: context),
            get_rag_creation_schema=AsyncMock(return_value={}),
            get_rag_retrieval_schema=AsyncMock(return_value={}),
            list_knowledge_engines=AsyncMock(return_value=[]),
            list_parsers=AsyncMock(return_value=[]),
        ),
    )


@pytest.mark.asyncio
async def test_list_and_get_forward_explicit_context():
    app = _app()
    app.rag_mgr.get_all_knowledge_base_details.return_value = [{'uuid': 'kb-a'}]
    app.rag_mgr.get_knowledge_base_details.return_value = {'uuid': 'kb-a'}
    service = KnowledgeService(app)

    assert await service.get_knowledge_bases(CONTEXT) == [{'uuid': 'kb-a'}]
    assert await service.get_knowledge_base(CONTEXT, 'kb-a') == {'uuid': 'kb-a'}
    app.rag_mgr.get_all_knowledge_base_details.assert_awaited_once_with(CONTEXT)
    app.rag_mgr.get_knowledge_base_details.assert_awaited_once_with(CONTEXT, 'kb-a')


@pytest.mark.asyncio
async def test_none_context_fails_closed_before_plugin_or_manager_access():
    app = _app()
    service = KnowledgeService(app)

    with pytest.raises(WorkspaceRequiredError):
        await service.get_knowledge_bases(None)
    with pytest.raises(WorkspaceRequiredError):
        await service.create_knowledge_base(None, {'knowledge_engine_plugin_id': 'author/engine'})
    app.plugin_connector.get_rag_creation_schema.assert_not_awaited()
    app.rag_mgr.create_knowledge_base.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_validates_schema_and_binds_context():
    app = _app()
    app.plugin_connector.get_rag_creation_schema.return_value = {
        'schema': [{'name': 'endpoint', 'label': {'en_US': 'Endpoint'}, 'required': True}]
    }
    app.rag_mgr.create_knowledge_base.return_value = SimpleNamespace(uuid='kb-created')
    service = KnowledgeService(app)

    with pytest.raises(ValueError, match='Endpoint is required'):
        await service.create_knowledge_base(
            CONTEXT,
            {'knowledge_engine_plugin_id': 'author/engine'},
        )

    result = await service.create_knowledge_base(
        CONTEXT,
        {
            'name': 'KB',
            'description': 'desc',
            'knowledge_engine_plugin_id': 'author/engine',
            'creation_settings': {'endpoint': 'https://example.invalid'},
        },
    )
    assert result == 'kb-created'
    app.rag_mgr.create_knowledge_base.assert_awaited_once_with(
        CONTEXT,
        name='KB',
        knowledge_engine_plugin_id='author/engine',
        creation_settings={'endpoint': 'https://example.invalid'},
        retrieval_settings={},
        description='desc',
    )


@pytest.mark.asyncio
async def test_update_rejects_guessed_uuid_and_scopes_reload():
    app = _app()
    service = KnowledgeService(app)

    with pytest.raises(WorkspaceNotFoundError):
        await service.update_knowledge_base(CONTEXT, 'kb-other', {'name': 'stolen'})
    app.persistence_mgr.execute_async.assert_not_awaited()

    app.rag_mgr.get_knowledge_base_details.return_value = {'uuid': 'kb-a', 'workspace_uuid': 'workspace-a'}
    await service.update_knowledge_base(CONTEXT, 'kb-a', {'name': 'updated', 'uuid': 'ignored'})
    app.rag_mgr.remove_knowledge_base_from_runtime.assert_awaited_once_with(CONTEXT, 'kb-a')
    app.rag_mgr.load_knowledge_base.assert_awaited_once_with(
        CONTEXT,
        {'uuid': 'kb-a', 'workspace_uuid': 'workspace-a'},
    )


@pytest.mark.asyncio
async def test_runtime_retrieve_uses_execution_context():
    app = _app()
    entry = SimpleNamespace(model_dump=Mock(return_value={'id': 'entry-a'}))
    runtime_kb = SimpleNamespace(retrieve=AsyncMock(return_value=[entry]))
    app.rag_mgr.get_knowledge_base_by_uuid.return_value = runtime_kb
    service = KnowledgeService(app)

    assert await service.retrieve_knowledge_base(CONTEXT, 'kb-a', 'query', {'top_k': 3}) == [{'id': 'entry-a'}]
    runtime_kb.retrieve.assert_awaited_once_with(CONTEXT, 'query', settings={'top_k': 3})


@pytest.mark.asyncio
async def test_runtime_retrieve_cross_workspace_uuid_is_not_found():
    app = _app()
    service = KnowledgeService(app)
    with pytest.raises(WorkspaceNotFoundError):
        await service.retrieve_knowledge_base(CONTEXT, 'kb-other', 'query')


@pytest.mark.asyncio
async def test_file_listing_checks_parent_knowledge_base_first():
    app = _app()
    service = KnowledgeService(app)
    with pytest.raises(WorkspaceNotFoundError):
        await service.get_files_by_knowledge_base(CONTEXT, 'kb-other')
    app.persistence_mgr.execute_async.assert_not_awaited()

    app.rag_mgr.get_knowledge_base_details.return_value = {'uuid': 'kb-a'}
    row = SimpleNamespace(uuid='file-a')
    app.persistence_mgr.execute_async.return_value = _Rows([row])
    app.persistence_mgr.serialize_model.return_value = {'uuid': 'file-a'}
    assert await service.get_files_by_knowledge_base(CONTEXT, 'kb-a') == [{'uuid': 'file-a'}]


@pytest.mark.asyncio
async def test_store_and_delete_file_require_runtime_parent_and_capability():
    app = _app()
    runtime_kb = SimpleNamespace(
        store_file=AsyncMock(return_value='task-a'),
        delete_file=AsyncMock(),
    )
    app.rag_mgr.get_knowledge_base_by_uuid.return_value = runtime_kb
    app.rag_mgr.get_knowledge_base_details.return_value = {'knowledge_engine': {'capabilities': ['doc_ingestion']}}
    service = KnowledgeService(app)

    assert await service.store_file(CONTEXT, 'kb-a', 'upload.pdf', 'author/parser') == 'task-a'
    runtime_kb.store_file.assert_awaited_once_with(CONTEXT, 'upload.pdf', parser_plugin_id='author/parser')
    await service.delete_file(CONTEXT, 'kb-a', 'file-a')
    runtime_kb.delete_file.assert_awaited_once_with(CONTEXT, 'file-a')


@pytest.mark.asyncio
async def test_delete_knowledge_base_rejects_cross_workspace_uuid():
    app = _app()
    service = KnowledgeService(app)
    with pytest.raises(WorkspaceNotFoundError):
        await service.delete_knowledge_base(CONTEXT, 'kb-other')
    app.rag_mgr.delete_knowledge_base.assert_not_awaited()


@pytest.mark.asyncio
async def test_engine_and_parser_discovery_require_context_and_filter_results():
    app = _app()
    app.plugin_connector.list_knowledge_engines.return_value = [{'plugin_id': 'author/engine'}]
    app.plugin_connector.list_parsers.return_value = [
        {'id': 'text', 'supported_mime_types': ['text/plain']},
        {'id': 'pdf', 'supported_mime_types': ['application/pdf']},
    ]
    service = KnowledgeService(app)

    assert await service.list_knowledge_engines(CONTEXT) == [{'plugin_id': 'author/engine'}]
    assert await service.list_parsers(CONTEXT, 'application/pdf') == [
        {'id': 'pdf', 'supported_mime_types': ['application/pdf']}
    ]
    with pytest.raises(WorkspaceRequiredError):
        await service.list_parsers(None)


@pytest.mark.asyncio
async def test_engine_discovery_rejects_connector_workspace_or_generation_mismatch():
    app = _app()
    app.plugin_connector.require_workspace_context.side_effect = WorkspaceNotFoundError('Plugin resource not found')
    service = KnowledgeService(app)

    with pytest.raises(WorkspaceNotFoundError, match='Plugin resource not found'):
        await service.list_knowledge_engines(CONTEXT)

    app.plugin_connector.list_knowledge_engines.assert_not_awaited()


@pytest.mark.asyncio
async def test_schema_validation_refences_before_second_runtime_call():
    app = _app()
    app.plugin_connector.require_workspace_context.side_effect = [
        CONTEXT,
        WorkspaceNotFoundError('Plugin resource not found'),
    ]
    service = KnowledgeService(app)

    with pytest.raises(WorkspaceNotFoundError, match='Plugin resource not found'):
        await service.create_knowledge_base(
            CONTEXT,
            {'knowledge_engine_plugin_id': 'author/engine'},
        )

    app.plugin_connector.get_rag_creation_schema.assert_awaited_once()
    app.plugin_connector.get_rag_retrieval_schema.assert_not_awaited()
    app.rag_mgr.create_knowledge_base.assert_not_awaited()


@pytest.mark.asyncio
async def test_engine_schemas_are_context_gated_and_fail_soft_on_connector_error():
    app = _app()
    app.plugin_connector.get_rag_creation_schema.return_value = {'schema': ['creation']}
    app.plugin_connector.get_rag_retrieval_schema.side_effect = RuntimeError('offline')
    service = KnowledgeService(app)

    assert await service.get_engine_creation_schema(CONTEXT, 'author/engine') == {'schema': ['creation']}
    assert await service.get_engine_retrieval_schema(CONTEXT, 'author/engine') == {}
    with pytest.raises(WorkspaceRequiredError):
        await service.get_engine_creation_schema(None, 'author/engine')


# Preserve the original service regression matrix with the new explicit
# Workspace context.  These intentionally overlap a few isolation-focused
# tests above so legacy business behavior cannot disappear behind new guards.
class TestKnowledgeServiceInit:
    def test_init_stores_app_reference(self):
        app = _app()

        service = KnowledgeService(app)

        assert service.ap is app


class TestGetKnowledgeBases:
    @pytest.mark.asyncio
    async def test_returns_all_kb_details(self):
        app = _app()
        app.rag_mgr.get_all_knowledge_base_details.return_value = [{'uuid': 'kb1', 'name': 'KB1'}]

        result = await KnowledgeService(app).get_knowledge_bases(CONTEXT)

        assert result == [{'uuid': 'kb1', 'name': 'KB1'}]
        app.rag_mgr.get_all_knowledge_base_details.assert_awaited_once_with(CONTEXT)

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_kbs(self):
        app = _app()

        assert await KnowledgeService(app).get_knowledge_bases(CONTEXT) == []


class TestGetKnowledgeBase:
    @pytest.mark.asyncio
    async def test_returns_kb_details_by_uuid(self):
        app = _app()
        app.rag_mgr.get_knowledge_base_details.return_value = {'uuid': 'kb1', 'name': 'KB1'}

        result = await KnowledgeService(app).get_knowledge_base(CONTEXT, 'kb1')

        assert result == {'uuid': 'kb1', 'name': 'KB1'}

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        app = _app()

        assert await KnowledgeService(app).get_knowledge_base(CONTEXT, 'nonexistent') is None


class TestCreateKnowledgeBase:
    @pytest.mark.asyncio
    async def test_creates_kb_with_required_fields(self):
        app = _app()
        app.rag_mgr.create_knowledge_base.return_value = SimpleNamespace(uuid='new_kb_uuid')
        service = KnowledgeService(app)
        kb_data = {
            'name': 'Test KB',
            'knowledge_engine_plugin_id': 'author/engine',
            'description': 'Test description',
        }

        result = await service.create_knowledge_base(CONTEXT, kb_data)

        assert result == 'new_kb_uuid'
        app.rag_mgr.create_knowledge_base.assert_awaited_once_with(
            CONTEXT,
            name='Test KB',
            knowledge_engine_plugin_id='author/engine',
            creation_settings={},
            retrieval_settings={},
            description='Test description',
        )

    @pytest.mark.asyncio
    async def test_raises_when_missing_plugin_id(self):
        app = _app()

        with pytest.raises(ValueError, match='knowledge_engine_plugin_id is required'):
            await KnowledgeService(app).create_knowledge_base(CONTEXT, {'name': 'Test'})

        app.rag_mgr.create_knowledge_base.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_creates_with_default_name(self):
        app = _app()
        app.rag_mgr.create_knowledge_base.return_value = SimpleNamespace(uuid='new_kb_uuid')

        await KnowledgeService(app).create_knowledge_base(
            CONTEXT,
            {'knowledge_engine_plugin_id': 'author/engine'},
        )

        assert app.rag_mgr.create_knowledge_base.await_args.kwargs['name'] == 'Untitled'


class TestUpdateKnowledgeBase:
    @pytest.mark.asyncio
    async def test_updates_mutable_fields_only(self):
        app = _app()
        app.rag_mgr.get_knowledge_base_details.return_value = {'uuid': 'kb1', 'name': 'Updated'}
        service = KnowledgeService(app)

        await service.update_knowledge_base(
            CONTEXT,
            'kb1',
            {
                'name': 'New Name',
                'description': 'New desc',
                'uuid': 'should_be_filtered',
            },
        )

        update_statement = app.persistence_mgr.execute_async.await_args_list[0].args[0]
        params = update_statement.compile().params
        assert params['name'] == 'New Name'
        assert params['description'] == 'New desc'
        assert 'uuid' not in params
        app.rag_mgr.remove_knowledge_base_from_runtime.assert_awaited_once_with(CONTEXT, 'kb1')

    @pytest.mark.asyncio
    async def test_returns_early_when_no_mutable_fields(self):
        app = _app()
        app.rag_mgr.get_knowledge_base_details.return_value = {'uuid': 'kb1'}

        await KnowledgeService(app).update_knowledge_base(
            CONTEXT,
            'kb1',
            {'uuid': 'should_be_filtered'},
        )

        app.persistence_mgr.execute_async.assert_not_awaited()
        app.rag_mgr.remove_knowledge_base_from_runtime.assert_not_awaited()


class TestCheckDocCapability:
    @pytest.mark.asyncio
    async def test_passes_when_capability_supported(self):
        app = _app()
        app.rag_mgr.get_knowledge_base_details.return_value = {'knowledge_engine': {'capabilities': ['doc_ingestion']}}

        await KnowledgeService(app)._check_doc_capability(CONTEXT, 'kb1', 'document upload')

    @pytest.mark.asyncio
    async def test_raises_when_kb_not_found(self):
        app = _app()

        with pytest.raises(WorkspaceNotFoundError, match='Knowledge base not found'):
            await KnowledgeService(app)._check_doc_capability(
                CONTEXT,
                'nonexistent',
                'test operation',
            )

    @pytest.mark.asyncio
    async def test_raises_when_capability_not_supported(self):
        app = _app()
        app.rag_mgr.get_knowledge_base_details.return_value = {
            'knowledge_engine': {'capabilities': ['other_capability']}
        }

        with pytest.raises(Exception, match='does not support document upload'):
            await KnowledgeService(app)._check_doc_capability(
                CONTEXT,
                'kb1',
                'document upload',
            )


class TestListKnowledgeEngines:
    @pytest.mark.asyncio
    async def test_returns_engines_from_plugin_connector(self):
        app = _app()
        app.plugin_connector.list_knowledge_engines.return_value = [{'id': 'engine1', 'name': 'Engine 1'}]

        result = await KnowledgeService(app).list_knowledge_engines(CONTEXT)

        assert result == [{'id': 'engine1', 'name': 'Engine 1'}]

    @pytest.mark.asyncio
    async def test_returns_empty_when_plugin_disabled(self):
        app = _app()
        app.plugin_connector.is_enable_plugin = False

        assert await KnowledgeService(app).list_knowledge_engines(CONTEXT) == []
        app.plugin_connector.list_knowledge_engines.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_empty_on_exception(self):
        app = _app()
        app.plugin_connector.list_knowledge_engines.side_effect = RuntimeError('Connection error')

        assert await KnowledgeService(app).list_knowledge_engines(CONTEXT) == []
        app.logger.warning.assert_called_once()


class TestListParsers:
    @pytest.mark.asyncio
    async def test_returns_all_parsers(self):
        app = _app()
        app.plugin_connector.list_parsers.return_value = [
            {'id': 'parser1', 'supported_mime_types': ['text/plain']},
            {'id': 'parser2', 'supported_mime_types': ['application/pdf']},
        ]

        result = await KnowledgeService(app).list_parsers(CONTEXT)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_filters_by_mime_type(self):
        app = _app()
        app.plugin_connector.list_parsers.return_value = [
            {'id': 'parser1', 'supported_mime_types': ['text/plain']},
            {'id': 'parser2', 'supported_mime_types': ['application/pdf']},
        ]

        result = await KnowledgeService(app).list_parsers(CONTEXT, 'application/pdf')

        assert result == [{'id': 'parser2', 'supported_mime_types': ['application/pdf']}]

    @pytest.mark.asyncio
    async def test_returns_empty_when_plugin_disabled(self):
        app = _app()
        app.plugin_connector.is_enable_plugin = False

        assert await KnowledgeService(app).list_parsers(CONTEXT) == []
        app.plugin_connector.list_parsers.assert_not_awaited()


class TestGetEngineSchemas:
    @pytest.mark.asyncio
    async def test_returns_creation_schema(self):
        app = _app()
        app.plugin_connector.get_rag_creation_schema.return_value = {'properties': {'name': {'type': 'string'}}}

        result = await KnowledgeService(app).get_engine_creation_schema(
            CONTEXT,
            'author/engine',
        )

        assert 'properties' in result

    @pytest.mark.asyncio
    async def test_returns_retrieval_schema(self):
        app = _app()
        app.plugin_connector.get_rag_retrieval_schema.return_value = {'properties': {'top_k': {'type': 'integer'}}}

        result = await KnowledgeService(app).get_engine_retrieval_schema(
            CONTEXT,
            'author/engine',
        )

        assert 'properties' in result

    @pytest.mark.asyncio
    async def test_returns_empty_dict_on_exception(self):
        app = _app()
        app.plugin_connector.get_rag_creation_schema.side_effect = RuntimeError('Plugin error')

        result = await KnowledgeService(app).get_engine_creation_schema(
            CONTEXT,
            'author/engine',
        )

        assert result == {}
        app.logger.warning.assert_called_once()


class TestKnowledgeBaseSecretViews:
    @pytest.mark.asyncio
    async def test_creation_settings_are_redacted_for_resource_view_only(self):
        app = _app()
        raw = {
            'uuid': 'kb-secret',
            'creation_settings': {
                'dify_apikey': 'dify-secret',
                'headers': {'Authorization': 'Bearer secret'},
            },
        }
        app.rag_mgr.get_all_knowledge_base_details.return_value = [raw]
        service = KnowledgeService(app)

        redacted = await service.get_knowledge_bases(CONTEXT)
        manager_view = await service.get_knowledge_bases(CONTEXT, include_secret=True)

        assert redacted[0]['creation_settings']['dify_apikey'] == '***'
        assert redacted[0]['creation_settings']['headers']['Authorization'] == '***'
        assert manager_view[0]['creation_settings']['dify_apikey'] == 'dify-secret'
        assert raw['creation_settings']['dify_apikey'] == 'dify-secret'

    @pytest.mark.asyncio
    async def test_new_masked_creation_secret_is_rejected(self):
        app = _app()

        with pytest.raises(ValueError, match='no existing value'):
            await KnowledgeService(app).create_knowledge_base(
                CONTEXT,
                {
                    'knowledge_engine_plugin_id': 'author/engine',
                    'creation_settings': {'dify_apikey': '***'},
                },
            )

        app.rag_mgr.create_knowledge_base.assert_not_awaited()
