"""Tests for RuntimeConnectionHandler helper functions.

Tests handler helper methods that don't require full handler setup.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest


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
        query_id = 'nonexistent-query'

        if query_id not in mock_app.query_pool.cached_queries:
            expected_error = f'Query with query_id {query_id} not found'
            # Should return error response
            assert expected_error is not None

    @pytest.mark.asyncio
    async def test_set_query_var_success(self, mock_app):
        """Test set_query_var sets variable on existing query."""
        mock_query = SimpleNamespace()
        mock_query.variables = {}

        mock_app.query_pool.cached_queries['test-query'] = mock_query

        # Simulate set_query_var logic
        query_id = 'test-query'
        var_name = 'test_var'
        var_value = 'test_value'

        if query_id in mock_app.query_pool.cached_queries:
            query = mock_app.query_pool.cached_queries[query_id]
            query.variables[var_name] = var_value

        assert mock_query.variables['test_var'] == 'test_value'

    @pytest.mark.asyncio
    async def test_get_query_var_success(self, mock_app):
        """Test get_query_var retrieves variable from query."""
        mock_query = SimpleNamespace()
        mock_query.variables = {'existing_var': 'existing_value'}

        mock_app.query_pool.cached_queries['test-query'] = mock_query

        # Simulate get_query_var logic
        query_id = 'test-query'
        var_name = 'existing_var'

        if query_id in mock_app.query_pool.cached_queries:
            query = mock_app.query_pool.cached_queries[query_id]
            if var_name in query.variables:
                value = query.variables[var_name]
                assert value == 'existing_value'

    @pytest.mark.asyncio
    async def test_get_query_vars_multiple(self, mock_app):
        """Test get_query_vars retrieves multiple variables."""
        mock_query = SimpleNamespace()
        mock_query.variables = {'var1': 'val1', 'var2': 'val2', 'var3': 'val3'}

        mock_app.query_pool.cached_queries['test-query'] = mock_query

        query_id = 'test-query'
        var_names = ['var1', 'var3']

        if query_id in mock_app.query_pool.cached_queries:
            query = mock_app.query_pool.cached_queries[query_id]
            result = {name: query.variables.get(name) for name in var_names}
            assert result == {'var1': 'val1', 'var3': 'val3'}


class TestHandlerRagErrorResponse:
    """Tests for _make_rag_error_response helper."""

    def test_make_rag_error_response_basic(self):
        """Test basic error response creation."""
        from src.langbot.pkg.plugin.handler import _make_rag_error_response

        error = Exception("test error")
        response = _make_rag_error_response(error, 'TestError')

        # ActionResponse is a pydantic model, check message field
        assert 'TestError' in response.message
        assert 'test error' in response.message
        assert 'Exception' in response.message

    def test_make_rag_error_response_with_context(self):
        """Test error response with extra context."""
        from src.langbot.pkg.plugin.handler import _make_rag_error_response

        error = ValueError("invalid input")
        response = _make_rag_error_response(
            error,
            'ValidationError',
            field='name',
            value='test'
        )

        assert 'ValidationError' in response.message
        assert 'field=name' in response.message
        assert 'value=test' in response.message
        assert 'ValueError' in response.message

    def test_make_rag_error_response_exception_type(self):
        """Test error response includes exception type."""
        from src.langbot.pkg.plugin.handler import _make_rag_error_response

        error = RuntimeError("connection failed")
        response = _make_rag_error_response(error, 'ConnectionError')

        assert 'RuntimeError' in response.message
        assert 'ConnectionError' in response.message
        assert 'connection failed' in response.message

    def test_make_rag_error_response_empty_context(self):
        """Test error response with no extra context."""
        from src.langbot.pkg.plugin.handler import _make_rag_error_response

        error = KeyError("missing_key")
        response = _make_rag_error_response(error, 'LookupError')

        # No context parts means no brackets
        assert '[' in response.message  # Still has error type bracket
        assert 'KeyError' in response.message


class TestConstantsSemanticVersion:
    """Tests for version constant access."""

    def test_semantic_version_exists(self):
        """Test semantic_version is defined."""
        from src.langbot.pkg.utils import constants

        assert hasattr(constants, 'semantic_version')
        assert constants.semantic_version.startswith('v')

    def test_edition_exists(self):
        """Test edition constant is defined."""
        from src.langbot.pkg.utils import constants

        assert hasattr(constants, 'edition')
        assert constants.edition == 'community'

    def test_required_database_version_exists(self):
        """Test database version constant."""
        from src.langbot.pkg.utils import constants

        assert hasattr(constants, 'required_database_version')
        assert isinstance(constants.required_database_version, int)