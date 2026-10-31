"""Test plugin list sorting functionality."""

from contextlib import nullcontext
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from langbot_plugin.entities.io.context import InstallationBinding

from langbot.pkg.api.http.context import ExecutionContext


TEST_EXECUTION_CONTEXT = ExecutionContext(
    instance_uuid='instance-a',
    workspace_uuid='workspace-a',
    placement_generation=1,
)
TEST_INSTALLATION_BINDING = InstallationBinding(
    instance_uuid=TEST_EXECUTION_CONTEXT.instance_uuid,
    workspace_uuid=TEST_EXECUTION_CONTEXT.workspace_uuid,
    placement_generation=TEST_EXECUTION_CONTEXT.placement_generation,
    installation_uuid='00000000-0000-4000-8000-000000000001',
    runtime_revision=1,
    artifact_digest='a' * 64,
)


def configure_connector(connector) -> None:
    connector._execution_context.set(TEST_EXECUTION_CONTEXT)
    connector._operation_bindings = AsyncMock(return_value=[TEST_INSTALLATION_BINDING])
    connector.handler.installation_scope = MagicMock(side_effect=lambda _binding: nullcontext())


@pytest.mark.asyncio
async def test_plugin_list_sorting_debug_first():
    """Test that debug plugins appear before non-debug plugins."""
    from langbot.pkg.plugin.connector import PluginRuntimeConnector

    # Mock the application
    mock_app = MagicMock()
    mock_app.instance_config.data.get.return_value = {'enable': True}
    mock_app.logger = MagicMock()

    # Create connector
    connector = PluginRuntimeConnector(mock_app, AsyncMock())
    connector.handler = MagicMock()
    configure_connector(connector)

    # Mock plugin data with different debug states and timestamps
    now = datetime.now()
    mock_plugins = [
        {
            'debug': False,
            'manifest': {
                'manifest': {
                    'metadata': {
                        'author': 'author1',
                        'name': 'plugin1',
                    }
                }
            },
        },
        {
            'debug': True,
            'manifest': {
                'manifest': {
                    'metadata': {
                        'author': 'author2',
                        'name': 'plugin2',
                    }
                }
            },
        },
        {
            'debug': False,
            'manifest': {
                'manifest': {
                    'metadata': {
                        'author': 'author3',
                        'name': 'plugin3',
                    }
                }
            },
        },
    ]

    connector.handler.list_plugins = AsyncMock(return_value=mock_plugins)

    # Mock database query to return all timestamps in a single batch
    async def mock_load_workspace_settings(_execution_context):
        # Create mock rows for all plugins with timestamps
        mock_rows = []

        # plugin1: oldest, plugin2: middle, plugin3: newest
        mock_row1 = MagicMock()
        mock_row1.plugin_author = 'author1'
        mock_row1.plugin_name = 'plugin1'
        mock_row1.created_at = now - timedelta(days=2)
        mock_rows.append(mock_row1)

        mock_row2 = MagicMock()
        mock_row2.plugin_author = 'author2'
        mock_row2.plugin_name = 'plugin2'
        mock_row2.created_at = now - timedelta(days=1)
        mock_rows.append(mock_row2)

        mock_row3 = MagicMock()
        mock_row3.plugin_author = 'author3'
        mock_row3.plugin_name = 'plugin3'
        mock_row3.created_at = now
        mock_rows.append(mock_row3)

        return mock_rows

    connector._load_workspace_settings = AsyncMock(side_effect=mock_load_workspace_settings)

    # Call list_plugins
    result = await connector.list_plugins()

    # Verify sorting: debug plugin should be first
    assert len(result) == 3
    assert result[0]['debug'] is True  # plugin2 (debug)
    assert result[0]['manifest']['manifest']['metadata']['name'] == 'plugin2'

    # Remaining should be sorted by created_at (newest first)
    assert result[1]['debug'] is False
    assert result[1]['manifest']['manifest']['metadata']['name'] == 'plugin3'  # newest non-debug
    assert result[2]['debug'] is False
    assert result[2]['manifest']['manifest']['metadata']['name'] == 'plugin1'  # oldest non-debug


@pytest.mark.asyncio
async def test_plugin_list_sorting_by_installation_time():
    """Test that non-debug plugins are sorted by installation time (newest first)."""
    from langbot.pkg.plugin.connector import PluginRuntimeConnector

    # Mock the application
    mock_app = MagicMock()
    mock_app.instance_config.data.get.return_value = {'enable': True}
    mock_app.logger = MagicMock()

    # Create connector
    connector = PluginRuntimeConnector(mock_app, AsyncMock())
    connector.handler = MagicMock()
    configure_connector(connector)

    # Mock plugin data - all non-debug with different installation times
    now = datetime.now()
    mock_plugins = [
        {
            'debug': False,
            'manifest': {
                'manifest': {
                    'metadata': {
                        'author': 'author1',
                        'name': 'oldest_plugin',
                    }
                }
            },
        },
        {
            'debug': False,
            'manifest': {
                'manifest': {
                    'metadata': {
                        'author': 'author2',
                        'name': 'middle_plugin',
                    }
                }
            },
        },
        {
            'debug': False,
            'manifest': {
                'manifest': {
                    'metadata': {
                        'author': 'author3',
                        'name': 'newest_plugin',
                    }
                }
            },
        },
    ]

    connector.handler.list_plugins = AsyncMock(return_value=mock_plugins)

    # Mock database query to return all timestamps in a single batch
    async def mock_load_workspace_settings(_execution_context):
        # Create mock rows for all plugins with timestamps
        mock_rows = []

        # oldest_plugin: oldest, middle_plugin: middle, newest_plugin: newest
        mock_row1 = MagicMock()
        mock_row1.plugin_author = 'author1'
        mock_row1.plugin_name = 'oldest_plugin'
        mock_row1.created_at = now - timedelta(days=10)
        mock_rows.append(mock_row1)

        mock_row2 = MagicMock()
        mock_row2.plugin_author = 'author2'
        mock_row2.plugin_name = 'middle_plugin'
        mock_row2.created_at = now - timedelta(days=5)
        mock_rows.append(mock_row2)

        mock_row3 = MagicMock()
        mock_row3.plugin_author = 'author3'
        mock_row3.plugin_name = 'newest_plugin'
        mock_row3.created_at = now
        mock_rows.append(mock_row3)

        return mock_rows

    connector._load_workspace_settings = AsyncMock(side_effect=mock_load_workspace_settings)

    # Call list_plugins
    result = await connector.list_plugins()

    # Verify sorting: newest first
    assert len(result) == 3
    assert result[0]['manifest']['manifest']['metadata']['name'] == 'newest_plugin'
    assert result[1]['manifest']['manifest']['metadata']['name'] == 'middle_plugin'
    assert result[2]['manifest']['manifest']['metadata']['name'] == 'oldest_plugin'


@pytest.mark.asyncio
async def test_plugin_list_empty():
    """Test that empty plugin list is handled correctly."""
    from langbot.pkg.plugin.connector import PluginRuntimeConnector

    # Mock the application
    mock_app = MagicMock()
    mock_app.instance_config.data.get.return_value = {'enable': True}
    mock_app.logger = MagicMock()

    # Create connector
    connector = PluginRuntimeConnector(mock_app, AsyncMock())
    connector.handler = MagicMock()
    configure_connector(connector)

    # Mock empty plugin list
    connector.handler.list_plugins = AsyncMock(return_value=[])

    # Call list_plugins
    result = await connector.list_plugins()

    # Verify empty list
    assert len(result) == 0
