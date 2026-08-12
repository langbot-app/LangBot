"""Tests for RuntimeConnectionHandler helper functions.

Tests handler helper methods that don't require full handler setup.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock
import pytest

from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction
from langbot_plugin.entities.io.context import ActionContext, InstallationBinding


def make_handler(app):
    """Create a RuntimeConnectionHandler with mocked external connection."""
    from langbot.pkg.plugin.handler import RuntimeConnectionHandler

    workspace_context = ActionContext(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=1,
    )
    app.workspace_service = SimpleNamespace(
        get_execution_binding=AsyncMock(
            return_value=SimpleNamespace(
                instance_uuid=workspace_context.instance_uuid,
                workspace_uuid=workspace_context.workspace_uuid,
                placement_generation=workspace_context.placement_generation,
            )
        )
    )
    runtime_handler = RuntimeConnectionHandler(
        Mock(),
        AsyncMock(return_value=True),
        app,
    )
    installation_binding = InstallationBinding(
        **workspace_context.model_dump(exclude_none=True),
        installation_uuid='00000000-0000-4000-8000-000000000001',
        runtime_revision=1,
        artifact_digest='a' * 64,
    )
    runtime_handler.register_installation_binding(
        installation_binding,
        plugin_author='test-author',
        plugin_name='test-plugin',
    )
    runtime_handler._current_action_context.set(installation_binding)
    query_pool = getattr(app, 'query_pool', None)
    if query_pool is not None and hasattr(query_pool, 'cached_queries'):

        def scoped_query(query):
            if query is not None:
                query.instance_uuid = workspace_context.instance_uuid
                query.workspace_uuid = workspace_context.workspace_uuid
                query.placement_generation = workspace_context.placement_generation
            return query

        query_pool.get_query = AsyncMock(
            side_effect=lambda workspace_uuid, query_uuid: scoped_query(query_pool.cached_queries.get(query_uuid))
        )
        query_pool.get_query_by_legacy_id = AsyncMock(
            side_effect=lambda workspace_uuid, query_id: scoped_query(query_pool.cached_queries.get(query_id))
        )
    return runtime_handler


class TestHandlerQueryVariables:
    """Tests for handler query variable logic."""

    @pytest.fixture
    def mock_app(self):
        """Create mock app with query pool."""
        app = SimpleNamespace()

        app.query_pool = SimpleNamespace()
        app.query_pool.cached_queries = {}

        app.logger = SimpleNamespace()
        app.logger.debug = MagicMock()

        return app

    @pytest.mark.asyncio
    async def test_set_query_var_query_not_found(self, mock_app):
        """Test set_query_var returns error when query not found."""
        runtime_handler = make_handler(mock_app)

        response = await runtime_handler.actions[PluginToRuntimeAction.SET_QUERY_VAR.value](
            {
                'query_id': 'nonexistent-query',
                'key': 'test_var',
                'value': 'test_value',
            }
        )

        assert response.code != 0
        assert 'nonexistent-query' in response.message

    @pytest.mark.asyncio
    async def test_set_query_var_success(self, mock_app):
        """Test set_query_var sets variable on existing query."""
        runtime_handler = make_handler(mock_app)
        mock_query = SimpleNamespace()
        mock_query.variables = {}

        mock_app.query_pool.cached_queries['test-query'] = mock_query

        response = await runtime_handler.actions[PluginToRuntimeAction.SET_QUERY_VAR.value](
            {
                'query_id': 'test-query',
                'key': 'test_var',
                'value': 'test_value',
            }
        )

        assert response.code == 0
        assert mock_query.variables['test_var'] == 'test_value'

    @pytest.mark.asyncio
    async def test_get_query_var_success(self, mock_app):
        """Test get_query_var retrieves variable from query."""
        runtime_handler = make_handler(mock_app)
        mock_query = SimpleNamespace()
        mock_query.variables = {'existing_var': 'existing_value'}

        mock_app.query_pool.cached_queries['test-query'] = mock_query

        response = await runtime_handler.actions[PluginToRuntimeAction.GET_QUERY_VAR.value](
            {
                'query_id': 'test-query',
                'key': 'existing_var',
            }
        )

        assert response.code == 0
        assert response.data == {'value': 'existing_value'}

    @pytest.mark.asyncio
    async def test_get_query_vars_multiple(self, mock_app):
        """Test get_query_vars returns the query's variable mapping."""
        runtime_handler = make_handler(mock_app)
        mock_query = SimpleNamespace()
        mock_query.variables = {'var1': 'val1', 'var2': 'val2', 'var3': 'val3'}

        mock_app.query_pool.cached_queries['test-query'] = mock_query

        response = await runtime_handler.actions[PluginToRuntimeAction.GET_QUERY_VARS.value](
            {
                'query_id': 'test-query',
            }
        )

        assert response.code == 0
        assert response.data == {'vars': mock_query.variables}


class TestHandlerRagErrorResponse:
    """Tests for _make_rag_error_response helper."""

    def test_make_rag_error_response_basic(self):
        """Test basic error response creation."""
        from langbot.pkg.plugin.handler import _make_rag_error_response

        error = Exception('test error')
        response = _make_rag_error_response(error, 'TestError')

        # ActionResponse is a pydantic model, check message field
        assert 'TestError' in response.message
        assert 'test error' in response.message
        assert 'Exception' in response.message

    def test_make_rag_error_response_with_context(self):
        """Test error response with extra context."""
        from langbot.pkg.plugin.handler import _make_rag_error_response

        error = ValueError('invalid input')
        response = _make_rag_error_response(error, 'ValidationError', field='name', value='test')

        assert 'ValidationError' in response.message
        assert 'field=name' in response.message
        assert 'value=test' in response.message
        assert 'ValueError' in response.message

    def test_make_rag_error_response_exception_type(self):
        """Test error response includes exception type."""
        from langbot.pkg.plugin.handler import _make_rag_error_response

        error = RuntimeError('connection failed')
        response = _make_rag_error_response(error, 'ConnectionError')

        assert 'RuntimeError' in response.message
        assert 'ConnectionError' in response.message
        assert 'connection failed' in response.message

    def test_make_rag_error_response_empty_context(self):
        """Test error response with no extra context."""
        from langbot.pkg.plugin.handler import _make_rag_error_response

        error = KeyError('missing_key')
        response = _make_rag_error_response(error, 'LookupError')

        # No context parts means no brackets
        assert '[' in response.message  # Still has error type bracket
        assert 'KeyError' in response.message


class TestHandlerPluginDiagnostic:
    @pytest.mark.asyncio
    async def test_notify_plugin_diagnostic_falls_back_to_raw_protocol_action(self):
        """Diagnostic forwarding works before the SDK enum exists."""
        app = SimpleNamespace()
        app.logger = SimpleNamespace(debug=MagicMock())
        runtime_handler = make_handler(app)
        runtime_handler.call_action = AsyncMock(return_value={})

        payload = {'code': 'response_delivery_failed'}
        await runtime_handler.notify_plugin_diagnostic(payload)

        action = runtime_handler.call_action.await_args.args[0]
        assert action.value == 'plugin_diagnostic'
        assert runtime_handler.call_action.await_args.args[1] is payload
        assert runtime_handler.call_action.await_args.kwargs['timeout'] == 5

    def test_langbot_to_runtime_action_uses_enum_when_available(self):
        """The compatibility helper should prefer SDK enums once available."""
        from langbot.pkg.plugin import handler as plugin_handler

        sentinel = object()
        original = plugin_handler.LangBotToRuntimeAction
        plugin_handler.LangBotToRuntimeAction = SimpleNamespace(PLUGIN_DIAGNOSTIC=sentinel)
        try:
            assert plugin_handler._langbot_to_runtime_action('PLUGIN_DIAGNOSTIC', 'plugin_diagnostic') is sentinel
        finally:
            plugin_handler.LangBotToRuntimeAction = original


class TestConstantsSemanticVersion:
    """Tests for version constant access."""

    def test_semantic_version_exists(self):
        """Test semantic_version is defined."""
        from langbot.pkg.utils import constants

        assert hasattr(constants, 'semantic_version')
        assert constants.semantic_version.startswith('v')

    def test_edition_exists(self):
        """Test edition constant is defined."""
        from langbot.pkg.utils import constants

        assert hasattr(constants, 'edition')
        assert constants.edition == 'community'

    def test_required_database_version_exists(self):
        """Test database version constant."""
        from langbot.pkg.utils import constants

        assert hasattr(constants, 'required_database_version')
        assert isinstance(constants.required_database_version, int)
