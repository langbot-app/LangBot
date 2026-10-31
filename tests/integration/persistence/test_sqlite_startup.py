"""Verify startup checkpoint completion, contention, and retry semantics."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.persistence import alembic_runner, resource_urls, sqlite_startup
from tests.integration.persistence.test_sqlite_migration_backup import _manager

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _prepare(engine):
    async with engine.connect() as connection:
        await connection.exec_driver_sql('PRAGMA journal_mode=WAL')
        await connection.exec_driver_sql('PRAGMA wal_autocheckpoint=0')
        await connection.exec_driver_sql('CREATE TABLE retained (value TEXT)')
        await connection.exec_driver_sql("INSERT INTO retained VALUES ('keep')")
        await connection.commit()
    await alembic_runner.run_alembic_stamp(engine, alembic_runner.get_alembic_head())


async def test_checkpoint_truncates_wal_and_preserves_committed_data(tmp_path):
    path = tmp_path / 'startup.db'
    engine = create_async_engine(f'sqlite+aiosqlite:///{path}')
    try:
        await _prepare(engine)
        wal = path.with_name(path.name + '-wal')
        assert wal.stat().st_size > 0
        async with engine.connect() as connection:
            timeout = (await connection.exec_driver_sql('PRAGMA busy_timeout')).scalar_one()
        await sqlite_startup.checkpoint_after_migration(engine)
        assert wal.stat().st_size == 0
        async with engine.connect() as connection:
            assert (await connection.exec_driver_sql('SELECT value FROM retained')).scalar_one() == 'keep'
            assert (await connection.exec_driver_sql('PRAGMA busy_timeout')).scalar_one() == timeout
    finally:
        await engine.dispose()


@pytest.mark.parametrize('blocker', ['reader', 'writer'])
async def test_busy_checkpoint_preserves_revision_and_retries(tmp_path, monkeypatch, blocker):
    path = tmp_path / 'busy.db'
    engine = create_async_engine(f'sqlite+aiosqlite:///{path}')
    monkeypatch.setattr(sqlite_startup, 'STARTUP_BUSY_TIMEOUT_MS', 20)
    try:
        await _prepare(engine)
        async with engine.connect() as occupied:
            await occupied.exec_driver_sql('BEGIN' if blocker == 'reader' else 'BEGIN IMMEDIATE')
            await occupied.exec_driver_sql('SELECT * FROM retained')
            if blocker == 'reader':
                async with engine.begin() as writer:
                    await writer.exec_driver_sql("INSERT INTO retained VALUES ('new')")
            with pytest.raises(RuntimeError, match='startup WAL checkpoint did not complete'):
                await sqlite_startup.checkpoint_after_migration(engine)
            async with engine.connect() as connection:
                assert (await connection.exec_driver_sql('PRAGMA busy_timeout')).scalar_one() == 5000
            assert await alembic_runner.get_alembic_current(engine) == alembic_runner.get_alembic_head()
            await occupied.rollback()
        await sqlite_startup.checkpoint_after_migration(engine)
        assert path.with_name(path.name + '-wal').stat().st_size == 0
    finally:
        await engine.dispose()


async def test_initialize_stops_before_runtime_setup_and_retries_at_head(tmp_path, monkeypatch):
    from langbot.pkg.persistence import database

    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "gate.db"}')
    manager = _manager(engine)
    manager.ap.instance_config = SimpleNamespace(data={'database': {'use': 'sqlite'}})
    db = SimpleNamespace(engine=engine, initialize=AsyncMock(), get_engine=lambda: engine)

    class TestDatabase:
        name = 'sqlite'

        def __new__(cls, *args, **kwargs):
            return db

    monkeypatch.setattr(database, 'preregistered_managers', [TestDatabase])
    manager._initialize_managed_schema = AsyncMock()
    manager._enable_sqlite_foreign_keys_after_migration = AsyncMock()
    manager.write_space_model_providers = AsyncMock()
    install = Mock()
    monkeypatch.setattr(resource_urls, 'install', install)
    checkpoint = AsyncMock(side_effect=RuntimeError('checkpoint failure'))
    monkeypatch.setattr(sqlite_startup, 'checkpoint_after_migration', checkpoint)
    try:
        with pytest.raises(RuntimeError, match='checkpoint failure'):
            await manager.initialize()
        install.assert_not_called()
        manager.write_space_model_providers.assert_not_awaited()
        manager._initialize_managed_schema.assert_awaited_once()
        manager._enable_sqlite_foreign_keys_after_migration.assert_not_awaited()
        checkpoint.side_effect = None
        await manager.initialize()
        assert checkpoint.await_count == 2
        install.assert_called_once()
        manager._enable_sqlite_foreign_keys_after_migration.assert_awaited_once()
        manager.write_space_model_providers.assert_awaited_once()
    finally:
        await engine.dispose()


async def test_checkpoint_waits_for_writer_to_finish(tmp_path, monkeypatch):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "wait.db"}')
    monkeypatch.setattr(sqlite_startup, 'STARTUP_BUSY_TIMEOUT_MS', 2000)
    try:
        await _prepare(engine)
        async with engine.connect() as writer:
            await writer.exec_driver_sql('BEGIN IMMEDIATE')
            task = asyncio.create_task(sqlite_startup.checkpoint_after_migration(engine))
            try:
                await asyncio.sleep(0.05)
                assert not task.done()
                await writer.rollback()
                await task
            finally:
                await writer.rollback()
                await task
    finally:
        await engine.dispose()


async def test_non_sqlite_checkpoint_does_not_connect():
    engine = SimpleNamespace(dialect=SimpleNamespace(name='postgresql'), connect=Mock())
    await sqlite_startup.checkpoint_after_migration(engine)
    engine.connect.assert_not_called()


def _database_manager(tmp_path):
    from langbot.pkg.persistence.databases.sqlite import SQLiteDatabaseManager

    ap = SimpleNamespace(
        instance_config=SimpleNamespace(data={'database': {'sqlite': {'path': str(tmp_path / 'wal.db')}}})
    )
    return SQLiteDatabaseManager(ap)


async def test_wal_policy_applies_to_all_connections_after_pool_disposal(tmp_path):
    manager = _database_manager(tmp_path)
    await manager.initialize()
    try:
        for _ in range(2):
            async with manager.engine.connect() as first, manager.engine.connect() as second:
                for connection in (first, second):
                    assert (await connection.exec_driver_sql('PRAGMA journal_size_limit')).scalar_one() == 64 * 1024**2
                    assert (await connection.exec_driver_sql('PRAGMA wal_autocheckpoint')).scalar_one() == 1000
                    assert (await connection.exec_driver_sql('PRAGMA synchronous')).scalar_one() == 2
            await manager.engine.dispose()
    finally:
        await manager.engine.dispose()


async def test_large_wal_shrinks_on_reuse_without_forced_checkpoint(tmp_path):
    manager = _database_manager(tmp_path)
    await manager.initialize()
    wal = tmp_path / 'wal.db-wal'
    try:
        async with manager.engine.connect() as connection:
            await connection.exec_driver_sql('CREATE TABLE payload (data BLOB)')
            await connection.exec_driver_sql('INSERT INTO payload VALUES (zeroblob(73400320))')
            await connection.commit()
            assert wal.stat().st_size > 64 * 1024**2
            await connection.exec_driver_sql('INSERT INTO payload VALUES (NULL)')
            await connection.commit()
            assert wal.stat().st_size == 64 * 1024**2
            assert (await connection.exec_driver_sql('SELECT count(*) FROM payload')).scalar_one() == 2
    finally:
        await manager.engine.dispose()


async def test_retention_limit_preserves_wal_needed_by_reader(tmp_path):
    manager = _database_manager(tmp_path)
    await manager.initialize()
    wal = tmp_path / 'wal.db-wal'
    try:
        async with manager.engine.connect() as writer, manager.engine.connect() as reader:
            await writer.exec_driver_sql('CREATE TABLE payload (data BLOB)')
            await writer.exec_driver_sql('INSERT INTO payload VALUES (zeroblob(8388608))')
            await writer.commit()
            await writer.exec_driver_sql('PRAGMA wal_checkpoint(TRUNCATE)')
            await writer.commit()
            await reader.exec_driver_sql('BEGIN')
            await reader.exec_driver_sql('SELECT length(data) FROM payload')
            for _ in range(9):
                await writer.exec_driver_sql('UPDATE payload SET data=randomblob(8388608)')
                await writer.commit()
            assert wal.stat().st_size > 64 * 1024**2
            assert (await reader.exec_driver_sql('SELECT hex(substr(data, 1, 1)) FROM payload')).scalar_one() == '00'
            _, frames, checkpointed = (await writer.exec_driver_sql('PRAGMA wal_checkpoint(PASSIVE)')).one()
            assert frames > checkpointed
            await reader.rollback()
            _, frames, checkpointed = (await writer.exec_driver_sql('PRAGMA wal_checkpoint(PASSIVE)')).one()
            assert frames == checkpointed
            await writer.exec_driver_sql('INSERT INTO payload VALUES (NULL)')
            await writer.commit()
            assert wal.stat().st_size == 64 * 1024**2
    finally:
        await manager.engine.dispose()
