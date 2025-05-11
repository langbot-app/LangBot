from __future__ import annotations

import abc
import typing

from . import app


preregistered_stages: dict[str, typing.Type[BootingStage]] = {}
"""预注册的请求处理阶段。在初始化时，所有请求处理阶段类会被注册到此字典中。

当前阶段暂不支持扩展
"""


def stage_class(name: str):
    def decorator(cls: typing.Type[BootingStage]) -> typing.Type[BootingStage]:
        preregistered_stages[name] = cls
        return cls

    return decorator


class BootingStage(abc.ABC):
    """启动阶段"""

    name: str = None

    @abc.abstractmethod
    async def run(self, ap: app.Application):
        """启动"""
        pass
