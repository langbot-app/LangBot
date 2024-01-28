from __future__ import annotations

import typing

from ...core import app, entities as core_entities
from . import entities
from ..session import entities as session_entities


class ToolManager:
    """LLM工具管理器
    """

    ap: app.Application

    all_functions: list[entities.LLMFunction]
    
    def __init__(self, ap: app.Application):
        self.ap = ap
        self.all_functions = []

    async def initialize(self):
        pass

    def register_legacy_function(self, name: str, description: str, parameters: dict, func: callable):
        """注册函数
        """
        async def wrapper(query, **kwargs):
            return func(**kwargs)
        function = entities.LLMFunction(
            name=name,
            description=description,
            human_desc='',
            enable=True,
            parameters=parameters,
            func=wrapper
        )
        self.all_functions.append(function)

    async def register_function(self, function: entities.LLMFunction):
        """添加函数
        """
        self.all_functions.append(function)

    async def get_function(self, name: str) -> entities.LLMFunction:
        """获取函数
        """
        for function in self.all_functions:
            if function.name == name:
                return function
        return None
    
    async def get_all_functions(self) -> list[entities.LLMFunction]:
        """获取所有函数
        """
        return self.all_functions
    
    async def generate_tools_for_openai(self, conversation: session_entities.Conversation) -> str:
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
