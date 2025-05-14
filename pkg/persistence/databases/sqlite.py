from __future__ import annotations

import sqlalchemy.ext.asyncio as sqlalchemy_asyncio

from .. import database


@database.manager_class('sqlite')
class SQLiteDatabaseManager(database.BaseDatabaseManager):
    """SQLite 数据库管理类"""

    async def initialize(self) -> None:
        sqlite_path = 'data/langbot.db'
        self.engine = sqlalchemy_asyncio.create_async_engine(f'sqlite+aiosqlite:///{sqlite_path}')
