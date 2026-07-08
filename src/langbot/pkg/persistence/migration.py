from __future__ import annotations

import typing
import abc

from ..core import app


preregistered_db_migrations: list[typing.Type[DBMigration]] = []


def migration_class(number: int):
    """Migration class decorator"""

    def wrapper(cls: typing.Type[DBMigration]) -> typing.Type[DBMigration]:
        cls.number = number
        preregistered_db_migrations.append(cls)
        return cls

    return wrapper


class DBMigration(abc.ABC):
    """Database migration"""

    number: int
    """Migration number"""

    def __init__(self, ap: app.Application):
        self.ap = ap

    @abc.abstractmethod
    async def upgrade(self):
        """Upgrade"""
        pass

    @abc.abstractmethod
    async def downgrade(self):
        """Downgrade"""
        pass
