from __future__ import annotations

import abc
import typing

from . import app


preregistered_stages: dict[str, typing.Type[BootingStage]] = {}
"""Pre-registered request processing stages. All request processing stage classes are registered in this dictionary during initialization.

Currently not supported for extension
"""


def stage_class(name: str):
    def decorator(cls: typing.Type[BootingStage]) -> typing.Type[BootingStage]:
        preregistered_stages[name] = cls
        return cls

    return decorator


class BootingStage(abc.ABC):
    """Booting stage"""

    name: str = None

    @abc.abstractmethod
    async def run(self, ap: app.Application):
        """Run"""
        pass
