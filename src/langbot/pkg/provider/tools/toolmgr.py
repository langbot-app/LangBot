from __future__ import annotations

import typing
from typing import TYPE_CHECKING

import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
from langbot_plugin.api.entities.events import pipeline_query

if TYPE_CHECKING:
    from ...core import app
    from langbot.pkg.provider.tools.loaders import (
        mcp as mcp_loader,
        native as native_loader,
        plugin as plugin_loader,
        skill as skill_loader,
        skill_authoring as skill_authoring_loader,
    )


class ToolManager:
    """LLM工具管理器"""

    ap: app.Application

    native_tool_loader: native_loader.NativeToolLoader
    plugin_tool_loader: plugin_loader.PluginToolLoader
    mcp_tool_loader: mcp_loader.MCPLoader
    skill_tool_loader: skill_loader.SkillToolLoader
    skill_authoring_tool_loader: skill_authoring_loader.SkillAuthoringToolLoader

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        from langbot.pkg.utils import importutil
        from langbot.pkg.provider.tools import loaders
        from langbot.pkg.provider.tools.loaders import (
            mcp as mcp_loader,
            native as native_loader,
            plugin as plugin_loader,
            skill as skill_loader,
            skill_authoring as skill_authoring_loader,
        )

        importutil.import_modules_in_pkg(loaders)

        self.native_tool_loader = native_loader.NativeToolLoader(self.ap)
        await self.native_tool_loader.initialize()
        self.plugin_tool_loader = plugin_loader.PluginToolLoader(self.ap)
        await self.plugin_tool_loader.initialize()
        self.mcp_tool_loader = mcp_loader.MCPLoader(self.ap)
        await self.mcp_tool_loader.initialize()
        self.skill_tool_loader = skill_loader.SkillToolLoader(self.ap)
        await self.skill_tool_loader.initialize()
        self.skill_authoring_tool_loader = skill_authoring_loader.SkillAuthoringToolLoader(self.ap)
        await self.skill_authoring_tool_loader.initialize()

    async def get_all_tools(
        self,
        bound_plugins: list[str] | None = None,
        bound_mcp_servers: list[str] | None = None,
        include_skill_authoring: bool = False,
    ) -> list[resource_tool.LLMTool]:
        """获取所有函数"""
        all_functions: list[resource_tool.LLMTool] = []

        all_functions.extend(await self.native_tool_loader.get_tools())
        if include_skill_authoring:
            all_functions.extend(await self.skill_authoring_tool_loader.get_tools())
        all_functions.extend(await self.plugin_tool_loader.get_tools(bound_plugins))
        all_functions.extend(await self.mcp_tool_loader.get_tools(bound_mcp_servers))

        return all_functions

    async def generate_tools_for_openai(self, use_funcs: list[resource_tool.LLMTool]) -> list:
        """生成函数列表"""
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
        """为anthropic生成函数列表

        e.g.

        [
          {
            "name": "get_stock_price",
            "description": "Get the current stock price for a given ticker symbol.",
            "input_schema": {
              "type": "object",
              "properties": {
                "ticker": {
                  "type": "string",
                  "description": "The stock ticker symbol, e.g. AAPL for Apple Inc."
                }
              },
              "required": ["ticker"]
            }
          }
        ]
        """

        tools = []

        for function in use_funcs:
            function_schema = {
                'name': function.name,
                'description': function.description,
                'input_schema': function.parameters,
            }
            tools.append(function_schema)

        return tools

    async def execute_func_call(self, name: str, parameters: dict, query: pipeline_query.Query) -> typing.Any:
        """执行函数调用"""

        if await self.native_tool_loader.has_tool(name):
            return await self.native_tool_loader.invoke_tool(name, parameters, query)
        elif await self.plugin_tool_loader.has_tool(name):
            return await self.plugin_tool_loader.invoke_tool(name, parameters, query)
        elif await self.mcp_tool_loader.has_tool(name):
            return await self.mcp_tool_loader.invoke_tool(name, parameters, query)
        elif await self.skill_authoring_tool_loader.has_tool(name):
            return await self.skill_authoring_tool_loader.invoke_tool(name, parameters, query)
        elif self.skill_tool_loader.has_tool(name, query):
            return await self.skill_tool_loader.invoke_tool(name, parameters, query)
        else:
            raise ValueError(f'未找到工具: {name}')

    async def shutdown(self):
        """关闭所有工具"""
        await self.native_tool_loader.shutdown()
        await self.plugin_tool_loader.shutdown()
        await self.mcp_tool_loader.shutdown()
        await self.skill_authoring_tool_loader.shutdown()
        await self.skill_tool_loader.shutdown()
