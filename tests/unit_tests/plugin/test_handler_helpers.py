"""Unit tests for plugin handler helper functions and methods.

Tests cover:
- _make_rag_error_response() helper function
- RuntimeConnectionHandler cleanup_plugin_data method
"""
from __future__ import annotations

import pytest
from unittest.mock import Mock, AsyncMock
from importlib import import_module


def get_handler_module():
    """Lazy import to avoid circular import issues."""
    return import_module('langbot.pkg.plugin.handler')


class TestMakeRagErrorResponse:
    """Tests for _make_rag_error_response helper function."""

    def test_creates_error_response_with_exception(self):
        """Test basic error response creation."""
        handler = get_handler_module()

        error = ValueError("test error message")
        result = handler._make_rag_error_response(error, 'TestError')

        # ActionResponse.error() returns code=1 (error status)
        assert result.code == 1
        assert 'TestError' in result.message
        assert 'ValueError' in result.message
        assert 'test error message' in result.message

    def test_includes_error_type_in_message(self):
        """Test that error type is included in message."""
        handler = get_handler_module()

        error = RuntimeError("something went wrong")
        result = handler._make_rag_error_response(error, 'VectorStoreError')

        assert '[VectorStoreError/RuntimeError]' in result.message

    def test_includes_extra_context_in_message(self):
        """Test that extra context fields are included."""
        handler = get_handler_module()

        error = Exception("embedding failed")
        result = handler._make_rag_error_response(
            error,
            'EmbeddingError',
            embedding_model_uuid='test-uuid-123',
            collection_id='collection-456',
        )

        assert 'embedding_model_uuid=test-uuid-123' in result.message
        assert 'collection_id=collection-456' in result.message

    def test_handles_exception_with_no_message(self):
        """Test handling exception with empty message."""
        handler = get_handler_module()

        error = Exception()
        result = handler._make_rag_error_response(error, 'GenericError')

        # ActionResponse.error() returns code=1 (error status)
        assert result.code == 1
        assert '[GenericError/Exception]' in result.message

    def test_formats_context_with_multiple_fields(self):
        """Test multiple context fields are comma separated."""
        handler = get_handler_module()

        error = IOError("file not found")
        result = handler._make_rag_error_response(
            error,
            'FileServiceError',
            storage_path='/data/file.pdf',
            kb_id='kb-001',
        )

        assert '[storage_path=/data/file.pdf, kb_id=kb-001]' in result.message


class TestCleanupPluginData:
    """Tests for cleanup_plugin_data method."""

    @pytest.mark.asyncio
    async def test_deletes_plugin_settings(self):
        """Test that plugin settings are deleted."""
        handler_module = get_handler_module()

        mock_app = Mock()
        mock_app.persistence_mgr = AsyncMock()
        mock_app.persistence_mgr.execute_async = AsyncMock()

        # Mock the handler without connection (we only need ap)
        handler_instance = Mock(spec=handler_module.RuntimeConnectionHandler)
        handler_instance.ap = mock_app

        # Call cleanup_plugin_data
        await handler_module.RuntimeConnectionHandler.cleanup_plugin_data(
            handler_instance, 'test-author', 'test-plugin'
        )

        # Verify plugin settings delete was called
        calls = mock_app.persistence_mgr.execute_async.call_args_list
        assert len(calls) >= 1

    @pytest.mark.asyncio
    async def test_deletes_binary_storage(self):
        """Test that binary storage is deleted."""
        handler_module = get_handler_module()

        mock_app = Mock()
        mock_app.persistence_mgr = AsyncMock()
        mock_app.persistence_mgr.execute_async = AsyncMock()

        handler_instance = Mock(spec=handler_module.RuntimeConnectionHandler)
        handler_instance.ap = mock_app

        await handler_module.RuntimeConnectionHandler.cleanup_plugin_data(
            handler_instance, 'author', 'plugin-name'
        )

        # Should have at least 2 calls: one for settings, one for binary storage
        assert mock_app.persistence_mgr.execute_async.call_count >= 2