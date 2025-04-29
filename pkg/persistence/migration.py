from __future__ import annotations

import typing
import abc

from ..core import app


preregistered_db_migrations: list[typing.Type[DBMigration]] = []


def migration_class(number: int):
    """迁移类装饰器"""

    def wrapper(cls: typing.Type[DBMigration]) -> typing.Type[DBMigration]:
        cls.number = number
        preregistered_db_migrations.append(cls)
        return cls

    return wrapper


class DBMigration(abc.ABC):
    """数据库迁移"""

    number: int
    """迁移号"""

    def __init__(self, ap: app.Application):
        self.ap = ap

    @abc.abstractmethod
    async def upgrade(self):
        """升级"""
        pass

    @abc.abstractmethod
    async def downgrade(self):
        """降级"""
        pass
