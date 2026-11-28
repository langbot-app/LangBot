"""Lease maintenance cost follows in-flight work, never the number of Workspaces."""

import datetime
import importlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.agent.runner.run_ledger_store import RunLedgerStore
from langbot.pkg.entity.persistence import user, workspace  # noqa: F401
from langbot.pkg.entity.persistence.agent_run import AgentRun
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.execution_lease import ExecutionLeaseScope
from langbot.pkg.entity.persistence.monitoring import MonitoringMessage
from langbot.pkg.utils import execution_lease
from langbot.pkg.utils.execution_lease import (
    INTERRUPTED_REASON,
    LEASE_SECONDS,
    TICK_SECONDS,
    register_execution_scope,
    run_execution_lease_tick,
)

MIGRATION = importlib.import_module('langbot.pkg.persistence.alembic.versions.0046_execution_lease_scopes')
NOW = datetime.datetime(2026, 11, 6, 5, 29, 54)


@pytest.fixture(autouse=True)
def _clear_scope_cache():
    execution_lease._scope_written_at.clear()
    execution_lease._scope_used_at.clear()
    yield
    execution_lease._scope_written_at.clear()
    execution_lease._scope_used_at.clear()


@pytest.fixture
async def engine():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


def _seconds(value):
    return datetime.timedelta(seconds=value)


async def _add_run(engine, run_id, workspace_id, owner, expires_at, status='running'):
    async with engine.begin() as conn:
        await conn.execute(
            sa.insert(AgentRun).values(
                run_id=run_id,
                runner_id='runner',
                workspace_id=workspace_id,
                status=status,
                execution_owner_id=owner,
                execution_lease_expires_at=expires_at,
            )
        )


async def _add_pending(engine, message_id, workspace_uuid, owner, expires_at):
    async with engine.begin() as conn:
        await conn.execute(
            sa.insert(MonitoringMessage).values(
                id=message_id,
                workspace_uuid=workspace_uuid,
                timestamp=NOW,
                bot_id='bot',
                bot_name='bot',
                pipeline_id='pipeline',
                pipeline_name='pipeline',
                message_content='hello',
                session_id='session',
                status='pending',
                level='info',
                execution_owner_id=owner,
                execution_lease_expires_at=expires_at,
            )
        )


async def _runs(engine):
    async with engine.connect() as conn:
        return {row['run_id']: row for row in (await conn.execute(sa.select(AgentRun))).mappings()}


async def _scopes(engine):
    async with engine.connect() as conn:
        return {
            (row.owner_id, row.workspace_uuid): row
            for row in (await conn.execute(sa.select(ExecutionLeaseScope))).all()
        }


@pytest.mark.asyncio
async def test_long_run_survives_many_ticks_with_many_idle_workspaces(engine):
    """Regression for LANG-326: a 4.5 minute run was reaped by its own live Host."""
    for index in range(300):
        await _add_run(engine, f'history-{index}', f'idle-{index}', 'host-a', NOW - _seconds(3600), 'completed')
    await register_execution_scope(engine, 'busy', now=NOW, owner_id='host-a')
    await _add_run(engine, 'long', 'busy', 'host-a', NOW + _seconds(LEASE_SECONDS))
    await _add_pending(engine, 'user-message', 'busy', 'host-a', NOW + _seconds(LEASE_SECONDS))

    for tick in range(1, 31):  # ten minutes of maintenance
        assert await run_execution_lease_tick(engine, now=NOW + _seconds(tick * TICK_SECONDS), owner_id='host-a') == 0

    runs = await _runs(engine)
    assert runs['long']['status'] == 'running'
    assert runs['long']['execution_lease_expires_at'] == NOW + _seconds(30 * TICK_SECONDS + LEASE_SECONDS)
    async with engine.connect() as conn:
        assert (await conn.execute(sa.select(MonitoringMessage.status))).scalar_one() == 'pending'


@pytest.mark.asyncio
@pytest.mark.parametrize('idle_workspaces', [10, 500])
async def test_tick_statement_count_is_independent_of_workspace_count(engine, idle_workspaces):
    for index in range(idle_workspaces):
        await _add_run(engine, f'history-{index}', f'idle-{index}', 'host-a', NOW - _seconds(3600), 'completed')
    await register_execution_scope(engine, 'busy', now=NOW, owner_id='host-a')
    await _add_run(engine, 'live', 'busy', 'host-a', NOW + _seconds(LEASE_SECONDS))

    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    sa.event.listen(engine.sync_engine, 'before_cursor_execute', capture)
    try:
        await run_execution_lease_tick(engine, now=NOW + _seconds(TICK_SECONDS), owner_id='host-a')
    finally:
        sa.event.remove(engine.sync_engine, 'before_cursor_execute', capture)
    # Scope renewal + own-scope listing, two models per active Workspace, expired-scope listing.
    assert len(statements) <= 12, statements


@pytest.mark.asyncio
async def test_dead_host_scope_is_reaped_then_removed(engine):
    await register_execution_scope(engine, 'workspace', now=NOW, owner_id='dead-host')
    await _add_run(engine, 'orphan', 'workspace', 'dead-host', NOW + _seconds(LEASE_SECONDS))
    await _add_pending(engine, 'orphan-message', 'workspace', 'dead-host', NOW + _seconds(LEASE_SECONDS))
    await _add_run(engine, 'remote', 'workspace', 'dead-host', NOW - _seconds(1))
    async with engine.begin() as conn:
        await conn.execute(sa.update(AgentRun).where(AgentRun.run_id == 'remote').values(queue_name='remote'))

    # Before expiry another Host leaves the live owner alone.
    assert await run_execution_lease_tick(engine, now=NOW + _seconds(60), owner_id='host-b') == 0
    assert (await _runs(engine))['orphan']['status'] == 'running'

    later = NOW + _seconds(LEASE_SECONDS + 1)
    assert await run_execution_lease_tick(engine, now=later, owner_id='host-b') == 2
    runs = await _runs(engine)
    assert runs['orphan']['status'] == 'failed'
    assert runs['orphan']['status_reason'] == INTERRUPTED_REASON
    assert runs['remote']['status'] == 'running'
    assert await _scopes(engine) == {}


@pytest.mark.asyncio
async def test_dead_scope_with_unexpired_rows_waits_for_their_expiry(engine):
    await register_execution_scope(engine, 'workspace', now=NOW, owner_id='dead-host')
    await _add_run(engine, 'orphan', 'workspace', 'dead-host', NOW + _seconds(LEASE_SECONDS + 10))

    later = NOW + _seconds(LEASE_SECONDS + 1)
    assert await run_execution_lease_tick(engine, now=later, owner_id='host-b') == 0
    assert ('dead-host', 'workspace') in await _scopes(engine)
    assert await run_execution_lease_tick(engine, now=later + _seconds(TICK_SECONDS), owner_id='host-b') == 1
    assert await _scopes(engine) == {}


@pytest.mark.asyncio
async def test_own_scope_is_dropped_only_when_idle(engine):
    await register_execution_scope(engine, 'workspace', now=NOW, owner_id='host-a')
    # Registered but its row is not written yet: the scope must stay.
    await run_execution_lease_tick(engine, now=NOW + _seconds(TICK_SECONDS), owner_id='host-a')
    assert ('host-a', 'workspace') in await _scopes(engine)

    execution_lease._scope_used_at[('host-a', 'workspace')] -= LEASE_SECONDS
    await run_execution_lease_tick(engine, now=NOW + _seconds(2 * TICK_SECONDS), owner_id='host-a')
    assert await _scopes(engine) == {}

    # The next execution re-registers instead of trusting the stale cache.
    await register_execution_scope(engine, 'workspace', now=NOW, owner_id='host-a')
    assert ('host-a', 'workspace') in await _scopes(engine)


@pytest.mark.asyncio
async def test_registration_is_cached_within_a_tick(engine):
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        if 'execution_lease_scopes' in statement:
            statements.append(statement)

    sa.event.listen(engine.sync_engine, 'before_cursor_execute', capture)
    try:
        for _ in range(20):
            await register_execution_scope(engine, 'workspace', now=NOW, owner_id='host-a')
    finally:
        sa.event.remove(engine.sync_engine, 'before_cursor_execute', capture)
    assert len(statements) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('state', ['foreign', 'gone'])
async def test_unreapable_scopes_are_not_touched(engine, state):
    await register_execution_scope(engine, 'workspace', now=NOW, owner_id='dead-host')
    await _add_run(engine, 'orphan', 'workspace', 'dead-host', NOW)
    later = NOW + _seconds(LEASE_SECONDS + 1)

    async def check(workspace_uuid):
        return state

    assert await run_execution_lease_tick(engine, now=later, owner_id='host-b', check_workspace=check) == 0
    assert (await _runs(engine))['orphan']['status'] == 'running'
    scopes = await _scopes(engine)
    if state == 'foreign':
        assert scopes[('dead-host', 'workspace')].expires_at > later
    else:
        assert scopes == {}


@pytest.mark.asyncio
async def test_owner_may_finish_a_run_its_lapsed_lease_interrupted(engine):
    store = RunLedgerStore(engine)
    await store.create_run(run_id='mine', event_id=None, binding_id=None, runner_id='runner', workspace_id='workspace')
    await _add_run(engine, 'theirs', 'workspace', 'other-host', NOW)
    async with engine.begin() as conn:
        await conn.execute(
            sa.update(AgentRun)
            .where(AgentRun.run_id.in_(['mine', 'theirs']))
            .values(status='failed', status_reason=INTERRUPTED_REASON, finished_at=NOW)
        )

    finished = await store.finalize_run(run_id='mine', status='completed')
    assert finished['status'] == 'completed'
    assert finished['status_reason'] is None
    with pytest.raises(ValueError, match='Cannot transition terminal run'):
        await store.finalize_run(run_id='theirs', status='completed')
    assert 'workspace' in {key[1] for key in await _scopes(engine)}


def test_migration_backfills_scopes_for_already_leased_rows():
    sync_engine = sa.create_engine('sqlite:///:memory:')
    try:
        with sync_engine.begin() as connection:
            Base.metadata.create_all(connection)
            ExecutionLeaseScope.__table__.drop(connection)
            for run_id, workspace_id, owner, status, expiry in (
                ('live', 'w1', 'old-host', 'running', NOW),
                ('live-2', 'w1', 'old-host', 'running', NOW + _seconds(5)),
                ('done', 'w2', 'old-host', 'completed', NOW),
                ('legacy', 'w3', None, 'running', None),
            ):
                connection.execute(
                    sa.insert(AgentRun).values(
                        run_id=run_id,
                        runner_id='runner',
                        workspace_id=workspace_id,
                        status=status,
                        execution_owner_id=owner,
                        execution_lease_expires_at=expiry,
                    )
                )
            connection.execute(
                sa.insert(MonitoringMessage).values(
                    id='message',
                    workspace_uuid='w4',
                    timestamp=NOW,
                    bot_id='bot',
                    bot_name='bot',
                    pipeline_id='pipeline',
                    pipeline_name='pipeline',
                    message_content='hello',
                    session_id='session',
                    status='pending',
                    level='info',
                    execution_owner_id='old-host',
                    execution_lease_expires_at=NOW,
                )
            )
            with Operations.context(MigrationContext.configure(connection)):
                MIGRATION.upgrade()
                MIGRATION.upgrade()  # idempotent
            rows = connection.execute(
                sa.select(
                    ExecutionLeaseScope.owner_id, ExecutionLeaseScope.workspace_uuid, ExecutionLeaseScope.expires_at
                )
            ).all()
            assert sorted(rows) == [('old-host', 'w1', NOW + _seconds(5)), ('old-host', 'w4', NOW)]
            with Operations.context(MigrationContext.configure(connection)):
                MIGRATION.downgrade()
            assert not sa.inspect(connection).has_table('execution_lease_scopes')
    finally:
        sync_engine.dispose()
