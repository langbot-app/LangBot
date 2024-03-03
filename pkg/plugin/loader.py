from __future__ import annotations
from abc import ABCMeta

import typing
import abc

from ..core import app
from . import context, events


class PluginLoader(metaclass=abc.ABCMeta):
    """插件加载器抽象类"""

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        pass

    @abc.abstractmethod
    async def load_plugins(self) -> list[context.RuntimeContainer]:
        pass

