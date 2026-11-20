from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from langbot.pkg.core import app  # noqa: F401 - initialize manager registration before database imports
from langbot.pkg.persistence.databases.sqlite import SQLiteDatabaseManager

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_writer_commits_while_independent_reader_is_open(tmp_path):
    application = SimpleNamespace(
        instance_config=SimpleNamespace(data={'database': {'sqlite': {'path': str(tmp_path / 'concurrency.db')}}})
    )
    manager = SQLiteDatabaseManager(application)
    await manager.initialize()
    engine = manager.get_engine()
    try:
        async with engine.begin() as connection:
            await connection.execute(sa.text('CREATE TABLE probe (id INTEGER PRIMARY KEY, value TEXT)'))
            await connection.execute(sa.text("INSERT INTO probe VALUES (1, 'old')"))
        async with engine.connect() as reader:
            await reader.execute(sa.text('BEGIN'))
            assert (await reader.execute(sa.text('SELECT value FROM probe'))).scalar_one() == 'old'
            async with engine.connect() as writer:
                await writer.execute(sa.text('PRAGMA busy_timeout=250'))
                await writer.execute(sa.text("UPDATE probe SET value='new' WHERE id=1"))
                await writer.commit()
            await reader.rollback()
        async with engine.connect() as connection:
            assert (await connection.execute(sa.text('SELECT value FROM probe'))).scalar_one() == 'new'
    finally:
        await engine.dispose()


async def test_queued_ledger_waits_before_checkout_and_cancelled_writer_does_not_block(tmp_path):
    import asyncio

    from langbot.pkg.agent.runner.run_ledger_store import RunLedgerStore
    from langbot.pkg.entity.persistence.base import Base
    from langbot.pkg.persistence.mgr import PersistenceManager

    config = {'path': str(tmp_path / 'queue.db'), 'experimental_write_queue': True}
    application = SimpleNamespace(instance_config=SimpleNamespace(data={'database': {'sqlite': config}}))
    persistence = PersistenceManager(application)
    persistence.db = SQLiteDatabaseManager(application)
    await persistence.db.initialize()
    engine = persistence.get_db_engine()
    ledger = RunLedgerStore(engine)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await ledger.create_run(run_id='queue-test', event_id=None, binding_id=None, runner_id='test')

        entered = asyncio.Event()

        async def hold():
            async with persistence.tenant_write_uow('workspace') as outer:
                async with persistence.tenant_write_uow('workspace') as inner:
                    assert outer.session is inner.session
                with pytest.raises(RuntimeError, match='independent write transaction'):
                    await ledger.append_event(run_id='queue-test', sequence=3, event_type='test')
                entered.set()
                await asyncio.Future()

        async def append(sequence, started):
            started.set()
            return await ledger.append_event(run_id='queue-test', sequence=sequence, event_type='test')

        holder = asyncio.create_task(hold())
        await asyncio.wait_for(entered.wait(), 5)
        tasks = []
        for sequence in (1, 2):
            started = asyncio.Event()
            tasks.append(asyncio.create_task(append(sequence, started)))
            await started.wait()
        assert not any(task.done() for task in tasks)
        assert engine.pool.checkedout() == 0
        assert (await asyncio.wait_for(ledger.get_run('queue-test'), 5))['status'] == 'running'
        for task in (tasks[0], holder):
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert (await asyncio.wait_for(tasks[1], 5))['sequence'] == 2
        events, *_ = await ledger.page_run_events(run_id='queue-test')
        assert [event['sequence'] for event in events] == [2]
    finally:
        await engine.dispose()


async def test_write_timing_uses_committed_connection_and_ignores_rollback(tmp_path, caplog, monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSession

    from langbot.pkg.persistence import write_admission as admission

    config = {'path': str(tmp_path / 'timing.db'), 'experimental_write_timing': True}
    application = SimpleNamespace(instance_config=SimpleNamespace(data={'database': {'sqlite': config}}))
    manager = SQLiteDatabaseManager(application)
    await manager.initialize()
    engine = manager.get_engine()
    table = sa.Table('timing_example', sa.MetaData(), sa.Column('id', sa.Integer, primary_key=True))
    now = 0
    monkeypatch.setattr(admission, 'perf_counter', lambda: now)
    caplog.set_level('INFO', logger=admission.__name__)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(table.metadata.create_all)
        async with admission.write_slot(engine, 'monitoring.example'), AsyncSession(engine) as session:
            now = 1
            async with engine.begin() as other:
                await other.execute(table.insert().values(id=1))
            now = 3
            await session.execute(table.insert().values(id=2))
            now = 5
            await admission.commit_write(session)
            now = 8  # Post-commit result handling must not inflate the hold time.
        async with admission.write_slot(engine, 'monitoring.rolled_back'), AsyncSession(engine) as session:
            await session.execute(table.insert().values(id=3))
            await session.rollback()
        timings = [r.message for r in caplog.records if r.message.startswith('sqlite_write_timing')]
        assert len(timings) == 1
        assert 'op=monitoring.example queue_ms=0.000 before_write_ms=3000.000 through_commit_ms=2000.000' in timings[0]
    finally:
        await engine.dispose()
