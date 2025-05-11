# 此模块已过时，请引入 pkg.plugin.context 中的 register, handler 和 llm_func 来注册插件、事件处理函数和内容函数
# 各个事件模型请从 pkg.plugin.events 引入
# 最早将于 v3.4 移除此模块

from __future__ import annotations

import typing

from .context import BasePlugin as Plugin
from .events import *


def register(
    name: str, description: str, version: str, author
) -> typing.Callable[[typing.Type[Plugin]], typing.Type[Plugin]]:
    pass


def on(
    event: typing.Type[BaseEventModel],
) -> typing.Callable[[typing.Callable], typing.Callable]:
    pass


def func(
    name: str = None,
) -> typing.Callable:
    pass
