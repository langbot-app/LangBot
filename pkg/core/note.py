from __future__ import annotations

import abc
import typing

from . import app

preregistered_notes: list[typing.Type[LaunchNote]] = []


def note_class(name: str, number: int):
    """注册一个启动信息"""

    def decorator(cls: typing.Type[LaunchNote]) -> typing.Type[LaunchNote]:
        cls.name = name
        cls.number = number
        preregistered_notes.append(cls)
        return cls

    return decorator


class LaunchNote(abc.ABC):
    """启动信息"""

    name: str

    number: int

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    @abc.abstractmethod
    async def need_show(self) -> bool:
        """判断当前环境是否需要显示此启动信息"""
        pass

    @abc.abstractmethod
    async def yield_note(self) -> typing.AsyncGenerator[typing.Tuple[str, int], None]:
        """生成启动信息"""
        pass
