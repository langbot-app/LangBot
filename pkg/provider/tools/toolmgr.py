from __future__ import annotations

import typing

from ...core import app
from . import loader as tools_loader
from ...utils import importutil
from . import loaders
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool

importutil.import_modules_in_pkg(loaders)


class ToolManager:
    """LLM工具管理器"""

    ap: app.Application

    loaders: list[tools_loader.ToolLoader]

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.all_functions = []
        self.loaders = []

    async def initialize(self):
        for loader_cls in tools_loader.preregistered_loaders:
            loader_inst = loader_cls(self.ap)
            await loader_inst.initialize()
            self.loaders.append(loader_inst)

    async def get_all_tools(self, bound_plugins: list[str] | None = None) -> list[resource_tool.LLMTool]:
        """获取所有函数"""
        all_functions: list[resource_tool.LLMTool] = []

        for loader in self.loaders:
            all_functions.extend(await loader.get_tools(bound_plugins))

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

    async def execute_func_call(self, name: str, parameters: dict) -> typing.Any:
        """执行函数调用"""

        for loader in self.loaders:
            if await loader.has_tool(name):
                return await loader.invoke_tool(name, parameters)
        else:
            raise ValueError(f'未找到工具: {name}')

    async def shutdown(self):
        """关闭所有工具"""
        for loader in self.loaders:
            await loader.shutdown()
