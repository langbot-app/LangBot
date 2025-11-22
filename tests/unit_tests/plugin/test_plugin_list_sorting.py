"""Test plugin list sorting functionality."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


@pytest.mark.asyncio
async def test_plugin_list_sorting_debug_first():
    """Test that debug plugins appear before non-debug plugins."""
    from src.langbot.pkg.plugin.connector import PluginRuntimeConnector
    
    # Mock the application
    mock_app = MagicMock()
    mock_app.instance_config.data.get.return_value = {'enable': True}
    mock_app.logger = MagicMock()
    
    # Create connector
    connector = PluginRuntimeConnector(mock_app, AsyncMock())
    connector.handler = MagicMock()
    
    # Mock plugin data with different debug states and timestamps
    now = datetime.now()
    mock_plugins = [
        {
            'debug': False,
            'manifest': {
                'metadata': {
                    'author': 'author1',
                    'name': 'plugin1',
                }
            }
        },
        {
            'debug': True,
            'manifest': {
                'metadata': {
                    'author': 'author2',
                    'name': 'plugin2',
                }
            }
        },
        {
            'debug': False,
            'manifest': {
                'metadata': {
                    'author': 'author3',
                    'name': 'plugin3',
                }
            }
        },
    ]
    
    connector.handler.list_plugins = AsyncMock(return_value=mock_plugins)

    # Mock database query to return all timestamps in a single batch
    async def mock_execute_async(query):
        mock_result = MagicMock()

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

        # Make the result iterable
        mock_result.__iter__ = lambda self: iter(mock_rows)

        return mock_result

    mock_app.persistence_mgr.execute_async = mock_execute_async

    # Call list_plugins
    result = await connector.list_plugins()
    
    # Verify sorting: debug plugin should be first
    assert len(result) == 3
    assert result[0]['debug'] is True  # plugin2 (debug)
    assert result[0]['manifest']['metadata']['name'] == 'plugin2'
    
    # Remaining should be sorted by created_at (newest first)
    assert result[1]['debug'] is False
    assert result[1]['manifest']['metadata']['name'] == 'plugin3'  # newest non-debug
    assert result[2]['debug'] is False
    assert result[2]['manifest']['metadata']['name'] == 'plugin1'  # oldest non-debug


@pytest.mark.asyncio
async def test_plugin_list_sorting_by_installation_time():
    """Test that non-debug plugins are sorted by installation time (newest first)."""
    from src.langbot.pkg.plugin.connector import PluginRuntimeConnector
    
    # Mock the application
    mock_app = MagicMock()
    mock_app.instance_config.data.get.return_value = {'enable': True}
    mock_app.logger = MagicMock()
    
    # Create connector
    connector = PluginRuntimeConnector(mock_app, AsyncMock())
    connector.handler = MagicMock()
    
    # Mock plugin data - all non-debug with different installation times
    now = datetime.now()
    mock_plugins = [
        {
            'debug': False,
            'manifest': {
                'metadata': {
                    'author': 'author1',
                    'name': 'oldest_plugin',
                }
            }
        },
        {
            'debug': False,
            'manifest': {
                'metadata': {
                    'author': 'author2',
                    'name': 'middle_plugin',
                }
            }
        },
        {
            'debug': False,
            'manifest': {
                'metadata': {
                    'author': 'author3',
                    'name': 'newest_plugin',
                }
            }
        },
    ]

    connector.handler.list_plugins = AsyncMock(return_value=mock_plugins)

    # Mock database query to return all timestamps in a single batch
    async def mock_execute_async(query):
        mock_result = MagicMock()

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

        # Make the result iterable
        mock_result.__iter__ = lambda self: iter(mock_rows)

        return mock_result

    mock_app.persistence_mgr.execute_async = mock_execute_async
    
    # Call list_plugins
    result = await connector.list_plugins()
    
    # Verify sorting: newest first
    assert len(result) == 3
    assert result[0]['manifest']['metadata']['name'] == 'newest_plugin'
    assert result[1]['manifest']['metadata']['name'] == 'middle_plugin'
    assert result[2]['manifest']['metadata']['name'] == 'oldest_plugin'


@pytest.mark.asyncio
async def test_plugin_list_empty():
    """Test that empty plugin list is handled correctly."""
    from src.langbot.pkg.plugin.connector import PluginRuntimeConnector
    
    # Mock the application
    mock_app = MagicMock()
    mock_app.instance_config.data.get.return_value = {'enable': True}
    mock_app.logger = MagicMock()
    
    # Create connector
    connector = PluginRuntimeConnector(mock_app, AsyncMock())
    connector.handler = MagicMock()
    
    # Mock empty plugin list
    connector.handler.list_plugins = AsyncMock(return_value=[])
    
    # Call list_plugins
    result = await connector.list_plugins()
    
    # Verify empty list
    assert len(result) == 0
    assert result == []

