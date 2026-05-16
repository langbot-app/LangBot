"""Unit tests for persistence manager methods.

Tests cover:
- execute_async() with mock database
- get_db_engine() with mock database manager
"""
from __future__ import annotations

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from importlib import import_module
import sqlalchemy


def get_persistence_module():
    """Lazy import to avoid circular import issues."""
    return import_module('langbot.pkg.persistence.mgr')


class TestExecuteAsync:
    """Tests for execute_async method."""

    @pytest.mark.asyncio
    async def test_execute_async_calls_engine_execute(self):
        """Test that execute_async calls engine execute."""
        persistence = get_persistence_module()

        mock_app = Mock()
        mock_app.persistence_mgr = None

        mgr = persistence.PersistenceManager(mock_app)

        # Mock database manager with async engine
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=Mock())
        mock_conn.commit = AsyncMock()

        # Setup the async context manager
        async_cm = AsyncMock()
        async_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        async_cm.__aexit__ = AsyncMock(return_value=None)
        mock_engine.connect = Mock(return_value=async_cm)

        mock_db = Mock()
        mock_db.get_engine = Mock(return_value=mock_engine)
        mgr.db = mock_db

        # Execute a simple select
        await mgr.execute_async(sqlalchemy.select(1))

        mock_conn.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_async_returns_result(self):
        """Test that execute_async returns the result from execute.

        NOTE: This test verifies the return value chain - that the result
        from conn.execute() is properly returned by execute_async().
        The mock verifies the value propagation, not the SQL execution.
        For real SQL execution tests, see integration tests.
        """
        persistence = get_persistence_module()

        mock_app = Mock()
        mgr = persistence.PersistenceManager(mock_app)

        # Create a mock result with actual attributes to simulate real result
        mock_result = Mock(name='query_result')
        mock_result.scalar = Mock(return_value=1)  # Simulate scalar() method
        mock_result.scalars = Mock()  # Simulate scalars() method

        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_conn.commit = AsyncMock()

        async_cm = AsyncMock()
        async_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        async_cm.__aexit__ = AsyncMock(return_value=None)
        mock_engine.connect = Mock(return_value=async_cm)

        mock_db = Mock()
        mock_db.get_engine = Mock(return_value=mock_engine)
        mgr.db = mock_db

        result = await mgr.execute_async(sqlalchemy.text("SELECT 1"))

        # Verify result is the same object returned by execute
        assert result is mock_result
        # Verify result has expected methods (simulating real Result object)
        assert hasattr(result, 'scalar')
        assert result.scalar() == 1


class TestGetDbEngine:
    """Tests for get_db_engine method."""

    def test_get_db_engine_returns_engine_from_db_manager(self):
        """Test that get_db_engine returns engine from db manager."""
        persistence = get_persistence_module()

        mock_app = Mock()
        mgr = persistence.PersistenceManager(mock_app)

        mock_engine = Mock(name='engine')
        mock_db = Mock()
        mock_db.get_engine = Mock(return_value=mock_engine)
        mgr.db = mock_db

        engine = mgr.get_db_engine()

        assert engine == mock_engine
        mock_db.get_engine.assert_called_once()

    def test_get_db_engine_without_db_set_raises(self):
        """Test that get_db_engine raises when db is not set."""
        persistence = get_persistence_module()

        mock_app = Mock()
        mgr = persistence.PersistenceManager(mock_app)

        # db is not initialized
        mgr.db = None

        with pytest.raises(AttributeError):
            mgr.get_db_engine()


class TestSerializeModelEdgeCases:
    """Tests for serialize_model edge cases."""

    def test_serialize_model_with_all_columns_masked(self):
        """Test serialize_model when all columns are masked."""
        persistence = get_persistence_module()

        from sqlalchemy import Column, Integer, String
        from sqlalchemy.orm import declarative_base

        Base = declarative_base()

        class SimpleModel(Base):
            __tablename__ = 'simple'
            id = Column(Integer, primary_key=True)
            name = Column(String(50))

        mock_app = Mock()
        mgr = persistence.PersistenceManager(mock_app)

        instance = SimpleModel(id=1, name='test')
        result = mgr.serialize_model(SimpleModel, instance, masked_columns=['id', 'name'])

        # Result should be empty dict when all columns masked
        assert result == {}