"""Runner timestamp contract against real asyncpg and published schema DDL.

Run only on a disposable PostgreSQL via TEST_POSTGRES_URL. Each case owns a
unique schema and an unprivileged role; no existing tables or policies change.
"""

from __future__ import annotations

import datetime as dt
import importlib
import os
import uuid
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.agent.runner import event_log_store, run_ledger_store, transcript_store
from langbot.pkg.agent.runner.run_journal import AgentRunJournal
from langbot.pkg.entity.persistence.agent_run import AgentRun, AgentRunEvent, AgentRuntime
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.event_log import EventLog
from langbot.pkg.entity.persistence.transcript import Transcript

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.asyncio,
]

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 22, 4, 5, 6, 123000, tzinfo=UTC)
TABLES = [AgentRun.__table__, AgentRunEvent.__table__, AgentRuntime.__table__, EventLog.__table__, Transcript.__table__]


def _published_schema(connection):
    with Operations.context(MigrationContext.configure(connection)):
        for revision in (
            '58846a8d7a81_add_event_log_and_transcript_tables',
            '8d3a1f2c4b6e_add_agent_run_ledger',
            '0036_execution_host_leases',
        ):
            importlib.import_module(f'langbot.pkg.persistence.alembic.versions.{revision}').upgrade()


@pytest.fixture(params=['metadata', 'published_migrations'])
async def pg_engine(request, monkeypatch):
    url = os.environ.get('TEST_POSTGRES_URL')
    if not url:
        pytest.skip('TEST_POSTGRES_URL is required (disposable PostgreSQL)')
    namespace = f'runner_ts_{uuid.uuid4().hex}'
    admin = create_async_engine(url)
    engine = None
    try:
        async with admin.begin() as conn:
            await conn.execute(sa.text(f'CREATE ROLE {namespace} NOLOGIN NOSUPERUSER NOBYPASSRLS'))
            await conn.execute(sa.text(f'CREATE SCHEMA {namespace} AUTHORIZATION {namespace}'))
        engine = create_async_engine(
            url,
            connect_args={
                'server_settings': {'search_path': namespace, 'role': namespace, 'timezone': 'Asia/Shanghai'}
            },
        )
        async with engine.begin() as conn:
            role = (
                await conn.execute(sa.text('SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user'))
            ).one()
            assert role == (False, False)
            if request.param == 'metadata':
                await conn.run_sync(lambda sync: Base.metadata.create_all(sync, tables=TABLES))
            else:
                await conn.run_sync(_published_schema)
            columns = (
                await conn.execute(
                    sa.text(
                        'SELECT table_name, column_name, data_type FROM information_schema.columns '
                        "WHERE table_schema = current_schema() AND data_type LIKE 'timestamp%'"
                    )
                )
            ).all()
            assert columns
            assert all(column.data_type == 'timestamp without time zone' for column in columns)
        for module in (run_ledger_store, event_log_store, transcript_store):
            monkeypatch.setattr(module, '_utc_now', lambda: NOW)
        yield engine
    finally:
        if engine is not None:
            await engine.dispose()
        async with admin.begin() as conn:
            await conn.execute(sa.text(f'DROP SCHEMA IF EXISTS {namespace} CASCADE'))
            await conn.execute(sa.text(f'DROP ROLE IF EXISTS {namespace}'))
        await admin.dispose()


async def _legacy_run(engine, *, status='queued'):
    """An existing UTC-naive row must remain readable/updatable without DDL."""
    async with engine.begin() as conn:
        await conn.execute(
            sa.insert(AgentRun).values(
                run_id='legacy',
                runner_id='runner',
                status=status,
                created_at=NOW.replace(tzinfo=None),
                updated_at=(NOW - dt.timedelta(minutes=1)).replace(tzinfo=None),
                claim_token='old-token' if status == 'claimed' else None,
                claimed_by_runtime_id='old-runtime' if status == 'claimed' else None,
                claim_lease_expires_at=(NOW - dt.timedelta(seconds=1)).replace(tzinfo=None)
                if status == 'claimed'
                else None,
            )
        )


@pytest.mark.contract('runner_timestamps')
async def test_run_lifecycle_deadline_events_and_stats(pg_engine):
    store = run_ledger_store.RunLedgerStore(pg_engine)
    deadline = NOW + dt.timedelta(minutes=5)
    journal = AgentRunJournal(SimpleNamespace(persistence_mgr=SimpleNamespace(get_db_engine=lambda: pg_engine)))
    created = await journal.create_run(
        event=SimpleNamespace(
            event_id='event',
            conversation_id='conversation',
            thread_id=None,
            workspace_id='workspace-a',
            bot_id=None,
            event_type='message.received',
            source='debug',
            data={},
            delivery=SimpleNamespace(model_dump=lambda **kwargs: {}),
        ),
        binding=SimpleNamespace(binding_id='binding', agent_id='agent', processor_id='agent', processor_type='agent'),
        descriptor=SimpleNamespace(id='runner'),
        context={'run_id': 'debug-run', 'runtime': {'deadline_at': deadline.timestamp()}, 'input': {'text': 'test'}},
        authorization={},
    )
    assert created['created_at'] == int(NOW.timestamp())
    assert created['created_at_ms'] == round(NOW.timestamp() * 1000)
    assert created['started_at_ms'] == created['created_at_ms']
    assert created['deadline_at'] == int(deadline.timestamp())
    assert await store.get_run('debug-run') == created
    assert (
        await store.create_run(
            run_id='debug-run',
            event_id=None,
            binding_id=None,
            runner_id='runner',
        )
    ) == created
    event = await store.append_event(
        run_id='debug-run', sequence=1, event_type='message.completed', data={'text': 'ok'}
    )
    assert event['created_at'] == int(NOW.timestamp())
    assert await store.append_event(run_id='debug-run', sequence=1, event_type='duplicate') == event
    audit = await store.append_audit_event(run_id='debug-run', event_type='host.cancel_requested')
    assert audit['sequence'] == 2
    assert audit['created_at'] == int(NOW.timestamp())
    cancelled = await store.request_cancel(run_id='debug-run')
    assert cancelled['cancel_requested_at'] == int(NOW.timestamp())
    finished = await store.finalize_run(run_id='debug-run', status='completed')
    assert finished['finished_at_ms'] == round(NOW.timestamp() * 1000)
    assert await store.get_run('debug-run') == finished
    events, _, _, has_more = await store.page_run_events(run_id='debug-run')
    assert [row['sequence'] for row in events] == [1, 2]
    assert not has_more
    window = {'start_time': int(NOW.timestamp()) - 1, 'end_time': int(NOW.timestamp()) + 1}
    assert (await store.get_run_stats(**window))['completed_count'] == 1
    assert (await store.get_runner_stats(**window))[0]['completed_runs'] == 1
    async with pg_engine.connect() as conn:
        raw = (await conn.execute(sa.select(AgentRun.created_at, AgentRun.deadline_at))).one()
        assert raw == (NOW.replace(tzinfo=None), deadline.replace(tzinfo=None))


async def test_claim_renew_release_existing_naive_row(pg_engine):
    await _legacy_run(pg_engine)
    store = run_ledger_store.RunLedgerStore(pg_engine)
    claimed = await store.claim_next_run(runtime_id='runtime', lease_seconds=30)
    assert claimed['last_claimed_at'] == int(NOW.timestamp())
    token = claimed['claim_token']
    assert await store.validate_active_claim(run_id='legacy', runtime_id='runtime', claim_token=token)
    assert await store.renew_claim(run_id='legacy', claim_token='wrong') is None
    renewed = await store.renew_claim(run_id='legacy', claim_token=token, lease_seconds=90)
    assert renewed['claim_lease_expires_at'] == int(NOW.timestamp()) + 90
    released = await store.release_claim(run_id='legacy', claim_token=token, status='cancelled')
    assert released['finished_at'] == int(NOW.timestamp())
    assert released['claim_lease_expires_at'] is None
    assert await store.get_run('legacy') == released


async def test_reclaim_expired_naive_lease(pg_engine):
    await _legacy_run(pg_engine, status='claimed')
    store = run_ledger_store.RunLedgerStore(pg_engine)
    assert not await store.validate_active_claim(run_id='legacy', runtime_id='old-runtime', claim_token='old-token')
    assert await store.release_claim(run_id='legacy', claim_token='old-token') is None
    claimed = await store.claim_next_run(runtime_id='replacement')
    assert claimed['claimed_by_runtime_id'] == 'replacement'
    assert claimed['claim_token'] != 'old-token'


@pytest.mark.parametrize('offset', [None, 0, 8, -7])
async def test_expired_claim_cutoff_accepts_naive_and_offset_times(pg_engine, offset):
    await _legacy_run(pg_engine, status='claimed')
    store = run_ledger_store.RunLedgerStore(pg_engine)
    cutoff = NOW.replace(tzinfo=None) if offset is None else NOW.astimezone(dt.timezone(dt.timedelta(hours=offset)))
    released = await store.release_expired_claims(now=cutoff, status='timeout')
    assert len(released) == 1
    assert released[0]['updated_at'] == int(NOW.timestamp())
    assert released[0]['finished_at'] == int(NOW.timestamp())
    assert not await store.validate_active_claim(run_id='legacy', runtime_id='old-runtime', claim_token='old-token')


@pytest.mark.parametrize('offset', [None, 8, -7])
async def test_runtime_heartbeat_stale_cutoffs_and_stats(pg_engine, offset):
    store = run_ledger_store.RunLedgerStore(pg_engine)
    registered = await store.register_runtime(runtime_id='runtime', heartbeat_deadline_seconds=30)
    assert registered['last_heartbeat_at'] == int(NOW.timestamp())
    heartbeat = await store.heartbeat_runtime(runtime_id='runtime', heartbeat_deadline_seconds=60)
    assert heartbeat['heartbeat_deadline_at'] == int(NOW.timestamp()) + 60
    assert (await store.get_runtime_stats())['avg_heartbeat_age_seconds'] == 0
    later = NOW + dt.timedelta(seconds=61)
    cutoff = later.replace(tzinfo=None) if offset is None else later.astimezone(dt.timezone(dt.timedelta(hours=offset)))
    stale = await store.mark_stale_runtimes(now=cutoff, stale_after_seconds=60)
    assert len(stale) == 1
    assert stale[0]['updated_at'] == int(later.timestamp())
    assert (await store.get_runtime('runtime'))['status'] == 'stale'


@pytest.mark.parametrize('offset', [None, 8, -7])
async def test_event_log_timestamp_and_retention(pg_engine, offset):
    store = event_log_store.EventLogStore(pg_engine)
    event_time = NOW.replace(tzinfo=None) if offset is None else NOW.astimezone(dt.timezone(dt.timedelta(hours=offset)))
    await store.append_event(event_id='event', event_type='message', source='test', event_time=event_time)
    async with pg_engine.connect() as conn:
        row = (await conn.execute(sa.select(EventLog.event_time, EventLog.created_at))).one()
        assert row == (NOW.replace(tzinfo=None), NOW.replace(tzinfo=None))
    assert await store.cleanup_events_older_than(event_time) == 0
    assert await store.cleanup_events_older_than(event_time + dt.timedelta(seconds=1)) == 1


@pytest.mark.parametrize('offset', [None, 8, -7])
async def test_transcript_timestamp_and_retention(pg_engine, offset):
    store = transcript_store.TranscriptStore(pg_engine)
    await store.append_transcript(
        transcript_id='transcript', event_id='event', conversation_id='conversation', role='assistant'
    )
    async with pg_engine.connect() as conn:
        raw = (await conn.execute(sa.select(Transcript.created_at))).scalar_one()
        assert raw == NOW.replace(tzinfo=None)
    cutoff = NOW.replace(tzinfo=None) if offset is None else NOW.astimezone(dt.timezone(dt.timedelta(hours=offset)))
    assert await store.cleanup_transcripts_older_than(cutoff) == 0
    assert await store.cleanup_transcripts_older_than(cutoff + dt.timedelta(seconds=1)) == 1
