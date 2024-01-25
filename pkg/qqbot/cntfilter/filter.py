# 内容过滤器的抽象类
from __future__ import annotations
import abc

from ...boot import app
from . import entities


class ContentFilter(metaclass=abc.ABCMeta):

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    @property
    def enable_stages(self):
        """启用的阶段
        """
        return [
            entities.EnableStage.PRE,
            entities.EnableStage.POST
        ]

    async def initialize(self):
        """初始化过滤器
        """
        pass

    @abc.abstractmethod
    async def process(self, message: str) -> entities.FilterResult:
        """处理消息
        """
        raise NotImplementedError
