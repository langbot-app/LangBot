from __future__ import annotations

import typing
from typing import TYPE_CHECKING

import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
from langbot_plugin.api.entities.events import pipeline_query

from .errors import ToolNotFoundError

if TYPE_CHECKING:
    from ...core import app
    from langbot.pkg.provider.tools.loaders import (
        mcp as mcp_loader,
        native as native_loader,
        plugin as plugin_loader,
        skill_authoring as skill_authoring_loader,
    )


class ToolManager:
    """LLM工具管理器"""

    ap: app.Application

    native_tool_loader: native_loader.NativeToolLoader
    plugin_tool_loader: plugin_loader.PluginToolLoader
    mcp_tool_loader: mcp_loader.MCPLoader
    skill_tool_loader: skill_authoring_loader.SkillToolLoader

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        from langbot.pkg.utils import importutil
        from langbot.pkg.provider.tools import loaders
        from langbot.pkg.provider.tools.loaders import (
            mcp as mcp_loader,
            native as native_loader,
            plugin as plugin_loader,
            skill_authoring as skill_authoring_loader,
        )

        importutil.import_modules_in_pkg(loaders)

        self.native_tool_loader = native_loader.NativeToolLoader(self.ap)
        await self.native_tool_loader.initialize()

        self.plugin_tool_loader = plugin_loader.PluginToolLoader(self.ap)
        await self.plugin_tool_loader.initialize()
        self.mcp_tool_loader = mcp_loader.MCPLoader(self.ap)
        await self.mcp_tool_loader.initialize()
        self.skill_tool_loader = skill_authoring_loader.SkillToolLoader(self.ap)
        await self.skill_tool_loader.initialize()

    async def get_all_tools(
        self,
        bound_plugins: list[str] | None = None,
        bound_mcp_servers: list[str] | None = None,
        include_skill_authoring: bool = False,
    ) -> list[resource_tool.LLMTool]:
        all_functions: list[resource_tool.LLMTool] = []

        all_functions.extend(await self.native_tool_loader.get_tools())
        if include_skill_authoring:
            all_functions.extend(await self.skill_tool_loader.get_tools())
        all_functions.extend(await self.plugin_tool_loader.get_tools(bound_plugins))
        all_functions.extend(await self.mcp_tool_loader.get_tools(bound_mcp_servers))

        return all_functions

    async def get_tool_by_name(self, name: str) -> resource_tool.LLMTool | None:
        """Get tool by name from any active loader.

        Args:
            name: Tool name.

        Returns:
            LLMTool if found, None otherwise
        """
        for tool_loader in (
            self.native_tool_loader,
            self.plugin_tool_loader,
            self.mcp_tool_loader,
            self.skill_tool_loader,
        ):
            tool = await self._get_tool_from_loader(tool_loader, name)
            if tool:
                return tool

        return None

    async def _get_tool_from_loader(self, tool_loader: typing.Any, name: str) -> resource_tool.LLMTool | None:
        if hasattr(tool_loader, '_get_tool'):
            return await tool_loader._get_tool(name)

        for tool in await tool_loader.get_tools():
            if tool.name == name:
                return tool

        return None

    async def generate_tools_for_openai(self, use_funcs: list[resource_tool.LLMTool]) -> list:
        tools = []

        for function in use_funcs:
            function_schema = {
                'type': 'function',
                'function': {
                    'name': function.name,
                    'description': function.description,
                    'parameters': function.parameters,
                },
            }
            tools.append(function_schema)

        return tools

    async def generate_tools_for_anthropic(self, use_funcs: list[resource_tool.LLMTool]) -> list:
        tools = []

        for function in use_funcs:
            function_schema = {
                'name': function.name,
                'description': function.description,
                'input_schema': function.parameters,
            }
            tools.append(function_schema)

        return tools

    async def execute_func_call(self, name: str, parameters: dict, query: pipeline_query.Query | None) -> typing.Any:
        """Execute a tool call through the active tool loaders."""
        from langbot.pkg.telemetry import features as telemetry_features

        if await self.native_tool_loader.has_tool(name):
            telemetry_features.increment(query, 'tool_calls', 'native')
            return await self.native_tool_loader.invoke_tool(name, parameters, query)
        if await self.plugin_tool_loader.has_tool(name):
            telemetry_features.increment(query, 'tool_calls', 'plugin')
            return await self.plugin_tool_loader.invoke_tool(name, parameters, query)
        if await self.mcp_tool_loader.has_tool(name):
            telemetry_features.increment(query, 'tool_calls', 'mcp')
            return await self.mcp_tool_loader.invoke_tool(name, parameters, query)
        if await self.skill_tool_loader.has_tool(name):
            telemetry_features.increment(query, 'tool_calls', 'skill')
            return await self.skill_tool_loader.invoke_tool(name, parameters, query)
        raise ToolNotFoundError(name)

    async def shutdown(self):
        await self.native_tool_loader.shutdown()
        await self.plugin_tool_loader.shutdown()
        await self.mcp_tool_loader.shutdown()
        await self.skill_tool_loader.shutdown()
