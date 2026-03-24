from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import langbot_plugin.api.entities.builtin.resource.tool as resource_tool

from langbot.pkg.provider.tools.loaders.native import NativeToolLoader
from langbot.pkg.provider.tools.toolmgr import ToolManager


class StubLoader:
    def __init__(self, tools: list[resource_tool.LLMTool] | None = None, invoke_result=None):
        self._tools = tools or []
        self._invoke_result = invoke_result

    async def get_tools(self, *_args, **_kwargs):
        return self._tools

    async def has_tool(self, name: str) -> bool:
        return any(tool.name == name for tool in self._tools)

    async def invoke_tool(self, name: str, parameters: dict, query):
        return self._invoke_result(name, parameters, query) if callable(self._invoke_result) else self._invoke_result

    async def shutdown(self):
        return None


def make_tool(name: str) -> resource_tool.LLMTool:
    return resource_tool.LLMTool(
        name=name,
        human_desc=name,
        description=name,
        parameters={'type': 'object', 'properties': {}},
        func=lambda parameters: parameters,
    )


@pytest.mark.asyncio
async def test_tool_manager_lists_native_tools_first():
    manager = ToolManager(SimpleNamespace())
    manager.native_tool_loader = StubLoader([make_tool('sandbox_exec')])
    manager.plugin_tool_loader = StubLoader([make_tool('plugin_tool')])
    manager.mcp_tool_loader = StubLoader([make_tool('mcp_tool')])

    tools = await manager.get_all_tools()

    assert [tool.name for tool in tools] == ['sandbox_exec', 'plugin_tool', 'mcp_tool']


@pytest.mark.asyncio
async def test_tool_manager_routes_native_tool_calls():
    app = SimpleNamespace()
    manager = ToolManager(app)
    manager.native_tool_loader = StubLoader([make_tool('sandbox_exec')], invoke_result={'backend': 'fake'})
    manager.plugin_tool_loader = StubLoader([make_tool('plugin_tool')])
    manager.mcp_tool_loader = StubLoader([make_tool('mcp_tool')])

    result = await manager.execute_func_call('sandbox_exec', {'cmd': 'pwd'}, query=Mock())

    assert result == {'backend': 'fake'}


@pytest.mark.asyncio
async def test_native_tool_loader_hides_sandbox_exec_when_box_unavailable():
    loader = NativeToolLoader(SimpleNamespace(box_service=SimpleNamespace(available=False)))

    assert await loader.get_tools() == []
    assert await loader.has_tool('sandbox_exec') is False


@pytest.mark.asyncio
async def test_native_tool_loader_exposes_sandbox_exec_when_box_available():
    loader = NativeToolLoader(SimpleNamespace(box_service=SimpleNamespace(available=True)))

    tools = await loader.get_tools()

    assert [tool.name for tool in tools] == ['sandbox_exec']
    assert await loader.has_tool('sandbox_exec') is True
