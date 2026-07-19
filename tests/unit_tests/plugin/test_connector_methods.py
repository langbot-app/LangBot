"""Unit tests for plugin connector methods.

Tests cover:
- list_plugins() with filtering and sorting
- list_knowledge_engines() and list_parsers()
- RAG methods (ingest, retrieve, schema)
- Disabled plugin early returns
"""

from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock, Mock
from importlib import import_module

from tests.factories import text_query
from langbot_plugin.entities.io.context import InstallationBinding

from langbot.pkg.api.http.context import ExecutionContext


TEST_EXECUTION_CONTEXT = ExecutionContext(
    instance_uuid='instance-a',
    workspace_uuid='workspace-a',
    placement_generation=1,
)
TEST_INSTALLATION_BINDING = InstallationBinding(
    instance_uuid=TEST_EXECUTION_CONTEXT.instance_uuid,
    workspace_uuid=TEST_EXECUTION_CONTEXT.workspace_uuid,
    placement_generation=TEST_EXECUTION_CONTEXT.placement_generation,
    installation_uuid='00000000-0000-4000-8000-000000000001',
    runtime_revision=1,
    artifact_digest='a' * 64,
)


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
    mock_app.persistence_mgr.tenant_uow = None
    return mock_app


def create_mock_connector():
    """Create mock PluginRuntimeConnector instance for testing."""
    connector = get_connector_module()

    async def mock_disconnect_callback(conn):
        pass

    instance = connector.PluginRuntimeConnector(create_mock_app(), mock_disconnect_callback)
    instance._execution_context.set(TEST_EXECUTION_CONTEXT)
    instance._operation_bindings = AsyncMock(return_value=[TEST_INSTALLATION_BINDING])
    instance._target_binding = AsyncMock(return_value=TEST_INSTALLATION_BINDING)
    instance._load_workspace_settings = AsyncMock(return_value=[])
    instance.require_workspace_context = AsyncMock(side_effect=lambda context: context)
    return instance


def configure_handler(connector, runtime_handler):
    runtime_handler.installation_scope = Mock(side_effect=lambda _binding: nullcontext())
    connector.handler = runtime_handler
    return runtime_handler


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

        configure_handler(connector, AsyncMock())
        connector.handler.list_plugins = AsyncMock(
            return_value=[{'manifest': {'manifest': {'metadata': {'author': 'test', 'name': 'plugin'}}}}]
        )

        result = await connector.list_plugins()

        connector.handler.list_plugins.assert_called_once()
        assert result == [{'manifest': {'manifest': {'metadata': {'author': 'test', 'name': 'plugin'}}}}]
        connector._load_workspace_settings.assert_awaited_once_with(TEST_EXECUTION_CONTEXT)

    @pytest.mark.asyncio
    async def test_filters_by_component_kinds(self):
        """Test that plugins are filtered by component kinds."""
        get_connector_module()
        connector = create_mock_connector()

        configure_handler(connector, AsyncMock())
        connector.handler.list_plugins = AsyncMock(
            return_value=[
                {
                    'manifest': {'manifest': {'metadata': {'author': 'a', 'name': 'p1'}}},
                    'components': [{'manifest': {'manifest': {'kind': 'Command'}}}],
                    'debug': False,
                },
                {
                    'manifest': {'manifest': {'metadata': {'author': 'b', 'name': 'p2'}}},
                    'components': [{'manifest': {'manifest': {'kind': 'Tool'}}}],
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

        configure_handler(connector, AsyncMock())
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
        connector.ap.persistence_mgr.execute_async = AsyncMock(return_value=Mock(__iter__=lambda self: iter([])))

        result = await connector.list_plugins()

        # Debug plugin should be first
        assert result[0]['debug'] is True


class TestPluginDiagnostics:
    @pytest.mark.asyncio
    async def test_emit_event_preserves_response_sources(self):
        connector = create_mock_connector()
        query = text_query('hello')
        event = query.message_event
        object.__setattr__(event, 'query', query)
        connector_module = get_connector_module()
        original_from_event = connector_module.context.EventContext.from_event
        original_model_validate = connector_module.context.EventContext.model_validate
        response_sources = [
            {
                'kind': 'reply_message_chain',
                'plugin': {'author': 'tester', 'name': 'demo'},
            }
        ]

        async def emit_event_response(event_context, include_plugins=None):
            return {
                'event_context': event_context,
                'emitted_plugins': [],
                'response_sources': response_sources,
            }

        configure_handler(connector, AsyncMock())
        connector.handler.emit_event = AsyncMock(side_effect=emit_event_response)

        fake_event_ctx = Mock()
        event_dump = event.model_dump()
        event_dump['event_name'] = 'FriendMessage'
        fake_event_ctx.model_dump.return_value = {
            'query_id': query.query_id,
            'eid': 0,
            'event_name': 'FriendMessage',
            'event': event_dump,
            'is_prevent_default': False,
            'is_prevent_postorder': False,
        }
        connector_module.context.EventContext.from_event = Mock(return_value=fake_event_ctx)
        parsed_event_ctx = Mock()
        connector_module.context.EventContext.model_validate = Mock(return_value=parsed_event_ctx)
        try:
            event_ctx = await connector.emit_event(event)
        finally:
            connector_module.context.EventContext.from_event = original_from_event
            connector_module.context.EventContext.model_validate = original_model_validate

        assert event_ctx is parsed_event_ctx
        assert event_ctx._response_sources == response_sources

    @pytest.mark.asyncio
    async def test_emit_event_leaves_response_sources_absent_for_old_runtime(self):
        connector = create_mock_connector()
        query = text_query('hello')
        event = query.message_event
        object.__setattr__(event, 'query', query)
        connector_module = get_connector_module()
        original_from_event = connector_module.context.EventContext.from_event
        original_model_validate = connector_module.context.EventContext.model_validate

        async def emit_event_response(event_context, include_plugins=None):
            return {
                'event_context': event_context,
                'emitted_plugins': [
                    {'manifest': {'metadata': {'author': 'tester', 'name': 'demo'}}},
                ],
            }

        configure_handler(connector, AsyncMock())
        connector.handler.emit_event = AsyncMock(side_effect=emit_event_response)

        fake_event_ctx = Mock()
        event_dump = event.model_dump()
        event_dump['event_name'] = 'FriendMessage'
        fake_event_ctx.model_dump.return_value = {
            'query_id': query.query_id,
            'eid': 0,
            'event_name': 'FriendMessage',
            'event': event_dump,
            'is_prevent_default': False,
            'is_prevent_postorder': False,
        }
        connector_module.context.EventContext.from_event = Mock(return_value=fake_event_ctx)
        parsed_event_ctx = Mock()
        connector_module.context.EventContext.model_validate = Mock(return_value=parsed_event_ctx)
        try:
            event_ctx = await connector.emit_event(event)
        finally:
            connector_module.context.EventContext.from_event = original_from_event
            connector_module.context.EventContext.model_validate = original_model_validate

        assert event_ctx._response_sources == []
        assert event_ctx._emitted_plugins == [
            {'manifest': {'metadata': {'author': 'tester', 'name': 'demo'}}},
        ]

    @pytest.mark.asyncio
    async def test_notify_plugin_diagnostic_skips_when_disabled(self):
        connector_module = get_connector_module()

        async def mock_disconnect(conn):
            pass

        mock_app = create_mock_app()
        mock_app.instance_config.data = {'plugin': {'enable': False}}
        connector = connector_module.PluginRuntimeConnector(mock_app, mock_disconnect)
        configure_handler(connector, AsyncMock())

        await connector.notify_plugin_diagnostic({'code': 'response_delivery_failed'})

        connector.handler.notify_plugin_diagnostic.assert_not_called()

    @pytest.mark.asyncio
    async def test_notify_plugin_diagnostic_is_best_effort(self):
        connector = create_mock_connector()
        configure_handler(connector, AsyncMock())
        connector.handler.notify_plugin_diagnostic = AsyncMock(side_effect=RuntimeError('action not found'))

        await connector.notify_plugin_diagnostic({'code': 'response_delivery_failed'})

        connector.handler.notify_plugin_diagnostic.assert_awaited_once()
        connector.ap.logger.debug.assert_called_once()


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

        configure_handler(connector, AsyncMock())
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

        configure_handler(connector, AsyncMock())
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

        configure_handler(connector, AsyncMock())
        connector.handler.parse_document = AsyncMock(return_value={'content': 'parsed'})

        result = await connector.call_parser(
            'author/parser',
            {'mime_type': 'text/plain', 'filename': 'test.txt'},
            b'file content',
        )

        connector.handler.parse_document.assert_called_once_with(
            'author',
            'parser',
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

        configure_handler(connector, AsyncMock())
        connector.handler.rag_ingest_document = AsyncMock(return_value={'status': 'success'})

        result = await connector.call_rag_ingest('author/engine', {'file': 'test.pdf'})

        connector.handler.rag_ingest_document.assert_called_once_with('author', 'engine', {'file': 'test.pdf'})
        assert result['status'] == 'success'

    @pytest.mark.asyncio
    async def test_call_rag_retrieve(self):
        """Test call_rag_retrieve calls handler."""
        get_connector_module()
        connector = create_mock_connector()

        configure_handler(connector, AsyncMock())
        connector.handler.retrieve_knowledge = AsyncMock(
            return_value={
                'results': [
                    {'id': 'doc1', 'content': [{'type': 'text', 'text': 'test'}], 'metadata': {}, 'distance': 0.1}
                ]
            }
        )

        result = await connector.call_rag_retrieve('author/engine', {'query': 'test'})

        connector.handler.retrieve_knowledge.assert_called_once_with('author', 'engine', '', {'query': 'test'})
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

        configure_handler(connector, AsyncMock())
        connector.handler.get_rag_creation_schema = AsyncMock(return_value={'properties': {'name': {'type': 'string'}}})

        result = await connector.get_rag_creation_schema('author/engine')

        connector.handler.get_rag_creation_schema.assert_called_once_with('author', 'engine')
        assert result == {'properties': {'name': {'type': 'string'}}}

    @pytest.mark.asyncio
    async def test_get_rag_retrieval_schema(self):
        """Test get_rag_retrieval_schema calls handler."""
        get_connector_module()
        connector = create_mock_connector()

        configure_handler(connector, AsyncMock())
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

        configure_handler(connector, AsyncMock())
        connector.handler.rag_on_kb_create = AsyncMock(return_value={'status': 'ok'})

        await connector.rag_on_kb_create('author/engine', 'kb-uuid', {'model': 'test'})

        connector.handler.rag_on_kb_create.assert_called_once_with('author', 'engine', 'kb-uuid', {'model': 'test'})

    @pytest.mark.asyncio
    async def test_rag_on_kb_delete(self):
        """Test rag_on_kb_delete calls handler."""
        get_connector_module()
        connector = create_mock_connector()

        configure_handler(connector, AsyncMock())
        connector.handler.rag_on_kb_delete = AsyncMock(return_value={'status': 'ok'})

        await connector.rag_on_kb_delete('author/engine', 'kb-uuid')

        connector.handler.rag_on_kb_delete.assert_called_once_with('author', 'engine', 'kb-uuid')

    @pytest.mark.asyncio
    async def test_call_rag_delete_document(self):
        """Test call_rag_delete_document calls handler."""
        get_connector_module()
        connector = create_mock_connector()

        configure_handler(connector, AsyncMock())
        connector.handler.rag_delete_document = AsyncMock(return_value=True)

        result = await connector.call_rag_delete_document('author/engine', 'doc-uuid', 'kb-uuid')

        connector.handler.rag_delete_document.assert_called_once_with('author', 'engine', 'doc-uuid', 'kb-uuid')
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

        configure_handler(connector, AsyncMock())
        connector.handler.get_plugin_info = AsyncMock(return_value={'manifest': {'metadata': {'name': 'plugin'}}})

        result = await connector.get_plugin_info('author', 'plugin')

        connector.handler.get_plugin_info.assert_called_once_with('author', 'plugin')
        assert result == {'manifest': {'metadata': {'name': 'plugin'}}}


class TestSetPluginConfig:
    """Tests for set_plugin_config method."""

    @pytest.mark.asyncio
    async def test_updates_revision_then_applies_desired_state(self):
        """Config changes are fenced by a new runtime revision."""
        get_connector_module()
        connector = create_mock_connector()

        configure_handler(connector, AsyncMock())
        connector.handler.register_installation_binding = Mock()
        connector.handler.apply_plugin_installation = AsyncMock(return_value={'state': 'running'})
        setting = SimpleNamespace(
            installation_uuid=TEST_INSTALLATION_BINDING.installation_uuid,
            runtime_revision=1,
            artifact_digest=TEST_INSTALLATION_BINDING.artifact_digest,
            enabled=True,
            install_info={'_artifact_storage': 'tenant_binary_storage_v1'},
        )
        connector._setting_for_plugin = AsyncMock(return_value=(TEST_EXECUTION_CONTEXT, setting))
        connector.ap.persistence_mgr.execute_async = AsyncMock(return_value=SimpleNamespace(rowcount=1))

        await connector.set_plugin_config('author', 'plugin', {'setting': 'value'})

        applied_binding = connector.handler.apply_plugin_installation.await_args.args[0]
        assert applied_binding.runtime_revision == 2
        assert applied_binding.installation_uuid == TEST_INSTALLATION_BINDING.installation_uuid
        connector.handler.register_installation_binding.assert_called_once_with(
            applied_binding,
            plugin_author='author',
            plugin_name='plugin',
        )
        connector.handler.apply_plugin_installation.assert_awaited_once_with(
            applied_binding,
            artifact_package=None,
            enabled=True,
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

        configure_handler(connector, AsyncMock())
        connector.handler.ping = AsyncMock(return_value={'status': 'ok'})

        await connector.ping_plugin_runtime()

        connector.handler.ping.assert_called_once()
