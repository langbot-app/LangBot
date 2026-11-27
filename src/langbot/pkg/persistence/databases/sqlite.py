from __future__ import annotations

import sqlalchemy
import sqlalchemy.ext.asyncio as sqlalchemy_asyncio

from .. import database
from ..write_admission import enable_sqlite_write_queue, enable_sqlite_write_timing


WAL_RETAIN_BYTES = 64 * 1024 * 1024
BUSY_TIMEOUT_MS = 30_000


def _configure_connection(dbapi_connection, _connection_record):
    # This limit applies when a WAL resets, not while a transaction or reader
    # still needs its frames. Keep SQLite's automatic checkpoint policy.
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute(f'PRAGMA busy_timeout={BUSY_TIMEOUT_MS}')
        cursor.execute(f'PRAGMA journal_size_limit={WAL_RETAIN_BYTES}')
    finally:
        cursor.close()


@database.manager_class('sqlite')
class SQLiteDatabaseManager(database.BaseDatabaseManager):
    """SQLite database manager"""

    async def initialize(self) -> None:
        config = self.ap.instance_config.data.get('database', {}).get('sqlite', {})
        db_file_path = config.get('path', 'data/langbot.db')
        engine_url = f'sqlite+aiosqlite:///{db_file_path}'
        self.engine = sqlalchemy_asyncio.create_async_engine(engine_url)
        mode = config.get('experimental_write_queue', False)
        if mode is True or mode == 'artifact_ledger':
            enable_sqlite_write_queue(self.engine, monitoring=mode is True)
        if config.get('experimental_write_timing') is True:
            enable_sqlite_write_timing(self.engine)
        sqlalchemy.event.listen(self.engine.sync_engine, 'connect', _configure_connection)
        # Reader transactions must not block independent plugin callback commits.
        # Configure the persistent journal before serving requests, not per write.
        async with self.engine.connect() as connection:
            # Fresh files can adopt the format without rebuilding existing data.
            await connection.execute(sqlalchemy.text('PRAGMA auto_vacuum=INCREMENTAL'))
            await connection.execute(sqlalchemy.text('PRAGMA journal_mode=WAL'))
            await connection.commit()
