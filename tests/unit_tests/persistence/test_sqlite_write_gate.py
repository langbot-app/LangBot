"""Writer admission on real pooled connections, including failure/cleanup paths."""

import asyncio
import gc
import sqlite3
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from langbot.pkg.persistence.sqlite_write_gate import install


class Base(DeclarativeBase):
    pass


class Row(Base):
    __tablename__ = 'gate_rows'
    id: Mapped[int] = mapped_column(primary_key=True)


@pytest.fixture
async def database(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "gate.db"}')
    gate = install(engine)
    async with engine.begin() as connection:
        await connection.exec_driver_sql('PRAGMA journal_mode=WAL')
        await connection.run_sync(Base.metadata.create_all)
    yield engine, gate
    await engine.dispose()
    assert not gate.lock.locked()
    assert gate.waiting == 0


async def queued(gate):
    async with asyncio.timeout(2):
        while gate.waiting == 0:
            await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_session_flush_and_direct_writer_share_gate_without_blocking_reads(database):
    engine, gate = database
    async with AsyncSession(engine) as session, engine.connect() as direct:
        session.add(Row(id=1))
        await session.flush()
        writer = asyncio.create_task(direct.exec_driver_sql('INSERT INTO gate_rows VALUES (2)'))
        await queued(gate)
        async with engine.connect() as reader:
            assert await asyncio.wait_for(reader.scalar(sa.select(sa.func.count()).select_from(Row)), 1) == 0
        await session.commit()
        await asyncio.wait_for(writer, 1)
        assert gate.lock.locked()
        await direct.commit()
    async with engine.connect() as reader:
        assert await reader.scalar(sa.select(sa.func.count()).select_from(Row)) == 2


@pytest.mark.asyncio
async def test_cancel_waiter_does_not_unlock_owner(database):
    engine, gate = database
    async with engine.connect() as owner, engine.connect() as waiting:
        await owner.exec_driver_sql('INSERT INTO gate_rows VALUES (1)')
        task = asyncio.create_task(waiting.exec_driver_sql('INSERT INTO gate_rows VALUES (2)'))
        await queued(gate)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert gate.lock.locked() and gate.waiting == 0
        await owner.rollback()
        await waiting.exec_driver_sql('INSERT INTO gate_rows VALUES (3)')
        await waiting.commit()


@pytest.mark.asyncio
async def test_savepoint_rollback_keeps_gate_until_outer_transaction_ends(database):
    engine, gate = database
    async with engine.connect() as connection:
        await connection.exec_driver_sql('BEGIN')
        nested = await connection.begin_nested()
        await connection.execute(sa.insert(Row).values(id=1))
        await nested.rollback()
        assert gate.lock.locked()
        await connection.rollback()
        assert not gate.lock.locked()
        nested = await connection.begin_nested()
        await connection.execute(sa.insert(Row).values(id=2))
        await nested.commit()
        assert not gate.lock.locked()  # SQLite released the outermost SAVEPOINT.


@pytest.mark.asyncio
async def test_failed_statement_and_commit_release_on_rollback(database):
    engine, gate = database
    async with engine.connect() as connection:
        await connection.exec_driver_sql('PRAGMA foreign_keys=ON')
        await connection.exec_driver_sql('CREATE TABLE parent (id INTEGER PRIMARY KEY)')
        await connection.exec_driver_sql(
            'CREATE TABLE child (id INTEGER REFERENCES parent(id) DEFERRABLE INITIALLY DEFERRED)'
        )
        await connection.commit()
        await connection.exec_driver_sql('INSERT INTO child VALUES (123)')
        with pytest.raises(sa.exc.IntegrityError):
            await connection.commit()
        assert gate.lock.locked()
        # A failed commit leaves SQLite's physical transaction open. Closing
        # must roll it back before another connection is admitted.
    assert not gate.lock.locked()
    async with engine.begin() as connection:
        await connection.exec_driver_sql('INSERT INTO gate_rows VALUES (1)')
        with pytest.raises(sa.exc.IntegrityError):
            await connection.exec_driver_sql('INSERT INTO gate_rows VALUES (1)')
        assert gate.lock.locked()
    assert not gate.lock.locked()


@pytest.mark.asyncio
async def test_dispose_reconnect_and_cte_dml(database):
    engine, gate = database
    for _ in range(2):
        async with engine.connect() as connection:
            count = gate.acquisitions
            await connection.exec_driver_sql('/* INSERT ignored */ WITH x(v) AS (SELECT 1) SELECT v FROM x')
            assert gate.acquisitions == count
            await connection.exec_driver_sql('WITH x(v) AS (SELECT 5) INSERT OR REPLACE INTO gate_rows SELECT v FROM x')
            # SQLite's legacy mode autocommits a leading WITH; no retained lock.
            await connection.commit()
            await connection.exec_driver_sql('PRAGMA user_version=3')
            assert await connection.scalar(sa.text('PRAGMA user_version')) == 3
            count = gate.acquisitions
            await connection.exec_driver_sql('PRAGMA user_version(4)')
            assert gate.acquisitions == count + 1
            assert await connection.scalar(sa.text('PRAGMA user_version')) == 4
            count = gate.acquisitions
            await connection.exec_driver_sql('PRAGMA table_info(gate_rows)')
            assert gate.acquisitions == count
            await connection.exec_driver_sql('PRAGMA incremental_vacuum(1)')
            assert not gate.lock.locked()
        await engine.dispose()


@pytest.mark.asyncio
async def test_gc_force_close_releases_after_driver_close(database):
    engine, gate = database
    connection = await engine.connect()
    await connection.exec_driver_sql('INSERT INTO gate_rows VALUES (1)')
    del connection
    with pytest.warns(sa.exc.SAWarning, match='garbage collector'):
        gc.collect()
    async with asyncio.timeout(2):
        while gate.lock.locked():
            await asyncio.sleep(0.01)
    async with engine.begin() as connection:
        await connection.exec_driver_sql('INSERT INTO gate_rows VALUES (2)')


@pytest.mark.asyncio
async def test_cancelled_statement_drains_before_release(database):
    engine, gate = database
    started = asyncio.Event()
    loop = asyncio.get_running_loop()
    import time

    def slow():
        loop.call_soon_threadsafe(started.set)
        time.sleep(0.1)
        return 1

    async with engine.connect() as connection:
        raw = (await connection.get_raw_connection()).driver_connection
        await raw.create_function('slow', 0, slow)
        task = asyncio.create_task(connection.exec_driver_sql('INSERT INTO gate_rows VALUES (slow())'))
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    async with engine.begin() as connection:
        await asyncio.wait_for(connection.exec_driver_sql('INSERT INTO gate_rows VALUES (2)'), 2)


def test_non_sqlite_engine_is_not_touched():
    # No event API or sync engine is needed on the PostgreSQL path.
    assert install(SimpleNamespace(dialect=SimpleNamespace(name='postgresql'))) is None


@pytest.mark.asyncio
async def test_cancel_commit_retains_gate_until_connection_is_closed(database):
    engine, gate = database
    entered = asyncio.Event()
    async with engine.connect() as connection:
        await connection.exec_driver_sql('INSERT INTO gate_rows VALUES (1)')
        driver = (await connection.get_raw_connection()).driver_connection

        async def blocked_commit():
            entered.set()
            await asyncio.Event().wait()

        driver.commit = blocked_commit
        task = asyncio.create_task(connection.commit())
        await asyncio.wait_for(entered.wait(), 1)
        assert gate.lock.locked()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    async with engine.begin() as connection:
        await asyncio.wait_for(connection.exec_driver_sql('INSERT INTO gate_rows VALUES (2)'), 1)
        assert await connection.scalar(sa.select(sa.func.count()).select_from(Row)) == 1


@pytest.mark.asyncio
async def test_failed_rollback_is_retried_before_pool_reuse(database):
    engine, gate = database
    async with engine.connect() as connection:
        await connection.exec_driver_sql('INSERT INTO gate_rows VALUES (1)')
        driver = (await connection.get_raw_connection()).driver_connection
        original = driver.rollback

        async def fail_once():
            driver.rollback = original
            raise sqlite3.OperationalError('injected rollback failure')

        driver.rollback = fail_once
        with pytest.raises(sa.exc.OperationalError, match='injected rollback failure'):
            await connection.rollback()
        assert gate.lock.locked()
    async with engine.begin() as connection:
        await asyncio.wait_for(connection.exec_driver_sql('INSERT INTO gate_rows VALUES (2)'), 1)
        assert await connection.scalar(sa.select(sa.func.count()).select_from(Row)) == 1


@pytest.mark.asyncio
async def test_pool_reset_rollback_failure_closes_before_admitting_writer(database):
    engine, gate = database
    connection = await engine.connect()
    await connection.exec_driver_sql('INSERT INTO gate_rows VALUES (1)')
    driver = (await connection.get_raw_connection()).driver_connection

    async def broken_rollback():
        raise sqlite3.OperationalError('persistent rollback failure')

    driver.rollback = broken_rollback
    with pytest.raises(sa.exc.OperationalError, match='persistent rollback failure'):
        await connection.rollback()
    await connection.close()
    async with engine.begin() as connection:
        await asyncio.wait_for(connection.exec_driver_sql('INSERT INTO gate_rows VALUES (2)'), 1)
        assert await connection.scalar(sa.select(sa.func.count()).select_from(Row)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'statement,writes',
    [
        ('WITH select1 AS (SELECT 7) INSERT INTO gate_rows SELECT * FROM select1', True),
        ('\ufeffINSERT INTO gate_rows VALUES (1)', True),
        ('WITH x AS (SELECT 2)\ufeff INSERT INTO gate_rows SELECT * FROM x', True),
        ('WITH 中SELECT文 AS (SELECT 8) INSERT INTO gate_rows SELECT * FROM 中SELECT文', True),
        ('WITH update1 AS (SELECT 9) SELECT * FROM update1', False),
        ('WITH a😺SELECT AS (SELECT 8) INSERT INTO gate_rows SELECT * FROM a😺SELECT', True),
        ('WITH a😺UPDATE AS (SELECT 9) SELECT * FROM a😺UPDATE', False),
        ('WITH "insert" AS (SELECT 9) SELECT * FROM "insert"', False),
        ('WITH replace AS (SELECT 9) SELECT * FROM replace', False),
        (
            'WITH RECURSIVE select1(n) AS (VALUES(1) UNION ALL SELECT n+1 FROM select1 WHERE n<3), '
            'update1 AS NOT MATERIALIZED (SELECT n FROM select1) INSERT INTO gate_rows SELECT n FROM update1',
            True,
        ),
        ('PRAGMA "incremental_vacuum"', True),
        ('PRAGMA main."wal_checkpoint"', True),
        ('PRAGMA [user_version](4)', True),
        ("PRAGMA table_info('a=b')", False),
        ('PRAGMA table_info(gate_rows) /* = */', False),
    ],
)
async def test_direct_sql_classification_matches_sqlite(database, statement, writes):
    engine, gate = database
    async with engine.connect() as connection:
        acquired = gate.acquisitions
        result = await connection.exec_driver_sql(statement)
        if result.returns_rows:
            result.all()
        await connection.commit()
        assert gate.acquisitions - acquired == int(writes)
        if writes and statement.startswith('WITH'):
            assert await connection.scalar(sa.select(sa.func.count()).select_from(Row)) > 0


@pytest.mark.asyncio
@pytest.mark.parametrize('physically_closed', [False, True])
@pytest.mark.parametrize('method', ['close', 'invalidate'])
async def test_close_failure_fails_queued_and_future_writers(database, physically_closed, method):
    engine, gate = database
    owner = await engine.connect()
    waiting = await engine.connect()
    await owner.exec_driver_sql('INSERT INTO gate_rows VALUES (1)')
    driver = (await owner.get_raw_connection()).driver_connection
    original_close = driver.close

    async def broken_close():
        if physically_closed:
            await original_close()
        raise sqlite3.OperationalError('injected close completion error')

    driver.close = broken_close
    task = asyncio.create_task(waiting.exec_driver_sql('INSERT INTO gate_rows VALUES (2)'))
    await queued(gate)
    try:
        if method == 'invalidate':
            # Pool invalidation logs/swallow close errors; the gate must still fail closed.
            await owner.invalidate()
        else:
            with pytest.raises(sqlite3.OperationalError, match='injected close completion error'):
                await owner.run_sync(lambda connection: connection.connection.dbapi_connection.close())
        with pytest.raises(RuntimeError, match='gate unavailable.*restart the process'):
            await asyncio.wait_for(task, 1)
        with pytest.raises(RuntimeError, match='gate unavailable.*restart the process'):
            await waiting.exec_driver_sql('INSERT INTO gate_rows VALUES (3)')
        assert gate.failed and not gate.lock.locked()
    finally:
        driver.close = original_close
        await original_close()
        await owner.invalidate()
        await owner.close()
        await waiting.close()


def test_engine_reuse_on_another_loop_fails_explicitly_even_after_dispose(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "loops.db"}')
    gate = install(engine)

    async def first_loop():
        async with engine.begin() as connection:
            await connection.exec_driver_sql('CREATE TABLE example (id INTEGER)')
        # Force asyncio.Lock itself to bind through contention too.
        await gate.acquire()
        waiter = asyncio.create_task(gate.acquire())
        await queued(gate)
        gate.lock.release()
        await waiter
        gate.lock.release()
        await engine.dispose()

    async def other_loop():
        with pytest.raises(RuntimeError, match='another event loop; create a new engine'):
            async with engine.connect():
                pass
        assert not gate.lock.locked()
        await engine.dispose()

    for scenario in (first_loop, other_loop):
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(scenario())
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            loop.close()
