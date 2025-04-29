from __future__ import annotations

import abc

from ..core import app
from . import context


class PluginLoader(metaclass=abc.ABCMeta):
    """插件加载器抽象类"""

    ap: app.Application

    plugins: list[context.RuntimeContainer]

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.plugins = []

    async def initialize(self):
        pass

    @abc.abstractmethod
    async def load_plugins(self):
        pass
