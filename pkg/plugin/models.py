from __future__ import annotations

import typing

from .context import BasePlugin as Plugin
from .events import *

def register(
    name: str,
    description: str,
    version: str,
    author
) -> typing.Callable[[typing.Type[Plugin]], typing.Type[Plugin]]:
    pass


def on(
    event: typing.Type[BaseEventModel]
) -> typing.Callable[[typing.Callable], typing.Callable]:
    pass


def func(
    name: str=None,
) -> typing.Callable:
    pass


def handler(
    event: typing.Type[BaseEventModel]
) -> typing.Callable[[typing.Callable], typing.Callable]:
    pass


def llm_func(
    name: str=None,
) -> typing.Callable:
    pass