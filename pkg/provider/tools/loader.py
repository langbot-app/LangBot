from __future__ import annotations

import abc
import typing

from ...core import app
from . import entities as tools_entities


preregistered_loaders = []

def loader_class(name: str):
    """注册一个工具加载器
    """
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
    def get_tools(self) -> list[tools_entities.LLMFunction]:
        """获取所有工具"""
        pass
