"""Unit tests for plugin connector methods.

Tests cover:
- list_plugins() with filtering and sorting
- list_knowledge_engines() and list_parsers()
- RAG methods (ingest, retrieve, schema)
- Disabled plugin early returns
"""
from __future__ import annotations

import pytest
from unittest.mock import Mock, AsyncMock
from importlib import import_module


def get_connector_module():
    """Lazy import to avoid circular import issues."""
    return import_module('langbot.pkg.plugin.connector')


def create_mock_app():
    """Create mock Application for testing."""
    mock_app = Mock()
    mock_app.logger = Mock()
    mock_app.instance_config = Mock()
    mock_app.instance_config.data = {'plugin': {'enable': True}}
    mock_app.persistence_mgr = AsyncMock()
    mock_app.persistence_mgr.execute_async = AsyncMock()
    return mock_app


def create_mock_connector():
    """Create mock PluginRuntimeConnector instance for testing."""
    connector = get_connector_module()

    async def mock_disconnect_callback(conn):
        pass

    return connector.PluginRuntimeConnector(create_mock_app(), mock_disconnect_callback)


class TestListPlugins:
    """Tests for list_plugins method."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_plugin_disabled(self):
        """Test returns empty list when plugin system disabled."""
        connector_module = get_connector_module()

        async def mock_disconnect(conn):
            pass

        mock_app = create_mock_app()
        mock_app.instance_config.data = {'plugin': {'enable': False}}

        connector = connector_module.PluginRuntimeConnector(mock_app, mock_disconnect)

        result = await connector.list_plugins()

        assert result == []

    @pytest.mark.asyncio
    async def test_calls_handler_list_plugins(self):
        """Test that handler.list_plugins is called."""
        get_connector_module()
        connector = create_mock_connector()

        connector.handler = AsyncMock()
        connector.handler.list_plugins = AsyncMock(
            return_value=[{'manifest': {'manifest': {'metadata': {'author': 'test', 'name': 'plugin'}}}}]
        )

        result = await connector.list_plugins()

        connector.handler.list_plugins.assert_called_once()
        assert result == [{'manifest': {'manifest': {'metadata': {'author': 'test', 'name': 'plugin'}}}}]

    @pytest.mark.asyncio
    async def test_filters_by_component_kinds(self):
        """Test that plugins are filtered by component kinds."""
        get_connector_module()
        connector = create_mock_connector()

        connector.handler = AsyncMock()
        connector.handler.list_plugins = AsyncMock(
            return_value=[
                {
                    'manifest': {'manifest': {'metadata': {'author': 'a', 'name': 'p1'}}},
                    'components': [
                        {'manifest': {'manifest': {'kind': 'Command'}}}
                    ],
                    'debug': False,
                },
                {
                    'manifest': {'manifest': {'metadata': {'author': 'b', 'name': 'p2'}}},
                    'components': [
                        {'manifest': {'manifest': {'kind': 'Tool'}}}
                    ],
                    'debug': False,
                },
            ]
        )

        result = await connector.list_plugins(component_kinds=['Command'])

        assert len(result) == 1
        assert result[0]['manifest']['manifest']['metadata']['name'] == 'p1'

    @pytest.mark.asyncio
    async def test_sorts_debug_plugins_first(self):
        """Test that debug plugins are sorted first."""
        get_connector_module()
        connector = create_mock_connector()

        connector.handler = AsyncMock()
        connector.handler.list_plugins = AsyncMock(
            return_value=[
                {
                    'manifest': {'manifest': {'metadata': {'author': 'a', 'name': 'normal'}}},
                    'components': [],
                    'debug': False,
                },
                {
                    'manifest': {'manifest': {'metadata': {'author': 'b', 'name': 'debug'}}},
                    'components': [],
                    'debug': True,
                },
            ]
        )
        connector.ap.persistence_mgr.execute_async = AsyncMock(
            return_value=Mock(__iter__=lambda self: iter([]))
        )

        result = await connector.list_plugins()

        # Debug plugin should be first
        assert result[0]['debug'] is True


class TestListKnowledgeEngines:
    """Tests for list_knowledge_engines method."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_plugin_disabled(self):
        """Test returns empty list when plugin system disabled."""
        connector_module = get_connector_module()

        async def mock_disconnect(conn):
            pass

        mock_app = create_mock_app()
        mock_app.instance_config.data = {'plugin': {'enable': False}}

        connector = connector_module.PluginRuntimeConnector(mock_app, mock_disconnect)

        result = await connector.list_knowledge_engines()

        assert result == []

    @pytest.mark.asyncio
    async def test_calls_handler_list_knowledge_engines(self):
        """Test that handler method is called."""
        get_connector_module()
        connector = create_mock_connector()

        connector.handler = AsyncMock()
        connector.handler.list_knowledge_engines = AsyncMock(
            return_value=[{'plugin_id': 'author/engine', 'name': 'Engine'}]
        )

        result = await connector.list_knowledge_engines()

        connector.handler.list_knowledge_engines.assert_called_once()
        assert result == [{'plugin_id': 'author/engine', 'name': 'Engine'}]


class TestListParsers:
    """Tests for list_parsers method."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_plugin_disabled(self):
        """Test returns empty list when plugin system disabled."""
        connector_module = get_connector_module()

        async def mock_disconnect(conn):
            pass

        mock_app = create_mock_app()
        mock_app.instance_config.data = {'plugin': {'enable': False}}

        connector = connector_module.PluginRuntimeConnector(mock_app, mock_disconnect)

        result = await connector.list_parsers()

        assert result == []

    @pytest.mark.asyncio
    async def test_calls_handler_list_parsers(self):
        """Test that handler method is called."""
        get_connector_module()
        connector = create_mock_connector()

        connector.handler = AsyncMock()
        connector.handler.list_parsers = AsyncMock(
            return_value=[{'plugin_id': 'author/parser', 'supported_mime_types': ['text/plain']}]
        )

        result = await connector.list_parsers()

        connector.handler.list_parsers.assert_called_once()
        assert result == [{'plugin_id': 'author/parser', 'supported_mime_types': ['text/plain']}]


class TestCallParser:
    """Tests for call_parser method."""

    @pytest.mark.asyncio
    async def test_calls_handler_parse_document(self):
        """Test that handler.parse_document is called with correct args."""
        get_connector_module()
        connector = create_mock_connector()

        connector.handler = AsyncMock()
        connector.handler.parse_document = AsyncMock(return_value={'content': 'parsed'})

        result = await connector.call_parser(
            'author/parser',
            {'mime_type': 'text/plain', 'filename': 'test.txt'},
            b'file content',
        )

        connector.handler.parse_document.assert_called_once_with(
            'author', 'parser',
            {'mime_type': 'text/plain', 'filename': 'test.txt'},
            b'file content',
        )
        assert result['content'] == 'parsed'


class TestRAGMethods:
    """Tests for RAG-related methods."""

    @pytest.mark.asyncio
    async def test_call_rag_ingest(self):
        """Test call_rag_ingest calls handler with parsed plugin ID."""
        get_connector_module()
        connector = create_mock_connector()

        connector.handler = AsyncMock()
        connector.handler.rag_ingest_document = AsyncMock(return_value={'status': 'success'})

        result = await connector.call_rag_ingest('author/engine', {'file': 'test.pdf'})

        connector.handler.rag_ingest_document.assert_called_once_with(
            'author', 'engine', {'file': 'test.pdf'}
        )
        assert result['status'] == 'success'

    @pytest.mark.asyncio
    async def test_call_rag_retrieve(self):
        """Test call_rag_retrieve calls handler."""
        get_connector_module()
        connector = create_mock_connector()

        connector.handler = AsyncMock()
        connector.handler.retrieve_knowledge = AsyncMock(
            return_value={'results': [{'id': 'doc1', 'content': [{'type': 'text', 'text': 'test'}], 'metadata': {}, 'distance': 0.1}]}
        )

        result = await connector.call_rag_retrieve('author/engine', {'query': 'test'})

        connector.handler.retrieve_knowledge.assert_called_once_with(
            'author', 'engine', '', {'query': 'test'}
        )
        assert result == {
            'results': [
                {
                    'id': 'doc1',
                    'content': [{'type': 'text', 'text': 'test'}],
                    'metadata': {},
                    'distance': 0.1,
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_get_rag_creation_schema(self):
        """Test get_rag_creation_schema calls handler."""
        get_connector_module()
        connector = create_mock_connector()

        connector.handler = AsyncMock()
        connector.handler.get_rag_creation_schema = AsyncMock(
            return_value={'properties': {'name': {'type': 'string'}}}
        )

        result = await connector.get_rag_creation_schema('author/engine')

        connector.handler.get_rag_creation_schema.assert_called_once_with('author', 'engine')
        assert result == {'properties': {'name': {'type': 'string'}}}

    @pytest.mark.asyncio
    async def test_get_rag_retrieval_schema(self):
        """Test get_rag_retrieval_schema calls handler."""
        get_connector_module()
        connector = create_mock_connector()

        connector.handler = AsyncMock()
        connector.handler.get_rag_retrieval_schema = AsyncMock(
            return_value={'properties': {'top_k': {'type': 'integer'}}}
        )

        result = await connector.get_rag_retrieval_schema('author/engine')

        connector.handler.get_rag_retrieval_schema.assert_called_once_with('author', 'engine')
        assert result == {'properties': {'top_k': {'type': 'integer'}}}

    @pytest.mark.asyncio
    async def test_rag_on_kb_create(self):
        """Test rag_on_kb_create calls handler."""
        get_connector_module()
        connector = create_mock_connector()

        connector.handler = AsyncMock()
        connector.handler.rag_on_kb_create = AsyncMock(return_value={'status': 'ok'})

        await connector.rag_on_kb_create('author/engine', 'kb-uuid', {'model': 'test'})

        connector.handler.rag_on_kb_create.assert_called_once_with(
            'author', 'engine', 'kb-uuid', {'model': 'test'}
        )

    @pytest.mark.asyncio
    async def test_rag_on_kb_delete(self):
        """Test rag_on_kb_delete calls handler."""
        get_connector_module()
        connector = create_mock_connector()

        connector.handler = AsyncMock()
        connector.handler.rag_on_kb_delete = AsyncMock(return_value={'status': 'ok'})

        await connector.rag_on_kb_delete('author/engine', 'kb-uuid')

        connector.handler.rag_on_kb_delete.assert_called_once_with('author', 'engine', 'kb-uuid')

    @pytest.mark.asyncio
    async def test_call_rag_delete_document(self):
        """Test call_rag_delete_document calls handler."""
        get_connector_module()
        connector = create_mock_connector()

        connector.handler = AsyncMock()
        connector.handler.rag_delete_document = AsyncMock(return_value=True)

        result = await connector.call_rag_delete_document('author/engine', 'doc-uuid', 'kb-uuid')

        connector.handler.rag_delete_document.assert_called_once_with(
            'author', 'engine', 'doc-uuid', 'kb-uuid'
        )
        assert result is True


class TestRetrieveKnowledge:
    """Tests for retrieve_knowledge method."""

    @pytest.mark.asyncio
    async def test_returns_empty_results_when_plugin_disabled(self):
        """Test returns empty when plugin disabled."""
        connector_module = get_connector_module()

        async def mock_disconnect(conn):
            pass

        mock_app = create_mock_app()
        mock_app.instance_config.data = {'plugin': {'enable': False}}

        connector = connector_module.PluginRuntimeConnector(mock_app, mock_disconnect)

        result = await connector.retrieve_knowledge('author', 'engine', 'retriever', {})

        assert result == {'results': []}


class TestDisabledPluginEarlyReturns:
    """Tests for early returns when plugin system is disabled."""

    @pytest.mark.asyncio
    async def test_list_tools_returns_empty(self):
        """Test list_tools returns empty when disabled."""
        connector_module = get_connector_module()

        async def mock_disconnect(conn):
            pass

        mock_app = create_mock_app()
        mock_app.instance_config.data = {'plugin': {'enable': False}}

        connector = connector_module.PluginRuntimeConnector(mock_app, mock_disconnect)

        result = await connector.list_tools()

        assert result == []

    @pytest.mark.asyncio
    async def test_list_commands_returns_empty(self):
        """Test list_commands returns empty when disabled."""
        connector_module = get_connector_module()

        async def mock_disconnect(conn):
            pass

        mock_app = create_mock_app()
        mock_app.instance_config.data = {'plugin': {'enable': False}}

        connector = connector_module.PluginRuntimeConnector(mock_app, mock_disconnect)

        result = await connector.list_commands()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_debug_info_returns_empty(self):
        """Test get_debug_info returns empty dict when disabled."""
        connector_module = get_connector_module()

        async def mock_disconnect(conn):
            pass

        mock_app = create_mock_app()
        mock_app.instance_config.data = {'plugin': {'enable': False}}

        connector = connector_module.PluginRuntimeConnector(mock_app, mock_disconnect)

        result = await connector.get_debug_info()

        assert result == {}


class TestGetPluginInfo:
    """Tests for get_plugin_info method."""

    @pytest.mark.asyncio
    async def test_calls_handler_get_plugin_info(self):
        """Test that handler.get_plugin_info is called."""
        get_connector_module()
        connector = create_mock_connector()

        connector.handler = AsyncMock()
        connector.handler.get_plugin_info = AsyncMock(
            return_value={'manifest': {'metadata': {'name': 'plugin'}}}
        )

        result = await connector.get_plugin_info('author', 'plugin')

        connector.handler.get_plugin_info.assert_called_once_with('author', 'plugin')
        assert result == {'manifest': {'metadata': {'name': 'plugin'}}}


class TestSetPluginConfig:
    """Tests for set_plugin_config method."""

    @pytest.mark.asyncio
    async def test_calls_handler_set_plugin_config(self):
        """Test that handler.set_plugin_config is called."""
        get_connector_module()
        connector = create_mock_connector()

        connector.handler = AsyncMock()
        connector.handler.set_plugin_config = AsyncMock(return_value={'status': 'ok'})

        await connector.set_plugin_config('author', 'plugin', {'setting': 'value'})

        connector.handler.set_plugin_config.assert_called_once_with(
            'author', 'plugin', {'setting': 'value'}
        )


class TestPingPluginRuntime:
    """Tests for ping_plugin_runtime method."""

    @pytest.mark.asyncio
    async def test_raises_when_handler_not_set(self):
        """Test that exception is raised when handler not initialized."""
        get_connector_module()
        connector = create_mock_connector()

        # handler is not set
        with pytest.raises(Exception, match='Plugin runtime is not connected') as exc_info:
            await connector.ping_plugin_runtime()

        assert 'not connected' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_calls_handler_ping(self):
        """Test that handler.ping is called."""
        get_connector_module()
        connector = create_mock_connector()

        connector.handler = AsyncMock()
        connector.handler.ping = AsyncMock(return_value={'status': 'ok'})

        await connector.ping_plugin_runtime()

        connector.handler.ping.assert_called_once()
