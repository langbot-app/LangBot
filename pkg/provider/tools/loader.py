from __future__ import annotations

import abc
import typing

from ...core import app, entities as core_entities
from . import entities as tools_entities


preregistered_loaders: list[typing.Type[ToolLoader]] = []


def loader_class(name: str):
    """注册一个工具加载器"""

    def decorator(cls: typing.Type[ToolLoader]) -> typing.Type[ToolLoader]:
        cls.name = name
        preregistered_loaders.append(cls)
        return cls

    return decorator


class ToolLoader(abc.ABC):
    """工具加载器"""

    name: str = None

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        pass

    @abc.abstractmethod
    async def get_tools(self, enabled: bool = True) -> list[tools_entities.LLMFunction]:
        """获取所有工具"""
        pass

    @abc.abstractmethod
    async def has_tool(self, name: str) -> bool:
        """检查工具是否存在"""
        pass

    @abc.abstractmethod
    async def invoke_tool(self, query: core_entities.Query, name: str, parameters: dict) -> typing.Any:
        """执行工具调用"""
        pass

    @abc.abstractmethod
    async def shutdown(self):
        """关闭工具"""
        pass
