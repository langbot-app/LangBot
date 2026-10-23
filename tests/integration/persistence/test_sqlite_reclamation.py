"""Exercise physical format conversion and bounded reclamation on real files."""

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.persistence import alembic_runner, sqlite_reclamation
from tests.integration.persistence.test_sqlite_migration_backup import _manager

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('mode', [0, 1, 2])
async def test_conversion_preserves_data_and_is_repeatable(tmp_path, mode):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "convert.db"}')
    try:
        async with engine.begin() as connection:
            await connection.exec_driver_sql(f'PRAGMA auto_vacuum={mode}')
            await connection.exec_driver_sql('CREATE TABLE retained (id INTEGER PRIMARY KEY, value TEXT)')
            await connection.exec_driver_sql("INSERT INTO retained VALUES (1, 'keep')")
        await alembic_runner.run_alembic_stamp(engine, '0041_resource_urls')
        for _ in range(2):
            await _manager(engine)._run_alembic_migrations()
        async with engine.connect() as connection:
            assert (await connection.exec_driver_sql('PRAGMA auto_vacuum')).scalar_one() == 2
            assert (await connection.exec_driver_sql('SELECT value FROM retained')).scalar_one() == 'keep'
            assert (await connection.exec_driver_sql('PRAGMA quick_check')).scalar_one() == 'ok'
        backups = list((tmp_path / 'migration-backups').glob('*.json'))
        assert len(backups) == (1 if mode == 0 else 0)
    finally:
        await engine.dispose()


async def test_conversion_failure_restores_original_format_and_revision(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "failure.db"}')

    @sa.event.listens_for(engine.sync_engine, 'after_cursor_execute')
    def fail_after_conversion(connection, cursor, statement, parameters, context, executemany):
        if statement == 'VACUUM':
            raise RuntimeError('injected conversion failure')

    try:
        async with engine.begin() as connection:
            await connection.exec_driver_sql('CREATE TABLE retained (value TEXT)')
            await connection.exec_driver_sql("INSERT INTO retained VALUES ('keep')")
        await alembic_runner.run_alembic_stamp(engine, '0041_resource_urls')
        with pytest.raises(RuntimeError, match='injected conversion failure'):
            await _manager(engine)._run_alembic_migrations()
        assert await alembic_runner.get_alembic_current(engine) == '0041_resource_urls'
        async with engine.connect() as connection:
            assert (await connection.exec_driver_sql('PRAGMA auto_vacuum')).scalar_one() == 0
            assert (await connection.exec_driver_sql('SELECT value FROM retained')).scalar_one() == 'keep'
    finally:
        await engine.dispose()


@pytest.mark.parametrize('slow', [False, True])
@pytest.mark.parametrize('journal', ['DELETE', 'WAL'])
async def test_reclamation_shrinks_file_and_adapts_without_full_vacuum(tmp_path, monkeypatch, slow, journal):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "reclaim.db"}')
    statements = []

    @sa.event.listens_for(engine.sync_engine, 'before_cursor_execute')
    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    try:
        async with engine.begin() as connection:
            await connection.exec_driver_sql('PRAGMA auto_vacuum=INCREMENTAL')
            await connection.exec_driver_sql(f'PRAGMA journal_mode={journal}')
            await connection.exec_driver_sql('CREATE TABLE payloads (id INTEGER PRIMARY KEY, data BLOB)')
            await connection.exec_driver_sql('INSERT INTO payloads(data) VALUES (randomblob(4194304))')
            await connection.exec_driver_sql('DELETE FROM payloads')
        async with engine.connect() as connection:
            before = (await connection.exec_driver_sql('PRAGMA page_count')).scalar_one()
            timeout = (await connection.exec_driver_sql('PRAGMA busy_timeout')).scalar_one()
            driver = (await connection.get_raw_connection()).driver_connection
            await driver.set_trace_callback(statements.append)
        monkeypatch.setattr(sqlite_reclamation, 'ROUND_SECONDS', 0.1)
        monkeypatch.setattr(sqlite_reclamation, 'PAUSE_SECONDS', 0.001)
        monkeypatch.setattr(sqlite_reclamation, 'TARGET_SECONDS', 0 if slow else 100)
        await sqlite_reclamation.reclaim_free_pages(engine)
        batches = [int(s.split('(')[1].split(')')[0]) for s in statements if 'incremental_vacuum(' in s]
        assert len(batches) > 1
        assert max(batches) <= 512 and min(batches) >= 1
        assert batches[1] < batches[0] if slow else batches[1] > batches[0]
        assert 'VACUUM' not in statements
        async with engine.connect() as connection:
            assert (await connection.exec_driver_sql('PRAGMA page_count')).scalar_one() < before
            assert (await connection.exec_driver_sql('PRAGMA busy_timeout')).scalar_one() == timeout
            await connection.exec_driver_sql('INSERT INTO payloads(data) VALUES (NULL)')
            await connection.commit()
    finally:
        await engine.dispose()


async def test_reclamation_yields_to_existing_writer(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "busy.db"}')
    try:
        async with engine.begin() as connection:
            await connection.exec_driver_sql('PRAGMA auto_vacuum=INCREMENTAL')
            await connection.exec_driver_sql('CREATE TABLE payloads (data BLOB)')
            await connection.exec_driver_sql('INSERT INTO payloads VALUES (randomblob(1048576))')
            await connection.exec_driver_sql('DELETE FROM payloads')
        async with engine.connect() as writer:
            await writer.exec_driver_sql('BEGIN IMMEDIATE')
            await sqlite_reclamation.reclaim_free_pages(engine)
            assert sqlite_reclamation._states[engine].pages == 4
            await writer.rollback()
    finally:
        await engine.dispose()
