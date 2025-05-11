from __future__ import annotations
import abc
import typing


from ...core import app
from ...core import entities as core_entities
from ...platform.types import message as platform_message


preregistered_strategies: list[typing.Type[LongTextStrategy]] = []


def strategy_class(
    name: str,
) -> typing.Callable[[typing.Type[LongTextStrategy]], typing.Type[LongTextStrategy]]:
    """长文本处理策略类装饰器

    Args:
        name (str): 策略名称

    Returns:
        typing.Callable[[typing.Type[LongTextStrategy]], typing.Type[LongTextStrategy]]: 装饰器
    """

    def decorator(cls: typing.Type[LongTextStrategy]) -> typing.Type[LongTextStrategy]:
        assert issubclass(cls, LongTextStrategy)

        cls.name = name

        preregistered_strategies.append(cls)

        return cls

    return decorator


class LongTextStrategy(metaclass=abc.ABCMeta):
    """长文本处理策略抽象类"""

    name: str

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        pass

    @abc.abstractmethod
    async def process(self, message: str, query: core_entities.Query) -> list[platform_message.MessageComponent]:
        """处理长文本

        在 platform.json 中配置 long-text-process 字段，只要 文本长度超过了 threshold 就会调用此方法

        Args:
            message (str): 消息
            query (core_entities.Query): 此次请求的上下文对象

        Returns:
            list[platform_message.MessageComponent]: 转换后的 平台 消息组件列表
        """
        return []
