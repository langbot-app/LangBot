from __future__ import annotations
import abc

from ...core import app
from . import entities


class PromptLoader(metaclass=abc.ABCMeta):
    """Prompt加载器抽象类
    """

    ap: app.Application

    prompts: list[entities.Prompt]

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.prompts = []

    async def initialize(self):
        pass

    @abc.abstractmethod
    async def load(self):
        """加载Prompt
        """
        raise NotImplementedError

    def get_prompts(self) -> list[entities.Prompt]:
        """获取Prompt列表
        """
        return self.prompts
