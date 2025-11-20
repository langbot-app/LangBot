from __future__ import annotations

import typing
import abc

from ...core import app
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query

preregistered_truncators: list[typing.Type[Truncator]] = []


def truncator_class(
    name: str,
) -> typing.Callable[[typing.Type[Truncator]], typing.Type[Truncator]]:
    """截断器类装饰器

    Args:
        name (str): 截断器名称

    Returns:
        typing.Callable[[typing.Type[Truncator]], typing.Type[Truncator]]: 装饰器
    """

    def decorator(cls: typing.Type[Truncator]) -> typing.Type[Truncator]:
        assert issubclass(cls, Truncator)

        cls.name = name

        preregistered_truncators.append(cls)

        return cls

    return decorator


class Truncator(abc.ABC):
    """消息截断器基类"""

    name: str

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        pass

    @abc.abstractmethod
    async def truncate(self, query: pipeline_query.Query) -> pipeline_query.Query:
        """截断

        一般只需要操作query.messages，也可以扩展操作query.prompt, query.user_message。
        请勿操作其他字段。
        """
        pass
