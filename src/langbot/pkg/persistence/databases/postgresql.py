from __future__ import annotations

import sqlalchemy
import sqlalchemy.ext.asyncio as sqlalchemy_asyncio

from .. import database
from ..postgresql_url import normalize_asyncpg_url


@database.manager_class('postgresql')
class PostgreSQLDatabaseManager(database.BaseDatabaseManager):
    """PostgreSQL database manager"""

    async def initialize(self) -> None:
        if self.url_override is not None:
            engine_url = self.url_override
        else:
            postgresql_config = self.ap.instance_config.data.get('database', {}).get('postgresql', {})
            explicit_url = postgresql_config.get('url')
            if explicit_url:
                if not isinstance(explicit_url, str):
                    raise ValueError('database.postgresql.url must be a string')
                try:
                    engine_url = sqlalchemy.engine.make_url(explicit_url)
                except Exception:
                    raise ValueError('database.postgresql.url is invalid') from None
                try:
                    engine_url = normalize_asyncpg_url(engine_url)
                except ValueError:
                    raise ValueError('database.postgresql.url must use valid PostgreSQL asyncpg options') from None
            else:
                engine_url = sqlalchemy.URL.create(
                    'postgresql+asyncpg',
                    username=postgresql_config.get('user', 'postgres'),
                    password=postgresql_config.get('password', 'postgres'),
                    host=postgresql_config.get('host', '127.0.0.1'),
                    port=postgresql_config.get('port', 5432),
                    database=postgresql_config.get('database', 'postgres'),
                )
        self.engine = sqlalchemy_asyncio.create_async_engine(engine_url)
