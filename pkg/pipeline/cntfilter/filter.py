# 内容过滤器的抽象类
from __future__ import annotations
import abc
import typing

from ...core import app
from . import entities


preregistered_filters: list[typing.Type[ContentFilter]] = []


def filter_class(
    name: str
) -> typing.Callable[[typing.Type[ContentFilter]], typing.Type[ContentFilter]]:
    """内容过滤器类装饰器

    Args:
        name (str): 过滤器名称

    Returns:
        typing.Callable[[typing.Type[ContentFilter]], typing.Type[ContentFilter]]: 装饰器
    """
    def decorator(cls: typing.Type[ContentFilter]) -> typing.Type[ContentFilter]:
        assert issubclass(cls, ContentFilter)

        cls.name = name

        preregistered_filters.append(cls)

        return cls

    return decorator


class ContentFilter(metaclass=abc.ABCMeta):
    """内容过滤器抽象类"""

    name: str

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
