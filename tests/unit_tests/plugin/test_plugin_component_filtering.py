"""Test plugin list filtering by component kinds."""

from contextlib import nullcontext
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
    connector._load_workspace_settings = AsyncMock(return_value=[])
    connector.handler.installation_scope = MagicMock(side_effect=lambda _binding: nullcontext())


@pytest.mark.asyncio
async def test_plugin_list_filter_by_component_kinds():
    """Test that plugins can be filtered by component kinds."""
    from langbot.pkg.plugin.connector import PluginRuntimeConnector

    # Mock the application
    mock_app = MagicMock()
    mock_app.instance_config.data.get.return_value = {'enable': True}
    mock_app.logger = MagicMock()

    # Create connector
    connector = PluginRuntimeConnector(mock_app, AsyncMock())
    connector.handler = MagicMock()
    configure_connector(connector)

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
            'components': [{'manifest': {'manifest': {'kind': 'Tool', 'metadata': {'name': 'tool1'}}}}],
        },
        {
            'debug': False,
            'manifest': {
                'manifest': {
                    'metadata': {
                        'author': 'author2',
                        'name': 'plugin_with_knowledge_engine_only',
                    }
                }
            },
            'components': [{'manifest': {'manifest': {'kind': 'KnowledgeEngine', 'metadata': {'name': 'retriever1'}}}}],
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
            'components': [{'manifest': {'manifest': {'kind': 'Command', 'metadata': {'name': 'cmd1'}}}}],
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
            'components': [{'manifest': {'manifest': {'kind': 'EventListener', 'metadata': {'name': 'listener1'}}}}],
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
                {'manifest': {'manifest': {'kind': 'KnowledgeEngine', 'metadata': {'name': 'retriever2'}}}},
                {'manifest': {'manifest': {'kind': 'Tool', 'metadata': {'name': 'tool2'}}}},
            ],
        },
    ]

    connector.handler.list_plugins = AsyncMock(return_value=mock_plugins)

    # Mock database query
    async def mock_execute_async(query):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
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
    # Plugin with only KnowledgeEngine should NOT be included
    assert 'plugin_with_knowledge_engine_only' not in plugin_names


@pytest.mark.asyncio
async def test_plugin_list_filter_no_filter():
    """Test that all plugins are returned when no filter is specified."""
    from langbot.pkg.plugin.connector import PluginRuntimeConnector

    # Mock the application
    mock_app = MagicMock()
    mock_app.instance_config.data.get.return_value = {'enable': True}
    mock_app.logger = MagicMock()

    # Create connector
    connector = PluginRuntimeConnector(mock_app, AsyncMock())
    connector.handler = MagicMock()
    configure_connector(connector)

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
            'components': [{'manifest': {'manifest': {'kind': 'Tool', 'metadata': {'name': 'tool1'}}}}],
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
            'components': [{'manifest': {'manifest': {'kind': 'KnowledgeEngine', 'metadata': {'name': 'retriever1'}}}}],
        },
    ]

    connector.handler.list_plugins = AsyncMock(return_value=mock_plugins)

    # Mock database query
    async def mock_execute_async(query):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
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
    from langbot.pkg.plugin.connector import PluginRuntimeConnector

    # Mock the application
    mock_app = MagicMock()
    mock_app.instance_config.data.get.return_value = {'enable': True}
    mock_app.logger = MagicMock()

    # Create connector
    connector = PluginRuntimeConnector(mock_app, AsyncMock())
    connector.handler = MagicMock()
    configure_connector(connector)

    # Mock plugin data - only KnowledgeEngine plugins
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
            'components': [{'manifest': {'manifest': {'kind': 'KnowledgeEngine', 'metadata': {'name': 'retriever1'}}}}],
        },
    ]

    connector.handler.list_plugins = AsyncMock(return_value=mock_plugins)

    # Mock database query
    async def mock_execute_async(query):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        return mock_result

    mock_app.persistence_mgr.execute_async = mock_execute_async

    # Filter by Tool kind - should return empty list
    result = await connector.list_plugins(component_kinds=['Tool'])

    assert len(result) == 0


@pytest.mark.asyncio
async def test_plugin_list_filter_plugin_without_components():
    """Test that plugins without components are excluded when filtering."""
    from langbot.pkg.plugin.connector import PluginRuntimeConnector

    # Mock the application
    mock_app = MagicMock()
    mock_app.instance_config.data.get.return_value = {'enable': True}
    mock_app.logger = MagicMock()

    # Create connector
    connector = PluginRuntimeConnector(mock_app, AsyncMock())
    connector.handler = MagicMock()
    configure_connector(connector)

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
            'components': [{'manifest': {'manifest': {'kind': 'Tool', 'metadata': {'name': 'tool1'}}}}],
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
            'components': [],
        },
    ]

    connector.handler.list_plugins = AsyncMock(return_value=mock_plugins)

    # Mock database query
    async def mock_execute_async(query):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        return mock_result

    mock_app.persistence_mgr.execute_async = mock_execute_async

    # Filter by Tool kind - should return only plugin with Tool
    result = await connector.list_plugins(component_kinds=['Tool'])

    assert len(result) == 1
    assert result[0]['manifest']['manifest']['metadata']['name'] == 'plugin_with_tool'
