from __future__ import annotations

import abc

import sqlalchemy.ext.asyncio as sqlalchemy_asyncio

from ..core import app


preregistered_managers: list[type[BaseDatabaseManager]] = []


def manager_class(name: str) -> None:
    """Register a database manager class"""

    def decorator(cls: type[BaseDatabaseManager]) -> type[BaseDatabaseManager]:
        cls.name = name
        preregistered_managers.append(cls)
        return cls

    return decorator


class BaseDatabaseManager(abc.ABC):
    """Base database manager class"""

    name: str

    ap: app.Application

    engine: sqlalchemy_asyncio.AsyncEngine

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    @abc.abstractmethod
    async def initialize(self) -> None:
        pass

    def get_engine(self) -> sqlalchemy_asyncio.AsyncEngine:
        return self.engine
