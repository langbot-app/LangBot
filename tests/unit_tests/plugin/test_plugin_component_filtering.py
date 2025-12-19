"""Test plugin list filtering by component kinds."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
import pytest


@pytest.mark.asyncio
async def test_plugin_list_filter_by_component_kinds():
    """Test that plugins can be filtered by component kinds."""
    from src.langbot.pkg.plugin.connector import PluginRuntimeConnector

    # Mock the application
    mock_app = MagicMock()
    mock_app.instance_config.data.get.return_value = {'enable': True}
    mock_app.logger = MagicMock()

    # Create connector
    connector = PluginRuntimeConnector(mock_app, AsyncMock())
    connector.handler = MagicMock()

    # Mock plugin data with different component kinds
    mock_plugins = [
        {
            'debug': False,
            'manifest': {
                'manifest': {
                    'metadata': {
                        'author': 'author1',
                        'name': 'plugin_with_tool',
                    }
                }
            },
            'components': [
                {
                    'manifest': {
                        'manifest': {
                            'kind': 'Tool',
                            'metadata': {'name': 'tool1'}
                        }
                    }
                }
            ]
        },
        {
            'debug': False,
            'manifest': {
                'manifest': {
                    'metadata': {
                        'author': 'author2',
                        'name': 'plugin_with_knowledge_retriever_only',
                    }
                }
            },
            'components': [
                {
                    'manifest': {
                        'manifest': {
                            'kind': 'KnowledgeRetriever',
                            'metadata': {'name': 'retriever1'}
                        }
                    }
                }
            ]
        },
        {
            'debug': False,
            'manifest': {
                'manifest': {
                    'metadata': {
                        'author': 'author3',
                        'name': 'plugin_with_command',
                    }
                }
            },
            'components': [
                {
                    'manifest': {
                        'manifest': {
                            'kind': 'Command',
                            'metadata': {'name': 'cmd1'}
                        }
                    }
                }
            ]
        },
        {
            'debug': False,
            'manifest': {
                'manifest': {
                    'metadata': {
                        'author': 'author4',
                        'name': 'plugin_with_event_listener',
                    }
                }
            },
            'components': [
                {
                    'manifest': {
                        'manifest': {
                            'kind': 'EventListener',
                            'metadata': {'name': 'listener1'}
                        }
                    }
                }
            ]
        },
        {
            'debug': False,
            'manifest': {
                'manifest': {
                    'metadata': {
                        'author': 'author5',
                        'name': 'plugin_with_mixed_components',
                    }
                }
            },
            'components': [
                {
                    'manifest': {
                        'manifest': {
                            'kind': 'KnowledgeRetriever',
                            'metadata': {'name': 'retriever2'}
                        }
                    }
                },
                {
                    'manifest': {
                        'manifest': {
                            'kind': 'Tool',
                            'metadata': {'name': 'tool2'}
                        }
                    }
                }
            ]
        },
    ]

    connector.handler.list_plugins = AsyncMock(return_value=mock_plugins)

    # Mock database query
    async def mock_execute_async(query):
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([])
        return mock_result

    mock_app.persistence_mgr.execute_async = mock_execute_async

    # Test filtering by pipeline component kinds (Command, EventListener, Tool)
    pipeline_component_kinds = ['Command', 'EventListener', 'Tool']
    result = await connector.list_plugins(component_kinds=pipeline_component_kinds)

    # Verify that only plugins with pipeline-related components are returned
    assert len(result) == 4
    plugin_names = [p['manifest']['manifest']['metadata']['name'] for p in result]
    assert 'plugin_with_tool' in plugin_names
    assert 'plugin_with_command' in plugin_names
    assert 'plugin_with_event_listener' in plugin_names
    assert 'plugin_with_mixed_components' in plugin_names
    # Plugin with only KnowledgeRetriever should NOT be included
    assert 'plugin_with_knowledge_retriever_only' not in plugin_names


@pytest.mark.asyncio
async def test_plugin_list_filter_no_filter():
    """Test that all plugins are returned when no filter is specified."""
    from src.langbot.pkg.plugin.connector import PluginRuntimeConnector

    # Mock the application
    mock_app = MagicMock()
    mock_app.instance_config.data.get.return_value = {'enable': True}
    mock_app.logger = MagicMock()

    # Create connector
    connector = PluginRuntimeConnector(mock_app, AsyncMock())
    connector.handler = MagicMock()

    # Mock plugin data with different component kinds
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
            'components': [
                {
                    'manifest': {
                        'manifest': {
                            'kind': 'Tool',
                            'metadata': {'name': 'tool1'}
                        }
                    }
                }
            ]
        },
        {
            'debug': False,
            'manifest': {
                'manifest': {
                    'metadata': {
                        'author': 'author2',
                        'name': 'plugin2',
                    }
                }
            },
            'components': [
                {
                    'manifest': {
                        'manifest': {
                            'kind': 'KnowledgeRetriever',
                            'metadata': {'name': 'retriever1'}
                        }
                    }
                }
            ]
        },
    ]

    connector.handler.list_plugins = AsyncMock(return_value=mock_plugins)

    # Mock database query
    async def mock_execute_async(query):
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([])
        return mock_result

    mock_app.persistence_mgr.execute_async = mock_execute_async

    # Test without filter - should return all plugins
    result = await connector.list_plugins()

    assert len(result) == 2
    plugin_names = [p['manifest']['manifest']['metadata']['name'] for p in result]
    assert 'plugin1' in plugin_names
    assert 'plugin2' in plugin_names


@pytest.mark.asyncio
async def test_plugin_list_filter_empty_result():
    """Test that empty list is returned when no plugins match the filter."""
    from src.langbot.pkg.plugin.connector import PluginRuntimeConnector

    # Mock the application
    mock_app = MagicMock()
    mock_app.instance_config.data.get.return_value = {'enable': True}
    mock_app.logger = MagicMock()

    # Create connector
    connector = PluginRuntimeConnector(mock_app, AsyncMock())
    connector.handler = MagicMock()

    # Mock plugin data - only KnowledgeRetriever plugins
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
            'components': [
                {
                    'manifest': {
                        'manifest': {
                            'kind': 'KnowledgeRetriever',
                            'metadata': {'name': 'retriever1'}
                        }
                    }
                }
            ]
        },
    ]

    connector.handler.list_plugins = AsyncMock(return_value=mock_plugins)

    # Mock database query
    async def mock_execute_async(query):
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([])
        return mock_result

    mock_app.persistence_mgr.execute_async = mock_execute_async

    # Filter by Tool kind - should return empty list
    result = await connector.list_plugins(component_kinds=['Tool'])

    assert len(result) == 0


@pytest.mark.asyncio
async def test_plugin_list_filter_plugin_without_components():
    """Test that plugins without components are excluded when filtering."""
    from src.langbot.pkg.plugin.connector import PluginRuntimeConnector

    # Mock the application
    mock_app = MagicMock()
    mock_app.instance_config.data.get.return_value = {'enable': True}
    mock_app.logger = MagicMock()

    # Create connector
    connector = PluginRuntimeConnector(mock_app, AsyncMock())
    connector.handler = MagicMock()

    # Mock plugin data - one with components, one without
    mock_plugins = [
        {
            'debug': False,
            'manifest': {
                'manifest': {
                    'metadata': {
                        'author': 'author1',
                        'name': 'plugin_with_tool',
                    }
                }
            },
            'components': [
                {
                    'manifest': {
                        'manifest': {
                            'kind': 'Tool',
                            'metadata': {'name': 'tool1'}
                        }
                    }
                }
            ]
        },
        {
            'debug': False,
            'manifest': {
                'manifest': {
                    'metadata': {
                        'author': 'author2',
                        'name': 'plugin_without_components',
                    }
                }
            },
            'components': []
        },
    ]

    connector.handler.list_plugins = AsyncMock(return_value=mock_plugins)

    # Mock database query
    async def mock_execute_async(query):
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([])
        return mock_result

    mock_app.persistence_mgr.execute_async = mock_execute_async

    # Filter by Tool kind - should return only plugin with Tool
    result = await connector.list_plugins(component_kinds=['Tool'])

    assert len(result) == 1
    assert result[0]['manifest']['manifest']['metadata']['name'] == 'plugin_with_tool'
