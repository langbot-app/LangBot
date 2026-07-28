from __future__ import annotations

import json

import sqlalchemy.ext.asyncio as sqlalchemy_asyncio

from .. import database


async def _register_json_codecs(pg_conn) -> None:
    """Register asyncpg type codecs for JSON / JSONB so values come back as
    Python ``dict`` / ``list`` instead of raw ``str``.
    """
    await pg_conn.set_type_codec(
        'json',
        encoder=json.dumps,
        decoder=json.loads,
        schema='pg_catalog',
        format='text',
    )
    await pg_conn.set_type_codec(
        'jsonb',
        encoder=json.dumps,
        decoder=json.loads,
        schema='pg_catalog',
        format='text',
    )


def _patch_asyncpg_dialect() -> None:
    """Wrap ``AsyncAdapt_asyncpg_dbapi.connect`` so that every new
    asyncpg-backed SQLAlchemy connection gets our JSON codecs installed
    eagerly, via the wrapper's ``run_async`` hook.
    """
    from sqlalchemy.dialects.postgresql.asyncpg import AsyncAdapt_asyncpg_dbapi

    _orig = AsyncAdapt_asyncpg_dbapi.connect

    def _patched(self, *args, **kwargs):
        wrapper = _orig(self, *args, **kwargs)

        # `AsyncAdapt_asyncpg_connection.run_async(fn)` invokes `fn(conn)`
        # where `conn` is the real asyncpg.Connection. The hook must accept
        # that argument; some SQLAlchemy versions forward it positionally,
        # others don't, so we tolerate both.
        async def _init(conn=None):
            pg = conn
            if pg is None:
                adapt = wrapper.connection
                pg = adapt._connection if hasattr(adapt, '_connection') else adapt
            await _register_json_codecs(pg)

        wrapper.run_async(_init)
        return wrapper

    AsyncAdapt_asyncpg_dbapi.connect = _patched


# Apply the patch at module import time so subsequent engine creation
# inherits the codec registration.
_patch_asyncpg_dialect()


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
