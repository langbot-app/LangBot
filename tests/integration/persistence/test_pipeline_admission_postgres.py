"""Disposable PostgreSQL only: real row-lock admission, rollback, and FORCE RLS."""

import asyncio
import os
import copy
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from tests.unit_tests.api.service import test_pipeline_migration as base
from langbot.pkg.agent.runner.interaction_store import InteractionStore, InteractionScopeError
from langbot.pkg.persistence.pipeline_admission import lock_pipeline_admission
from langbot.pkg.entity.persistence.agent_interaction import AgentInteraction

URL = os.environ.get('LANGBOT_ADMISSION_TEST_URL')
pytestmark = [pytest.mark.asyncio, pytest.mark.skipif(not URL, reason='disposable PostgreSQL URL required')]


@pytest.fixture
async def env(tmp_path, monkeypatch):
    admin = create_async_engine(URL)
    async with admin.begin() as conn:
        await conn.execute(sa.text('DROP SCHEMA public CASCADE'))
        await conn.execute(sa.text('CREATE SCHEMA public'))
        await conn.execute(
            sa.text(
                'DO $$ BEGIN CREATE ROLE admission_runtime LOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$'
            )
        )
    monkeypatch.setattr(base, 'create_async_engine', lambda *a, **kw: admin)
    async for env in base.env.__wrapped__(tmp_path, monkeypatch):
        async with admin.begin() as conn:
            for table in ['legacy_pipelines', 'pipeline_migration_snapshots']:
                await conn.execute(sa.text(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY'))
                await conn.execute(sa.text(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY'))
                await conn.execute(
                    sa.text(
                        f"CREATE POLICY isolation ON {table} USING (workspace_uuid = current_setting('langbot.workspace_uuid', true)) WITH CHECK (workspace_uuid = current_setting('langbot.workspace_uuid', true))"
                    )
                )
            await conn.execute(sa.text('GRANT USAGE ON SCHEMA public TO admission_runtime'))
            await conn.execute(
                sa.text('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO admission_runtime')
            )
            await conn.execute(sa.text('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO admission_runtime'))
        runtime = create_async_engine(URL.replace('postgres@', 'admission_runtime@'))
        env.pm.db = base.NS(get_engine=lambda: runtime)
        env.runtime = runtime
        yield env
        await runtime.dispose()


async def write(env, workspace=base.WS, pipeline='one', expected=None, check=lambda: True):
    return await InteractionStore(env.runtime).create_request(
        interaction_id='form',
        run_id='run',
        binding_id='binding',
        runner_id=base.RID,
        processor_type='pipeline',
        processor_id=pipeline,
        workspace_id=workspace,
        request={},
        delivery_target={},
        expected_config=copy.deepcopy(base.SOURCE if expected is None else expected),
        authority_check=check,
    )


async def blocked(env):
    # Observe PostgreSQL's lock waiter, not an arbitrary scheduling sleep.
    async with asyncio.timeout(5):
        while True:
            async with env.engine.connect() as conn:
                n = (
                    await conn.execute(
                        sa.text(
                            "SELECT count(*) FROM pg_stat_activity WHERE usename='admission_runtime' AND wait_event_type='Lock'"
                        )
                    )
                ).scalar()
            if n:
                return
            await asyncio.sleep(0)


@pytest.mark.parametrize('outcome', ['commit', 'rollback', 'cancel'])
async def test_real_writer_waits_and_revalidates_after_transaction(env, outcome):
    writer = None
    try:
        async with env.pm.tenant_uow(base.WS) as uow:
            await lock_pipeline_admission(uow.session, base.WS, 'one')
            writer = asyncio.create_task(write(env))
            await blocked(env)
            assert not writer.done()
            async with env.engine.connect() as conn:
                assert not (await conn.execute(sa.select(AgentInteraction))).all()
            await uow.session.execute(
                sa.update(base.LegacyPipeline)
                .where(base.LegacyPipeline.uuid == 'one')
                .values(config=base.planner(base.SOURCE)['config'])
            )
            if outcome == 'rollback':
                raise RuntimeError('rollback')
            if outcome == 'cancel':
                raise asyncio.CancelledError()
    except (RuntimeError, asyncio.CancelledError):
        assert outcome != 'commit'
    if outcome == 'commit':
        with pytest.raises(InteractionScopeError):
            await writer
    else:
        assert (await writer)[0]['status'] == 'pending'


async def test_real_writer_first_blocks_migration_and_other_tenant_isolated(env):
    await write(env)
    async with env.pm.tenant_uow(base.WS) as uow:
        await lock_pipeline_admission(uow.session, base.WS, 'one')
        assert (
            await uow.session.execute(
                sa.select(AgentInteraction.status).where(AgentInteraction.workspace_id == base.WS)
            )
        ).scalar_one() == 'pending'
    with pytest.raises(InteractionScopeError):
        await write(env, workspace=base.OTHER)
    async with env.runtime.connect() as conn:
        assert not (await conn.execute(sa.select(base.LegacyPipeline))).all()
    async with env.pm.tenant_uow(base.OTHER) as uow:
        assert (await uow.session.execute(sa.select(base.LegacyPipeline.uuid))).scalars().all() == ['foreign']


async def test_real_migration_commit_activation_and_stale_writer(env):
    original = env.svc._activate

    async def activate(*args):
        with pytest.raises(InteractionScopeError):
            await write(env)
        return await original(*args)

    env.svc._activate = activate
    task = await base.execute(env)
    assert task.task_context.metadata['results'][0]['state'] == 'migrated'
    with pytest.raises(InteractionScopeError):
        await write(env)
    _, snapshots = await base.rows(env)
    assert snapshots[0]['state'] == 'active'


@pytest.mark.parametrize('boundary', ['cas', 'activation'])
async def test_real_no_phantom_between_check_and_publication(env, monkeypatch, boundary):
    writer = None
    sql = env.pm.execute_async
    state = env.svc._interaction_state
    entered_activation = False
    activate = env.svc._activate

    async def activation(*args):
        nonlocal entered_activation
        entered_activation = True
        return await activate(*args)

    async def start_waiter():
        nonlocal writer
        writer = asyncio.create_task(write(env))
        await blocked(env)
        assert not writer.done()

    async def execute_sql(statement, *args, **kwargs):
        result = await sql(statement, *args, **kwargs)
        if (
            boundary == 'cas'
            and isinstance(statement, sa.sql.dml.Insert)
            and statement.table.name == 'pipeline_migration_snapshots'
        ):
            await start_waiter()
        return result

    async def interaction_state(*args):
        result = await state(*args)
        if boundary == 'activation' and entered_activation:
            await start_waiter()
        return result

    monkeypatch.setattr(env.pm, 'execute_async', execute_sql)
    monkeypatch.setattr(env.svc, '_activate', activation)
    monkeypatch.setattr(env.svc, '_interaction_state', interaction_state)
    task = await base.execute(env)
    assert task.task_context.metadata['results'][0]['state'] == 'migrated'
    with pytest.raises(InteractionScopeError):
        await writer
    async with env.engine.connect() as conn:
        assert not (await conn.execute(sa.select(AgentInteraction))).all()


async def test_real_conversation_revoked_while_waiting(env):
    live = True
    async with env.pm.tenant_uow(base.WS) as uow:
        await lock_pipeline_admission(uow.session, base.WS, 'one')
        writer = asyncio.create_task(write(env, check=lambda: live))
        await blocked(env)
        live = False
    with pytest.raises(InteractionScopeError):
        await writer


async def test_real_other_tenant_writer_is_not_serialized(env):
    async with env.pm.tenant_uow(base.WS) as uow:
        await lock_pipeline_admission(uow.session, base.WS, 'one')
        record, _ = await asyncio.wait_for(write(env, workspace=base.OTHER, pipeline='foreign'), 3)
        assert record['workspace_id'] == base.OTHER


async def test_real_pending_before_commit_prevents_migration(env):
    body = await base.selection(env)
    await write(env)
    with pytest.raises(env.m.MigrationError, match='preview_stale'):
        await base.execute(env, body)
    configs, snapshots = await base.rows(env)
    assert configs['one'] == base.SOURCE and not snapshots
    env.ap.pipeline_mgr.publish_pipeline.assert_not_called()


# Run the unchanged cancellation/ambiguous-acknowledgement contracts on real PG.
test_real_cancel_commit_outcome = base.test_cancel_commit_reports_durable_outcome_and_stops_batch
test_real_cancel_activation_retry = base.test_cancel_activation_retry_reconciles_original_snapshot
test_real_unavailable_reconciliation = base.test_unavailable_commit_reconciliation_is_conservative
test_real_cancel_prepare = base.test_cancel_during_prepare_keeps_original_and_stops_batch
