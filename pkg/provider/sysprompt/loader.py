from __future__ import annotations
import abc
import typing

from ...core import app
from . import entities


preregistered_loaders: list[typing.Type[PromptLoader]] = []

def loader_class(name: str):

    def decorator(cls: typing.Type[PromptLoader]) -> typing.Type[PromptLoader]:
        cls.name = name
        preregistered_loaders.append(cls)
        return cls
    
    return decorator


class PromptLoader(metaclass=abc.ABCMeta):
    """Prompt加载器抽象类
    """
    name: str

    ap: app.Application

    prompts: list[entities.Prompt]

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.prompts = []

    async def initialize(self):
        pass

    @abc.abstractmethod
    async def load(self):
        """加载Prompt，存放到prompts列表中
        """
        raise NotImplementedError

    def get_prompts(self) -> list[entities.Prompt]:
        """获取Prompt列表
        """
        return self.prompts
