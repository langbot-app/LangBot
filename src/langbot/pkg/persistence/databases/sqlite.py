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
        self.engine = sqlalchemy_asyncio.create_async_engine(
            engine_url,
            connect_args={'timeout': 30},
            pool_pre_ping=True,
        )

        @sqlalchemy.event.listens_for(self.engine.sync_engine, 'connect')
        def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute('PRAGMA busy_timeout=30000')
                cursor.execute('PRAGMA journal_mode=WAL')
                cursor.execute('PRAGMA synchronous=NORMAL')
            finally:
                cursor.close()
