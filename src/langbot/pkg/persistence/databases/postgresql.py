from __future__ import annotations

import sqlalchemy.ext.asyncio as sqlalchemy_asyncio

from .. import database


@database.manager_class('postgresql')
class PostgreSQLDatabaseManager(database.BaseDatabaseManager):
    """PostgreSQL database manager"""

    async def initialize(self) -> None:
        postgresql_config = self.ap.instance_config.data.get('database', {}).get('postgresql', {})

        host = postgresql_config.get('host', '127.0.0.1')
        port = postgresql_config.get('port', 5432)
        user = postgresql_config.get('user', 'postgres')
        password = postgresql_config.get('password', 'postgres')
        database = postgresql_config.get('database', 'postgres')
        engine_url = f'postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}'
        self.engine = sqlalchemy_asyncio.create_async_engine(engine_url)
