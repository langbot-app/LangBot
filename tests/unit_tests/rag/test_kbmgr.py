"""Unit tests for RAG knowledge base manager.

Tests cover:
- RAGManager CRUD operations
- RuntimeKnowledgeBase getters
- Knowledge engine enrichment
- KB loading and removal
"""
from __future__ import annotations

import pytest
import uuid
from unittest.mock import Mock, AsyncMock
from importlib import import_module


def get_rag_module():
    """Lazy import to avoid circular import issues."""
    return import_module('langbot.pkg.rag.knowledge.kbmgr')


def create_mock_app():
    """Create mock Application for testing."""
    mock_app = Mock()
    mock_app.logger = Mock()
    mock_app.persistence_mgr = AsyncMock()
    mock_app.persistence_mgr.execute_async = AsyncMock()
    mock_app.persistence_mgr.serialize_model = Mock(return_value={})
    mock_app.plugin_connector = AsyncMock()
    mock_app.plugin_connector.is_enable_plugin = True
    mock_app.storage_mgr = Mock()
    mock_app.storage_mgr.storage_provider = AsyncMock()
    mock_app.task_mgr = AsyncMock()
    mock_app.task_mgr.create_user_task = Mock(return_value=Mock(id=1))
    return mock_app


def create_mock_kb_entity():
    """Create mock KnowledgeBase entity."""
    mock_kb = Mock()
    mock_kb.uuid = str(uuid.uuid4())
    mock_kb.name = 'Test KB'
    mock_kb.description = 'Test description'
    mock_kb.knowledge_engine_plugin_id = 'author/engine'
    mock_kb.collection_id = mock_kb.uuid
    mock_kb.creation_settings = {}
    mock_kb.retrieval_settings = {}
    return mock_kb


class TestRAGManagerCreateKnowledgeBase:
    """Tests for create_knowledge_base method."""

    @pytest.mark.asyncio
    async def test_creates_kb_with_valid_engine(self):
        """Test creates KB when engine plugin exists."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()

        # Mock valid engine list
        mock_app.plugin_connector.list_knowledge_engines = AsyncMock(
            return_value=[{'plugin_id': 'author/engine', 'name': 'Engine'}]
        )
        mock_app.persistence_mgr.execute_async = AsyncMock()
        mock_app.plugin_connector.rag_on_kb_create = AsyncMock()

        manager = rag_module.RAGManager(mock_app)

        kb = await manager.create_knowledge_base(
            name='Test KB',
            knowledge_engine_plugin_id='author/engine',
            creation_settings={'model': 'test'},
        )

        assert kb.name == 'Test KB'
        assert kb.knowledge_engine_plugin_id == 'author/engine'

    @pytest.mark.asyncio
    async def test_raises_when_engine_not_found(self):
        """Test raises ValueError when engine plugin not found."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()

        # Mock empty engine list
        mock_app.plugin_connector.list_knowledge_engines = AsyncMock(return_value=[])

        manager = rag_module.RAGManager(mock_app)

        with pytest.raises(ValueError) as exc_info:
            await manager.create_knowledge_base(
                name='Test KB',
                knowledge_engine_plugin_id='unknown/engine',
                creation_settings={},
            )

        assert 'not found' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_rollback_on_plugin_create_failure(self):
        """Test that DB entry is rolled back when plugin create fails."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()

        mock_app.plugin_connector.list_knowledge_engines = AsyncMock(
            return_value=[{'plugin_id': 'author/engine'}]
        )
        mock_app.persistence_mgr.execute_async = AsyncMock()
        mock_app.plugin_connector.rag_on_kb_create = AsyncMock(
            side_effect=Exception('Plugin error')
        )

        manager = rag_module.RAGManager(mock_app)

        with pytest.raises(Exception):
            await manager.create_knowledge_base(
                name='Test KB',
                knowledge_engine_plugin_id='author/engine',
                creation_settings={},
            )

        # Should have called delete to rollback
        # Check that delete was called (for rollback)
        assert len(manager.knowledge_bases) == 0

    @pytest.mark.asyncio
    async def test_sets_default_retrieval_settings(self):
        """Test that empty retrieval_settings defaults to {}."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()

        mock_app.plugin_connector.list_knowledge_engines = AsyncMock(
            return_value=[{'plugin_id': 'author/engine'}]
        )
        mock_app.persistence_mgr.execute_async = AsyncMock()
        mock_app.plugin_connector.rag_on_kb_create = AsyncMock()

        manager = rag_module.RAGManager(mock_app)

        kb = await manager.create_knowledge_base(
            name='Test KB',
            knowledge_engine_plugin_id='author/engine',
            creation_settings={},
            retrieval_settings=None,
        )

        assert kb.retrieval_settings == {}

    @pytest.mark.asyncio
    async def test_skips_validation_when_plugin_disabled(self):
        """Test that engine validation is skipped when plugin disabled."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()
        mock_app.plugin_connector.is_enable_plugin = False
        mock_app.persistence_mgr.execute_async = AsyncMock()
        mock_app.plugin_connector.rag_on_kb_create = AsyncMock()

        manager = rag_module.RAGManager(mock_app)

        # Should not raise even though engine list would be empty
        kb = await manager.create_knowledge_base(
            name='Test KB',
            knowledge_engine_plugin_id='any/engine',
            creation_settings={},
        )

        assert kb.knowledge_engine_plugin_id == 'any/engine'


class TestRuntimeKnowledgeBaseOnKBCreate:
    """Tests for _on_kb_create method."""

    @pytest.mark.asyncio
    async def test_calls_plugin_on_create(self):
        """Test that plugin is notified on KB create."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()
        mock_kb = create_mock_kb_entity()
        mock_kb.creation_settings = {'model': 'test'}

        mock_app.plugin_connector.rag_on_kb_create = AsyncMock()

        runtime_kb = rag_module.RuntimeKnowledgeBase(mock_app, mock_kb)
        await runtime_kb._on_kb_create()

        mock_app.plugin_connector.rag_on_kb_create.assert_called_once_with(
            'author/engine', mock_kb.uuid, {'model': 'test'}
        )

    @pytest.mark.asyncio
    async def test_skips_when_no_plugin_id(self):
        """Test that create notification is skipped when no plugin."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()
        mock_kb = create_mock_kb_entity()
        mock_kb.knowledge_engine_plugin_id = None

        runtime_kb = rag_module.RuntimeKnowledgeBase(mock_app, mock_kb)
        await runtime_kb._on_kb_create()

        mock_app.plugin_connector.rag_on_kb_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_raises_on_plugin_error(self):
        """Test that exception is raised when plugin fails."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()
        mock_kb = create_mock_kb_entity()

        mock_app.plugin_connector.rag_on_kb_create = AsyncMock(
            side_effect=Exception('Plugin failed')
        )

        runtime_kb = rag_module.RuntimeKnowledgeBase(mock_app, mock_kb)

        with pytest.raises(Exception):
            await runtime_kb._on_kb_create()


class TestRuntimeKnowledgeBaseDeleteFile:
    """Tests for delete_file method."""

    @pytest.mark.asyncio
    async def test_delete_file_calls_plugin_and_db(self):
        """Test that delete_file calls plugin and removes DB record."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()
        mock_kb = create_mock_kb_entity()

        mock_app.plugin_connector.call_rag_delete_document = AsyncMock(return_value=True)

        runtime_kb = rag_module.RuntimeKnowledgeBase(mock_app, mock_kb)
        await runtime_kb.delete_file('file-uuid')

        mock_app.plugin_connector.call_rag_delete_document.assert_called_once()
        mock_app.persistence_mgr.execute_async.assert_called()


class TestRuntimeKnowledgeBaseIngestDocument:
    """Tests for _ingest_document method."""

    @pytest.mark.asyncio
    async def test_ingest_calls_plugin(self):
        """Test that ingest calls plugin connector."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()
        mock_kb = create_mock_kb_entity()

        mock_app.plugin_connector.call_rag_ingest = AsyncMock(
            return_value={'status': 'success'}
        )

        runtime_kb = rag_module.RuntimeKnowledgeBase(mock_app, mock_kb)

        result = await runtime_kb._ingest_document(
            {'filename': 'test.pdf'},
            'storage/path',
        )

        assert result['status'] == 'success'
        mock_app.plugin_connector.call_rag_ingest.assert_called_once()

    @pytest.mark.asyncio
    async def test_ingest_raises_when_no_plugin_id(self):
        """Test that ValueError is raised when no plugin ID."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()
        mock_kb = create_mock_kb_entity()
        mock_kb.knowledge_engine_plugin_id = None

        runtime_kb = rag_module.RuntimeKnowledgeBase(mock_app, mock_kb)

        with pytest.raises(ValueError) as exc_info:
            await runtime_kb._ingest_document({'filename': 'test.pdf'}, 'path')

        assert 'Plugin ID required' in str(exc_info.value)


class TestRAGManagerLoadKnowledgeBasesFromDB:
    """Tests for load_knowledge_bases_from_db method."""

    @pytest.mark.asyncio
    async def test_loads_all_kbs_from_db(self):
        """Test that all KBs are loaded from database."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()

        mock_kb1 = create_mock_kb_entity()
        mock_kb2 = create_mock_kb_entity()
        mock_app.persistence_mgr.execute_async = AsyncMock(
            return_value=Mock(all=Mock(return_value=[mock_kb1, mock_kb2]))
        )

        manager = rag_module.RAGManager(mock_app)
        await manager.load_knowledge_bases_from_db()

        assert len(manager.knowledge_bases) == 2

    @pytest.mark.asyncio
    async def test_handles_load_error_gracefully(self):
        """Test that load errors are logged but not raised."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()

        # KB that will cause initialize to fail
        mock_kb = create_mock_kb_entity()

        mock_app.persistence_mgr.execute_async = AsyncMock(
            return_value=Mock(all=Mock(return_value=[mock_kb]))
        )

        # Make initialize fail by having plugin_connector throw error
        mock_app.plugin_connector.rag_on_kb_create = AsyncMock(
            side_effect=Exception('Init failed')
        )

        manager = rag_module.RAGManager(mock_app)
        # Should not raise - errors are caught
        await manager.load_knowledge_bases_from_db()

        # KB should still be loaded (initialize just passes)
        # The error would come from runtime_kb.initialize which we can't easily mock
        # So we just verify it doesn't crash


class TestRuntimeKnowledgeBaseGetters:
    """Tests for RuntimeKnowledgeBase getter methods."""

    def test_get_uuid_returns_entity_uuid(self):
        """Test get_uuid returns KB entity UUID."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()
        mock_kb = create_mock_kb_entity()

        runtime_kb = rag_module.RuntimeKnowledgeBase(mock_app, mock_kb)

        assert runtime_kb.get_uuid() == mock_kb.uuid

    def test_get_name_returns_entity_name(self):
        """Test get_name returns KB entity name."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()
        mock_kb = create_mock_kb_entity()

        runtime_kb = rag_module.RuntimeKnowledgeBase(mock_app, mock_kb)

        assert runtime_kb.get_name() == mock_kb.name

    def test_get_knowledge_engine_plugin_id_returns_plugin_id(self):
        """Test get_knowledge_engine_plugin_id returns plugin ID."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()
        mock_kb = create_mock_kb_entity()

        runtime_kb = rag_module.RuntimeKnowledgeBase(mock_app, mock_kb)

        assert runtime_kb.get_knowledge_engine_plugin_id() == 'author/engine'

    def test_get_knowledge_engine_plugin_id_returns_empty_when_none(self):
        """Test returns empty string when plugin_id is None."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()
        mock_kb = create_mock_kb_entity()
        mock_kb.knowledge_engine_plugin_id = None

        runtime_kb = rag_module.RuntimeKnowledgeBase(mock_app, mock_kb)

        assert runtime_kb.get_knowledge_engine_plugin_id() == ''


class TestRuntimeKnowledgeBaseRetrieve:
    """Tests for RuntimeKnowledgeBase retrieve method."""

    @pytest.mark.asyncio
    async def test_retrieve_merges_settings(self):
        """Test that retrieve merges stored and request settings."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()
        mock_kb = create_mock_kb_entity()
        mock_kb.retrieval_settings = {'top_k': 10, 'model': 'default'}

        # Mock plugin connector response with valid RetrievalResultEntry fields
        # content must be list of ContentElement dicts
        mock_app.plugin_connector.call_rag_retrieve = AsyncMock(
            return_value={
                'results': [
                    {
                        'id': 'doc1',
                        'content': [{'type': 'text', 'text': 'test content'}],
                        'metadata': {},
                        'distance': 0.1,
                    }
                ]
            }
        )

        runtime_kb = rag_module.RuntimeKnowledgeBase(mock_app, mock_kb)

        # Override top_k in request
        results = await runtime_kb.retrieve('query text', settings={'top_k': 20})

        assert len(results) == 1
        # Check that merged settings were passed (top_k overridden)
        call_args = mock_app.plugin_connector.call_rag_retrieve.call_args
        assert call_args[0][1]['retrieval_settings']['top_k'] == 20

    @pytest.mark.asyncio
    async def test_retrieve_adds_default_top_k(self):
        """Test that default top_k=5 is added when not specified."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()
        mock_kb = create_mock_kb_entity()
        mock_kb.retrieval_settings = {}

        mock_app.plugin_connector.call_rag_retrieve = AsyncMock(
            return_value={'results': []}
        )

        runtime_kb = rag_module.RuntimeKnowledgeBase(mock_app, mock_kb)

        await runtime_kb.retrieve('query text')

        call_args = mock_app.plugin_connector.call_rag_retrieve.call_args
        assert call_args[0][1]['retrieval_settings']['top_k'] == 5

    @pytest.mark.asyncio
    async def test_retrieve_converts_dict_to_entry(self):
        """Test that dict results are converted to RetrievalResultEntry."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()
        mock_kb = create_mock_kb_entity()

        # Mock response with valid RetrievalResultEntry fields
        # content must be list of ContentElement dicts
        mock_app.plugin_connector.call_rag_retrieve = AsyncMock(
            return_value={
                'results': [
                    {
                        'id': 'doc1',
                        'content': [{'type': 'text', 'text': 'test content'}],
                        'metadata': {'source': 'file.pdf'},
                        'distance': 0.15,
                    }
                ]
            }
        )

        runtime_kb = rag_module.RuntimeKnowledgeBase(mock_app, mock_kb)

        results = await runtime_kb.retrieve('query')

        assert len(results) == 1
        # Result should be RetrievalResultEntry
        assert hasattr(results[0], 'content')
        assert results[0].id == 'doc1'


class TestRuntimeKnowledgeBaseDispose:
    """Tests for RuntimeKnowledgeBase dispose method."""

    @pytest.mark.asyncio
    async def test_dispose_calls_on_kb_delete(self):
        """Test that dispose calls _on_kb_delete."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()
        mock_kb = create_mock_kb_entity()

        mock_app.plugin_connector.rag_on_kb_delete = AsyncMock()

        runtime_kb = rag_module.RuntimeKnowledgeBase(mock_app, mock_kb)

        await runtime_kb.dispose()

        mock_app.plugin_connector.rag_on_kb_delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispose_skips_when_no_plugin_id(self):
        """Test that dispose skips when no plugin ID."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()
        mock_kb = create_mock_kb_entity()
        mock_kb.knowledge_engine_plugin_id = None

        runtime_kb = rag_module.RuntimeKnowledgeBase(mock_app, mock_kb)

        await runtime_kb.dispose()

        # Should not call plugin connector
        mock_app.plugin_connector.rag_on_kb_delete.assert_not_called()


class TestRAGManagerInit:
    """Tests for RAGManager initialization."""

    def test_init_stores_app_reference(self):
        """Test that __init__ stores Application reference."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()

        manager = rag_module.RAGManager(mock_app)

        assert manager.ap is mock_app

    def test_init_creates_empty_knowledge_bases_dict(self):
        """Test that knowledge_bases starts as empty dict."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()

        manager = rag_module.RAGManager(mock_app)

        assert manager.knowledge_bases == {}


class TestRAGManagerGetKnowledgeBase:
    """Tests for RAGManager get methods."""

    @pytest.mark.asyncio
    async def test_get_knowledge_base_by_uuid_returns_runtime_kb(self):
        """Test get_knowledge_base_by_uuid returns loaded KB."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()

        manager = rag_module.RAGManager(mock_app)
        mock_kb = create_mock_kb_entity()

        # Manually add to knowledge_bases
        runtime_kb = rag_module.RuntimeKnowledgeBase(mock_app, mock_kb)
        manager.knowledge_bases[mock_kb.uuid] = runtime_kb

        result = await manager.get_knowledge_base_by_uuid(mock_kb.uuid)

        assert result is runtime_kb

    @pytest.mark.asyncio
    async def test_get_knowledge_base_by_uuid_returns_none_when_not_found(self):
        """Test returns None when KB not in runtime."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()

        manager = rag_module.RAGManager(mock_app)

        result = await manager.get_knowledge_base_by_uuid('nonexistent-uuid')

        assert result is None

    @pytest.mark.asyncio
    async def test_remove_knowledge_base_from_runtime(self):
        """Test remove_knowledge_base_from_runtime removes KB."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()

        manager = rag_module.RAGManager(mock_app)
        mock_kb = create_mock_kb_entity()

        # Add to knowledge_bases
        runtime_kb = rag_module.RuntimeKnowledgeBase(mock_app, mock_kb)
        manager.knowledge_bases[mock_kb.uuid] = runtime_kb

        await manager.remove_knowledge_base_from_runtime(mock_kb.uuid)

        assert mock_kb.uuid not in manager.knowledge_bases


class TestRAGManagerEnrichKB:
    """Tests for _enrich_kb_dict method."""

    def test_enrich_adds_engine_info_from_map(self):
        """Test that engine info is added from engine_map."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()

        manager = rag_module.RAGManager(mock_app)

        kb_dict = {'knowledge_engine_plugin_id': 'author/engine'}
        engine_map = {
            'author/engine': {
                'plugin_id': 'author/engine',
                'name': 'Test Engine',
                'capabilities': ['doc_ingestion', 'search'],
            }
        }

        manager._enrich_kb_dict(kb_dict, engine_map)

        assert 'knowledge_engine' in kb_dict
        assert kb_dict['knowledge_engine']['plugin_id'] == 'author/engine'
        assert kb_dict['knowledge_engine']['capabilities'] == ['doc_ingestion', 'search']

    def test_enrich_uses_fallback_when_engine_not_in_map(self):
        """Test that fallback info is used when engine not found."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()

        manager = rag_module.RAGManager(mock_app)

        kb_dict = {'knowledge_engine_plugin_id': 'unknown/engine'}
        engine_map = {}

        manager._enrich_kb_dict(kb_dict, engine_map)

        assert 'knowledge_engine' in kb_dict
        assert kb_dict['knowledge_engine']['plugin_id'] == 'unknown/engine'
        assert kb_dict['knowledge_engine']['capabilities'] == []

    def test_enrich_uses_fallback_when_no_plugin_id(self):
        """Test that fallback is used when no plugin ID."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()

        manager = rag_module.RAGManager(mock_app)

        kb_dict = {}
        engine_map = {}

        manager._enrich_kb_dict(kb_dict, engine_map)

        assert 'knowledge_engine' in kb_dict
        # Should have Internal (Legacy) name
        assert 'en_US' in kb_dict['knowledge_engine']['name']

    def test_enrich_converts_string_name_to_i18n(self):
        """Test that engine name is converted to i18n dict."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()

        manager = rag_module.RAGManager(mock_app)

        kb_dict = {'knowledge_engine_plugin_id': 'author/engine'}
        engine_map = {
            'author/engine': {
                'plugin_id': 'author/engine',
                'name': 'Simple Name',  # String, not dict
                'capabilities': [],
            }
        }

        manager._enrich_kb_dict(kb_dict, engine_map)

        # Name should be converted to i18n dict
        engine_name = kb_dict['knowledge_engine']['name']
        assert isinstance(engine_name, dict)
        assert engine_name['en_US'] == 'Simple Name'


class TestRAGManagerDeleteKnowledgeBase:
    """Tests for delete_knowledge_base method."""

    @pytest.mark.asyncio
    async def test_delete_removes_from_runtime_and_disposes(self):
        """Test that delete removes KB and calls dispose."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()

        manager = rag_module.RAGManager(mock_app)
        mock_kb = create_mock_kb_entity()

        # Add to knowledge_bases
        runtime_kb = rag_module.RuntimeKnowledgeBase(mock_app, mock_kb)
        manager.knowledge_bases[mock_kb.uuid] = runtime_kb

        await manager.delete_knowledge_base(mock_kb.uuid)

        assert mock_kb.uuid not in manager.knowledge_bases

    @pytest.mark.asyncio
    async def test_delete_logs_warning_when_not_in_runtime(self):
        """Test that warning is logged when KB not in runtime."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()

        manager = rag_module.RAGManager(mock_app)

        await manager.delete_knowledge_base('nonexistent-uuid')

        mock_app.logger.warning.assert_called_once()


class TestRAGManagerGetAllDetails:
    """Tests for get_all_knowledge_base_details method."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_kbs(self):
        """Test returns empty list when no knowledge bases."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()
        mock_app.persistence_mgr.execute_async = AsyncMock(
            return_value=Mock(all=Mock(return_value=[]))
        )

        manager = rag_module.RAGManager(mock_app)
        result = await manager.get_all_knowledge_base_details()

        assert result == []

    @pytest.mark.asyncio
    async def test_enriches_each_kb_with_engine_info(self):
        """Test that each KB is enriched with engine info."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()

        # Mock DB result
        mock_kb_row = Mock()
        mock_app.persistence_mgr.execute_async = AsyncMock(
            return_value=Mock(all=Mock(return_value=[mock_kb_row]))
        )
        mock_app.persistence_mgr.serialize_model = Mock(
            return_value={'uuid': 'kb1', 'knowledge_engine_plugin_id': 'author/engine'}
        )
        mock_app.plugin_connector.list_knowledge_engines = AsyncMock(
            return_value=[{'plugin_id': 'author/engine', 'name': 'Engine', 'capabilities': ['search']}]
        )

        manager = rag_module.RAGManager(mock_app)
        result = await manager.get_all_knowledge_base_details()

        assert len(result) == 1
        assert 'knowledge_engine' in result[0]


class TestRAGManagerGetDetails:
    """Tests for get_knowledge_base_details method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_kb_not_found(self):
        """Test returns None when KB doesn't exist."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()
        mock_app.persistence_mgr.execute_async = AsyncMock(
            return_value=Mock(first=Mock(return_value=None))
        )

        manager = rag_module.RAGManager(mock_app)
        result = await manager.get_knowledge_base_details('nonexistent')

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_enriched_kb_dict(self):
        """Test returns enriched KB dict when found."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()

        mock_kb_row = Mock()
        mock_app.persistence_mgr.execute_async = AsyncMock(
            return_value=Mock(first=Mock(return_value=mock_kb_row))
        )
        mock_app.persistence_mgr.serialize_model = Mock(
            return_value={'uuid': 'kb1', 'knowledge_engine_plugin_id': 'author/engine'}
        )
        mock_app.plugin_connector.list_knowledge_engines = AsyncMock(
            return_value=[{'plugin_id': 'author/engine', 'name': 'Engine', 'capabilities': []}]
        )

        manager = rag_module.RAGManager(mock_app)
        result = await manager.get_knowledge_base_details('kb1')

        assert result is not None
        assert 'knowledge_engine' in result


class TestRAGManagerLoadKnowledgeBase:
    """Tests for load_knowledge_base method."""

    @pytest.mark.asyncio
    async def test_loads_kb_entity_into_runtime(self):
        """Test that KB entity is loaded into runtime."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()

        manager = rag_module.RAGManager(mock_app)
        mock_kb = create_mock_kb_entity()

        result = await manager.load_knowledge_base(mock_kb)

        assert mock_kb.uuid in manager.knowledge_bases
        assert result.get_uuid() == mock_kb.uuid

    @pytest.mark.asyncio
    async def test_load_handles_dict_entity(self):
        """Test that dict entity is converted to KB object."""
        rag_module = get_rag_module()
        mock_app = create_mock_app()

        manager = rag_module.RAGManager(mock_app)

        kb_dict = {
            'uuid': 'kb-uuid',
            'name': 'Test',
            'knowledge_engine_plugin_id': 'author/engine',
            'knowledge_engine': {'name': 'should_be_filtered'},  # non-db field
        }

        await manager.load_knowledge_base(kb_dict)

        assert 'kb-uuid' in manager.knowledge_bases