"""Tests for PluginRuntimeConnector pure logic methods.

Tests methods that don't require real plugin runtime processes:
- _inspect_plugin_package: identity and deps extraction from zip files
- _parse_plugin_id: plugin ID string parsing
"""

from __future__ import annotations

import io
import zipfile
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


class TestExtractDepsMetadata:
    """Tests for dependency metadata extraction from plugin packages."""

    def _create_connector(self):
        """Create a connector instance for testing."""
        from langbot.pkg.plugin.connector import PluginRuntimeConnector

        mock_app = MagicMock()
        mock_app.instance_config.data.get.return_value = {'enable': True}
        mock_app.logger = MagicMock()

        connector = PluginRuntimeConnector(mock_app, MagicMock())
        return connector

    def test_extract_deps_with_requirements_txt(self):
        """Extract dependency count from requirements.txt in plugin zip."""
        connector = self._create_connector()

        # Create a mock zip file with requirements.txt
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            zf.writestr('requirements.txt', 'requests>=2.0\nflask\n# comment\n\nnumpy')

        zip_bytes = zip_buffer.getvalue()

        task_context = SimpleNamespace(metadata={})
        connector._inspect_plugin_package(zip_bytes, task_context)

        assert task_context.metadata['deps_total'] == 3  # requests>=2.0, flask, numpy
        # deps_list contains full requirement lines including version specifiers
        assert 'requests>=2.0' in task_context.metadata['deps_list']
        assert 'flask' in task_context.metadata['deps_list']
        assert 'numpy' in task_context.metadata['deps_list']

    def test_extract_deps_empty_requirements(self):
        """Handle empty requirements.txt."""
        connector = self._create_connector()

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            zf.writestr('requirements.txt', '# only comments\n\n')

        zip_bytes = zip_buffer.getvalue()

        task_context = SimpleNamespace(metadata={})
        connector._inspect_plugin_package(zip_bytes, task_context)

        assert task_context.metadata['deps_total'] == 0
        assert task_context.metadata['deps_list'] == []

    def test_extract_deps_no_requirements_txt(self):
        """Handle zip without requirements.txt."""
        connector = self._create_connector()

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            zf.writestr('plugin.py', 'print("hello")')

        zip_bytes = zip_buffer.getvalue()

        task_context = SimpleNamespace(metadata={})
        connector._inspect_plugin_package(zip_bytes, task_context)

        # No requirements.txt found, metadata unchanged
        assert 'deps_total' not in task_context.metadata

    def test_extract_deps_none_task_context(self):
        """Handle None task_context gracefully."""
        connector = self._create_connector()

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            zf.writestr('requirements.txt', 'requests')

        zip_bytes = zip_buffer.getvalue()

        # Should return early without error
        connector._inspect_plugin_package(zip_bytes, None)

    def test_extract_deps_invalid_zip(self):
        """Handle invalid zip file gracefully."""
        connector = self._create_connector()

        # Not a valid zip
        invalid_bytes = b'not a zip file'

        task_context = SimpleNamespace(metadata={})
        connector._inspect_plugin_package(invalid_bytes, task_context)

        # Should catch exception and pass silently
        assert 'deps_total' not in task_context.metadata

    def test_extract_deps_nested_requirements(self):
        """Handle requirements.txt in nested directory."""
        connector = self._create_connector()

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            zf.writestr('subdir/requirements.txt', 'pytest\nblack')

        zip_bytes = zip_buffer.getvalue()

        task_context = SimpleNamespace(metadata={})
        connector._inspect_plugin_package(zip_bytes, task_context)

        # Should find requirements.txt in subdirectory
        assert task_context.metadata['deps_total'] == 2


class TestParsePluginId:
    """Tests for _parse_plugin_id static method."""

    def test_parse_valid_plugin_id(self):
        """Parse valid plugin ID format 'author/name'."""
        from langbot.pkg.plugin.connector import PluginRuntimeConnector

        author, name = PluginRuntimeConnector._parse_plugin_id('myauthor/myplugin')
        assert author == 'myauthor'
        assert name == 'myplugin'

    def test_parse_plugin_id_empty(self):
        """Empty plugin ID is invalid."""
        from langbot.pkg.plugin.connector import PluginRuntimeConnector

        with pytest.raises(ValueError):
            PluginRuntimeConnector._parse_plugin_id('')
