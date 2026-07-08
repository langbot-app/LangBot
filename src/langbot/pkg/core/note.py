from __future__ import annotations

import abc
import typing

from . import app

preregistered_notes: list[typing.Type[LaunchNote]] = []


def note_class(name: str, number: int):
    """Register a launch information"""

    def decorator(cls: typing.Type[LaunchNote]) -> typing.Type[LaunchNote]:
        cls.name = name
        cls.number = number
        preregistered_notes.append(cls)
        return cls

    return decorator


class LaunchNote(abc.ABC):
    """Launch information"""

    name: str

    number: int

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    @abc.abstractmethod
    async def need_show(self) -> bool:
        """Determine if the current environment needs to display this launch information"""
        pass

    @abc.abstractmethod
    async def yield_note(self) -> typing.AsyncGenerator[typing.Tuple[str, int], None]:
        """Generate launch information"""
        pass
