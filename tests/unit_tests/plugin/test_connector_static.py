"""Unit tests for plugin connector static methods.

Tests cover:
- _parse_plugin_id() parsing and validation
"""
from __future__ import annotations

import pytest
from importlib import import_module


def get_connector_module():
    """Lazy import to avoid circular import issues."""
    return import_module('langbot.pkg.plugin.connector')


class TestParsePluginId:
    """Tests for _parse_plugin_id static method."""

    def test_valid_plugin_id_simple(self):
        """Test parsing valid plugin ID with simple format."""
        connector = get_connector_module()
        author, name = connector.PluginRuntimeConnector._parse_plugin_id('langbot/rag-engine')
        assert author == 'langbot'
        assert name == 'rag-engine'

    def test_invalid_plugin_id_no_slash(self):
        """Test that ValueError is raised when no slash present."""
        connector = get_connector_module()
        with pytest.raises(ValueError) as exc_info:
            connector.PluginRuntimeConnector._parse_plugin_id('invalid-plugin-id')
        assert 'Invalid plugin_id format' in str(exc_info.value)
        assert 'invalid-plugin-id' in str(exc_info.value)

    def test_invalid_plugin_id_empty_string(self):
        """Test that ValueError is raised for empty string."""
        connector = get_connector_module()
        with pytest.raises(ValueError) as exc_info:
            connector.PluginRuntimeConnector._parse_plugin_id('')
        assert 'Invalid plugin_id format' in str(exc_info.value)

    def test_valid_plugin_id_single_character_parts(self):
        """Test parsing plugin ID with single character author and name."""
        connector = get_connector_module()
        author, name = connector.PluginRuntimeConnector._parse_plugin_id('a/b')
        assert author == 'a'
        assert name == 'b'

    def test_valid_plugin_id_with_hyphens_and_underscores(self):
        """Test parsing plugin ID with hyphens and underscores."""
        connector = get_connector_module()
        author, name = connector.PluginRuntimeConnector._parse_plugin_id('lang-bot/my_rag_engine')
        assert author == 'lang-bot'
        assert name == 'my_rag_engine'
