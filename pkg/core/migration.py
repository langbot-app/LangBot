from __future__ import annotations

import abc
import typing

from . import app


preregistered_migrations: list[typing.Type[Migration]] = []
"""当前阶段暂不支持扩展"""


def migration_class(name: str, number: int):
    """注册一个迁移"""

    def decorator(cls: typing.Type[Migration]) -> typing.Type[Migration]:
        cls.name = name
        cls.number = number
        preregistered_migrations.append(cls)
        return cls

    return decorator


class Migration(abc.ABC):
    """一个版本的迁移"""

    name: str

    number: int

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    @abc.abstractmethod
    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        pass

    @abc.abstractmethod
    async def run(self):
        """执行迁移"""
        pass
