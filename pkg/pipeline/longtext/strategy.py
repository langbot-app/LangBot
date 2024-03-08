from __future__ import annotations
import abc
import typing

import mirai
from mirai.models.message import MessageComponent

from ...core import app
from ...core import entities as core_entities


preregistered_strategies: list[typing.Type[LongTextStrategy]] = []


def strategy_class(
    name: str
) -> typing.Callable[[typing.Type[LongTextStrategy]], typing.Type[LongTextStrategy]]:
    def decorator(cls: typing.Type[LongTextStrategy]) -> typing.Type[LongTextStrategy]:
        assert issubclass(cls, LongTextStrategy)

        cls.name = name

        preregistered_strategies.append(cls)

        return cls

    return decorator


class LongTextStrategy(metaclass=abc.ABCMeta):
    """长文本处理策略抽象类
    """

    name: str

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap
    
    async def initialize(self):
        pass
    
    @abc.abstractmethod
    async def process(self, message: str, query: core_entities.Query) -> list[MessageComponent]:
        return []
