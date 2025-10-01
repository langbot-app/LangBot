"""
Simple standalone tests to verify test infrastructure
These tests don't import the actual pipeline code to avoid circular import issues
"""

import pytest
from unittest.mock import Mock, AsyncMock


def test_pytest_works():
    """Verify pytest is working"""
    assert True


@pytest.mark.asyncio
async def test_async_works():
    """Verify async tests work"""
    mock = AsyncMock(return_value=42)
    result = await mock()
    assert result == 42


def test_mocks_work():
    """Verify mocking works"""
    mock = Mock()
    mock.return_value = 'test'
    assert mock() == 'test'


def test_fixtures_work(mock_app):
    """Verify fixtures are loaded"""
    assert mock_app is not None
    assert mock_app.logger is not None
    assert mock_app.sess_mgr is not None


def test_sample_query(sample_query):
    """Verify sample query fixture works"""
    assert sample_query.query_id == 'test-query-id'
    assert sample_query.launcher_id == 12345
