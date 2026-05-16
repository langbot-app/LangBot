"""Unit tests for persistence serialize_model function.

Tests cover:
- serialize_model() with various column types
- datetime conversion to isoformat
- masked_columns exclusion
"""
from __future__ import annotations

import datetime
from unittest.mock import Mock

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base
from importlib import import_module


def get_persistence_module():
    """Lazy import to avoid circular import issues."""
    return import_module('langbot.pkg.persistence.mgr')


# Create a simple test model
Base = declarative_base()


class TestModel(Base):
    __tablename__ = 'test_model'
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    created_at = Column(DateTime)
    updated_at = Column(DateTime, nullable=True)


class TestSerializeModel:
    """Tests for serialize_model method."""

    def test_serialize_string_and_int_columns(self):
        """Test that string and int columns are serialized directly."""
        persistence = get_persistence_module()

        # Create a mock persistence manager
        mock_app = Mock()
        mock_app.persistence_mgr = None
        mgr = persistence.PersistenceManager(mock_app)

        # Create test model instance
        instance = TestModel(id=1, name='test_name', created_at=datetime.datetime(2024, 1, 15, 10, 30, 0))

        result = mgr.serialize_model(TestModel, instance)

        assert result['id'] == 1
        assert result['name'] == 'test_name'

    def test_serialize_datetime_to_isoformat(self):
        """Test that datetime columns are converted to isoformat string."""
        persistence = get_persistence_module()

        mock_app = Mock()
        mgr = persistence.PersistenceManager(mock_app)

        dt = datetime.datetime(2024, 1, 15, 10, 30, 45)
        instance = TestModel(id=1, name='test', created_at=dt)

        result = mgr.serialize_model(TestModel, instance)

        assert result['created_at'] == '2024-01-15T10:30:45'
        assert isinstance(result['created_at'], str)

    def test_serialize_datetime_with_timezone(self):
        """Test datetime with timezone conversion."""
        persistence = get_persistence_module()

        mock_app = Mock()
        mgr = persistence.PersistenceManager(mock_app)

        # datetime with timezone
        dt = datetime.datetime(2024, 1, 15, 10, 30, 45, tzinfo=datetime.timezone.utc)
        instance = TestModel(id=1, name='test', created_at=dt)

        result = mgr.serialize_model(TestModel, instance)

        assert '2024-01-15' in result['created_at']
        assert isinstance(result['created_at'], str)

    def test_serialize_none_datetime(self):
        """Test that None datetime column is serialized as None."""
        persistence = get_persistence_module()

        mock_app = Mock()
        mgr = persistence.PersistenceManager(mock_app)

        instance = TestModel(id=1, name='test', created_at=datetime.datetime.now(), updated_at=None)

        result = mgr.serialize_model(TestModel, instance)

        # None datetime should be None (not converted to isoformat)
        assert result['updated_at'] is None

    def test_masked_columns_excluded(self):
        """Test that masked columns are excluded from output."""
        persistence = get_persistence_module()

        mock_app = Mock()
        mgr = persistence.PersistenceManager(mock_app)

        instance = TestModel(id=1, name='secret_name', created_at=datetime.datetime.now())

        result = mgr.serialize_model(TestModel, instance, masked_columns=['name'])

        assert 'id' in result
        assert 'created_at' in result
        assert 'name' not in result

    def test_masked_columns_multiple(self):
        """Test that multiple masked columns are excluded."""
        persistence = get_persistence_module()

        mock_app = Mock()
        mgr = persistence.PersistenceManager(mock_app)

        instance = TestModel(id=1, name='secret', created_at=datetime.datetime.now())

        result = mgr.serialize_model(TestModel, instance, masked_columns=['id', 'name'])

        assert 'id' not in result
        assert 'name' not in result
        assert 'created_at' in result
