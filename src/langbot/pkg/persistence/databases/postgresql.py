from __future__ import annotations

import sqlalchemy
import sqlalchemy.ext.asyncio as sqlalchemy_asyncio

from .. import database
from ..postgresql_url import normalize_asyncpg_url


@database.manager_class('postgresql')
class PostgreSQLDatabaseManager(database.BaseDatabaseManager):
    """PostgreSQL database manager"""

    @staticmethod
    def _pool_integer(
        config: dict,
        name: str,
        default: int,
        *,
        minimum: int,
    ) -> int:
        value = config.get(name, default)
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            comparator = 'non-negative' if minimum == 0 else 'positive'
            raise ValueError(f'database.postgresql.{name} must be a {comparator} integer')
        return value

    async def initialize(self) -> None:
        postgresql_config = self.ap.instance_config.data.get('database', {}).get('postgresql', {})
        if not isinstance(postgresql_config, dict):
            raise ValueError('database.postgresql must be an object')
        if self.url_override is not None:
            engine_url = self.url_override
        else:
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
        self.engine = sqlalchemy_asyncio.create_async_engine(
            engine_url,
            pool_size=self._pool_integer(
                postgresql_config,
                'pool_size',
                10,
                minimum=1,
            ),
            max_overflow=self._pool_integer(
                postgresql_config,
                'max_overflow',
                10,
                minimum=0,
            ),
            pool_timeout=self._pool_integer(
                postgresql_config,
                'pool_timeout_seconds',
                30,
                minimum=1,
            ),
            pool_recycle=self._pool_integer(
                postgresql_config,
                'pool_recycle_seconds',
                1800,
                minimum=1,
            ),
            pool_pre_ping=True,
        )
