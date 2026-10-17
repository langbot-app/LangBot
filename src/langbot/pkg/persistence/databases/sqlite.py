from __future__ import annotations

import sqlalchemy
import sqlalchemy.ext.asyncio as sqlalchemy_asyncio

from .. import database


@database.manager_class('sqlite')
class SQLiteDatabaseManager(database.BaseDatabaseManager):
    """SQLite database manager"""

    async def initialize(self) -> None:
        db_file_path = self.ap.instance_config.data.get('database', {}).get('sqlite', {}).get('path', 'data/langbot.db')
        engine_url = f'sqlite+aiosqlite:///{db_file_path}'
        self.engine = sqlalchemy_asyncio.create_async_engine(engine_url)
        # Reader transactions must not block independent plugin callback commits.
        # Configure the persistent journal before serving requests, not per write.
        async with self.engine.connect() as connection:
            await connection.execute(sqlalchemy.text('PRAGMA journal_mode=WAL'))
            await connection.commit()
