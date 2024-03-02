from __future__ import annotations

import abc
import typing

from . import app


preregistered_stages: list[typing.Type[BootingStage]] = {}

def stage_class(
    name: str
):
    def decorator(cls: typing.Type[BootingStage]) -> typing.Type[BootingStage]:
        preregistered_stages[name] = cls
        return cls

    return decorator


class BootingStage(abc.ABC):
    """启动阶段
    """
    name: str = None

    @abc.abstractmethod
    async def run(self, ap: app.Application):
        """启动
        """
        pass
