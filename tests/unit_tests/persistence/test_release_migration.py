from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy

from langbot.__main__ import _build_parser
from langbot.pkg.persistence import release_migration
from langbot.pkg.persistence.mgr import PersistenceManager, PersistenceMode


def _cloud_config(*, database_use: str = 'postgresql', runtime_user: str = 'langbot_runtime') -> dict:
    return {
        'database': {
            'use': database_use,
            'postgresql': {
                'host': 'runtime-db',
                'port': 5432,
                'user': runtime_user,
                'password': 'runtime-secret',
                'database': 'langbot',
            },
            'cloud_migration': {
                'operator_dsn_env': 'TEST_LANGBOT_OPERATOR_DSN',
            },
        },
        'vdb': {
            'use': 'pgvector',
            'pgvector': {
                'use_business_database': True,
                'allowed_dimensions': [384, 1536],
            },
        },
    }


def _operator_environ(
    *,
    user: str = 'langbot_migrator',
    database: str = 'langbot',
    host: str = 'runtime-db',
    port: int = 5432,
) -> dict[str, str]:
    return {
        'TEST_LANGBOT_OPERATOR_DSN': (f'postgresql://{user}:operator%40secret@{host}:{port}/{database}?sslmode=require')
    }


def test_cloud_migration_cli_is_explicit() -> None:
    args = _build_parser().parse_args(['migrate', '--cloud'])
    assert args.command == 'migrate'
    assert args.cloud is True

    with pytest.raises(SystemExit) as exc_info:
        _build_parser().parse_args(['migrate'])
    assert exc_info.value.code == 2


def test_operator_url_is_separate_and_preserves_escaped_secret() -> None:
    url = release_migration._operator_database_url(
        _cloud_config(),
        environ=_operator_environ(),
    )

    assert url.drivername == 'postgresql+asyncpg'
    assert url.username == 'langbot_migrator'
    assert url.password == 'operator@secret'
    assert url.host == 'runtime-db'
    assert url.port == 5432
    assert url.database == 'langbot'
    assert url.query['ssl'] == 'require'
    assert 'sslmode' not in url.query


@pytest.mark.parametrize(
    ('config', 'environ', 'message'),
    [
        (_cloud_config(database_use='sqlite'), _operator_environ(), 'SQLite fallback is forbidden'),
        (_cloud_config(), {}, 'requires the operator DSN'),
        (_cloud_config(), {'TEST_LANGBOT_OPERATOR_DSN': 'not a secret://operator-password'}, 'DSN is invalid'),
        (
            _cloud_config(),
            {'TEST_LANGBOT_OPERATOR_DSN': 'postgresql://operator:secret@runtime-db:not-a-port/langbot'},
            'DSN is invalid',
        ),
        (_cloud_config(), _operator_environ(user='langbot_runtime'), 'distinct operator role'),
        (_cloud_config(), _operator_environ(database='another_database'), 'configured runtime database'),
        (_cloud_config(), _operator_environ(host='other-cluster'), 'runtime PostgreSQL endpoint'),
        (_cloud_config(), _operator_environ(port=6432), 'runtime PostgreSQL endpoint'),
    ],
)
def test_operator_url_rejects_unsafe_configuration(config: dict, environ: dict[str, str], message: str) -> None:
    with pytest.raises(release_migration.CloudReleaseMigrationConfigurationError, match=message) as exc_info:
        release_migration._operator_database_url(config, environ=environ)
    assert 'operator-password' not in str(exc_info.value)


@pytest.mark.asyncio
async def test_release_migration_disposes_operator_engine_on_failure(monkeypatch) -> None:
    engine = SimpleNamespace(dispose=AsyncMock())
    manager = SimpleNamespace(
        db=SimpleNamespace(engine=engine),
        initialize=AsyncMock(side_effect=RuntimeError('migration failed')),
    )

    def manager_factory(*args, **kwargs):
        del args, kwargs
        return manager

    monkeypatch.setattr(release_migration, 'PersistenceManager', manager_factory)
    ap = SimpleNamespace(
        instance_config=SimpleNamespace(data=_cloud_config()),
        logger=logging.getLogger('release-migration-disposal-test'),
        persistence_mgr=None,
    )

    with pytest.raises(RuntimeError, match='migration failed'):
        await release_migration.run_cloud_release_migration(ap, environ=_operator_environ())

    assert ap.persistence_mgr is manager
    engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_release_mode_rejects_sqlite_before_schema_changes(tmp_path, monkeypatch) -> None:
    from langbot.pkg.persistence import mgr as persistence_mgr_module
    from langbot.pkg.persistence.databases.sqlite import SQLiteDatabaseManager

    monkeypatch.setattr(persistence_mgr_module.database, 'preregistered_managers', [SQLiteDatabaseManager])
    ap = SimpleNamespace(
        instance_config=SimpleNamespace(
            data={
                'database': {
                    'use': 'sqlite',
                    'sqlite': {'path': str(tmp_path / 'must-not-migrate.db')},
                }
            }
        ),
        logger=logging.getLogger('release-migration-sqlite-rejection-test'),
    )
    manager = PersistenceManager(ap, mode=PersistenceMode.RELEASE_MIGRATION)
    with pytest.raises(RuntimeError, match='requires PostgreSQL'):
        await manager.initialize()
    await manager.get_db_engine().dispose()

    engine = sqlalchemy.create_engine(f'sqlite:///{tmp_path / "must-not-migrate.db"}')
    try:
        assert sqlalchemy.inspect(engine).get_table_names() == []
    finally:
        engine.dispose()
