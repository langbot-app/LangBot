from __future__ import annotations

import sqlalchemy
import sqlalchemy.ext.asyncio as sqlalchemy_asyncio

from .. import database
from ..postgresql_url import normalize_asyncpg_url


MAX_POOL_CONNECTIONS = 100
MAX_POOL_TIMEOUT_SECONDS = 300
MAX_POOL_RECYCLE_SECONDS = 86_400
MAX_STATEMENT_TIMEOUT_MS = 300_000
MAX_LOCK_TIMEOUT_MS = 60_000
MAX_IDLE_TRANSACTION_TIMEOUT_MS = 300_000


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
        maximum: int,
    ) -> int:
        value = config.get(name, default)
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            comparator = 'non-negative' if minimum == 0 else 'positive'
            raise ValueError(f'database.postgresql.{name} must be a {comparator} integer no greater than {maximum}')
        return value

    async def initialize(self) -> None:
        self._pool_timeouts_total = 0
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
        self.pool_size = self._pool_integer(
            postgresql_config,
            'pool_size',
            10,
            minimum=1,
            maximum=MAX_POOL_CONNECTIONS,
        )
        self.max_overflow = self._pool_integer(
            postgresql_config,
            'max_overflow',
            10,
            minimum=0,
            maximum=MAX_POOL_CONNECTIONS,
        )
        if self.pool_size + self.max_overflow > MAX_POOL_CONNECTIONS:
            raise ValueError(f'database.postgresql pool_size + max_overflow must not exceed {MAX_POOL_CONNECTIONS}')
        self.pool_timeout_seconds = self._pool_integer(
            postgresql_config,
            'pool_timeout_seconds',
            30,
            minimum=1,
            maximum=MAX_POOL_TIMEOUT_SECONDS,
        )
        self.pool_recycle_seconds = self._pool_integer(
            postgresql_config,
            'pool_recycle_seconds',
            1800,
            minimum=1,
            maximum=MAX_POOL_RECYCLE_SECONDS,
        )
        connect_args = {}
        self.statement_timeout_ms = 0
        self.lock_timeout_ms = 0
        self.idle_transaction_timeout_ms = 0
        if self.persistence_mode == 'cloud_runtime':
            self.statement_timeout_ms = self._pool_integer(
                postgresql_config,
                'statement_timeout_ms',
                60_000,
                minimum=1,
                maximum=MAX_STATEMENT_TIMEOUT_MS,
            )
            self.lock_timeout_ms = self._pool_integer(
                postgresql_config,
                'lock_timeout_ms',
                5_000,
                minimum=1,
                maximum=MAX_LOCK_TIMEOUT_MS,
            )
            self.idle_transaction_timeout_ms = self._pool_integer(
                postgresql_config,
                'idle_in_transaction_session_timeout_ms',
                60_000,
                minimum=1,
                maximum=MAX_IDLE_TRANSACTION_TIMEOUT_MS,
            )
            connect_args = {
                'server_settings': {
                    'statement_timeout': str(self.statement_timeout_ms),
                    'lock_timeout': str(self.lock_timeout_ms),
                    'idle_in_transaction_session_timeout': str(self.idle_transaction_timeout_ms),
                }
            }
        self.engine = sqlalchemy_asyncio.create_async_engine(
            engine_url,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_timeout=self.pool_timeout_seconds,
            pool_recycle=self.pool_recycle_seconds,
            pool_pre_ping=True,
            **({'connect_args': connect_args} if connect_args else {}),
        )

    def resource_stats(self) -> dict[str, int]:
        """Return aggregate pool gauges without exposing connection details."""

        pool = self.engine.pool

        def read(name: str) -> int:
            method = getattr(pool, name, None)
            if not callable(method):
                return 0
            try:
                return int(method())
            except Exception:
                return 0

        return {
            'configured_size': self.pool_size,
            'configured_max_overflow': self.max_overflow,
            'configured_capacity': self.pool_size + self.max_overflow,
            'statement_timeout_ms': self.statement_timeout_ms,
            'lock_timeout_ms': self.lock_timeout_ms,
            'idle_in_transaction_session_timeout_ms': self.idle_transaction_timeout_ms,
            'timeouts_total': self._pool_timeouts_total,
            'checked_in': read('checkedin'),
            'checked_out': read('checkedout'),
            'overflow': max(read('overflow'), 0),
        }

    def record_pool_timeout(self) -> None:
        self._pool_timeouts_total += 1
