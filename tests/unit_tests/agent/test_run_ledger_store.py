"""Tests for RunLedgerStore host primitives."""

from __future__ import annotations

import datetime

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from langbot.pkg.agent.runner.run_ledger_store import RunLedgerStore
from langbot.pkg.entity.persistence.agent_run import AgentRun
from langbot.pkg.entity.persistence.base import Base


UTC = datetime.timezone.utc


@pytest.fixture
async def db_engine(tmp_path):
    db_path = tmp_path / 'run_ledger_store.db'
    engine = create_async_engine(f'sqlite+aiosqlite:///{db_path}', echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
def store(db_engine):
    return RunLedgerStore(db_engine)


@pytest.mark.asyncio
async def test_create_queued_run_claim_renew_release(store):
    run = await store.create_run(
        run_id='run-queued',
        event_id='evt-1',
        binding_id='binding-1',
        runner_id='runner-a',
        status='queued',
        queue_name='default',
        priority=10,
        requested_runtime_id='runtime-a',
    )

    assert run['status'] == 'queued'
    assert run['started_at'] is None
    assert run['queue_name'] == 'default'
    assert run['priority'] == 10
    assert run['requested_runtime_id'] == 'runtime-a'

    assert await store.claim_next_run(runtime_id='runtime-b', queue_name='default') is None

    claimed = await store.claim_next_run(runtime_id='runtime-a', queue_name='default', lease_seconds=30)

    assert claimed is not None
    assert claimed['run_id'] == 'run-queued'
    assert claimed['status'] == 'claimed'
    assert claimed['claimed_by_runtime_id'] == 'runtime-a'
    assert claimed['claim_token']
    assert claimed['dispatch_attempts'] == 1
    assert claimed['claim_lease_expires_at'] is not None
    assert claimed['last_claimed_at'] is not None

    token = claimed['claim_token']
    assert await store.renew_claim(run_id='run-queued', claim_token='wrong-token') is None

    renewed = await store.renew_claim(run_id='run-queued', claim_token=token, lease_seconds=90)

    assert renewed is not None
    assert 'claim_token' not in renewed
    assert renewed['claim_lease_expires_at'] >= claimed['claim_lease_expires_at']

    released = await store.release_claim(
        run_id='run-queued',
        claim_token=token,
        status='queued',
        status_reason='runtime released capacity',
    )

    assert released is not None
    assert released['status'] == 'queued'
    assert released['status_reason'] == 'runtime released capacity'
    assert released['claimed_by_runtime_id'] is None
    assert 'claim_token' not in released
    assert released['claim_lease_expires_at'] is None
    assert released['dispatch_attempts'] == 1


@pytest.mark.asyncio
async def test_claim_next_run_applies_scope_filters(store):
    await store.create_run(
        run_id='run-other-runner',
        event_id='evt-other-runner',
        binding_id='binding-1',
        runner_id='runner-b',
        conversation_id='conv-a',
        bot_id='bot-a',
        workspace_id='workspace-a',
        status='queued',
        queue_name='default',
        priority=30,
    )
    await store.create_run(
        run_id='run-other-conversation',
        event_id='evt-other-conversation',
        binding_id='binding-1',
        runner_id='runner-a',
        conversation_id='conv-b',
        bot_id='bot-a',
        workspace_id='workspace-a',
        status='queued',
        queue_name='default',
        priority=20,
    )
    await store.create_run(
        run_id='run-allowed',
        event_id='evt-allowed',
        binding_id='binding-1',
        runner_id='runner-a',
        conversation_id='conv-a',
        bot_id='bot-a',
        workspace_id='workspace-a',
        status='queued',
        queue_name='default',
        priority=10,
    )

    claimed = await store.claim_next_run(
        runtime_id='runtime-a',
        queue_name='default',
        runner_ids=['runner-a'],
        conversation_id='conv-a',
        bot_id='bot-a',
        workspace_id='workspace-a',
        thread_id=None,
        strict_thread=True,
    )

    assert claimed is not None
    assert claimed['run_id'] == 'run-allowed'


@pytest.mark.asyncio
async def test_expired_claim_can_be_reclaimed(store, db_engine):
    await store.create_run(
        run_id='run-expired',
        event_id='evt-2',
        binding_id='binding-1',
        runner_id='runner-a',
        status='queued',
        queue_name='default',
    )
    first_claim = await store.claim_next_run(runtime_id='runtime-a', queue_name='default', lease_seconds=60)
    assert first_claim is not None

    session_factory = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(
            sqlalchemy.update(AgentRun)
            .where(AgentRun.run_id == 'run-expired')
            .values(claim_lease_expires_at=datetime.datetime.now(UTC) - datetime.timedelta(seconds=1))
        )
        await session.commit()

    reclaimed = await store.claim_next_run(runtime_id='runtime-b', queue_name='default', lease_seconds=60)

    assert reclaimed is not None
    assert reclaimed['run_id'] == 'run-expired'
    assert reclaimed['claimed_by_runtime_id'] == 'runtime-b'
    assert reclaimed['claim_token'] != first_claim['claim_token']
    assert reclaimed['dispatch_attempts'] == 2


@pytest.mark.asyncio
async def test_release_expired_claims_requeues_runs(store, db_engine):
    await store.create_run(
        run_id='run-expired-release',
        event_id='evt-3',
        binding_id='binding-1',
        runner_id='runner-a',
        status='queued',
        queue_name='default',
    )
    await store.create_run(
        run_id='run-active-claim',
        event_id='evt-4',
        binding_id='binding-1',
        runner_id='runner-a',
        status='queued',
        queue_name='default',
    )
    expired_claim = await store.claim_next_run(runtime_id='runtime-a', queue_name='default', lease_seconds=60)
    active_claim = await store.claim_next_run(runtime_id='runtime-b', queue_name='default', lease_seconds=60)
    assert expired_claim is not None
    assert active_claim is not None

    session_factory = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(
            sqlalchemy.update(AgentRun)
            .where(AgentRun.run_id == 'run-expired-release')
            .values(claim_lease_expires_at=datetime.datetime.now(UTC) - datetime.timedelta(seconds=1))
        )
        await session.commit()

    released = await store.release_expired_claims()

    assert [run['run_id'] for run in released] == ['run-expired-release']
    assert released[0]['status'] == 'queued'
    assert released[0]['status_reason'] == 'claim lease expired'
    assert released[0]['claimed_by_runtime_id'] is None
    assert 'claim_token' not in released[0]
    assert released[0]['claim_lease_expires_at'] is None

    active = await store.get_run('run-active-claim')
    assert active is not None
    assert active['status'] == 'claimed'
    assert active['claimed_by_runtime_id'] == active_claim['claimed_by_runtime_id']
    assert 'claim_token' not in active


@pytest.mark.asyncio
async def test_expired_claim_cannot_renew_or_release(store, db_engine):
    await store.create_run(
        run_id='run-stale-claim',
        event_id='evt-stale',
        binding_id='binding-1',
        runner_id='runner-a',
        status='queued',
        queue_name='default',
    )
    claimed = await store.claim_next_run(runtime_id='runtime-a', queue_name='default', lease_seconds=60)
    assert claimed is not None
    token = claimed['claim_token']

    session_factory = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(
            sqlalchemy.update(AgentRun)
            .where(AgentRun.run_id == 'run-stale-claim')
            .values(claim_lease_expires_at=datetime.datetime.now(UTC) - datetime.timedelta(seconds=1))
        )
        await session.commit()

    assert await store.renew_claim(run_id='run-stale-claim', claim_token=token, runtime_id='runtime-a') is None
    assert await store.release_claim(run_id='run-stale-claim', claim_token=token, runtime_id='runtime-a') is None


@pytest.mark.asyncio
async def test_run_status_validation_and_terminal_transition_rules(store):
    with pytest.raises(ValueError, match='Unknown run status'):
        await store.create_run(
            run_id='run-invalid-create',
            event_id='evt-invalid',
            binding_id='binding-1',
            runner_id='runner-a',
            status='bogus',
        )

    await store.create_run(
        run_id='run-invalid-release',
        event_id='evt-release',
        binding_id='binding-1',
        runner_id='runner-a',
        status='queued',
        queue_name='default',
    )
    claim = await store.claim_next_run(runtime_id='runtime-a', queue_name='default')
    assert claim is not None
    with pytest.raises(ValueError, match='Unknown run status'):
        await store.release_claim(
            run_id='run-invalid-release',
            claim_token=claim['claim_token'],
            runtime_id='runtime-a',
            status='bogus',
        )

    await store.create_run(
        run_id='run-terminal',
        event_id='evt-terminal',
        binding_id='binding-1',
        runner_id='runner-a',
    )
    with pytest.raises(ValueError, match='Unknown run status'):
        await store.finalize_run(run_id='run-terminal', status='bogus')

    completed = await store.finalize_run(
        run_id='run-terminal',
        status='completed',
        metadata={'attempt': 1},
    )
    assert completed is not None
    assert completed['status'] == 'completed'

    merged = await store.finalize_run(
        run_id='run-terminal',
        status='completed',
        metadata={'retry_observed': True},
    )
    assert merged is not None
    assert merged['metadata'] == {'attempt': 1, 'retry_observed': True}

    with pytest.raises(ValueError, match='Cannot transition terminal run'):
        await store.finalize_run(run_id='run-terminal', status='failed')


@pytest.mark.asyncio
async def test_append_audit_event_uses_next_sequence(store):
    await store.create_run(
        run_id='run-audit',
        event_id='evt-5',
        binding_id='binding-1',
        runner_id='runner-a',
    )
    await store.append_event(
        run_id='run-audit',
        sequence=1,
        event_type='message.completed',
        data={'ok': True},
    )

    event = await store.append_audit_event(
        run_id='run-audit',
        event_type='admin.run_cancel',
        data={'action': 'run_cancel'},
        metadata={'permission': 'agent_run:admin'},
    )

    assert event is not None
    assert event['sequence'] == 2
    assert event['type'] == 'admin.run_cancel'
    assert event['source'] == 'host'
    assert event['data'] == {'action': 'run_cancel'}
    assert event['metadata'] == {'permission': 'agent_run:admin'}
    assert await store.append_audit_event(run_id='missing', event_type='admin.missing') is None


@pytest.mark.asyncio
async def test_runtime_register_heartbeat_list_and_mark_stale(store):
    registered = await store.register_runtime(
        runtime_id='runtime-a',
        display_name='Runtime A',
        endpoint='http://runtime-a',
        version='1.0.0',
        capabilities={'stream': True},
        labels={'region': 'test'},
        metadata={'slot_count': 2},
        heartbeat_deadline_seconds=30,
    )

    assert registered['runtime_id'] == 'runtime-a'
    assert registered['status'] == 'online'
    assert registered['display_name'] == 'Runtime A'
    assert registered['capabilities'] == {'stream': True}
    assert registered['labels'] == {'region': 'test'}
    assert registered['metadata'] == {'slot_count': 2}
    assert registered['last_heartbeat_at'] is not None
    assert registered['heartbeat_deadline_at'] is not None

    heartbeat = await store.heartbeat_runtime(
        runtime_id='runtime-a',
        metadata={'active_runs': 1},
        heartbeat_deadline_seconds=30,
    )

    assert heartbeat is not None
    assert heartbeat['metadata'] == {'slot_count': 2, 'active_runs': 1}

    runtimes, total_count = await store.list_runtimes(statuses=['online'])
    assert [runtime['runtime_id'] for runtime in runtimes] == ['runtime-a']
    assert total_count == 1

    stale = await store.mark_stale_runtimes(
        now=datetime.datetime.now(UTC) + datetime.timedelta(seconds=31),
    )

    assert [runtime['runtime_id'] for runtime in stale] == ['runtime-a']
    assert stale[0]['status'] == 'stale'
    assert (await store.get_runtime('runtime-a'))['status'] == 'stale'


@pytest.mark.asyncio
async def test_runtime_stats_splits_active_and_claimed_runs(store):
    await store.register_runtime(runtime_id='runtime-a')
    await store.create_run(
        run_id='run-running',
        event_id='evt-running',
        binding_id='binding-1',
        runner_id='runner-a',
        status='running',
    )
    await store.create_run(
        run_id='run-claimed',
        event_id='evt-claimed',
        binding_id='binding-1',
        runner_id='runner-a',
        status='queued',
        queue_name='default',
    )
    assert await store.claim_next_run(runtime_id='runtime-a', queue_name='default') is not None

    stats = await store.get_runtime_stats()

    assert stats['active_runs'] == 2
    assert stats['claimed_runs'] == 1


@pytest.mark.asyncio
async def test_runner_stats_reports_zero_success_rate_for_failed_only_runner(store):
    now = int(datetime.datetime.now(UTC).timestamp())
    await store.create_run(
        run_id='run-failed',
        event_id='evt-failed',
        binding_id='binding-1',
        runner_id='runner-a',
        status='failed',
    )

    stats = await store.get_runner_stats(start_time=now - 10, end_time=now + 10)

    assert stats[0]['runner_id'] == 'runner-a'
    assert stats[0]['failed_runs'] == 1
    assert stats[0]['success_rate'] == 0.0
