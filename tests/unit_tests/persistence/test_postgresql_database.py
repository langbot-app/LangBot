from __future__ import annotations

from types import SimpleNamespace

import pytest

# Persistence manager performs the package's database-manager registration;
# importing a concrete manager first would enter the historical app/mgr cycle.
from langbot.pkg.persistence import mgr as _persistence_mgr  # noqa: F401
from langbot.pkg.persistence.databases import postgresql


@pytest.mark.asyncio
async def test_postgresql_manager_parses_explicit_url_without_string_reassembly(monkeypatch) -> None:
    captured = None
    captured_options = None
    sentinel_engine = object()

    def create_engine(url, **options):
        nonlocal captured, captured_options
        captured = url
        captured_options = options
        return sentinel_engine

    monkeypatch.setattr(postgresql.sqlalchemy_asyncio, 'create_async_engine', create_engine)
    ap = SimpleNamespace(
        instance_config=SimpleNamespace(
            data={
                'database': {
                    'postgresql': {
                        'url': 'postgresql://runtime:p%40ss@db.internal:5432/langbot?sslmode=require',
                    }
                }
            }
        )
    )

    manager = postgresql.PostgreSQLDatabaseManager(ap)
    await manager.initialize()

    assert captured.drivername == 'postgresql+asyncpg'
    assert captured.password == 'p@ss'
    assert captured.query['ssl'] == 'require'
    assert 'sslmode' not in captured.query
    assert captured_options == {
        'pool_size': 10,
        'max_overflow': 10,
        'pool_timeout': 30,
        'pool_recycle': 1800,
        'pool_pre_ping': True,
    }
    assert manager.engine is sentinel_engine


@pytest.mark.asyncio
async def test_postgresql_manager_builds_structured_url_with_special_password(monkeypatch) -> None:
    captured = None

    def create_engine(url, **_options):
        nonlocal captured
        captured = url
        return object()

    monkeypatch.setattr(postgresql.sqlalchemy_asyncio, 'create_async_engine', create_engine)
    ap = SimpleNamespace(
        instance_config=SimpleNamespace(
            data={
                'database': {
                    'postgresql': {
                        'host': 'db.internal',
                        'port': 5432,
                        'user': 'runtime',
                        'password': 'p@ss:/?#word',
                        'database': 'langbot',
                    }
                }
            }
        )
    )

    await postgresql.PostgreSQLDatabaseManager(ap).initialize()

    assert captured.password == 'p@ss:/?#word'
    assert captured.host == 'db.internal'
    assert captured.database == 'langbot'


@pytest.mark.asyncio
async def test_postgresql_manager_applies_explicit_bounded_pool_options(monkeypatch) -> None:
    captured_options = None

    def create_engine(_url, **options):
        nonlocal captured_options
        captured_options = options
        return object()

    monkeypatch.setattr(postgresql.sqlalchemy_asyncio, 'create_async_engine', create_engine)
    ap = SimpleNamespace(
        instance_config=SimpleNamespace(
            data={
                'database': {
                    'postgresql': {
                        'pool_size': 24,
                        'max_overflow': 0,
                        'pool_timeout_seconds': 7,
                        'pool_recycle_seconds': 600,
                    }
                }
            }
        )
    )

    await postgresql.PostgreSQLDatabaseManager(ap).initialize()

    assert captured_options == {
        'pool_size': 24,
        'max_overflow': 0,
        'pool_timeout': 7,
        'pool_recycle': 600,
        'pool_pre_ping': True,
    }


@pytest.mark.asyncio
async def test_cloud_postgresql_manager_applies_bounded_server_timeouts(monkeypatch) -> None:
    captured_options = None

    def create_engine(_url, **options):
        nonlocal captured_options
        captured_options = options
        return object()

    monkeypatch.setattr(postgresql.sqlalchemy_asyncio, 'create_async_engine', create_engine)
    ap = SimpleNamespace(
        instance_config=SimpleNamespace(
            data={
                'database': {
                    'postgresql': {
                        'statement_timeout_ms': 45_000,
                        'lock_timeout_ms': 4_000,
                        'idle_in_transaction_session_timeout_ms': 55_000,
                    }
                }
            }
        )
    )

    manager = postgresql.PostgreSQLDatabaseManager(ap)
    manager.persistence_mode = 'cloud_runtime'
    await manager.initialize()

    assert captured_options['connect_args'] == {
        'server_settings': {
            'statement_timeout': '45000',
            'lock_timeout': '4000',
            'idle_in_transaction_session_timeout': '55000',
        }
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('name', 'value'),
    [
        ('pool_size', 0),
        ('pool_size', True),
        ('max_overflow', -1),
        ('pool_size', 101),
        ('max_overflow', 101),
        ('pool_timeout_seconds', 0),
        ('pool_timeout_seconds', 301),
        ('pool_recycle_seconds', '1800'),
        ('pool_recycle_seconds', 86401),
    ],
)
async def test_postgresql_manager_rejects_invalid_pool_options(name, value) -> None:
    ap = SimpleNamespace(instance_config=SimpleNamespace(data={'database': {'postgresql': {name: value}}}))

    with pytest.raises(ValueError, match=rf'database\.postgresql\.{name}'):
        await postgresql.PostgreSQLDatabaseManager(ap).initialize()


@pytest.mark.asyncio
async def test_postgresql_manager_rejects_combined_pool_capacity_above_hard_ceiling() -> None:
    ap = SimpleNamespace(
        instance_config=SimpleNamespace(
            data={
                'database': {
                    'postgresql': {
                        'pool_size': 60,
                        'max_overflow': 41,
                    }
                }
            }
        )
    )

    with pytest.raises(ValueError, match=r'pool_size \+ max_overflow'):
        await postgresql.PostgreSQLDatabaseManager(ap).initialize()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('name', 'value'),
    [
        ('statement_timeout_ms', 0),
        ('statement_timeout_ms', 300_001),
        ('lock_timeout_ms', 60_001),
        ('idle_in_transaction_session_timeout_ms', True),
        ('idle_in_transaction_session_timeout_ms', 300_001),
    ],
)
async def test_cloud_postgresql_manager_rejects_unsafe_server_timeouts(name, value) -> None:
    ap = SimpleNamespace(instance_config=SimpleNamespace(data={'database': {'postgresql': {name: value}}}))

    with pytest.raises(ValueError, match=rf'database\.postgresql\.{name}'):
        manager = postgresql.PostgreSQLDatabaseManager(ap)
        manager.persistence_mode = 'cloud_runtime'
        await manager.initialize()


@pytest.mark.asyncio
async def test_postgresql_manager_rejects_non_postgresql_url_without_echoing_secret() -> None:
    ap = SimpleNamespace(
        instance_config=SimpleNamespace(
            data={'database': {'postgresql': {'url': 'sqlite:///operator-super-secret.db'}}}
        )
    )

    manager = postgresql.PostgreSQLDatabaseManager(ap)
    with pytest.raises(ValueError, match='valid PostgreSQL') as exc_info:
        await manager.initialize()
    assert 'operator-super-secret' not in str(exc_info.value)
