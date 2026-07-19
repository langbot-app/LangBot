from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.provider.tools.loaders.mcp import (
    MCP_TOOL_LIST_RESOURCES,
    MCP_TOOL_READ_RESOURCE,
    MCPLoader,
    MCPSessionStatus,
)
from langbot.pkg.provider.tools.loaders.plugin import PluginToolLoader
from langbot_plugin.api.entities.builtin.resource.tool import LLMTool


def make_tool(name: str) -> LLMTool:
    return LLMTool(
        name=name,
        human_desc=name,
        description=name,
        parameters={'type': 'object', 'properties': {}},
        func=lambda parameters: parameters,
    )


@pytest.mark.asyncio
async def test_two_mcp_servers_with_same_tool_route_to_authorized_server():
    tool = make_tool('shared_tool')
    first = SimpleNamespace(
        server_uuid='mcp-a',
        get_tools=Mock(return_value=[tool]),
        invoke_mcp_tool=AsyncMock(return_value='from-a'),
    )
    second = SimpleNamespace(
        server_uuid='mcp-b',
        get_tools=Mock(return_value=[tool]),
        invoke_mcp_tool=AsyncMock(return_value='from-b'),
    )
    loader = MCPLoader(SimpleNamespace(logger=Mock()))
    loader.sessions = {'first': first, 'second': second}
    query = SimpleNamespace(variables={})

    result = await loader.invoke_tool(
        'shared_tool',
        {'value': 1},
        query,
        source_id='mcp-b',
    )

    assert result == 'from-b'
    first.invoke_mcp_tool.assert_not_awaited()
    second.invoke_mcp_tool.assert_awaited_once_with(
        'shared_tool',
        {'value': 1},
        query=query,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('reserved_name', [MCP_TOOL_LIST_RESOURCES, MCP_TOOL_READ_RESOURCE])
async def test_reserved_name_routes_to_real_mcp_tool_when_source_id_is_present(reserved_name):
    real_tool = make_tool(reserved_name)
    session = SimpleNamespace(
        server_uuid='srv-real',
        get_tools=Mock(return_value=[real_tool]),
        invoke_mcp_tool=AsyncMock(return_value='real-result'),
    )
    loader = MCPLoader(SimpleNamespace(logger=Mock()))
    loader.sessions = {'real': session}
    query = SimpleNamespace(variables={})

    assert await loader.has_tool(reserved_name, source_id='srv-real') is True
    assert await loader.get_tool(reserved_name, source_id='srv-real') is real_tool
    result = await loader.invoke_tool(reserved_name, {}, query, source_id='srv-real')

    assert result == 'real-result'
    session.invoke_mcp_tool.assert_awaited_once_with(reserved_name, {}, query=query)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('reserved_name', 'invoke_method'),
    [
        (MCP_TOOL_LIST_RESOURCES, '_invoke_mcp_list_resources'),
        (MCP_TOOL_READ_RESOURCE, '_invoke_mcp_read_resource'),
    ],
)
async def test_reserved_name_uses_host_synthetic_tool_when_source_id_is_none(
    reserved_name,
    invoke_method,
):
    real_tool = make_tool(reserved_name)
    session = SimpleNamespace(
        server_uuid='srv-real',
        server_name='real',
        enable=True,
        status=MCPSessionStatus.CONNECTED,
        session=object(),
        get_tools=Mock(return_value=[real_tool]),
        has_resource_support=Mock(return_value=True),
        invoke_mcp_tool=AsyncMock(return_value='real-result'),
    )
    loader = MCPLoader(SimpleNamespace(logger=Mock()))
    loader.sessions = {'real': session}
    synthetic_invoke = AsyncMock(return_value='synthetic-result')
    setattr(loader, invoke_method, synthetic_invoke)
    query = SimpleNamespace(variables={})

    assert await loader.has_tool(reserved_name, source_id=None) is True
    tool = await loader.get_tool(reserved_name, source_id=None)
    result = await loader.invoke_tool(reserved_name, {}, query, source_id=None)

    assert tool is not None
    assert tool is not real_tool
    assert result == 'synthetic-result'
    synthetic_invoke.assert_awaited_once_with({}, query)
    session.invoke_mcp_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_two_plugins_with_same_tool_forward_only_authorized_plugin():
    manifest = SimpleNamespace(
        owner='authorized/plugin',
        metadata=SimpleNamespace(
            name='shared_tool',
            description=SimpleNamespace(en_US='Shared tool'),
        ),
        spec={
            'llm_prompt': 'Shared tool',
            'parameters': {'type': 'object', 'properties': {}},
        },
    )
    connector = SimpleNamespace(
        list_tools=AsyncMock(return_value=[manifest]),
        call_tool=AsyncMock(return_value='authorized-result'),
    )
    loader = PluginToolLoader(SimpleNamespace(plugin_connector=connector, logger=Mock()))
    query = SimpleNamespace(session=SimpleNamespace(), query_id=7)
    query.session.model_dump = Mock(return_value={})

    result = await loader.invoke_tool(
        'shared_tool',
        {},
        query,
        source_id='authorized/plugin',
    )

    assert result == 'authorized-result'
    connector.call_tool.assert_awaited_once_with(
        'shared_tool',
        {},
        session=query.session,
        query_id=7,
        bound_plugins=['authorized/plugin'],
    )
