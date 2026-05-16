"""Unit tests for core app config validation methods.

Tests cover:
- _get_positive_int_config() validation
- _get_positive_float_config() validation
"""
from __future__ import annotations

from unittest.mock import Mock
from importlib import import_module


def get_app_module():
    """Lazy import to avoid circular import issues."""
    return import_module('langbot.pkg.core.app')


class TestGetPositiveIntConfig:
    """Tests for _get_positive_int_config method."""

    def test_returns_value_when_valid_positive_int(self):
        """Test returns parsed int for valid positive value."""
        app_module = get_app_module()

        mock_logger = Mock()

        app = app_module.Application()
        app.logger = mock_logger

        result = app._get_positive_int_config(10, default=30, name='test.config')

        assert result == 10
        mock_logger.warning.assert_not_called()

    def test_returns_value_when_valid_string_int(self):
        """Test returns parsed int for string value."""
        app_module = get_app_module()

        mock_logger = Mock()

        app = app_module.Application()
        app.logger = mock_logger

        result = app._get_positive_int_config('50', default=30, name='test.config')

        assert result == 50
        mock_logger.warning.assert_not_called()

    def test_returns_default_for_zero(self):
        """Test returns default when value is zero."""
        app_module = get_app_module()

        mock_logger = Mock()

        app = app_module.Application()
        app.logger = mock_logger

        result = app._get_positive_int_config(0, default=30, name='test.config')

        assert result == 30
        mock_logger.warning.assert_called_once()

    def test_returns_default_for_negative(self):
        """Test returns default when value is negative."""
        app_module = get_app_module()

        mock_logger = Mock()

        app = app_module.Application()
        app.logger = mock_logger

        result = app._get_positive_int_config(-5, default=30, name='test.config')

        assert result == 30
        mock_logger.warning.assert_called_once()

    def test_returns_default_for_invalid_string(self):
        """Test returns default when value is invalid string."""
        app_module = get_app_module()

        mock_logger = Mock()

        app = app_module.Application()
        app.logger = mock_logger

        result = app._get_positive_int_config('invalid', default=30, name='test.config')

        assert result == 30
        mock_logger.warning.assert_called_once()

    def test_returns_default_for_none(self):
        """Test returns default when value is None."""
        app_module = get_app_module()

        mock_logger = Mock()

        app = app_module.Application()
        app.logger = mock_logger

        result = app._get_positive_int_config(None, default=30, name='test.config')

        assert result == 30
        mock_logger.warning.assert_called_once()


class TestGetPositiveFloatConfig:
    """Tests for _get_positive_float_config method."""

    def test_returns_value_when_valid_positive_float(self):
        """Test returns parsed float for valid positive value."""
        app_module = get_app_module()

        mock_logger = Mock()

        app = app_module.Application()
        app.logger = mock_logger

        result = app._get_positive_float_config(1.5, default=2.0, name='test.config')

        assert result == 1.5
        mock_logger.warning.assert_not_called()

    def test_returns_value_when_valid_int(self):
        """Test returns float for valid int value."""
        app_module = get_app_module()

        mock_logger = Mock()

        app = app_module.Application()
        app.logger = mock_logger

        result = app._get_positive_float_config(2, default=1.0, name='test.config')

        assert result == 2.0
        mock_logger.warning.assert_not_called()

    def test_returns_value_when_valid_string_float(self):
        """Test returns parsed float for string value."""
        app_module = get_app_module()

        mock_logger = Mock()

        app = app_module.Application()
        app.logger = mock_logger

        result = app._get_positive_float_config('0.5', default=1.0, name='test.config')

        assert result == 0.5
        mock_logger.warning.assert_not_called()

    def test_returns_default_for_zero(self):
        """Test returns default when value is zero."""
        app_module = get_app_module()

        mock_logger = Mock()

        app = app_module.Application()
        app.logger = mock_logger

        result = app._get_positive_float_config(0.0, default=1.0, name='test.config')

        assert result == 1.0
        mock_logger.warning.assert_called_once()

    def test_returns_default_for_negative(self):
        """Test returns default when value is negative."""
        app_module = get_app_module()

        mock_logger = Mock()

        app = app_module.Application()
        app.logger = mock_logger

        result = app._get_positive_float_config(-1.0, default=2.0, name='test.config')

        assert result == 2.0
        mock_logger.warning.assert_called_once()

    def test_returns_default_for_invalid_string(self):
        """Test returns default when value is invalid string."""
        app_module = get_app_module()

        mock_logger = Mock()

        app = app_module.Application()
        app.logger = mock_logger

        result = app._get_positive_float_config('not-a-number', default=1.5, name='test.config')

        assert result == 1.5
        mock_logger.warning.assert_called_once()