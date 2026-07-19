"""One-shot, operator-only Cloud PostgreSQL release migration entrypoint."""

from __future__ import annotations

import asyncio
import os
import re
from collections.abc import Mapping

import sqlalchemy

from ..cloud.bootstrap import SUPPORTED_PGVECTOR_DIMENSIONS
from ..core import app as core_app
from ..core.stages.load_config import LoadConfigStage
from ..core.stages.setup_logger import SetupLoggerStage
from .mgr import PersistenceManager, PersistenceMode
from .postgresql_url import normalize_asyncpg_url


DEFAULT_OPERATOR_DSN_ENV = 'LANGBOT_CLOUD_MIGRATION_DSN'
_ENV_NAME = re.compile(r'^[A-Z_][A-Z0-9_]*$')


class CloudReleaseMigrationConfigurationError(RuntimeError):
    """Raised before any database operation when migration input is unsafe."""


def _url_endpoint(url: sqlalchemy.engine.URL, *, label: str) -> tuple[str, int]:
    """Return a comparison-safe PostgreSQL endpoint without leaking its DSN."""

    try:
        host = (url.host or '').strip().casefold()
        port = url.port or 5432
    except (TypeError, ValueError):
        raise CloudReleaseMigrationConfigurationError(f'{label} PostgreSQL host or port is invalid') from None
    if not host or isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise CloudReleaseMigrationConfigurationError(f'{label} PostgreSQL host or port is invalid')
    return host, port


def _operator_database_url(
    instance_config: dict,
    *,
    environ: Mapping[str, str],
) -> sqlalchemy.engine.URL:
    database_config = instance_config.get('database')
    if not isinstance(database_config, dict) or database_config.get('use') != 'postgresql':
        raise CloudReleaseMigrationConfigurationError(
            'Cloud release migration requires explicit database.use=postgresql; SQLite fallback is forbidden'
        )

    runtime_config = database_config.get('postgresql')
    if not isinstance(runtime_config, dict):
        raise CloudReleaseMigrationConfigurationError('Cloud runtime PostgreSQL configuration is missing')

    migration_config = database_config.get('cloud_migration', {})
    if not isinstance(migration_config, dict):
        raise CloudReleaseMigrationConfigurationError('database.cloud_migration must be a mapping')
    dsn_env = migration_config.get('operator_dsn_env', DEFAULT_OPERATOR_DSN_ENV)
    if not isinstance(dsn_env, str) or not _ENV_NAME.fullmatch(dsn_env):
        raise CloudReleaseMigrationConfigurationError(
            'database.cloud_migration.operator_dsn_env must name an uppercase environment variable'
        )

    raw_dsn = environ.get(dsn_env, '').strip()
    if not raw_dsn:
        raise CloudReleaseMigrationConfigurationError(
            f'Cloud release migration requires the operator DSN in environment variable {dsn_env}'
        )
    try:
        operator_url = sqlalchemy.engine.make_url(raw_dsn)
    except Exception:
        # Never echo a malformed DSN because it may contain an unescaped secret.
        raise CloudReleaseMigrationConfigurationError('Cloud release migration operator DSN is invalid') from None

    try:
        operator_url = normalize_asyncpg_url(operator_url)
    except ValueError:
        raise CloudReleaseMigrationConfigurationError(
            'Cloud release migration operator DSN must use valid PostgreSQL asyncpg options'
        ) from None

    operator_user = (operator_url.username or '').strip()
    operator_database = (operator_url.database or '').strip()
    operator_host, operator_port = _url_endpoint(operator_url, label='Cloud release migration operator')
    runtime_url_value = runtime_config.get('url')
    if runtime_url_value:
        if not isinstance(runtime_url_value, str):
            raise CloudReleaseMigrationConfigurationError('Cloud runtime PostgreSQL URL must be a string')
        try:
            runtime_url = sqlalchemy.engine.make_url(runtime_url_value)
        except Exception:
            raise CloudReleaseMigrationConfigurationError('Cloud runtime PostgreSQL URL is invalid') from None
        if runtime_url.drivername not in {'postgresql', 'postgresql+asyncpg'}:
            raise CloudReleaseMigrationConfigurationError('Cloud runtime database URL must use PostgreSQL')
        runtime_user = (runtime_url.username or '').strip()
        runtime_database = (runtime_url.database or '').strip()
        runtime_host, runtime_port = _url_endpoint(runtime_url, label='Cloud runtime')
    else:
        runtime_user = str(runtime_config.get('user', 'postgres') or '').strip()
        runtime_database = str(runtime_config.get('database', 'postgres') or '').strip()
        runtime_host = str(runtime_config.get('host', '') or '').strip().casefold()
        runtime_port = runtime_config.get('port', 5432)
    if not operator_user or not operator_database:
        raise CloudReleaseMigrationConfigurationError(
            'Cloud release migration operator DSN must include a user, host, and database'
        )
    if (
        not runtime_user
        or not runtime_database
        or not runtime_host
        or isinstance(runtime_port, bool)
        or not isinstance(runtime_port, int)
        or not 1 <= runtime_port <= 65535
    ):
        raise CloudReleaseMigrationConfigurationError(
            'Cloud runtime PostgreSQL user, host, port, and database are required'
        )
    if operator_user == runtime_user:
        raise CloudReleaseMigrationConfigurationError(
            'Cloud release migration requires a distinct operator role from the runtime PostgreSQL role'
        )
    if operator_database != runtime_database:
        raise CloudReleaseMigrationConfigurationError(
            'Cloud release migration operator DSN must target the configured runtime database'
        )
    if operator_host != runtime_host or operator_port != runtime_port:
        # The first Cloud release intentionally requires the migrator and
        # runtime to use the same PostgreSQL endpoint. Supporting a direct
        # operator endpoint plus a runtime pooler requires a database-backed
        # immutable cluster identity check; accepting aliases here would turn a
        # same-named database on another cluster into a silent migration target.
        raise CloudReleaseMigrationConfigurationError(
            'Cloud release migration operator DSN must target the configured runtime PostgreSQL endpoint'
        )

    vdb_config = instance_config.get('vdb')
    if not isinstance(vdb_config, dict) or vdb_config.get('use') != 'pgvector':
        raise CloudReleaseMigrationConfigurationError('Cloud release migration requires vdb.use=pgvector')
    pgvector_config = vdb_config.get('pgvector')
    if not isinstance(pgvector_config, dict) or pgvector_config.get('use_business_database') is not True:
        raise CloudReleaseMigrationConfigurationError(
            'Cloud release migration requires vdb.pgvector.use_business_database=true'
        )
    dimensions = pgvector_config.get('allowed_dimensions')
    if (
        not isinstance(dimensions, list)
        or not dimensions
        or any(isinstance(item, bool) or not isinstance(item, int) for item in dimensions)
        or not set(dimensions).issubset(SUPPORTED_PGVECTOR_DIMENSIONS)
    ):
        raise CloudReleaseMigrationConfigurationError(
            'Cloud release migration pgvector dimensions are outside the release-created index set'
        )

    return operator_url


async def run_cloud_release_migration(
    ap: core_app.Application,
    *,
    environ: Mapping[str, str] | None = None,
) -> None:
    """Run and validate one release migration with an isolated operator DSN."""

    operator_url = _operator_database_url(
        ap.instance_config.data,
        environ=os.environ if environ is None else environ,
    )
    manager = PersistenceManager(
        ap,
        mode=PersistenceMode.RELEASE_MIGRATION,
        database_url=operator_url,
    )
    ap.persistence_mgr = manager
    try:
        await manager.initialize()
        ap.logger.info('Cloud PostgreSQL release migration reached and validated the exact release head.')
    finally:
        db = getattr(manager, 'db', None)
        engine = getattr(db, 'engine', None)
        if engine is not None:
            await engine.dispose()


async def run_cloud_release_migration_from_config(loop: asyncio.AbstractEventLoop) -> None:
    """Load only process configuration/logging, then run the one-shot job."""

    ap = core_app.Application()
    ap.event_loop = loop
    await LoadConfigStage().run(ap)
    await SetupLoggerStage().run(ap)
    await run_cloud_release_migration(ap)
