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
    sentinel_engine = object()

    def create_engine(url):
        nonlocal captured
        captured = url
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
    assert manager.engine is sentinel_engine


@pytest.mark.asyncio
async def test_postgresql_manager_builds_structured_url_with_special_password(monkeypatch) -> None:
    captured = None

    def create_engine(url):
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
