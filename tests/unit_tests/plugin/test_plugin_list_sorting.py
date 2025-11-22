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
    
    # Mock database queries to return timestamps
    # plugin1: oldest, plugin2: middle, plugin3: newest
    call_count = [0]  # Use list to allow mutation in nested function
    
    async def mock_execute_async(query):
        mock_result = MagicMock()
        mock_row = MagicMock()
        
        # Return timestamps in order of calls
        # First call is for plugin1, second for plugin2, third for plugin3
        if call_count[0] == 0:
            mock_row.created_at = now - timedelta(days=2)  # plugin1 (oldest)
        elif call_count[0] == 1:
            mock_row.created_at = now - timedelta(days=1)  # plugin2 (middle)
        elif call_count[0] == 2:
            mock_row.created_at = now  # plugin3 (newest)
        
        call_count[0] += 1
        mock_result.first.return_value = mock_row
        
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
    
    # Mock database queries to return timestamps
    call_count = [0]
    
    async def mock_execute_async(query):
        mock_result = MagicMock()
        mock_row = MagicMock()
        
        # Return timestamps in order of calls
        if call_count[0] == 0:
            mock_row.created_at = now - timedelta(days=10)  # oldest_plugin
        elif call_count[0] == 1:
            mock_row.created_at = now - timedelta(days=5)  # middle_plugin
        elif call_count[0] == 2:
            mock_row.created_at = now  # newest_plugin
        
        call_count[0] += 1
        mock_result.first.return_value = mock_row
        
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

