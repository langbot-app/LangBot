from __future__ import annotations

import typing

from .context import BasePlugin as Plugin
from . import events

def register(
    name: str,
    description: str,
    version: str,
    author
) -> typing.Callable[[typing.Type[Plugin]], typing.Type[Plugin]]:
    pass


def on(
    event: typing.Type[events.BaseEventModel]
) -> typing.Callable[[typing.Callable], typing.Callable]:
    pass


def func(
    name: str=None,
) -> typing.Callable:
    pass
