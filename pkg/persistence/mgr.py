from __future__ import annotations

import asyncio
import datetime

import sqlalchemy.ext.asyncio as sqlalchemy_asyncio
import sqlalchemy

from . import database
from .entities import user, base
from ..core import app
from .databases import sqlite


class PersistenceManager:
    """持久化模块管理器"""

    ap: app.Application

    db: database.BaseDatabaseManager
    """数据库管理器"""

    meta: sqlalchemy.MetaData

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.meta = base.Base.metadata

    async def initialize(self):
        
        for manager in database.preregistered_managers:
            self.db = manager(self.ap)
            await self.db.initialize()

        await self.create_tables()

    async def create_tables(self):
        # TODO: 对扩展友好
        
        # 日志
        async with self.get_db_engine().connect() as conn:
            await conn.run_sync(self.meta.create_all)

            await conn.commit()

    async def execute_async(
        self,
        *args,
        **kwargs
    ) -> sqlalchemy.engine.cursor.CursorResult:
        async with self.get_db_engine().connect() as conn:
            result = await conn.execute(*args, **kwargs)
            await conn.commit()
            return result

    def get_db_engine(self) -> sqlalchemy_asyncio.AsyncEngine:
        return self.db.get_engine()
