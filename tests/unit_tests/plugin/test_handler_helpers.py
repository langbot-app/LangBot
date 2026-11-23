"""Unit tests for plugin handler helper functions and methods.

Tests cover:
- _make_rag_error_response() helper function
- RuntimeConnectionHandler cleanup_plugin_data method
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock, AsyncMock
from importlib import import_module
from types import SimpleNamespace


@pytest.mark.parametrize(
    'call_args',
    [
        {'num_retries': 0},
        {'max_retries': 0},
        {'timeout': 3},
        {'request_policy': {'stream_idle_timeout': 2}},
    ],
)
def test_llm_bridge_keeps_model_and_call_policy_layers_separate(call_args):
    from langbot.pkg.provider.modelmgr.request_policy import RequestPolicy

    model_args = {'temperature': 0.2, 'request_policy': {'retries': 2, 'read_timeout': 90}}
    model = SimpleNamespace(model_entity=SimpleNamespace(extra_args=model_args))
    merged = get_handler_module()._merge_model_extra_args(model, call_args, llm_policy=True)
    assert RequestPolicy.resolve(model_args, merged) == RequestPolicy.resolve(model_args, call_args)
    assert merged['temperature'] == 0.2
    assert model_args['request_policy'] == {'retries': 2, 'read_timeout': 90}


def get_handler_module():
    """Lazy import to avoid circular import issues."""
    return import_module('langbot.pkg.plugin.handler')


class TestMakeRagErrorResponse:
    """Tests for _make_rag_error_response helper function."""

    def test_creates_error_response_with_exception(self):
        """Test basic error response creation."""
        handler = get_handler_module()

        error = ValueError('test error message')
        result = handler._make_rag_error_response(error, 'TestError')

        # ActionResponse.error() returns code=1 (error status)
        assert result.code == 1
        assert 'TestError' in result.message
        assert 'ValueError' in result.message
        assert 'test error message' in result.message

    def test_includes_error_type_in_message(self):
        """Test that error type is included in message."""
        handler = get_handler_module()

        error = RuntimeError('something went wrong')
        result = handler._make_rag_error_response(error, 'VectorStoreError')

        assert '[VectorStoreError/RuntimeError]' in result.message

    def test_includes_extra_context_in_message(self):
        """Test that extra context fields are included."""
        handler = get_handler_module()

        error = Exception('embedding failed')
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

        error = IOError('file not found')
        result = handler._make_rag_error_response(
            error,
            'FileServiceError',
            storage_path='/data/file.pdf',
            kb_id='kb-001',
        )

        assert '[storage_path=/data/file.pdf, kb_id=kb-001]' in result.message


class TestCleanupPluginData:
    """Tests for cleanup_plugin_data method."""

    @pytest.fixture
    async def cleanup(self, plugin_db):
        from langbot.pkg.entity.persistence.plugin import PluginSetting
        from langbot.pkg.entity.persistence.bstorage import BinaryStorage
        from langbot_plugin.entities.io.context import InstallationBinding

        plugin_db.add_all(
            PluginSetting(workspace_uuid=workspace, plugin_author=author, plugin_name=name)
            for workspace, author, name in [
                ('workspace-a', 'test-author', 'test-plugin'),
                ('workspace-b', 'test-author', 'test-plugin'),
                ('workspace-a', 'other-author', 'test-plugin'),
                ('workspace-a', 'test-author', 'other-plugin'),
            ]
        )
        plugin_db.add_all(
            BinaryStorage(
                workspace_uuid=workspace, unique_key=key, key=key, owner_type=owner_type, owner=owner, value=b'data'
            )
            for workspace, key, owner_type, owner in [
                ('workspace-a', 'target', 'plugin', 'test-author/test-plugin'),
                ('workspace-b', 'other-workspace', 'plugin', 'test-author/test-plugin'),
                ('workspace-a', 'other-owner', 'plugin', 'other-author/test-plugin'),
                ('workspace-a', 'other-type', 'skill', 'test-author/test-plugin'),
            ]
        )
        await plugin_db.flush()
        app = Mock()
        app.persistence_mgr.execute_async = plugin_db.execute
        handler = get_handler_module().RuntimeConnectionHandler(Mock(), AsyncMock(), app)
        binding = InstallationBinding(
            instance_uuid='instance-a',
            workspace_uuid='workspace-a',
            placement_generation=1,
            installation_uuid='00000000-0000-4000-8000-000000000001',
            runtime_revision=1,
            artifact_digest='a' * 64,
        )
        with handler.installation_scope(binding):
            await handler.cleanup_plugin_data('test-author', 'test-plugin')
        return plugin_db

    @pytest.mark.asyncio
    async def test_deletes_plugin_settings(self, cleanup):
        import sqlalchemy
        from langbot.pkg.entity.persistence.plugin import PluginSetting

        rows = (
            await cleanup.execute(
                sqlalchemy.select(PluginSetting.workspace_uuid, PluginSetting.plugin_author, PluginSetting.plugin_name)
            )
        ).all()
        assert set(rows) == {
            ('workspace-b', 'test-author', 'test-plugin'),
            ('workspace-a', 'other-author', 'test-plugin'),
            ('workspace-a', 'test-author', 'other-plugin'),
        }

    @pytest.mark.asyncio
    async def test_deletes_binary_storage(self, cleanup):
        """Test that binary storage is deleted."""
        import sqlalchemy
        from langbot.pkg.entity.persistence.bstorage import BinaryStorage

        keys = (await cleanup.execute(sqlalchemy.select(BinaryStorage.unique_key))).scalars().all()
        assert set(keys) == {'other-workspace', 'other-owner', 'other-type'}
