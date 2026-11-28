"""Five independent SQLite write-lock and AgentRun consistency scenarios (#2747).

1. Single-process concurrency (queued & unqueued, competing writers, duplicate/host sequence races)
2. Multi-process contention (real OS child process holding BEGIN IMMEDIATE & concurrent ledger writes)
3. Mid-run cancellation (cancelled waiter + mid-run cancel under active write contention)
4. Retry (external retry_run & ledger busy retry under active SQLite contention)
5. Process recovery (interrupted lease reclaim, create_recovery_run, and engine restart durability)
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from langbot.pkg.agent.runner import run_ledger_store as ledger_mod
from langbot.pkg.agent.runner.run_ledger_store import RunLedgerStore, TerminalRunTransitionError
from langbot.pkg.core import app  # noqa: F401 - register persistence database managers
from langbot.pkg.entity.persistence.agent_run import AgentRun
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.persistence.databases.sqlite import BUSY_TIMEOUT_MS, SQLiteDatabaseManager
from langbot.pkg.persistence.write_admission import sqlite_write_deadline
from langbot.pkg.utils.execution_lease import INTERRUPTED_REASON, OWNER_ID as EXECUTION_OWNER_ID

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _create_sqlite_engine(db_path, *, write_queue: bool = False):
    application = SimpleNamespace(
        instance_config=SimpleNamespace(
            data={
                'database': {
                    'sqlite': {
                        'path': str(db_path),
                        'experimental_write_queue': write_queue,
                    }
                }
            }
        )
    )
    manager = SQLiteDatabaseManager(application)
    await manager.initialize()
    engine = manager.get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


async def _read_busy_timeout(engine) -> int:
    async with engine.connect() as conn:
        raw = await conn.get_raw_connection()
        async with raw.driver_connection.execute('PRAGMA busy_timeout') as cur:
            return int((await cur.fetchone())[0])


@pytest.mark.parametrize('write_queue', [False, True], ids=['unqueued', 'queued'])
async def test_scenario_1_single_process_concurrency_with_competing_writers(tmp_path, write_queue):
    """Scenario 1: 24 concurrent runs + competing short-write transactions + duplicate/host races."""
    db_path = tmp_path / f'single_proc_{write_queue}.db'
    engine = await _create_sqlite_engine(db_path, write_queue=write_queue)
    store = RunLedgerStore(engine)
    try:
        async with engine.begin() as conn:
            await conn.execute(sa.text('CREATE TABLE competing_writers (id INTEGER PRIMARY KEY, ticks INTEGER)'))
            await conn.execute(sa.text('INSERT INTO competing_writers VALUES (1, 0)'))

        run_ids = [f'run-sp-{index:02d}' for index in range(24)]
        for run_id in run_ids:
            await store.create_run(
                run_id=run_id,
                event_id=f'evt-{run_id}',
                binding_id='binding',
                runner_id='runner',
                workspace_id='ws',
            )

        stop_competing = asyncio.Event()

        async def competing_writer():
            while not stop_competing.is_set():
                async with engine.connect() as conn:
                    await conn.exec_driver_sql('BEGIN IMMEDIATE')
                    await conn.execute(sa.text('UPDATE competing_writers SET ticks = ticks + 1 WHERE id = 1'))
                    await asyncio.sleep(0.01)
                    await conn.commit()
                await asyncio.sleep(0.005)

        async def drive_run(run_id: str):
            await store.append_event(run_id=run_id, sequence=1, event_type='tool.call.completed', data={'ok': True})
            # Simulate concurrent duplicate replay racing onto sequence=2.
            dup_a, dup_b = await asyncio.gather(
                store.append_event(run_id=run_id, sequence=2, event_type='message.completed', data={'text': 'hi'}),
                store.append_event(run_id=run_id, sequence=2, event_type='message.completed', data={'text': 'hi'}),
            )
            assert dup_a['id'] == dup_b['id']
            await store.append_event(
                run_id=run_id, sequence=3, event_type='run.completed', data={'finish_reason': 'stop'}
            )
            # Two concurrent host-allocated sequence=None appends must allocate distinct monotonic slots.
            host_a, host_b = await asyncio.gather(
                store.append_event(run_id=run_id, sequence=None, event_type='audit.host.a', source='host'),
                store.append_event(run_id=run_id, sequence=None, event_type='audit.host.b', source='host'),
            )
            assert sorted([host_a['sequence'], host_b['sequence']]) == [4, 5]
            final = await store.finalize_run(run_id=run_id, status='completed')
            assert final['status'] == 'completed'

        competitors = [asyncio.create_task(competing_writer()) for _ in range(4)]
        try:
            await asyncio.gather(*(drive_run(run_id) for run_id in run_ids))
        finally:
            stop_competing.set()
            await asyncio.gather(*competitors)

        for run_id in run_ids:
            run = await store.get_run(run_id)
            assert run['status'] == 'completed'
            events, *_ = await store.page_run_events(run_id=run_id, limit=20)
            sequences = [event['sequence'] for event in events]
            assert sequences == [1, 2, 3, 4, 5]
        assert await _read_busy_timeout(engine) == BUSY_TIMEOUT_MS
    finally:
        await engine.dispose()


async def test_scenario_2_multiprocess_contention_recovery_deadline_and_serialization(tmp_path):
    """Scenario 2: real child OS process holding SQLite write locks and racing ledger writes."""
    db_path = tmp_path / 'multiprocess.db'
    engine = await _create_sqlite_engine(db_path, write_queue=False)
    store = RunLedgerStore(engine)
    try:
        await store.create_run(run_id='run-mp-recover', event_id='evt-1', binding_id='b', runner_id='r')
        await store.create_run(run_id='run-mp-deadline', event_id='evt-2', binding_id='b', runner_id='r')
        await store.create_run(run_id='run-mp-race', event_id='evt-3', binding_id='b', runner_id='r')

        # 2a: Child process holds BEGIN IMMEDIATE for 0.6s, then commits -> parent retries and succeeds.
        holder_code = (
            'import sqlite3, sys, time; '
            'conn = sqlite3.connect(sys.argv[1], timeout=30); '
            'conn.execute("BEGIN IMMEDIATE"); '
            'conn.execute("UPDATE agent_run SET updated_at = updated_at WHERE run_id = ?", (sys.argv[2],)); '
            'print("LOCKED", flush=True); '
            'time.sleep(float(sys.argv[3])); '
            'conn.commit(); '
            'conn.close()'
        )
        with subprocess.Popen(
            [sys.executable, '-c', holder_code, str(db_path), 'run-mp-recover', '0.6'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ) as proc:
            try:
                assert proc.stdout.readline().strip() == 'LOCKED'
                event = await store.append_event(run_id='run-mp-recover', sequence=1, event_type='run.completed')
                final = await store.finalize_run(run_id='run-mp-recover', status='completed')
                assert event['sequence'] == 1
                assert final['status'] == 'completed'
            finally:
                _, stderr = proc.communicate(timeout=10)
                assert proc.returncode == 0, stderr

        # 2b: Child process holds BEGIN IMMEDIATE for 2.0s while caller deadline is 0.45s -> bounded failure.
        with subprocess.Popen(
            [sys.executable, '-c', holder_code, str(db_path), 'run-mp-deadline', '2.0'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ) as proc2:
            try:
                assert proc2.stdout.readline().strip() == 'LOCKED'
                loop = asyncio.get_running_loop()
                started = loop.time()
                with sqlite_write_deadline(started + 0.45):
                    with pytest.raises(sa.exc.OperationalError, match='database is locked'):
                        await store.append_event(run_id='run-mp-deadline', sequence=1, event_type='message.completed')
                elapsed = loop.time() - started
                assert 0.3 <= elapsed < 1.3
            finally:
                _, stderr2 = proc2.communicate(timeout=10)
                assert proc2.returncode == 0, stderr2

        # 2c: Separate OS process races host-allocated appends and terminal finalization with parent.
        worker_code = (
            'import asyncio, json, sys\n'
            'from types import SimpleNamespace\n'
            'from langbot.pkg.core import app as _app\n'
            'from langbot.pkg.persistence.databases.sqlite import SQLiteDatabaseManager\n'
            'from langbot.pkg.agent.runner.run_ledger_store import RunLedgerStore, TerminalRunTransitionError\n'
            'async def run():\n'
            '    mgr = SQLiteDatabaseManager(SimpleNamespace(instance_config=SimpleNamespace('
            '        data={"database": {"sqlite": {"path": sys.argv[1]}}})))\n'
            '    await mgr.initialize()\n'
            '    store = RunLedgerStore(mgr.get_engine())\n'
            '    seqs = []\n'
            '    for i in range(6):\n'
            '        ev = await store.append_event(run_id=sys.argv[2], sequence=None, event_type="child.ev", data={"i": i})\n'
            '        seqs.append(ev["sequence"])\n'
            '    try:\n'
            '        res = await store.finalize_run(run_id=sys.argv[2], status="cancelled", status_reason="child")\n'
            '        outcome = res["status"]\n'
            '    except TerminalRunTransitionError:\n'
            '        outcome = "transition_rejected"\n'
            '    await mgr.get_engine().dispose()\n'
            '    print(json.dumps({"seqs": seqs, "outcome": outcome}), flush=True)\n'
            'asyncio.run(run())\n'
        )
        with subprocess.Popen(
            [sys.executable, '-c', worker_code, str(db_path), 'run-mp-race'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ) as child:
            parent_seqs: list[int] = []
            for index in range(6):
                ev = await store.append_event(
                    run_id='run-mp-race', sequence=None, event_type='parent.ev', data={'i': index}
                )
                parent_seqs.append(ev['sequence'])
            try:
                parent_final = await store.finalize_run(run_id='run-mp-race', status='completed')
                parent_outcome = parent_final['status']
            except TerminalRunTransitionError:
                parent_outcome = 'transition_rejected'

            stdout, stderr = child.communicate(timeout=30)
            assert child.returncode == 0, stderr
        child_result = json.loads(stdout.strip().splitlines()[-1])

        assert sorted(parent_seqs + child_result['seqs']) == list(range(1, 13))
        # Exactly one process wins terminal status; the other sees TerminalRunTransitionError.
        assert sorted([parent_outcome, child_result['outcome']]) in (
            ['completed', 'transition_rejected'],
            ['cancelled', 'transition_rejected'],
        )
        assert (await store.get_run('run-mp-race'))['status'] in {'completed', 'cancelled'}
        assert await _read_busy_timeout(engine) == BUSY_TIMEOUT_MS
    finally:
        await engine.dispose()


async def test_scenario_3_mid_run_cancellation_under_sqlite_write_contention(tmp_path):
    """Scenario 3: cancelling a blocked writer releases resources cleanly, and cancel finalize succeeds under contention."""
    db_path = tmp_path / 'cancel.db'
    engine = await _create_sqlite_engine(db_path, write_queue=True)
    store = RunLedgerStore(engine)
    try:
        await store.create_run(run_id='run-cancel-1', event_id='e1', binding_id='b', runner_id='r', workspace_id='ws')
        await store.create_run(run_id='run-cancel-2', event_id='e2', binding_id='b', runner_id='r', workspace_id='ws')

        # 3a: Cancel a task waiting on a real SQLite write lock; verify CancelledError propagates and DB stays healthy.
        holder = await engine.connect()
        await holder.exec_driver_sql('BEGIN IMMEDIATE')
        await holder.execute(
            sa.update(AgentRun).where(AgentRun.run_id == 'run-cancel-1').values(updated_at=AgentRun.updated_at)
        )
        blocked_task = asyncio.create_task(
            store.append_event(run_id='run-cancel-1', sequence=1, event_type='message.delta')
        )
        await asyncio.sleep(0.15)
        assert not blocked_task.done()
        blocked_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await blocked_task
        await holder.rollback()
        await holder.close()

        # 3b: Mid-run cancel request + host cancelled event + finalize_run('cancelled') under transient contention.
        holder2 = await engine.connect()
        await holder2.exec_driver_sql('BEGIN IMMEDIATE')
        await holder2.execute(
            sa.update(AgentRun).where(AgentRun.run_id == 'run-cancel-2').values(updated_at=AgentRun.updated_at)
        )

        async def release_soon():
            await asyncio.sleep(0.25)
            await holder2.commit()
            await holder2.close()

        releaser = asyncio.create_task(release_soon())
        cancel_req = await store.request_cancel(run_id='run-cancel-2', status_reason='user_abort')
        assert cancel_req is not None and cancel_req['cancel_requested_at'] is not None
        await releaser

        cancelled_event = await store.append_event(
            run_id='run-cancel-2', sequence=None, event_type='run.failed', data={'code': 'cancelled'}, source='host'
        )
        final = await store.finalize_run(run_id='run-cancel-2', status='cancelled', status_reason='user_abort')
        assert cancelled_event['sequence'] == 1
        assert final['status'] == 'cancelled'
        assert final['status_reason'] == 'user_abort'
        assert await _read_busy_timeout(engine) == BUSY_TIMEOUT_MS
    finally:
        await engine.dispose()


async def test_scenario_4_retry_run_and_ledger_busy_retry_under_contention(tmp_path):
    """Scenario 4: retry_run increments retry_count exactly once under real SQLite lock contention."""
    db_path = tmp_path / 'retry.db'
    engine = await _create_sqlite_engine(db_path, write_queue=False)
    store = RunLedgerStore(engine)
    try:
        await store.create_run(
            run_id='run-retry',
            event_id='evt-r',
            binding_id='b',
            runner_id='r',
            workspace_id='ws',
            status='queued',
            queue_name='default',
        )
        await store.append_event(run_id='run-retry', sequence=1, event_type='message.delta')
        await store.finalize_run(run_id='run-retry', status='failed', status_reason='upstream_error')

        # Hold a write lock via a separate connection and release mid-retry.
        holder = await engine.connect()
        await holder.exec_driver_sql('BEGIN IMMEDIATE')
        await holder.execute(
            sa.update(AgentRun).where(AgentRun.run_id == 'run-retry').values(updated_at=AgentRun.updated_at)
        )

        async def release():
            await asyncio.sleep(0.3)
            await holder.commit()
            await holder.close()

        releaser = asyncio.create_task(release())
        retried = await store.retry_run(run_id='run-retry', status_reason='operator_retry', resume_from_sequence=1)
        await releaser

        assert retried['status'] == 'queued'
        assert retried['finished_at'] is None
        assert retried['metadata']['retry_count'] == 1
        assert retried['metadata']['resume_from_sequence'] == 1
        events, *_ = await store.page_run_events(run_id='run-retry', limit=10)
        assert [event['sequence'] for event in events] == [1]
        assert await _read_busy_timeout(engine) == BUSY_TIMEOUT_MS
    finally:
        await engine.dispose()


async def test_scenario_5_process_recovery_reclaim_and_restart_durability(tmp_path):
    """Scenario 5: interrupted lease reclaim, recovery child creation under lock, and post-restart continuity."""
    db_path = tmp_path / 'recovery.db'
    engine = await _create_sqlite_engine(db_path, write_queue=False)
    store = RunLedgerStore(engine)
    try:
        # 5a: Interrupted run owned by this Host is reclaimed to completed under transient contention.
        await store.create_run(
            run_id='run-reclaim',
            event_id='evt-rec',
            binding_id='b',
            runner_id='r',
            workspace_id='ws',
        )
        await store.append_event(run_id='run-reclaim', sequence=1, event_type='message.completed')
        async with engine.begin() as conn:
            await conn.execute(
                sa.update(AgentRun)
                .where(AgentRun.run_id == 'run-reclaim')
                .values(
                    status='failed',
                    status_reason=INTERRUPTED_REASON,
                    execution_owner_id=EXECUTION_OWNER_ID,
                )
            )
        holder = await engine.connect()
        await holder.exec_driver_sql('BEGIN IMMEDIATE')
        await holder.execute(
            sa.update(AgentRun).where(AgentRun.run_id == 'run-reclaim').values(updated_at=AgentRun.updated_at)
        )

        async def release_holder():
            await asyncio.sleep(0.25)
            await holder.commit()
            await holder.close()

        releaser = asyncio.create_task(release_holder())
        await store.append_event(run_id='run-reclaim', sequence=2, event_type='run.completed')
        reclaimed = await store.finalize_run(run_id='run-reclaim', status='completed')
        await releaser
        assert reclaimed['status'] == 'completed'
        assert reclaimed['status_reason'] is None

        # 5b: Create & authorize recovery child run from a failed source run.
        await store.create_run(
            run_id='run-source-failed',
            event_id='evt-src',
            binding_id='b',
            runner_id='r',
            workspace_id='ws',
            authorization={'runner_id': 'r'},
        )
        await store.finalize_run(run_id='run-source-failed', status='failed', status_reason='crash')
        child, created = await store.create_recovery_run(
            source_run_id='run-source-failed',
            run_id='run-recovery-child',
            event_id='recovery:run-recovery-child',
            metadata={'processor_type': 'agent'},
        )
        assert created is True and child['status'] == 'running'
        await store.authorize_recovery_run(
            'run-recovery-child',
            authorization={'runner_id': 'r', 'recovered': True},
            deadline_at=None,
        )
        await store.append_event(run_id='run-recovery-child', sequence=1, event_type='message.completed')
        await store.finalize_run(run_id='run-recovery-child', status='completed')
    finally:
        await engine.dispose()

    # 5c: Simulate full Host restart with a brand-new SQLite engine on the same WAL file.
    restarted_engine = await _create_sqlite_engine(db_path, write_queue=False)
    restarted_store = RunLedgerStore(restarted_engine)
    try:
        reclaimed_after = await restarted_store.get_run('run-reclaim')
        child_after = await restarted_store.get_run('run-recovery-child')
        assert reclaimed_after['status'] == 'completed'
        assert child_after['status'] == 'completed'
        # Host audit event after restart continues monotonically at sequence=3.
        post_restart = await restarted_store.append_event(
            run_id='run-reclaim', sequence=None, event_type='audit.post_restart', source='host'
        )
        assert post_restart['sequence'] == 3
        events, *_ = await restarted_store.page_run_events(run_id='run-reclaim', limit=10)
        assert [event['sequence'] for event in events] == [1, 2, 3]
        assert ledger_mod.BUSY_RETRY_ATTEMPTS > 0
    finally:
        await restarted_engine.dispose()
