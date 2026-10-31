"""Unit tests for plugin connector static methods.

Tests cover:
- _parse_plugin_id() parsing and validation
"""

from __future__ import annotations

from importlib import import_module

import pytest


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


def test_runtime_id_is_stable_across_core_restarts(monkeypatch):
    connector = get_connector_module()
    monkeypatch.setattr(connector.constants, 'instance_id', 'instance-a')

    assert connector.PluginRuntimeConnector._build_runtime_id() == 'instance-a:plugin-runtime'


def test_runtime_connect_timeout_defaults_to_three_minutes():
    connector = get_connector_module()
    assert connector.PluginRuntimeConnector._runtime_connect_timeout({}) == 180.0


def test_runtime_connect_timeout_reads_typed_plugin_config():
    connector = get_connector_module()
    assert connector.PluginRuntimeConnector._runtime_connect_timeout({'connect_timeout_seconds': 45.5}) == 45.5


@pytest.mark.parametrize('value', [True, False, None, 0, -1, float('nan'), float('inf'), '180', object()])
def test_runtime_connect_timeout_rejects_invalid_values(value):
    connector = get_connector_module()
    with pytest.raises(ValueError, match='plugin.connect_timeout_seconds'):
        connector.PluginRuntimeConnector._runtime_connect_timeout({'connect_timeout_seconds': value})


def test_runtime_connect_timeout_error_displays_actual_seconds():
    connector = get_connector_module()

    assert connector.PluginRuntimeConnector._runtime_connect_timeout_error(45.5) == (
        'Plugin runtime did not become ready within 45.5 seconds'
    )
