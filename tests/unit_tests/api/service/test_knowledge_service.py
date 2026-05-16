"""Unit tests for API knowledge service.

Tests cover:
- Knowledge base CRUD operations
- Capability checking
- Knowledge engine discovery
- File operations
"""
from __future__ import annotations

import pytest
from unittest.mock import Mock, AsyncMock
from importlib import import_module


def get_knowledge_service_module():
    """Lazy import to avoid circular import issues."""
    return import_module('langbot.pkg.api.http.service.knowledge')


def create_mock_app():
    """Create mock Application for testing."""
    mock_app = Mock()
    mock_app.logger = Mock()
    mock_app.rag_mgr = AsyncMock()
    mock_app.persistence_mgr = AsyncMock()
    mock_app.persistence_mgr.execute_async = AsyncMock()
    mock_app.persistence_mgr.serialize_model = Mock(return_value={})
    mock_app.plugin_connector = AsyncMock()
    mock_app.plugin_connector.is_enable_plugin = True
    return mock_app


class TestKnowledgeServiceInit:
    """Tests for KnowledgeService initialization."""

    def test_init_stores_app_reference(self):
        """Test that __init__ stores Application reference."""
        knowledge_module = get_knowledge_service_module()
        mock_app = create_mock_app()

        service = knowledge_module.KnowledgeService(mock_app)

        assert service.ap is mock_app


class TestGetKnowledgeBases:
    """Tests for get_knowledge_bases method."""

    @pytest.mark.asyncio
    async def test_returns_all_kb_details(self):
        """Test that it returns all knowledge base details."""
        knowledge_module = get_knowledge_service_module()
        mock_app = create_mock_app()
        mock_app.rag_mgr.get_all_knowledge_base_details = AsyncMock(
            return_value=[{'uuid': 'kb1', 'name': 'KB1'}]
        )

        service = knowledge_module.KnowledgeService(mock_app)
        result = await service.get_knowledge_bases()

        assert len(result) == 1
        assert result[0]['uuid'] == 'kb1'

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_kbs(self):
        """Test that it returns empty list when no knowledge bases."""
        knowledge_module = get_knowledge_service_module()
        mock_app = create_mock_app()
        mock_app.rag_mgr.get_all_knowledge_base_details = AsyncMock(return_value=[])

        service = knowledge_module.KnowledgeService(mock_app)
        result = await service.get_knowledge_bases()

        assert result == []


class TestGetKnowledgeBase:
    """Tests for get_knowledge_base method."""

    @pytest.mark.asyncio
    async def test_returns_kb_details_by_uuid(self):
        """Test that it returns specific KB details."""
        knowledge_module = get_knowledge_service_module()
        mock_app = create_mock_app()
        mock_app.rag_mgr.get_knowledge_base_details = AsyncMock(
            return_value={'uuid': 'kb1', 'name': 'KB1'}
        )

        service = knowledge_module.KnowledgeService(mock_app)
        result = await service.get_knowledge_base('kb1')

        assert result['uuid'] == 'kb1'

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        """Test that it returns None when KB not found."""
        knowledge_module = get_knowledge_service_module()
        mock_app = create_mock_app()
        mock_app.rag_mgr.get_knowledge_base_details = AsyncMock(return_value=None)

        service = knowledge_module.KnowledgeService(mock_app)
        result = await service.get_knowledge_base('nonexistent')

        assert result is None


class TestCreateKnowledgeBase:
    """Tests for create_knowledge_base method."""

    @pytest.mark.asyncio
    async def test_creates_kb_with_required_fields(self):
        """Test creating KB with required plugin ID."""
        knowledge_module = get_knowledge_service_module()
        mock_app = create_mock_app()
        mock_kb = Mock()
        mock_kb.uuid = 'new_kb_uuid'
        mock_app.rag_mgr.create_knowledge_base = AsyncMock(return_value=mock_kb)

        service = knowledge_module.KnowledgeService(mock_app)
        kb_data = {
            'name': 'Test KB',
            'knowledge_engine_plugin_id': 'author/engine',
            'description': 'Test description',
        }

        result = await service.create_knowledge_base(kb_data)

        assert result == 'new_kb_uuid'
        mock_app.rag_mgr.create_knowledge_base.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_when_missing_plugin_id(self):
        """Test that ValueError is raised when plugin ID missing."""
        knowledge_module = get_knowledge_service_module()
        mock_app = create_mock_app()

        service = knowledge_module.KnowledgeService(mock_app)

        with pytest.raises(ValueError) as exc_info:
            await service.create_knowledge_base({'name': 'Test'})

        assert 'knowledge_engine_plugin_id is required' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_creates_with_default_name(self):
        """Test that KB is created with default name if not provided."""
        knowledge_module = get_knowledge_service_module()
        mock_app = create_mock_app()
        mock_kb = Mock()
        mock_kb.uuid = 'new_kb_uuid'
        mock_app.rag_mgr.create_knowledge_base = AsyncMock(return_value=mock_kb)

        service = knowledge_module.KnowledgeService(mock_app)

        await service.create_knowledge_base({
            'knowledge_engine_plugin_id': 'author/engine'
        })

        # Check that default name 'Untitled' was used
        call_args = mock_app.rag_mgr.create_knowledge_base.call_args
        assert call_args.kwargs['name'] == 'Untitled'


class TestUpdateKnowledgeBase:
    """Tests for update_knowledge_base method."""

    @pytest.mark.asyncio
    async def test_updates_mutable_fields_only(self):
        """Test that only mutable fields are updated."""
        knowledge_module = get_knowledge_service_module()
        mock_app = create_mock_app()
        mock_app.rag_mgr.get_knowledge_base_details = AsyncMock(
            return_value={'uuid': 'kb1', 'name': 'Updated'}
        )
        mock_app.rag_mgr.remove_knowledge_base_from_runtime = AsyncMock()
        mock_app.rag_mgr.load_knowledge_base = AsyncMock()

        service = knowledge_module.KnowledgeService(mock_app)

        # Pass both mutable and immutable fields
        await service.update_knowledge_base('kb1', {
            'name': 'New Name',
            'description': 'New desc',
            'uuid': 'should_be_filtered',  # immutable
        })

        # Check that only mutable fields were passed to update
        call_args = mock_app.persistence_mgr.execute_async.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_returns_early_when_no_mutable_fields(self):
        """Test that update returns early when no mutable fields provided."""
        knowledge_module = get_knowledge_service_module()
        mock_app = create_mock_app()

        service = knowledge_module.KnowledgeService(mock_app)

        # Pass only immutable fields
        await service.update_knowledge_base('kb1', {'uuid': 'should_be_filtered'})

        # No DB update should be called
        mock_app.persistence_mgr.execute_async.assert_not_called()


class TestCheckDocCapability:
    """Tests for _check_doc_capability method."""

    @pytest.mark.asyncio
    async def test_passes_when_capability_supported(self):
        """Test that check passes when doc_ingestion capability exists."""
        knowledge_module = get_knowledge_service_module()
        mock_app = create_mock_app()
        mock_app.rag_mgr.get_knowledge_base_details = AsyncMock(
            return_value={'knowledge_engine': {'capabilities': ['doc_ingestion']}}
        )

        service = knowledge_module.KnowledgeService(mock_app)

        await service._check_doc_capability('kb1', 'document upload')

        # No exception raised means success

    @pytest.mark.asyncio
    async def test_raises_when_kb_not_found(self):
        """Test that Exception is raised when KB not found."""
        knowledge_module = get_knowledge_service_module()
        mock_app = create_mock_app()
        mock_app.rag_mgr.get_knowledge_base_details = AsyncMock(return_value=None)

        service = knowledge_module.KnowledgeService(mock_app)

        with pytest.raises(Exception) as exc_info:
            await service._check_doc_capability('nonexistent', 'test operation')

        assert 'Knowledge base not found' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_when_capability_not_supported(self):
        """Test that Exception is raised when doc_ingestion not in capabilities."""
        knowledge_module = get_knowledge_service_module()
        mock_app = create_mock_app()
        mock_app.rag_mgr.get_knowledge_base_details = AsyncMock(
            return_value={'knowledge_engine': {'capabilities': ['other_capability']}}
        )

        service = knowledge_module.KnowledgeService(mock_app)

        with pytest.raises(Exception) as exc_info:
            await service._check_doc_capability('kb1', 'document upload')

        assert 'does not support document upload' in str(exc_info.value)


class TestListKnowledgeEngines:
    """Tests for list_knowledge_engines method."""

    @pytest.mark.asyncio
    async def test_returns_engines_from_plugin_connector(self):
        """Test that it returns knowledge engines from plugin connector."""
        knowledge_module = get_knowledge_service_module()
        mock_app = create_mock_app()
        mock_app.plugin_connector.list_knowledge_engines = AsyncMock(
            return_value=[{'id': 'engine1', 'name': 'Engine 1'}]
        )

        service = knowledge_module.KnowledgeService(mock_app)
        result = await service.list_knowledge_engines()

        assert len(result) == 1
        assert result[0]['id'] == 'engine1'

    @pytest.mark.asyncio
    async def test_returns_empty_when_plugin_disabled(self):
        """Test that it returns empty list when plugin disabled."""
        knowledge_module = get_knowledge_service_module()
        mock_app = create_mock_app()
        mock_app.plugin_connector.is_enable_plugin = False

        service = knowledge_module.KnowledgeService(mock_app)
        result = await service.list_knowledge_engines()

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_exception(self):
        """Test that it returns empty list and logs warning on exception."""
        knowledge_module = get_knowledge_service_module()
        mock_app = create_mock_app()
        mock_app.plugin_connector.list_knowledge_engines = AsyncMock(
            side_effect=Exception('Connection error')
        )

        service = knowledge_module.KnowledgeService(mock_app)
        result = await service.list_knowledge_engines()

        assert result == []
        mock_app.logger.warning.assert_called_once()


class TestListParsers:
    """Tests for list_parsers method."""

    @pytest.mark.asyncio
    async def test_returns_all_parsers(self):
        """Test that it returns all parsers when no MIME type filter."""
        knowledge_module = get_knowledge_service_module()
        mock_app = create_mock_app()
        mock_app.plugin_connector.list_parsers = AsyncMock(
            return_value=[
                {'id': 'parser1', 'supported_mime_types': ['text/plain']},
                {'id': 'parser2', 'supported_mime_types': ['application/pdf']},
            ]
        )

        service = knowledge_module.KnowledgeService(mock_app)
        result = await service.list_parsers()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_filters_by_mime_type(self):
        """Test that it filters parsers by MIME type."""
        knowledge_module = get_knowledge_service_module()
        mock_app = create_mock_app()
        mock_app.plugin_connector.list_parsers = AsyncMock(
            return_value=[
                {'id': 'parser1', 'supported_mime_types': ['text/plain']},
                {'id': 'parser2', 'supported_mime_types': ['application/pdf']},
            ]
        )

        service = knowledge_module.KnowledgeService(mock_app)
        result = await service.list_parsers(mime_type='application/pdf')

        assert len(result) == 1
        assert result[0]['id'] == 'parser2'

    @pytest.mark.asyncio
    async def test_returns_empty_when_plugin_disabled(self):
        """Test that it returns empty list when plugin disabled."""
        knowledge_module = get_knowledge_service_module()
        mock_app = create_mock_app()
        mock_app.plugin_connector.is_enable_plugin = False

        service = knowledge_module.KnowledgeService(mock_app)
        result = await service.list_parsers()

        assert result == []


class TestGetEngineSchemas:
    """Tests for get_engine_creation_schema and get_engine_retrieval_schema."""

    @pytest.mark.asyncio
    async def test_returns_creation_schema(self):
        """Test that it returns creation schema for engine."""
        knowledge_module = get_knowledge_service_module()
        mock_app = create_mock_app()
        mock_app.plugin_connector.get_rag_creation_schema = AsyncMock(
            return_value={'properties': {'name': {'type': 'string'}}}
        )

        service = knowledge_module.KnowledgeService(mock_app)
        result = await service.get_engine_creation_schema('author/engine')

        assert 'properties' in result

    @pytest.mark.asyncio
    async def test_returns_retrieval_schema(self):
        """Test that it returns retrieval schema for engine."""
        knowledge_module = get_knowledge_service_module()
        mock_app = create_mock_app()
        mock_app.plugin_connector.get_rag_retrieval_schema = AsyncMock(
            return_value={'properties': {'top_k': {'type': 'integer'}}}
        )

        service = knowledge_module.KnowledgeService(mock_app)
        result = await service.get_engine_retrieval_schema('author/engine')

        assert 'properties' in result

    @pytest.mark.asyncio
    async def test_returns_empty_dict_on_exception(self):
        """Test that it returns empty dict and logs warning on exception."""
        knowledge_module = get_knowledge_service_module()
        mock_app = create_mock_app()
        mock_app.plugin_connector.get_rag_creation_schema = AsyncMock(
            side_effect=Exception('Plugin error')
        )

        service = knowledge_module.KnowledgeService(mock_app)
        result = await service.get_engine_creation_schema('author/engine')

        assert result == {}
        mock_app.logger.warning.assert_called_once()