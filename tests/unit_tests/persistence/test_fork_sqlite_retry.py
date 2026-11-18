from __future__ import annotations

import asyncio
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import insert as sqlite_insert


def _mock_manager(*, dialect_name: object = None):
    manager = import_module('langbot.pkg.persistence.mgr').PersistenceManager(Mock())
    connection = AsyncMock()
    context = AsyncMock()
    context.__aenter__.return_value = connection
    engine = Mock()
    if dialect_name is not None:
        engine.dialect = SimpleNamespace(name=dialect_name)
    engine.connect.return_value = context
    manager.db = Mock()
    manager.db.get_engine.return_value = engine
    return manager, connection


@pytest.mark.asyncio
async def test_replay_safe_statements_retry_on_sqlite_locked_with_backoff():
    table = sa.table('kv', sa.column('k'), sa.column('v'))
    insert_excluded = sqlite_insert(table).values(k='a', v='2')
    insert_excluded = insert_excluded.on_conflict_do_update(
        index_elements=['k'],
        set_={'v': insert_excluded.excluded.v},
    )
    replay_safe_statements = [
        sa.text('SELECT 1'),
        sa.select(table.c.v).where(table.c.k == 'a'),
        sa.update(table).where(table.c.k == 'a').values(v='b'),
        sa.delete(table).where(table.c.k == 'a'),
        sa.insert(table).prefix_with('OR IGNORE').values(k='a', v='1'),
        sqlite_insert(table).values(k='a', v='1').on_conflict_do_nothing(),
        insert_excluded,
        sa.insert(table).values(k='a', v='1').execution_options(sqlite_retry_safe=True),
    ]

    for stmt in replay_safe_statements:
        manager, connection = _mock_manager()
        result = Mock()
        locked = sa.exc.OperationalError('STMT', {}, Exception('database is locked'))
        connection.execute.side_effect = [locked, result]

        with patch('langbot.pkg.persistence.mgr.asyncio.sleep', new_callable=AsyncMock) as sleep:
            assert await manager.execute_async(stmt) is result

        assert connection.execute.await_count == 2
        connection.commit.assert_awaited_once()
        sleep.assert_awaited_once_with(0.1)


@pytest.mark.asyncio
async def test_non_replay_safe_statements_do_not_retry_on_sqlite_locked():
    table = sa.table('kv', sa.column('k'), sa.column('v'), sa.column('n'))
    unsafe_calls = [
        (sa.insert(table).values(k='a', v='1'), (), {}),
        (sa.update(table).where(table.c.k == 'a').values(n=table.c.n + 1), (), {}),
        (sa.update(table).where(table.c.k == 'a').values(v=sa.func.random()), (), {}),
        (sa.text('INSERT INTO kv VALUES (:k, :v)'), (), {}),
        (sa.delete(table).where(table.c.k == 'a').returning(table.c.k), (), {}),
        (
            sa.text('SELECT :k'),
            (item for item in [{'k': 'a'}]),
            {},
        ),
        (sa.update(table).where(table.c.k == 'a').values(v='b').execution_options(sqlite_retry_safe=False), (), {}),
    ]

    for stmt, extra_args, kwargs in unsafe_calls:
        manager, connection = _mock_manager()
        locked = sa.exc.OperationalError('STMT', {}, Exception('database is locked'))
        connection.execute.side_effect = locked

        with patch('langbot.pkg.persistence.mgr.asyncio.sleep', new_callable=AsyncMock) as sleep:
            with pytest.raises(sa.exc.OperationalError):
                if extra_args:
                    await manager.execute_async(stmt, extra_args, **kwargs)
                else:
                    await manager.execute_async(stmt, **kwargs)

        assert connection.execute.await_count == 1
        sleep.assert_not_awaited()
        connection.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_commit_stage_locked_write_does_not_replay_already_executed_dml():
    table = sa.table('kv', sa.column('k'), sa.column('v'))
    manager, connection = _mock_manager()
    connection.execute.return_value = Mock()
    connection.commit.side_effect = sa.exc.OperationalError('COMMIT', {}, Exception('database is locked'))

    with patch('langbot.pkg.persistence.mgr.asyncio.sleep', new_callable=AsyncMock) as sleep:
        with pytest.raises(sa.exc.OperationalError):
            await manager.execute_async(sa.update(table).where(table.c.k == 'a').values(v='x'))

    assert connection.execute.await_count == 1
    assert connection.commit.await_count == 1
    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_sqlite_retry_stops_at_limit_non_lock_and_non_sqlite_dialect():
    manager, connection = _mock_manager()
    for message, attempts in [('database is locked', manager._sqlite_locked_retry_max_attempts), ('syntax error', 1)]:
        connection.execute.reset_mock()
        connection.execute.side_effect = sa.exc.OperationalError('SELECT', {}, Exception(message))
        with patch('langbot.pkg.persistence.mgr.asyncio.sleep', new_callable=AsyncMock):
            with pytest.raises(sa.exc.OperationalError):
                await manager.execute_async(sa.text('SELECT 1'))
        assert connection.execute.await_count == attempts
    connection.commit.assert_not_awaited()

    pg_manager, pg_connection = _mock_manager(dialect_name='postgresql')
    pg_connection.execute.side_effect = sa.exc.OperationalError('SELECT', {}, Exception('database is locked'))
    with patch('langbot.pkg.persistence.mgr.asyncio.sleep', new_callable=AsyncMock) as sleep:
        with pytest.raises(sa.exc.OperationalError):
            await pg_manager.execute_async(sa.text('SELECT 1'))
    assert pg_connection.execute.await_count == 1
    sleep.assert_not_awaited()


async def _init_real_sqlite_manager(db_path):
    mgr_mod = import_module('langbot.pkg.persistence.mgr')
    sqlite_mod = import_module('langbot.pkg.persistence.databases.sqlite')

    ap = SimpleNamespace(
        instance_config=SimpleNamespace(data={'database': {'sqlite': {'path': str(db_path)}}}),
        logger=SimpleNamespace(warning=lambda *a, **k: None, info=lambda *a, **k: None, error=lambda *a, **k: None),
    )
    db_mgr = sqlite_mod.SQLiteDatabaseManager(ap)
    await db_mgr.initialize()

    pm = mgr_mod.PersistenceManager(ap)
    pm.db = db_mgr

    meta = sa.MetaData()
    kv = sa.Table('kv', meta, sa.Column('k', sa.String, primary_key=True), sa.Column('v', sa.String))
    async with db_mgr.engine.begin() as conn:
        await conn.run_sync(meta.create_all)
        await conn.execute(sa.insert(kv).values(k='k1', v='initial'))
    return pm, db_mgr, kv


@pytest.mark.asyncio
async def test_real_sqlite_contention_recovers_when_lock_released_before_30s(tmp_path):
    pm, db_mgr, kv = await _init_real_sqlite_manager(tmp_path / 'before_30s.db')
    attempts = 0

    try:
        # Hold write lock across the first 5s attempt slice, then commit at 6.2s (< 30s).
        holder = await db_mgr.engine.connect()
        await holder.exec_driver_sql('BEGIN IMMEDIATE')
        await holder.execute(sa.update(kv).where(kv.c.k == 'k1').values(v='held'))

        @sa.event.listens_for(db_mgr.engine.sync_engine, 'before_cursor_execute')
        def _count_updates(_conn, _cursor, statement, _parameters, _context, _executemany):
            nonlocal attempts
            if statement.startswith('UPDATE kv'):
                attempts += 1

        async def _release_holder():
            await asyncio.sleep(6.2)
            await holder.commit()
            await holder.close()

        releaser = asyncio.create_task(_release_holder())
        started = asyncio.get_running_loop().time()
        await pm.execute_async(sa.update(kv).where(kv.c.k == 'k1').values(v='from_execute_async'))
        elapsed = asyncio.get_running_loop().time() - started
        await releaser

        async with db_mgr.engine.connect() as verify_conn:
            val = (await verify_conn.execute(sa.select(kv.c.v).where(kv.c.k == 'k1'))).scalar_one()
        print(f'REAL_SQLITE_BEFORE_30S outcome=success attempts={attempts} elapsed={elapsed:.3f}s')
        assert val == 'from_execute_async'
        assert attempts == 2
        assert 5.5 <= elapsed < 12.0
    finally:
        await db_mgr.engine.dispose()


@pytest.mark.asyncio
async def test_real_sqlite_contention_bounds_total_wait_when_lock_held_past_30s(tmp_path):
    pm, db_mgr, kv = await _init_real_sqlite_manager(tmp_path / 'after_30s.db')
    attempts = 0

    holder = None
    releaser = None
    try:
        holder = await db_mgr.engine.connect()
        await holder.exec_driver_sql('BEGIN IMMEDIATE')
        await holder.execute(sa.update(kv).where(kv.c.k == 'k1').values(v='held'))

        @sa.event.listens_for(db_mgr.engine.sync_engine, 'before_cursor_execute')
        def _count_updates(_conn, _cursor, statement, _parameters, _context, _executemany):
            nonlocal attempts
            if statement.startswith('UPDATE kv'):
                attempts += 1

        async def _release_holder_late():
            await asyncio.sleep(31.5)
            await holder.commit()
            await holder.close()

        releaser = asyncio.create_task(_release_holder_late())
        started = asyncio.get_running_loop().time()
        with pytest.raises(sa.exc.OperationalError, match='database is locked'):
            await pm.execute_async(sa.update(kv).where(kv.c.k == 'k1').values(v='timed_out'))
        elapsed = asyncio.get_running_loop().time() - started

        await releaser
        holder = None

        async with db_mgr.engine.connect() as verify_conn:
            val = (await verify_conn.execute(sa.select(kv.c.v).where(kv.c.k == 'k1'))).scalar_one()
            raw = await verify_conn.get_raw_connection()
            async with raw.driver_connection.execute('PRAGMA busy_timeout') as cur:
                restored_timeout = (await cur.fetchone())[0]

        print(
            f'REAL_SQLITE_AFTER_30S outcome=OperationalError(database is locked) '
            f'attempts={attempts} elapsed={elapsed:.3f}s restored_busy_timeout={restored_timeout}'
        )
        assert val == 'held'
        assert 2 <= attempts <= 6
        assert 29.0 <= elapsed < 33.5
        assert restored_timeout == 30000
    finally:
        if releaser is not None and not releaser.done():
            releaser.cancel()
        if holder is not None:
            await holder.rollback()
            await holder.close()
        await db_mgr.engine.dispose()


@pytest.mark.asyncio
async def test_real_sqlite_contention_respects_caller_remaining_deadline(tmp_path):
    pm, db_mgr, kv = await _init_real_sqlite_manager(tmp_path / 'caller_deadline.db')
    attempts = 0

    holder = None
    try:
        holder = await db_mgr.engine.connect()
        await holder.exec_driver_sql('BEGIN IMMEDIATE')
        await holder.execute(sa.update(kv).where(kv.c.k == 'k1').values(v='held'))

        @sa.event.listens_for(db_mgr.engine.sync_engine, 'before_cursor_execute')
        def _count_updates(_conn, _cursor, statement, _parameters, _context, _executemany):
            nonlocal attempts
            if statement.startswith('UPDATE kv'):
                attempts += 1

        loop = asyncio.get_running_loop()
        started = loop.time()
        with pm.sqlite_retry_deadline(started + 1.2):
            with pytest.raises(sa.exc.OperationalError, match='database is locked'):
                await pm.execute_async(sa.update(kv).where(kv.c.k == 'k1').values(v='deadline_hit'))
        elapsed = loop.time() - started

        await holder.rollback()
        await holder.close()
        holder = None
        print(
            f'REAL_SQLITE_CALLER_DEADLINE outcome=OperationalError(database is locked) '
            f'attempts={attempts} elapsed={elapsed:.3f}s'
        )
        assert attempts == 1
        assert 1.0 <= elapsed < 2.3
    finally:
        if holder is not None:
            await holder.rollback()
            await holder.close()
        await db_mgr.engine.dispose()
