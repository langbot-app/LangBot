from __future__ import annotations

import typing

from ...core import app, entities as core_entities
from . import entities


class ToolManager:
    """LLM工具管理器
    """

    ap: app.Application
    
    def __init__(self, ap: app.Application):
        self.ap = ap
        self.all_functions = []

    async def initialize(self):
        pass

    async def get_function(self, name: str) -> entities.LLMFunction:
        """获取函数
        """
        for function in await self.get_all_functions():
            if function.name == name:
                return function
        return None
    
    async def get_all_functions(self) -> list[entities.LLMFunction]:
        """获取所有函数
        """
        all_functions: list[entities.LLMFunction] = []
    
        for plugin in self.ap.plugin_mgr.plugins:
            all_functions.extend(plugin.content_functions)
        
        return all_functions

    async def generate_tools_for_openai(self, conversation: core_entities.Conversation) -> str:
        """生成函数列表
        """
        tools = []

        for function in conversation.use_funcs:
            if function.enable:
                function_schema = {
                    "type": "function",
                    "function": {
                        "name": function.name,
                        "description": function.description,
                        "parameters": function.parameters
                    }
                }
                tools.append(function_schema)

        return tools

    async def execute_func_call(
        self,
        query: core_entities.Query,
        name: str,
        parameters: dict
    ) -> typing.Any:
        """执行函数调用
        """

        # return "i'm not sure for the args "+str(parameters)

        function = await self.get_function(name)
        if function is None:
            return None
        
        parameters = parameters.copy()

        parameters = {
            "query": query,
            **parameters
        }
        
        return await function.func(**parameters)
