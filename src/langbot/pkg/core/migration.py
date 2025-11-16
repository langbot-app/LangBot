from __future__ import annotations

import abc
import typing

from . import app


preregistered_migrations: list[typing.Type[Migration]] = []
"""Currently not supported for extension"""


def migration_class(name: str, number: int):
    """Register a migration"""

    def decorator(cls: typing.Type[Migration]) -> typing.Type[Migration]:
        cls.name = name
        cls.number = number
        preregistered_migrations.append(cls)
        return cls

    return decorator


class Migration(abc.ABC):
    """A version migration"""

    name: str

    number: int

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    @abc.abstractmethod
    async def need_migrate(self) -> bool:
        """Determine if the current environment needs to run this migration"""
        pass

    @abc.abstractmethod
    async def run(self):
        """Run migration"""
        pass
