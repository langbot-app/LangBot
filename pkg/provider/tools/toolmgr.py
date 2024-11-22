from __future__ import annotations

import typing
import traceback

from ...core import app, entities as core_entities
from . import entities
from ...plugin import context as plugin_context


class ToolManager:
    """LLM工具管理器"""

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.all_functions = []

    async def initialize(self):
        pass

    async def get_function_and_plugin(
        self, name: str
    ) -> typing.Tuple[entities.LLMFunction, plugin_context.BasePlugin]:
        """获取函数和插件实例"""
        for plugin in self.ap.plugin_mgr.plugins(
            enabled=True, status=plugin_context.RuntimeContainerStatus.INITIALIZED
        ):
            for function in plugin.content_functions:
                if function.name == name:
                    return function, plugin.plugin_inst
        return None, None

    async def get_all_functions(self, plugin_enabled: bool=None, plugin_status: plugin_context.RuntimeContainerStatus=None) -> list[entities.LLMFunction]:
        """获取所有函数"""
        all_functions: list[entities.LLMFunction] = []

        for plugin in self.ap.plugin_mgr.plugins(
            enabled=plugin_enabled, status=plugin_status
        ):
            all_functions.extend(plugin.content_functions)

        return all_functions

    async def generate_tools_for_openai(self, use_funcs: list[entities.LLMFunction]) -> list:
        """生成函数列表"""
        tools = []

        for function in use_funcs:
            function_schema = {
                "type": "function",
                "function": {
                    "name": function.name,
                    "description": function.description,
                    "parameters": function.parameters,
                },
            }
            tools.append(function_schema)

        return tools

    async def generate_tools_for_anthropic(
        self, use_funcs: list[entities.LLMFunction]
    ) -> list:
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
                "name": function.name,
                "description": function.description,
                "input_schema": function.parameters,
            }
            tools.append(function_schema)

        return tools

    async def execute_func_call(
        self, query: core_entities.Query, name: str, parameters: dict
    ) -> typing.Any:
        """执行函数调用"""

        try:

            function, plugin = await self.get_function_and_plugin(name)
            if function is None:
                return None

            parameters = parameters.copy()

            parameters = {"query": query, **parameters}

            return await function.func(plugin, **parameters)
        except Exception as e:
            self.ap.logger.error(f"执行函数 {name} 时发生错误: {e}")
            traceback.print_exc()
            return f"error occurred when executing function {name}: {e}"
        finally:
            plugin = None

            for p in self.ap.plugin_mgr.plugins():
                if function in p.content_functions:
                    plugin = p
                    break

            if plugin is not None:

                await self.ap.ctr_mgr.usage.post_function_record(
                    plugin={
                        "name": plugin.plugin_name,
                        "remote": plugin.plugin_source,
                        "version": plugin.plugin_version,
                        "author": plugin.plugin_author,
                    },
                    function_name=function.name,
                    function_description=function.description,
                )