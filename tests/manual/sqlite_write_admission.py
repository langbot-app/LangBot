"""Measure concurrent Box publication, Ledger writes and reads. See dev-docs/review/sqlite-write-admission.md."""

# ruff: noqa: F811
import asyncio
from contextvars import ContextVar
import json
import os
from pathlib import Path
import random
from time import perf_counter
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from langbot.pkg.agent.runner.run_ledger_store import RunLedgerStore
from langbot.pkg.box.runner import RunnerBoxService, RunBoxBinding
from langbot.pkg.persistence.databases.sqlite import SQLiteDatabaseManager
from tests.integration.storage.test_artifact_publication_policy import (
    _producer,
    artifact_replicas,  # noqa: F401 -- pytest fixture
    replicas,  # noqa: F401 -- pytest fixture
    persistence_case,  # noqa: F401 -- fixture dependencies
)
from tests.integration.storage.test_artifact_run_inputs import _run_context
from tests.utils.artifact_store import seed_run


@pytest.mark.asyncio
async def test_queue(artifact_replicas):
    case = artifact_replicas
    app = case.a.app
    mode = os.environ['ADMISSION']
    assert mode in {'on', 'off'}
    enabled = mode == 'on'
    app.instance_config.data['database'] = {
        'sqlite': {'path': case.a.engine.url.database, 'experimental_write_queue': enabled}
    }
    db = SQLiteDatabaseManager(app)
    await db.initialize()
    app.persistence_mgr.db = db
    engine = db.engine
    assert bool(engine.sync_engine.get_execution_options().get('langbot_sqlite_write_queue')) == enabled
    context = ContextVar('append_time', default=None)

    @sa.event.listens_for(engine.sync_engine, 'after_cursor_execute')
    def after_write(conn, cur, stmt, args, ctx, many):
        if stmt.startswith('INSERT INTO agent_run_event'):
            start, samples = context.get()
            samples['first_write'].append(1000 * (perf_counter() - start))

    if enabled:
        queue = engine.sync_engine.get_execution_options()['langbot_sqlite_write_queue']
        acquire = queue.acquire

        async def timed_acquire():
            start = perf_counter()
            result = await acquire()
            sample = context.get()
            if sample:
                sample[1]['queue'].append(1000 * (perf_counter() - start))
            return result

        queue.acquire = timed_acquire
    try:
        async with engine.connect() as conn:
            assert (await conn.exec_driver_sql('PRAGMA journal_mode')).scalar() == 'wal'
            assert (await conn.exec_driver_sql('PRAGMA busy_timeout')).scalar() == 30000
        pub = await app.artifact_publication_service.set(case.context, 'agent', await _producer(case), True)
        service = RunnerBoxService(SimpleNamespace(ap=app))
        ledger = RunLedgerStore(engine)
        runs = [_run_context(case).trigger_principal.run_id for _ in range(12)]
        for rid in runs:
            await seed_run(app, case.a.context, rid)
        with Path(os.environ['BENCH_OUT']).open('w', buffering=1) as output:
            for wave in range(17):
                queries = []
                for size in (1, 1, 10, 10):
                    run = _run_context(case)
                    rid = run.trigger_principal.run_id
                    await seed_run(app, run, rid)
                    binding = RunBoxBinding(rid, 'session', {}, 'private')
                    for i in range(size):
                        asset = await app.artifact_service.create_run_output(run, f'{i}.txt', b'test', 'text/plain')
                        binding.exported[str(i)] = {'id': str(i), 'artifact_id': asset['id']}
                    queries.append(
                        SimpleNamespace(_execution_context=run, _box_binding=binding, _output_publication=pub)
                    )
                lat = {k: [] for k in ('publish', 'append', 'first_write', 'read', 'queue')}

                async def publish(query):
                    start = perf_counter()
                    ids = list(query._box_binding.exported)
                    result = await service.commit_files(query, ids)
                    lat['publish'].append(1000 * (perf_counter() - start))
                    assert [x['id'] for x in result['items']] == ids
                    assert all(x['lifecycle'] == 'persistent' for x in result['items'])

                async def write(rid):
                    for i in range(4):
                        seq = 4 * wave + i + 1
                        start = perf_counter()
                        token = context.set((start, lat))
                        try:
                            row = await ledger.append_event(run_id=rid, sequence=seq, event_type='test')
                        finally:
                            context.reset(token)
                        lat['append'].append(1000 * (perf_counter() - start))
                        assert (row['run_id'], row['sequence']) == (rid, seq)

                async def read(rid):
                    for _ in range(6):
                        start = perf_counter()
                        row = await ledger.get_run(rid)
                        lat['read'].append(1000 * (perf_counter() - start))
                        assert row['run_id'] == rid

                work = [publish(q) for q in queries] + [write(r) for r in runs] + [read(r) for r in runs[:4]]
                random.Random(wave).shuffle(work)
                start = perf_counter()
                await asyncio.gather(*work)
                elapsed = perf_counter() - start
                assert [len(lat[k]) for k in ('publish', 'append', 'first_write', 'read')] == [4, 48, 48, 24]
                assert len(lat['queue']) == (48 if enabled else 0)
                print(json.dumps(dict(wave=wave, seconds=elapsed, **lat)), file=output)
        for rid in runs:
            events, *_ = await ledger.page_run_events(run_id=rid, limit=100)
            assert [row['sequence'] for row in events] == list(range(1, 69))
    finally:
        await engine.dispose()
