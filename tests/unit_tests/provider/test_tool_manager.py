"""Unit tests for ToolManager.

Tests cover:
- Tool schema generation for OpenAI and Anthropic
- Tool execution dispatch
"""
from __future__ import annotations

import pytest
from unittest.mock import Mock, AsyncMock
from importlib import import_module

import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


def get_toolmgr_module():
    """Lazy import to avoid circular import issues."""
    return import_module('langbot.pkg.provider.tools.toolmgr')


class TestToolManagerInit:
    """Tests for ToolManager initialization."""

    def test_init_stores_app_reference(self):
        """Test that __init__ stores the Application reference."""
        toolmgr = get_toolmgr_module()

        mock_app = Mock()
        manager = toolmgr.ToolManager(mock_app)
        assert manager.ap is mock_app

    def test_init_no_tool_loaders(self):
        """Test that tool loaders are not initialized before initialize()."""
        toolmgr = get_toolmgr_module()

        mock_app = Mock()
        manager = toolmgr.ToolManager(mock_app)
        assert hasattr(manager, 'plugin_tool_loader') is False or manager.plugin_tool_loader is None


class TestToolManagerSchemaGeneration:
    """Tests for tool schema generation methods."""

    @pytest.fixture
    def mock_app(self):
        """Create mock app."""
        mock_app = Mock()
        mock_app.logger = Mock()
        return mock_app

    @pytest.fixture
    def sample_tools(self):
        """Create sample LLMTool list for testing."""
        def dummy_weather_func(**kwargs):
            return "weather result"

        def dummy_calc_func(**kwargs):
            return "calc result"

        tools = [
            resource_tool.LLMTool(
                name='get_weather',
                human_desc='Get current weather for a location',
                description='Get current weather for a location',
                parameters={
                    'type': 'object',
                    'properties': {
                        'location': {
                            'type': 'string',
                            'description': 'City name'
                        }
                    },
                    'required': ['location']
                },
                func=dummy_weather_func
            ),
            resource_tool.LLMTool(
                name='calculate',
                human_desc='Perform a calculation',
                description='Perform a calculation',
                parameters={
                    'type': 'object',
                    'properties': {
                        'expression': {
                            'type': 'string',
                            'description': 'Math expression'
                        }
                    },
                    'required': ['expression']
                },
                func=dummy_calc_func
            ),
        ]
        return tools

    @pytest.mark.asyncio
    async def test_generate_tools_for_openai(self, mock_app, sample_tools):
        """Test that generate_tools_for_openai produces correct schema."""
        toolmgr = get_toolmgr_module()

        manager = toolmgr.ToolManager(mock_app)
        result = await manager.generate_tools_for_openai(sample_tools)

        assert len(result) == 2

        # Verify first tool schema
        tool1 = result[0]
        assert tool1['type'] == 'function'
        assert tool1['function']['name'] == 'get_weather'
        assert tool1['function']['description'] == 'Get current weather for a location'
        assert 'parameters' in tool1['function']
        assert tool1['function']['parameters']['type'] == 'object'

        # Verify second tool schema
        tool2 = result[1]
        assert tool2['type'] == 'function'
        assert tool2['function']['name'] == 'calculate'

    @pytest.mark.asyncio
    async def test_generate_tools_for_anthropic(self, mock_app, sample_tools):
        """Test that generate_tools_for_anthropic produces correct schema."""
        toolmgr = get_toolmgr_module()

        manager = toolmgr.ToolManager(mock_app)
        result = await manager.generate_tools_for_anthropic(sample_tools)

        assert len(result) == 2

        # Verify first tool schema (Anthropic format)
        tool1 = result[0]
        assert tool1['name'] == 'get_weather'
        assert tool1['description'] == 'Get current weather for a location'
        assert 'input_schema' in tool1
        assert tool1['input_schema']['type'] == 'object'

        # Verify second tool schema
        tool2 = result[1]
        assert tool2['name'] == 'calculate'
        assert 'input_schema' in tool2

    @pytest.mark.asyncio
    async def test_generate_tools_empty_list(self, mock_app):
        """Test that generating tools from empty list returns empty list."""
        toolmgr = get_toolmgr_module()

        manager = toolmgr.ToolManager(mock_app)

        openai_result = await manager.generate_tools_for_openai([])
        assert openai_result == []

        anthropic_result = await manager.generate_tools_for_anthropic([])
        assert anthropic_result == []

    @pytest.mark.asyncio
    async def test_openai_schema_fields_complete(self, mock_app, sample_tools):
        """Test that OpenAI schema includes all required fields."""
        toolmgr = get_toolmgr_module()

        manager = toolmgr.ToolManager(mock_app)
        result = await manager.generate_tools_for_openai(sample_tools)

        for tool_schema in result:
            assert 'type' in tool_schema
            assert tool_schema['type'] == 'function'
            assert 'function' in tool_schema
            func = tool_schema['function']
            assert 'name' in func
            assert 'description' in func
            assert 'parameters' in func

    @pytest.mark.asyncio
    async def test_anthropic_schema_fields_complete(self, mock_app, sample_tools):
        """Test that Anthropic schema includes all required fields."""
        toolmgr = get_toolmgr_module()

        manager = toolmgr.ToolManager(mock_app)
        result = await manager.generate_tools_for_anthropic(sample_tools)

        for tool_schema in result:
            assert 'name' in tool_schema
            assert 'description' in tool_schema
            assert 'input_schema' in tool_schema


class TestToolManagerExecuteFuncCall:
    """Tests for execute_func_call method."""

    @pytest.fixture
    def mock_app_with_loaders(self):
        """Create mock app with mock tool loaders."""
        mock_app = Mock()
        mock_app.logger = Mock()

        # Create mock plugin loader
        mock_plugin_loader = Mock()
        mock_plugin_loader.has_tool = AsyncMock(return_value=False)
        mock_plugin_loader.invoke_tool = AsyncMock(return_value='plugin_result')
        mock_plugin_loader.initialize = AsyncMock()
        mock_plugin_loader.shutdown = AsyncMock()

        # Create mock MCP loader
        mock_mcp_loader = Mock()
        mock_mcp_loader.has_tool = AsyncMock(return_value=False)
        mock_mcp_loader.invoke_tool = AsyncMock(return_value='mcp_result')
        mock_mcp_loader.initialize = AsyncMock()
        mock_mcp_loader.shutdown = AsyncMock()

        return mock_app, mock_plugin_loader, mock_mcp_loader

    @pytest.fixture
    def sample_query(self):
        """Create sample query for testing."""
        query = Mock(spec=pipeline_query.Query)
        return query

    @pytest.mark.asyncio
    async def test_execute_calls_plugin_loader_when_has_tool(
        self, mock_app_with_loaders, sample_query
    ):
        """Test that execute_func_call uses plugin loader when tool exists there."""
        toolmgr = get_toolmgr_module()

        mock_app, mock_plugin_loader, mock_mcp_loader = mock_app_with_loaders
        mock_plugin_loader.has_tool = AsyncMock(return_value=True)

        manager = toolmgr.ToolManager(mock_app)
        manager.plugin_tool_loader = mock_plugin_loader
        manager.mcp_tool_loader = mock_mcp_loader

        result = await manager.execute_func_call(
            'test_tool',
            {'param': 'value'},
            sample_query
        )

        assert result == 'plugin_result'
        mock_plugin_loader.invoke_tool.assert_called_once_with(
            'test_tool', {'param': 'value'}, sample_query
        )
        # MCP loader should not be called
        mock_mcp_loader.invoke_tool.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_calls_mcp_loader_when_plugin_not_found(
        self, mock_app_with_loaders, sample_query
    ):
        """Test that execute_func_call uses MCP loader when plugin doesn't have tool."""
        toolmgr = get_toolmgr_module()

        mock_app, mock_plugin_loader, mock_mcp_loader = mock_app_with_loaders
        mock_plugin_loader.has_tool = AsyncMock(return_value=False)
        mock_mcp_loader.has_tool = AsyncMock(return_value=True)

        manager = toolmgr.ToolManager(mock_app)
        manager.plugin_tool_loader = mock_plugin_loader
        manager.mcp_tool_loader = mock_mcp_loader

        result = await manager.execute_func_call(
            'test_tool',
            {'param': 'value'},
            sample_query
        )

        assert result == 'mcp_result'
        mock_mcp_loader.invoke_tool.assert_called_once_with(
            'test_tool', {'param': 'value'}, sample_query
        )

    @pytest.mark.asyncio
    async def test_execute_raises_when_tool_not_found(
        self, mock_app_with_loaders, sample_query
    ):
        """Test that execute_func_call raises ValueError when tool not found."""
        toolmgr = get_toolmgr_module()

        mock_app, mock_plugin_loader, mock_mcp_loader = mock_app_with_loaders
        mock_plugin_loader.has_tool = AsyncMock(return_value=False)
        mock_mcp_loader.has_tool = AsyncMock(return_value=False)

        manager = toolmgr.ToolManager(mock_app)
        manager.plugin_tool_loader = mock_plugin_loader
        manager.mcp_tool_loader = mock_mcp_loader

        with pytest.raises(ValueError, match='未找到工具'):
            await manager.execute_func_call(
                'unknown_tool',
                {},
                sample_query
            )

    @pytest.mark.asyncio
    async def test_plugin_loader_checked_first(
        self, mock_app_with_loaders, sample_query
    ):
        """Test that plugin loader is checked before MCP loader."""
        toolmgr = get_toolmgr_module()

        mock_app, mock_plugin_loader, mock_mcp_loader = mock_app_with_loaders
        # Both loaders have the tool, but plugin should be used
        mock_plugin_loader.has_tool = AsyncMock(return_value=True)
        mock_mcp_loader.has_tool = AsyncMock(return_value=True)

        manager = toolmgr.ToolManager(mock_app)
        manager.plugin_tool_loader = mock_plugin_loader
        manager.mcp_tool_loader = mock_mcp_loader

        await manager.execute_func_call('test_tool', {}, sample_query)

        # Plugin loader should be invoked, MCP should not
        mock_plugin_loader.invoke_tool.assert_called_once()
        mock_mcp_loader.invoke_tool.assert_not_called()


class TestToolManagerShutdown:
    """Tests for shutdown method."""

    @pytest.mark.asyncio
    async def test_shutdown_calls_loader_shutdown(self):
        """Test that shutdown calls shutdown on both loaders."""
        toolmgr = get_toolmgr_module()

        mock_app = Mock()
        mock_plugin_loader = Mock()
        mock_plugin_loader.shutdown = AsyncMock()
        mock_mcp_loader = Mock()
        mock_mcp_loader.shutdown = AsyncMock()

        manager = toolmgr.ToolManager(mock_app)
        manager.plugin_tool_loader = mock_plugin_loader
        manager.mcp_tool_loader = mock_mcp_loader

        await manager.shutdown()

        mock_plugin_loader.shutdown.assert_called_once()
        mock_mcp_loader.shutdown.assert_called_once()