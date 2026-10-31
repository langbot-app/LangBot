"""Whole-source metadata, reversible ingress, and bounded candidate selection."""

import datetime as dt
import json
import random
from collections import defaultdict

import pytest
import sqlalchemy as sa

from langbot.pkg.entity.persistence import monitoring as models
from langbot.pkg.entity.persistence.event_log import EventLog
from langbot.pkg.persistence.session_summary_writer import SessionSummaryWriter
from tests.integration.persistence.test_monitoring_postgres import cloud_database as postgres_fixture
from tests.unit_tests.api.service.test_monitoring_sessions import (
    context,
    rebuild_summaries,
    replay_summary_message,
    service as summary_service_fixture,
    session_counts_from_facts,
)


pytestmark = [pytest.mark.asyncio, pytest.mark.session_summary]
service = summary_service_fixture
cloud_database = postgres_fixture
FIELDS = ('bot_name', 'platform', 'user_id', 'user_name', 'pipeline_id', 'pipeline_name')


async def ingress(service, identity, user, pipeline, *, bot='a', owner='group'):
    await service.record_ingress_event(
        context(bot),
        event_id=identity,
        event_type='message.received',
        bot_id=bot,
        bot_name=user,
        platform=user,
        payload={},
        conversation_id=owner,
        actor_id=user,
        actor_name=user,
        routes=[{'target_uuid': pipeline, 'target_type': pipeline}] if pipeline else [],
    )


async def message(service, user, pipeline, *, bot='a', owner='topic', event=None, role='user'):
    return await service.record_message(
        context(bot),
        bot_id=bot,
        bot_name=user or '',
        platform=user,
        pipeline_id=pipeline,
        pipeline_name=pipeline,
        user_id=user,
        user_name=None,
        session_id=owner,
        message_content='hello',
        event_id=event,
        role=role,
    )


async def projection(service):
    return {
        (row['bot_id'], row['session_id']): (row['message_count'], *(row[field] for field in FIELDS))
        for row in (await service.get_sessions(context()))[0]
    }


async def facts(service):
    """Calculate independently from retained sources, never receipts or Writer state."""
    async with service.ap.persistence_mgr.get_db_engine().connect() as connection:
        messages = (await connection.execute(sa.select(models.MonitoringMessage))).mappings().all()
        events = (await connection.execute(sa.select(EventLog))).mappings().all()
    messages = {row['id']: dict(row) for row in messages}
    ingresses = {}
    for row in events:
        metadata = json.loads(row['metadata_json'] or '{}')
        route = next((route for route in metadata.get('routes', []) if route.get('target_uuid')), {})
        ingresses[row['event_id']] = dict(
            bot_id=row['bot_id'],
            session_id=row['conversation_id'],
            timestamp=row['event_time'] or row['created_at'],
            role='user',
            bot_name=metadata.get('bot_name') or '',
            platform=metadata.get('platform'),
            user_id=row['actor_id'],
            user_name=row['actor_name'],
            pipeline_id=route.get('target_uuid') or '',
            pipeline_name=route.get('target_type') or '',
        )
    counts = session_counts_from_facts(messages, ingresses)
    covered = {
        (row['bot_id'], alias)
        for identity, row in messages.items()
        if row['role'] != 'assistant'
        for alias in (identity, row['event_id'])
        if alias is not None
    }
    sources = defaultdict(list)
    for identity, row in messages.items():
        sources[(row['bot_id'], row['session_id'])].append(('message:' + identity, row))
    for identity, row in ingresses.items():
        if (row['bot_id'], identity) not in covered:
            sources[(row['bot_id'], row['session_id'])].append(('event:' + identity, row))
    expected = {}
    for key, entries in sources.items():
        _, selected = max(
            entries,
            key=lambda entry: (
                entry[1]['role'] != 'assistant',
                entry[1]['timestamp'],
                entry[0].encode('utf-8'),
            ),
        )
        expected[key] = (counts[key], *(selected[field] for field in FIELDS))
    return expected


@pytest.mark.contract('summary_fact_equivalence')
@pytest.mark.contract('summary_snapshot')
@pytest.mark.parametrize('transfer', ['message', 'late_link'])
@pytest.mark.parametrize('base', ['message', 'event', 'expired_event', 'legacy'])
async def test_transfer_restores_the_remaining_whole_snapshot(service, transfer, base):
    receipt = models.MonitoringSessionReceipt
    engine = service.ap.persistence_mgr.get_db_engine()
    if base == 'legacy':
        async with engine.begin() as connection:
            await connection.execute(
                sa.insert(models.MonitoringSession).values(
                    workspace_uuid='workspace',
                    bot_id='a',
                    session_id='group',
                    bot_name='Alice',
                    platform='Alice',
                    user_id='Alice',
                    user_name='Alice',
                    pipeline_id='A',
                    pipeline_name='A',
                    message_count=99,
                    start_time=dt.datetime(2026, 1, 1),
                    last_activity=dt.datetime(2026, 1, 1),
                )
            )
    elif base == 'message':
        await message(service, 'Alice', 'A', owner='group')
    else:
        await ingress(service, 'alice-event', 'Alice', 'A')
        if base == 'expired_event':
            assert (
                await service._delete_expired_in_batches(
                    context(),
                    receipt,
                    receipt.timestamp,
                    receipt.source_key,
                    dt.datetime(2100, 1, 1),
                    1,
                    1,
                )
                == 1
            )
    baseline = await projection(service)
    await ingress(service, 'bob-event', 'Bob', 'B')
    identity = await message(service, 'Bob', 'B', event='bob-event' if transfer == 'message' else None)
    if transfer == 'late_link':
        await service.link_execution_message(context(), identity, 'run', 'bob-event')
        await service.link_execution_message(context(), identity, 'run', 'bob-event')
    projected = await projection(service)
    assert projected['a', 'group'] == baseline['a', 'group']
    assert projected['a', 'topic'][0] == 1
    if base in ('message', 'event'):
        assert projected == await facts(service)
        await rebuild_summaries(service, batch_size=1)
        assert await projection(service) == projected


@pytest.mark.contract('summary_retention')
@pytest.mark.contract('summary_atomicity')
@pytest.mark.contract('summary_snapshot')
@pytest.mark.parametrize('rollback', [False, True])
async def test_expiry_seals_the_selected_candidate_atomically(service, monkeypatch, rollback):
    await ingress(service, 'alice-event', 'Alice', 'A')
    before = await projection(service)
    receipt = models.MonitoringSessionReceipt
    async with service.ap.persistence_mgr.get_db_engine().begin() as connection:
        await connection.execute(
            sa.update(receipt)
            .where(receipt.source_key == 'event:alice-event')
            .values(
                timestamp=dt.datetime(2000, 1, 1),
            )
        )
    if rollback:
        original = SessionSummaryWriter._merge_base

        async def abort_after_seal(self, *args):
            await original(self, *args)
            raise RuntimeError('abort seal')

        with monkeypatch.context() as patch:
            patch.setattr(SessionSummaryWriter, '_merge_base', abort_after_seal)
            with pytest.raises(RuntimeError, match='abort seal'):
                await service.cleanup_expired_records(
                    context(), retention_days=1, batch_size=1, max_batches_per_table=1
                )
        assert await projection(service) == before
        async with service.ap.persistence_mgr.get_db_engine().connect() as connection:
            assert (await connection.execute(sa.select(sa.func.count()).select_from(receipt))).scalar_one() == 1
    deleted = await service.cleanup_expired_records(context(), retention_days=1, batch_size=1, max_batches_per_table=1)
    assert deleted['monitoring_session_receipts'] == 1
    assert await projection(service) == before
    await ingress(service, 'bob-event', 'Bob', 'B')
    identity = await message(service, 'Bob', 'B')
    await service.link_execution_message(context(), identity, 'run', 'bob-event')
    assert (await projection(service))['a', 'group'] == before['a', 'group']


@pytest.mark.contract('summary_fact_equivalence')
@pytest.mark.contract('summary_snapshot')
@pytest.mark.parametrize('seed', [17, 43, 97])
async def test_every_randomized_write_replay_and_link_matches_source_facts(service, seed):
    rng = random.Random(seed)
    events, messages = {}, []
    for index in range(45):
        operation = rng.choice(('ingress', 'ingress', 'message', 'message', 'replay', 'link'))
        bot = rng.choice(('a', 'b'))
        if operation == 'ingress':
            if events and rng.randrange(3) == 0:
                event = rng.choice(list(events))
                bot, owner, user, pipeline = events[event]
            else:
                event, owner = f'event-{index}', rng.choice(('group', 'topic'))
                user, pipeline = rng.choice(('Alice', 'Bob', 'Carol')), rng.choice(('A', 'B', '', '__discard__'))
                events[event] = bot, owner, user, pipeline
            await ingress(service, event, user, pipeline, bot=bot, owner=owner)
        elif operation == 'message':
            event = rng.choice(list(events)) if events and rng.randrange(2) else None
            if event:
                bot = events[event][0]
            identity = await message(
                service,
                rng.choice(('Alice', None)),
                rng.choice(('A', 'B', '', '__discard__')),
                bot=bot,
                owner=rng.choice(('group', 'topic')),
                event=event,
                role=rng.choice(('user', 'assistant')),
            )
            messages.append(identity)
        elif operation == 'replay' and messages:
            await replay_summary_message(service, 'workspace', rng.choice(messages))
        elif operation == 'link' and events and messages:
            async with service.ap.persistence_mgr.get_db_engine().connect() as connection:
                unlinked = (
                    await connection.execute(
                        sa.select(models.MonitoringMessage.id, models.MonitoringMessage.bot_id).where(
                            models.MonitoringMessage.event_id.is_(None),
                            models.MonitoringMessage.role != 'assistant',
                        )
                    )
                ).all()
            if unlinked:
                identity, bot = rng.choice(unlinked)
                matching = [key for key, value in events.items() if value[0] == bot]
                if matching:
                    await service.link_execution_message(context(), identity, 'run', rng.choice(matching))
        assert await projection(service) == await facts(service), (seed, index, operation)
    expected = await projection(service)
    await rebuild_summaries(service, batch_size=1)
    assert await projection(service) == expected


@pytest.mark.contract('summary_retention')
@pytest.mark.contract('summary_snapshot')
async def test_receipt_expiry_uses_source_identity_instead_of_message_role(service):
    await message(service, 'Alice', 'A', owner='group', role='event')
    before = await projection(service)
    receipt = models.MonitoringSessionReceipt
    async with service.ap.persistence_mgr.get_db_engine().begin() as connection:
        await connection.execute(
            sa.update(receipt)
            .where(receipt.source_key.startswith('message:'))
            .values(timestamp=dt.datetime(2000, 1, 1))
        )
    deleted = await service.cleanup_expired_records(context(), 1, batch_size=1, max_batches_per_table=1)
    assert deleted['monitoring_session_receipts'] == 1
    assert await projection(service) == before


@pytest.mark.contract('summary_retention')
@pytest.mark.contract('summary_snapshot')
async def test_candidate_selection_work_does_not_grow_with_ingress_history(service):
    receipt = models.MonitoringSessionReceipt
    engine = service.ap.persistence_mgr.get_db_engine()
    await ingress(service, 'seed', 'Alice', 'A')
    measurements = []
    for size in (100, 10000):
        timestamp = dt.datetime(2026, 1, 1)
        async with engine.begin() as connection:
            await connection.execute(sa.delete(receipt))
            await connection.execute(
                sa.insert(receipt),
                [
                    dict(
                        workspace_uuid='workspace',
                        bot_id='a',
                        session_id='group',
                        source_key=f'event:{index:08}',
                        role='event',
                        covered=False,
                        timestamp=timestamp,
                        source_timestamp=timestamp,
                        candidate_snapshot=json.dumps(
                            dict(
                                source_key=f'event:{index:08}',
                                timestamp=timestamp.isoformat(),
                                role='user',
                                bot_name='Alice',
                                platform=None,
                                user_id=str(index),
                                user_name=None,
                                pipeline_id='',
                                pipeline_name='',
                            )
                        ),
                    )
                    for index in range(size)
                ],
            )
        steps = [0]

        def tick():
            steps[0] += 1
            return 0

        async def handler(callback):
            async with engine.connect() as connection:
                await connection.run_sync(
                    lambda sync: sync.connection.dbapi_connection.run_async(
                        lambda raw: raw._execute(raw._conn.set_progress_handler, callback, 1),
                    )
                )

        await handler(tick)
        try:
            async with service._summary_session('workspace') as session:
                await SessionSummaryWriter('sqlite')._refresh(session, 'workspace', 'a', 'group')
        finally:
            await handler(None)
        measurements.append(steps[0])
        assert (await service.get_sessions(context()))[0][0]['user_id'] == str(size - 1)
    assert measurements[1] <= measurements[0] + 30, measurements


@pytest.mark.asyncio(loop_scope='module')
@pytest.mark.postgres
@pytest.mark.contract('summary_postgres')
@pytest.mark.contract('summary_retention')
@pytest.mark.contract('summary_snapshot')
async def test_postgres_expiry_and_late_link_restore_the_same_snapshot(cloud_database, monkeypatch):
    """Force a late link to wait on a summary locked by ingress expiry."""
    import asyncio
    from tests.integration.persistence.test_monitoring_postgres import WORKSPACE_A, _context, _read

    ap, admin = cloud_database
    monitoring = ap.monitoring_service
    ctx = _context(WORKSPACE_A)
    bot = 'snapshot-expiry-race'
    for user, pipeline in [('Alice', 'A'), ('Bob', 'B')]:
        await monitoring.record_ingress_event(
            ctx,
            event_id=bot + user,
            event_type='message.received',
            bot_id=bot,
            bot_name=user,
            platform=user,
            payload={},
            conversation_id='group',
            actor_id=user,
            actor_name=user,
            routes=[{'target_uuid': pipeline, 'target_type': pipeline}],
        )
    identity = await monitoring.record_message(
        ctx,
        bot_id=bot,
        bot_name='Bob',
        pipeline_id='B',
        pipeline_name='B',
        platform='Bob',
        user_id='Bob',
        user_name='Bob',
        session_id='topic',
        message_content='hello',
    )
    receipt = models.MonitoringSessionReceipt
    async with admin.begin() as connection:
        await connection.execute(
            sa.update(receipt)
            .where(
                receipt.workspace_uuid == WORKSPACE_A,
                receipt.bot_id == bot,
                receipt.source_key == 'event:' + bot + 'Alice',
            )
            .values(timestamp=dt.datetime(2000, 1, 1))
        )
    sealed, release, attempted = (asyncio.Event() for _ in range(3))
    original = SessionSummaryWriter._merge_base
    cover_task = None
    cover_pid = None

    async def pause_seal(self, session, workspace, bot_id, owner, snapshot):
        await original(self, session, workspace, bot_id, owner, snapshot)
        if bot_id == bot and snapshot['source_key'] == 'event:' + bot + 'Alice':
            sealed.set()
            await asyncio.wait_for(release.wait(), 5)

    def observe_sql(connection, cursor, sql, parameters, execution, executemany):
        nonlocal cover_pid
        statement = getattr(execution.compiled, 'statement', None)
        if asyncio.current_task() is cover_task and getattr(statement, '_for_update_arg', None) is not None:
            cover_pid = connection.connection.driver_connection.get_server_pid()
            attempted.set()

    monkeypatch.setattr(SessionSummaryWriter, '_merge_base', pause_seal)
    engine = ap.persistence_mgr.get_db_engine()
    sa.event.listen(engine.sync_engine, 'before_cursor_execute', observe_sql)
    expiry_task = asyncio.create_task(monitoring.cleanup_expired_records(ctx, 1, batch_size=1, max_batches_per_table=1))
    try:
        await asyncio.wait_for(sealed.wait(), 5)
        cover_task = asyncio.create_task(monitoring.link_execution_message(ctx, identity, 'run', bot + 'Bob'))
        await asyncio.wait_for(attempted.wait(), 5)
        async with asyncio.timeout(5):
            while True:
                async with admin.connect() as connection:
                    if await connection.scalar(
                        sa.text("SELECT wait_event_type='Lock' FROM pg_stat_activity WHERE pid=:pid"),
                        {'pid': cover_pid},
                    ):
                        break
                await asyncio.sleep(0.01)
        release.set()
        deleted, _ = await asyncio.wait_for(asyncio.gather(expiry_task, cover_task), 10)
        assert deleted['monitoring_session_receipts'] == 1
    finally:
        release.set()
        sa.event.remove(engine.sync_engine, 'before_cursor_execute', observe_sql)
        tasks = [task for task in (expiry_task, cover_task) if task is not None]
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    rows, _ = await _read(monitoring, 'get_sessions', ctx, bot_ids=[bot])
    rows = {row['session_id']: row for row in rows}
    assert rows['group']['message_count'] == rows['topic']['message_count'] == 1
    assert tuple(rows['group'][field] for field in FIELDS) == ('Alice', 'Alice', 'Alice', 'Alice', 'A', 'A')


@pytest.mark.asyncio(loop_scope='module')
@pytest.mark.postgres
@pytest.mark.contract('summary_postgres')
@pytest.mark.contract('summary_snapshot')
async def test_postgres_candidate_query_uses_a_bounded_index_scan(cloud_database):
    """Explain the Writer's actual candidate query, rather than a test-only query."""
    ap, admin = cloud_database
    from tests.integration.persistence.test_monitoring_postgres import WORKSPACE_A, _context

    monitoring = ap.monitoring_service
    ctx = _context(WORKSPACE_A)
    bot = 'snapshot-scale'
    await monitoring.record_ingress_event(
        ctx,
        event_id=bot,
        event_type='message.received',
        bot_id=bot,
        bot_name='Bot',
        platform=None,
        payload={},
        conversation_id='group',
        actor_id='Alice',
    )
    receipt = models.MonitoringSessionReceipt
    captured = []

    def observe_sql(connection, statement, multiparams, params, execution_options):
        # before_cursor_execute can expose an older statement's bound values
        # from the compilation cache. Explain this invocation's statement.
        if getattr(statement, 'is_select', False) and 'candidate_snapshot' in statement.selected_columns:
            captured.append(statement)

    engine = ap.persistence_mgr.get_db_engine()
    sa.event.listen(engine.sync_engine, 'before_execute', observe_sql)
    try:
        for size in (100, 10000):
            timestamp = dt.datetime(2026, 1, 1)
            async with admin.begin() as connection:
                await connection.execute(
                    sa.delete(receipt).where(receipt.workspace_uuid == WORKSPACE_A, receipt.bot_id == bot)
                )
                await connection.execute(
                    sa.insert(receipt),
                    [
                        dict(
                            workspace_uuid=WORKSPACE_A,
                            bot_id=bot,
                            session_id='group',
                            source_key=f'event:{i:08}',
                            role='event',
                            covered=False,
                            timestamp=timestamp,
                            source_timestamp=timestamp,
                            candidate_snapshot=json.dumps(
                                dict(
                                    source_key=f'event:{i:08}',
                                    timestamp=timestamp.isoformat(),
                                    role='user',
                                    bot_name='Bot',
                                    platform=None,
                                    user_id='Alice',
                                    user_name=None,
                                    pipeline_id='',
                                    pipeline_name='',
                                )
                            ),
                        )
                        for i in range(size)
                    ],
                )
                await connection.execute(sa.text('ANALYZE monitoring_session_receipts'))
            captured.clear()
            async with monitoring._summary_session(WORKSPACE_A) as session:
                await monitoring._summary_writer()._refresh(session, WORKSPACE_A, bot, 'group')
            # The summary read also selects base_snapshot; only receipt candidate
            # queries have this selected column. A full candidate scan must fail.
            assert len(captured) == 1
            sql = str(captured[0].compile(dialect=admin.dialect, compile_kwargs={'literal_binds': True}))
            async with admin.connect() as connection:
                explain = (
                    await connection.execute(sa.text('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + sql))
                ).scalar_one()
            plan = (json.loads(explain) if isinstance(explain, str) else explain)[0]['Plan']

            def walk(node):
                yield node
                for child in node.get('Plans', []):
                    yield from walk(child)

            nodes = list(walk(plan))
            assert any(node.get('Index Name') == 'ix_session_receipts_candidate' for node in nodes), plan
            assert not any(node['Node Type'] in ('Seq Scan', 'Sort') for node in nodes), plan
            assert plan['Actual Rows'] == 1
            assert plan.get('Shared Hit Blocks', 0) + plan.get('Shared Read Blocks', 0) < 25, plan
    finally:
        sa.event.remove(engine.sync_engine, 'before_execute', observe_sql)
