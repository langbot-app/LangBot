"""Unit tests for plugin connector _inspect_plugin_package method.

Tests cover:
- Extracting requirements.txt from ZIP
- Parsing dependency lines
- Handling missing requirements.txt
- Handling empty/malformed requirements.txt
"""
from __future__ import annotations

import zipfile
import io
from unittest.mock import Mock
from importlib import import_module


def get_connector_module():
    """Lazy import to avoid circular import issues."""
    return import_module('langbot.pkg.plugin.connector')


def create_mock_connector():
    """Create a mock PluginRuntimeConnector instance for testing."""
    connector = get_connector_module()
    mock_app = Mock()
    mock_app.logger = Mock()
    mock_app.instance_config = Mock()
    mock_app.instance_config.data = {'plugin': {'enable': True}}

    # Mock disconnect callback
    async def mock_disconnect_callback(connector):
        pass

    return connector.PluginRuntimeConnector(mock_app, mock_disconnect_callback)


def create_zip_with_requirements(requirements_content: str) -> bytes:
    """Create a ZIP file containing requirements.txt with given content."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('requirements.txt', requirements_content)
    return buf.getvalue()


def create_zip_with_nested_requirements(requirements_content: str) -> bytes:
    """Create a ZIP file with requirements.txt in nested directory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('plugin/requirements.txt', requirements_content)
    return buf.getvalue()


def create_zip_without_requirements() -> bytes:
    """Create a ZIP file without requirements.txt."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('main.py', 'print("hello")')
        zf.writestr('manifest.yaml', 'name: test')
    return buf.getvalue()


class TestExtractDepsMetadata:
    """Tests for dependency metadata extraction from plugin packages."""

    def test_extract_simple_requirements(self):
        """Test extracting simple requirements.txt."""
        connector_instance = create_mock_connector()

        # Create test ZIP
        zip_bytes = create_zip_with_requirements('requests>=2.0\nflask==1.0\nnumpy')

        # Create task context
        task_context = Mock()
        task_context.metadata = {}

        connector_instance._inspect_plugin_package(zip_bytes, task_context)

        assert task_context.metadata.get('deps_total') == 3
        assert task_context.metadata.get('deps_list') == ['requests>=2.0', 'flask==1.0', 'numpy']

    def test_extract_requirements_with_comments_and_empty_lines(self):
        """Test that comments and empty lines are filtered."""
        connector_instance = create_mock_connector()

        requirements = '''# This is a comment
requests>=2.0

# Another comment
flask==1.0

numpy'''
        zip_bytes = create_zip_with_requirements(requirements)

        task_context = Mock()
        task_context.metadata = {}

        connector_instance._inspect_plugin_package(zip_bytes, task_context)

        assert task_context.metadata.get('deps_total') == 3
        assert '# This is a comment' not in task_context.metadata.get('deps_list', [])

    def test_extract_nested_requirements(self):
        """Test extracting requirements.txt from nested directory."""
        connector_instance = create_mock_connector()

        zip_bytes = create_zip_with_nested_requirements('requests\nflask')

        task_context = Mock()
        task_context.metadata = {}

        connector_instance._inspect_plugin_package(zip_bytes, task_context)

        # Should find nested requirements.txt (ends with 'requirements.txt')
        assert task_context.metadata.get('deps_total') == 2

    def test_no_requirements_in_zip(self):
        """Test handling ZIP without requirements.txt."""
        connector_instance = create_mock_connector()

        zip_bytes = create_zip_without_requirements()

        task_context = Mock()
        task_context.metadata = {}

        connector_instance._inspect_plugin_package(zip_bytes, task_context)

        # metadata should remain empty (no deps found)
        assert task_context.metadata.get('deps_total') is None
        assert task_context.metadata.get('deps_list') is None

    def test_empty_requirements_file(self):
        """Test handling empty requirements.txt."""
        connector_instance = create_mock_connector()

        zip_bytes = create_zip_with_requirements('')

        task_context = Mock()
        task_context.metadata = {}

        connector_instance._inspect_plugin_package(zip_bytes, task_context)

        # deps_total should be 0 (empty list after filtering)
        assert task_context.metadata.get('deps_total') == 0
        assert task_context.metadata.get('deps_list') == []

    def test_requirements_only_comments(self):
        """Test handling requirements.txt with only comments."""
        connector_instance = create_mock_connector()

        requirements = '''# Comment 1
# Comment 2
# Comment 3'''
        zip_bytes = create_zip_with_requirements(requirements)

        task_context = Mock()
        task_context.metadata = {}

        connector_instance._inspect_plugin_package(zip_bytes, task_context)

        assert task_context.metadata.get('deps_total') == 0
        assert task_context.metadata.get('deps_list') == []

    def test_task_context_none_returns_early(self):
        """Test that method returns early when task_context is None."""
        connector_instance = create_mock_connector()

        zip_bytes = create_zip_with_requirements('requests')

        # Should return without error when task_context is None
        connector_instance._inspect_plugin_package(zip_bytes, None)

        # No exception should be raised

    def test_malformed_zip_handling(self):
        """Test handling malformed ZIP bytes."""
        connector_instance = create_mock_connector()

        # Invalid ZIP bytes
        invalid_bytes = b'not a valid zip file'

        task_context = Mock()
        task_context.metadata = {}

        # Should silently handle exception (pass in try/except)
        connector_instance._inspect_plugin_package(invalid_bytes, task_context)

        # metadata should remain unchanged
        assert task_context.metadata == {}

    def test_requirements_with_unicode_decode_error(self):
        """Test handling requirements.txt with non-UTF8 content."""
        connector_instance = create_mock_connector()

        # Create ZIP with non-UTF8 content in requirements.txt
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            # Write bytes that will cause decode issues
            # \x80 is invalid UTF-8, but errors='ignore' will skip it
            zf.writestr('requirements.txt', b'requests\nflask\n\x80invalid')
        zip_bytes = buf.getvalue()

        task_context = Mock()
        task_context.metadata = {}

        # errors='ignore' will decode \x80invalid as 'invalid' (skipping \x80)
        connector_instance._inspect_plugin_package(zip_bytes, task_context)

        # All 3 lines will be parsed (requests, flask, invalid)
        assert task_context.metadata.get('deps_total') == 3
        assert 'invalid' in task_context.metadata.get('deps_list', [])
