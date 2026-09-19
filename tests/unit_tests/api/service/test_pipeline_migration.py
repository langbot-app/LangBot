"""Manual migration boundary tests; all configs are synthetic."""

import asyncio
import copy

import importlib
import importlib.util
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.authz import PermissionDeniedError, permissions_for_role
from langbot.pkg.api.http.context import RequestContext, PrincipalContext, PrincipalType, WorkspaceContext
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.pipeline import LegacyPipeline
from langbot.pkg.entity.persistence.plugin import PluginSetting
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.entity.persistence.workspace import Workspace
from langbot.pkg.persistence.mgr import PersistenceManager
from langbot.pkg.core.taskmgr import AsyncTaskManager

MODULE = 'langbot.pkg.api.http.service.pipeline_migration'
RID = 'plugin:langbot-team/TestAgent/default'
WS = '00000000-0000-0000-0000-000000000001'
OTHER = '00000000-0000-0000-0000-000000000002'
SOURCE = {'ai': {'runner': 'test', 'secret': 'synthetic-secret'}, 'output': {'keep': True}}


def module():
    assert importlib.util.find_spec(MODULE) is not None, 'manual migration service is missing'
    return importlib.import_module(MODULE)


def context(role='developer'):
    return RequestContext(
        'instance',
        1,
        'request',
        'user_token',
        PrincipalContext(PrincipalType.ACCOUNT, account_uuid='account'),
        WorkspaceContext(WS, 'membership', role, permissions_for_role(role)),
    )


def planner(config, extensions_preferences=None):
    base = dict(
        state='already_current',
        legacy_runner=None,
        target_runner_id=None,
        target_plugin=None,
        changed_paths=[],
        blockers=[],
        warnings=[],
    )
    if isinstance(config.get('ai', {}).get('runner'), str):
        target = copy.deepcopy(config)
        target['ai'] = {'runner': {'id': RID}, 'runner_config': {RID: {'api_key': config['ai']['secret']}}}
        base.update(
            state='ready',
            legacy_runner='test',
            target_runner_id=RID,
            target_plugin={'author': 'langbot-team', 'name': 'TestAgent', 'version': '1.0'},
            changed_paths=['ai.runner', 'ai.runner_config'],
            config=target,
        )
    return base


class PM(PersistenceManager):
    def __init__(self, engine):
        super().__init__(NS())
        self.db = NS(get_engine=lambda: engine)


@pytest.fixture
async def env(tmp_path, monkeypatch):
    m = module()
    monkeypatch.setattr(m, 'plan_legacy_pipeline', planner)
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "migration.db"}')
    async with engine.begin() as conn:
        names = {
            'users',
            'workspaces',
            'workspace_memberships',
            'workspace_execution_states',
            'legacy_pipelines',
            'plugin_settings',
            'pipeline_migration_snapshots',
            'agent_interaction',
        }
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=[Base.metadata.tables[n] for n in names]))
        await conn.execute(
            sa.insert(User).values(
                uuid='account',
                user='test@example.invalid',
                normalized_email='test@example.invalid',
                password='synthetic-not-a-password',
            )
        )
        await conn.execute(
            sa.insert(Workspace),
            [
                dict(uuid=ws, instance_uuid='instance', name=ws, slug=ws, source='cloud_projection')
                for ws in (WS, OTHER)
            ],
        )
        await conn.execute(
            sa.insert(LegacyPipeline),
            [
                dict(
                    uuid=pid,
                    workspace_uuid=ws,
                    name=pid,
                    description='kept',
                    for_version='4.10',
                    stages=[],
                    config=SOURCE,
                    extensions_preferences={'enable_all_plugins': True},
                )
                for pid, ws in [('one', WS), ('two', WS), ('foreign', OTHER)]
            ],
        )
        await conn.execute(
            sa.insert(PluginSetting).values(
                workspace_uuid=WS,
                plugin_author='langbot-team',
                plugin_name='TestAgent',
                enabled=True,
                install_info={'version': '1.0'},
            )
        )
    pm = PM(engine)
    binding = NS(instance_uuid='instance', workspace_uuid=WS, placement_generation=1)
    access = NS(
        workspace=NS(uuid=WS),
        membership=NS(uuid='membership', role='developer', projection_revision=0),
        execution=binding,
    )
    ap = NS(
        persistence_mgr=pm,
        event_loop=asyncio.get_running_loop(),
        instance_config=NS(data={}),
        workspace_service=NS(get_execution_binding=AsyncMock(return_value=binding)),
        workspace_collaboration_service=NS(resolve_account_workspace=AsyncMock(return_value=access)),
        pipeline_mgr=NS(prepare_pipeline=AsyncMock(return_value='candidate'), publish_pipeline=Mock()),
        sess_mgr=NS(session_list=[]),
        runner_registry=NS(
            list_runners=AsyncMock(
                return_value=[
                    NS(
                        id=RID,
                        usages=['agent'],
                        plugin_version='1.0',
                        config_schema=[{'name': 'api_key', 'type': 'string', 'required': True}],
                    )
                ]
            )
        ),
        plugin_connector=NS(require_workspace_context=AsyncMock()),
    )
    ap.task_mgr = AsyncTaskManager(ap)
    svc = m.PipelineMigrationService(ap)
    yield NS(m=m, ap=ap, svc=svc, engine=engine, pm=pm, access=access)
    await ap.task_mgr.wait_all()
    await engine.dispose()


async def selection(env, ids=('one',)):
    preview = await env.svc.preview(context())
    return {
        'confirmed': True,
        'items': [
            {k: item[k] for k in ('pipeline_uuid', 'preview_token')}
            for item in preview['items']
            if item['pipeline_uuid'] in ids
        ],
    }


async def execute(env, body=None):
    result = await env.svc.execute(context(), body or await selection(env))
    task = env.ap.task_mgr.get_task_by_id(result['task_id'])
    await task.task
    return task


async def rows(env):
    async with env.engine.connect() as conn:
        configs = dict((await conn.execute(sa.select(LegacyPipeline.uuid, LegacyPipeline.config))).all())
        backups = (await conn.execute(sa.select(env.m.PipelineMigrationSnapshot))).mappings().all()
    return configs, backups


def test_strict_confirmation_and_selection():
    m = module()
    valid = {'confirmed': True, 'items': [{'pipeline_uuid': 'one', 'preview_token': 'token'}]}
    assert m.validate_execute_request(valid) == valid['items']
    for body in [
        None,
        {},
        {**valid, 'confirmed': 'true'},
        {**valid, 'confirmed': 1},
        {**valid, 'confirmed': False},
        {**valid, 'workspace_uuid': WS},
        {**valid, 'items': []},
        {**valid, 'items': valid['items'] * 2},
        {**valid, 'items': [{'pipeline_uuid': 'one', 'preview_token': 'x', 'config': {}}]},
        {**valid, 'items': [{'pipeline_uuid': str(i), 'preview_token': 'x'} for i in range(51)]},
    ]:
        with pytest.raises(m.MigrationError):
            m.validate_execute_request(body)


@pytest.mark.asyncio
async def test_preview_is_scoped_secret_free_and_read_only(env):
    writes = []

    def observe(_conn, _cursor, statement, *_args):
        if statement.lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
            writes.append(statement)

    sa.event.listen(env.engine.sync_engine, 'before_cursor_execute', observe)
    result = await env.svc.preview(context('viewer'))
    assert result['total'] == 2
    assert {i['pipeline_uuid'] for i in result['items']} == {'one', 'two'}
    assert all(i['state'] == 'ready' and i['preview_token'] for i in result['items'])
    assert 'synthetic-secret' not in str(result)
    assert writes == []
    env.ap.runner_registry.list_runners.assert_not_awaited()
    env.ap.plugin_connector.require_workspace_context.assert_not_awaited()
    env.ap.pipeline_mgr.prepare_pipeline.assert_not_awaited()
    assert not env.ap.task_mgr.tasks


@pytest.mark.asyncio
async def test_viewer_and_foreign_ids_rejected_before_runtime(env):
    body = await selection(env)
    with pytest.raises(PermissionDeniedError):
        await env.svc.execute(context('viewer'), body)
    body['items'].append({'pipeline_uuid': 'foreign', 'preview_token': 'x'})
    with pytest.raises(env.m.MigrationError) as err:
        await env.svc.execute(context(), body)
    assert err.value.status_code == 404
    assert not env.ap.task_mgr.tasks
    env.ap.runner_registry.list_runners.assert_not_awaited()


@pytest.mark.asyncio
async def test_success_snapshot_atomic_preserves_source_and_task_scope(env):
    task = await execute(env)
    configs, backups = await rows(env)
    assert configs['one'] == planner(SOURCE)['config']
    assert configs['two'] == SOURCE
    assert len(backups) == 1 and backups[0]['source_snapshot']['config'] == SOURCE
    assert backups[0]['state'] == 'active'
    assert (task.instance_uuid, task.workspace_uuid, task.placement_generation) == ('instance', WS, 1)
    assert task.task_context.metadata == {
        'kind': 'pipeline_migration',
        'results': [{'pipeline_uuid': 'one', 'state': 'migrated', 'code': None}],
    }
    assert 'synthetic-secret' not in str(task.to_dict())
    env.ap.pipeline_mgr.publish_pipeline.assert_called_once()


@pytest.mark.asyncio
async def test_stale_preview_and_plugin_change_are_rejected(env):
    body = await selection(env)
    async with env.engine.begin() as conn:
        await conn.execute(sa.update(LegacyPipeline).where(LegacyPipeline.uuid == 'one').values(config={'edit': True}))
    with pytest.raises(env.m.MigrationError) as err:
        await env.svc.execute(context(), body)
    assert err.value.status_code == 409
    body = await selection(env, ('two',))
    async with env.engine.begin() as conn:
        await conn.execute(sa.update(PluginSetting).values(enabled=False))
    with pytest.raises(env.m.MigrationError):
        await env.svc.execute(context(), body)
    assert not env.ap.task_mgr.tasks


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['prepare', 'schema', 'membership', 'generation', 'edit'])
async def test_precommit_failures_keep_original_without_backup(env, failure):
    body = await selection(env)
    if failure == 'prepare':
        env.ap.pipeline_mgr.prepare_pipeline.side_effect = RuntimeError('synthetic-secret')
    elif failure == 'schema':
        env.ap.runner_registry.list_runners.return_value[0].config_schema = []

    async def prepare(*args, **kwargs):
        assert env.pm.current_session() is None
        if failure == 'membership':
            env.access.membership.role = 'viewer'
        if failure == 'generation':
            env.ap.workspace_service.get_execution_binding.side_effect = RuntimeError('synthetic-secret')
        if failure == 'edit':
            async with env.engine.begin() as conn:
                await conn.execute(
                    sa.update(LegacyPipeline)
                    .where(LegacyPipeline.uuid == 'one')
                    .values(extensions_preferences={'enable_all_plugins': False})
                )
        return 'candidate'

    if failure not in ('prepare', 'schema'):
        env.ap.pipeline_mgr.prepare_pipeline.side_effect = prepare
    task = await execute(env, body)
    configs, backups = await rows(env)
    assert configs['one'] == SOURCE and not backups
    assert task.task_context.metadata['results'][0]['state'] in ('blocked', 'failed', 'stale')
    assert 'synthetic-secret' not in str(task.to_dict())
    env.ap.pipeline_mgr.publish_pipeline.assert_not_called()


@pytest.mark.asyncio
async def test_activation_pending_explicit_retry_without_second_backup(env):
    env.ap.pipeline_mgr.publish_pipeline.side_effect = RuntimeError('synthetic-secret')
    task = await execute(env)
    assert task.task_context.metadata['results'][0]['state'] == 'activation_pending'
    configs, backups = await rows(env)
    assert configs['one'] != SOURCE and len(backups) == 1
    preview = await env.svc.preview(context())
    assert preview['items'][0]['state'] == 'activation_pending'
    env.ap.pipeline_mgr.publish_pipeline.side_effect = None
    task = await execute(env)
    assert task.task_context.metadata['results'][0]['state'] == 'migrated'
    _, backups = await rows(env)
    assert len(backups) == 1 and backups[0]['state'] == 'active'


@pytest.mark.asyncio
async def test_double_execute_commits_once_and_partial_results(env):
    body = await selection(env, ('one', 'two'))
    original_prepare = env.ap.pipeline_mgr.prepare_pipeline

    async def prepare(_ctx, entity):
        assert env.pm.current_session() is None
        if entity['uuid'] == 'two':
            raise RuntimeError('synthetic-secret')
        await asyncio.sleep(0)
        return 'candidate'

    original_prepare.side_effect = prepare
    first, second = await asyncio.gather(env.svc.execute(context(), body), env.svc.execute(context(), body))
    await env.ap.task_mgr.wait_all()
    configs, backups = await rows(env)
    assert len(backups) == 1
    assert configs['two'] == SOURCE
    results = [env.ap.task_mgr.get_task_by_id(r['task_id']).task_context.metadata['results'] for r in (first, second)]
    assert sum(item['state'] == 'migrated' for batch in results for item in batch) == 1
    assert all(batch[1]['state'] == 'failed' for batch in results)


@pytest.mark.asyncio
async def test_ordinary_update_requires_manual_migration_but_allows_metadata(env):
    from langbot.pkg.api.http.service.pipeline import PipelineService

    service = PipelineService(env.ap)
    env.ap.pipeline_mgr.remove_pipeline = AsyncMock()
    env.ap.pipeline_mgr.load_pipeline = AsyncMock()
    async with env.pm.tenant_scope(WS):
        with pytest.raises(ValueError, match='manual_migration_required'):
            await service.update_pipeline(context(), 'one', {'config': planner(SOURCE)['config']})
        await service.update_pipeline(context(), 'one', {'name': 'renamed'})
    configs, backups = await rows(env)
    assert configs['one'] == SOURCE and not backups


@pytest.mark.asyncio
async def test_snapshot_commit_failure_rolls_back_config_and_backup(env, monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSessionTransaction

    original = AsyncSessionTransaction.commit

    async def fail_write_commit(transaction):
        # Fail the actual transaction after both statements have run.
        result = await transaction.session.execute(
            sa.select(sa.func.count()).select_from(env.m.PipelineMigrationSnapshot)
        )
        if result.scalar() > 0:
            raise RuntimeError('synthetic-secret')
        await original(transaction)

    monkeypatch.setattr(AsyncSessionTransaction, 'commit', fail_write_commit)
    task = await execute(env)
    configs, backups = await rows(env)
    assert configs['one'] == SOURCE and not backups
    env.ap.pipeline_mgr.publish_pipeline.assert_not_called()
    assert task.task_context.metadata['results'][0]['state'] == 'failed'
    assert 'synthetic-secret' not in str(task.to_dict())


@pytest.mark.asyncio
async def test_plugin_changes_while_preparing_prevent_commit(env):
    async def prepare(*args):
        async with env.engine.begin() as conn:
            await conn.execute(sa.update(PluginSetting).values(runtime_revision=2))
        return 'candidate'

    env.ap.pipeline_mgr.prepare_pipeline.side_effect = prepare
    task = await execute(env)
    configs, backups = await rows(env)
    assert configs['one'] == SOURCE and not backups
    assert task.task_context.metadata['results'][0]['state'] == 'stale'


@pytest.mark.asyncio
async def test_scope_token_cannot_be_reused_by_other_identity_or_generation(env):
    import dataclasses

    body = await selection(env)
    ctx = dataclasses.replace(context(), placement_generation=2)
    env.access.execution.placement_generation = 2
    with pytest.raises(env.m.MigrationError):
        await env.svc.execute(ctx, body)
    assert not env.ap.task_mgr.tasks


@pytest.mark.asyncio
async def test_conversation_invalidation_is_workspace_scoped(env):
    good = NS(workspace_uuid=WS, using_conversation=NS(pipeline_uuid='one'))
    foreign = NS(workspace_uuid=OTHER, using_conversation=NS(pipeline_uuid='one'))
    env.ap.sess_mgr.session_list = [good, foreign]
    await execute(env)
    assert good.using_conversation is None
    assert foreign.using_conversation is not None


@pytest.mark.asyncio
async def test_runtime_schema_changes_during_prepare_prevent_commit(env):
    async def prepare(*args):
        env.ap.runner_registry.list_runners.return_value[0].config_schema = []
        return 'candidate'

    env.ap.pipeline_mgr.prepare_pipeline.side_effect = prepare
    task = await execute(env)
    configs, backups = await rows(env)
    assert configs['one'] == SOURCE and not backups
    assert task.task_context.metadata['results'][0]['state'] == 'blocked'


@pytest.mark.asyncio
async def test_real_planner_deerflow_schema_integration(env, monkeypatch):
    import json
    from pathlib import Path
    from langbot.pkg.pipeline.legacy_config_migration import plan_legacy_pipeline

    monkeypatch.setattr(env.m, 'plan_legacy_pipeline', plan_legacy_pipeline)
    source = {
        'ai': {
            'runner': {'runner': 'deerflow-api', 'expire-time': 60},
            'deerflow-api': {'api-base': 'https://synthetic.invalid', 'api-key': 'synthetic-secret'},
        },
        'output': {'misc': {'remove-think': False}},
    }
    plan = plan_legacy_pipeline(source, {'enable_all_plugins': True})
    assert plan['state'] == 'ready'
    async with env.engine.begin() as conn:
        await conn.execute(sa.update(LegacyPipeline).where(LegacyPipeline.uuid == 'one').values(config=source))
        await conn.execute(
            sa.insert(PluginSetting).values(
                workspace_uuid=WS, plugin_author='langbot-team', plugin_name='DeerFlowAgent', enabled=True
            )
        )
    schema = json.loads((Path(__file__).parent / 'fixtures/pipeline_migration_deerflow_schema.json').read_text())
    env.ap.runner_registry.list_runners.return_value = [
        NS(
            id=plan['target_runner_id'],
            usages=['agent'],
            plugin_version=plan['target_plugin']['version'],
            config_schema=schema,
        )
    ]
    task = await execute(env)
    assert task.task_context.metadata['results'][0]['state'] == 'migrated'
    configs, backups = await rows(env)
    assert configs['one'] == plan['config'] and backups[0]['source_snapshot']['config'] == source


@pytest.mark.asyncio
async def test_account_disabled_during_prepare_blocks_commit(env):
    async def prepare(*args):
        async with env.engine.begin() as conn:
            await conn.execute(sa.update(User).where(User.uuid == 'account').values(status='disabled'))
        return 'candidate'

    env.ap.pipeline_mgr.prepare_pipeline.side_effect = prepare
    task = await execute(env)
    configs, backups = await rows(env)
    assert configs['one'] == SOURCE and not backups
    assert task.task_context.metadata['results'][0]['state'] == 'blocked'


@pytest.mark.asyncio
async def test_plugin_disabled_after_commit_defers_activation(env, monkeypatch):
    original = env.svc._commit

    async def commit(*args):
        result = await original(*args)
        async with env.engine.begin() as conn:
            await conn.execute(sa.update(PluginSetting).values(enabled=False))
        return result

    monkeypatch.setattr(env.svc, '_commit', commit)
    task = await execute(env)
    assert task.task_context.metadata['results'][0]['state'] == 'activation_pending'
    env.ap.pipeline_mgr.publish_pipeline.assert_not_called()


@pytest.mark.asyncio
async def test_ambiguous_commit_acknowledgement_reports_pending(env, monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSessionTransaction

    original = AsyncSessionTransaction.commit
    failed = False

    async def fail_ack(transaction):
        nonlocal failed
        count = (
            await transaction.session.execute(sa.select(sa.func.count()).select_from(env.m.PipelineMigrationSnapshot))
        ).scalar()
        await original(transaction)
        if count and not failed:
            failed = True
            raise RuntimeError('synthetic-secret')

    monkeypatch.setattr(AsyncSessionTransaction, 'commit', fail_ack)
    task = await execute(env)
    configs, backups = await rows(env)
    assert configs['one'] != SOURCE and len(backups) == 1
    assert task.task_context.metadata['results'][0]['state'] == 'activation_pending'
    env.ap.pipeline_mgr.publish_pipeline.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('durable', [False, True], ids=['before_commit', 'after_durable_commit'])
async def test_cancel_commit_reports_durable_outcome_and_stops_batch(env, monkeypatch, durable):
    from sqlalchemy.ext.asyncio import AsyncSessionTransaction

    original = AsyncSessionTransaction.commit
    cancelled = False

    async def cancel_commit(transaction):
        nonlocal cancelled
        count = (
            await transaction.session.execute(sa.select(sa.func.count()).select_from(env.m.PipelineMigrationSnapshot))
        ).scalar()
        if count and not cancelled:
            cancelled = True
            if durable:
                await original(transaction)
            asyncio.current_task().cancel()
            await asyncio.sleep(0)
        await original(transaction)

    monkeypatch.setattr(AsyncSessionTransaction, 'commit', cancel_commit)
    task = await execute(env, await selection(env, ('one', 'two')))
    configs, backups = await rows(env)
    assert cancelled
    assert configs['one'] == (planner(SOURCE)['config'] if durable else SOURCE)
    assert len(backups) == int(durable)
    if durable:
        assert backups[0]['state'] == 'activation_pending'
    assert configs['two'] == SOURCE
    assert task.task_context.metadata['results'] == [
        {'pipeline_uuid': 'one', 'state': 'activation_pending' if durable else 'failed', 'code': 'operation_cancelled'},
        {'pipeline_uuid': 'two', 'state': 'failed', 'code': 'operation_cancelled'},
    ]
    env.ap.pipeline_mgr.prepare_pipeline.assert_awaited_once()
    env.ap.pipeline_mgr.publish_pipeline.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('durable', [False, True])
@pytest.mark.parametrize('initial_cancel', [False, True])
@pytest.mark.parametrize('reconcile_cancel', [False, True])
async def test_unavailable_commit_reconciliation_is_conservative(
    env, monkeypatch, durable, initial_cancel, reconcile_cancel
):
    from sqlalchemy.ext.asyncio import AsyncSessionTransaction

    original_commit = AsyncSessionTransaction.commit
    original_execute = env.pm.execute_async
    interrupted = False
    reconciliation_attempts = 0

    async def interrupt_commit(transaction):
        nonlocal interrupted
        count = (
            await transaction.session.execute(sa.select(sa.func.count()).select_from(env.m.PipelineMigrationSnapshot))
        ).scalar()
        if count and not interrupted:
            interrupted = True
            if durable:
                await original_commit(transaction)
            if initial_cancel:
                asyncio.current_task().cancel()
                await asyncio.sleep(0)
            raise RuntimeError('synthetic-secret')
        await original_commit(transaction)

    async def unavailable_reconciliation(statement, *args, **kwargs):
        nonlocal reconciliation_attempts
        if interrupted:
            reconciliation_attempts += 1
            if reconcile_cancel:
                # Repeated real cancellation must stop the batch, not start a
                # shield/retry loop or leave the current result as pending.
                asyncio.current_task().cancel()
                asyncio.current_task().cancel()
                await asyncio.sleep(0)
            raise RuntimeError('synthetic-secret')
        return await original_execute(statement, *args, **kwargs)

    monkeypatch.setattr(AsyncSessionTransaction, 'commit', interrupt_commit)
    monkeypatch.setattr(env.pm, 'execute_async', unavailable_reconciliation)
    task_id = (await env.svc.execute(context(), await selection(env, ('one', 'two'))))['task_id']
    task = env.ap.task_mgr.get_task_by_id(task_id)
    await asyncio.gather(task.task, return_exceptions=True)
    assert task.task.cancelled() is reconcile_cancel
    configs, backups = await rows(env)
    assert configs['one'] == (planner(SOURCE)['config'] if durable else SOURCE)
    assert len(backups) == int(durable)
    assert task.task_context.metadata['results'][0] == {
        'pipeline_uuid': 'one',
        'state': 'activation_pending',
        'code': 'commit_outcome_unknown',
    }
    if initial_cancel or reconcile_cancel:
        assert reconciliation_attempts == 1
        assert task.task_context.metadata['results'][1] == {
            'pipeline_uuid': 'two',
            'state': 'failed',
            'code': 'operation_cancelled',
        }
        env.ap.pipeline_mgr.prepare_pipeline.assert_awaited_once()
    assert configs['two'] == SOURCE
    assert 'synthetic-secret' not in str(task.task_context.metadata)
    env.ap.pipeline_mgr.publish_pipeline.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('durable_retry_ack', [False, True])
@pytest.mark.parametrize('reconcile_failure', [None, 'error', 'cancel'])
async def test_cancel_activation_retry_reconciles_original_snapshot(
    env, monkeypatch, durable_retry_ack, reconcile_failure
):
    from sqlalchemy.ext.asyncio import AsyncSessionTransaction

    env.ap.pipeline_mgr.publish_pipeline.side_effect = RuntimeError('synthetic-secret')
    await execute(env)
    before_configs, before_backups = await rows(env)
    body = await selection(env, ('one', 'two'))
    env.ap.pipeline_mgr.publish_pipeline.reset_mock(side_effect=True)
    env.ap.pipeline_mgr.prepare_pipeline.reset_mock()
    original_commit = AsyncSessionTransaction.commit
    original_service_commit = env.svc._commit
    original_execute = env.pm.execute_async
    interrupted = False
    in_commit = False
    reconciliation_attempts = 0

    async def service_commit(*args):
        nonlocal in_commit
        in_commit = True
        try:
            return await original_service_commit(*args)
        finally:
            in_commit = False

    async def cancel_ack(transaction):
        nonlocal interrupted
        if in_commit and not interrupted:
            interrupted = True
            if durable_retry_ack:
                await original_commit(transaction)
            asyncio.current_task().cancel()
            await asyncio.sleep(0)
        await original_commit(transaction)

    async def reconcile(statement, *args, **kwargs):
        nonlocal reconciliation_attempts
        if interrupted and not in_commit:
            reconciliation_attempts += 1
            if reconcile_failure == 'cancel':
                asyncio.current_task().cancel()
                await asyncio.sleep(0)
            if reconcile_failure == 'error':
                raise RuntimeError('synthetic-secret')
        return await original_execute(statement, *args, **kwargs)

    monkeypatch.setattr(env.svc, '_commit', service_commit)
    monkeypatch.setattr(AsyncSessionTransaction, 'commit', cancel_ack)
    monkeypatch.setattr(env.pm, 'execute_async', reconcile)
    task_id = (await env.svc.execute(context(), body))['task_id']
    task = env.ap.task_mgr.get_task_by_id(task_id)
    await asyncio.gather(task.task, return_exceptions=True)
    configs, backups = await rows(env)
    assert interrupted and configs == before_configs
    assert backups == before_backups
    assert backups[0]['state'] == 'activation_pending'
    assert reconciliation_attempts == 1
    assert task.task.cancelled() is (reconcile_failure == 'cancel')
    assert task.task_context.metadata['results'] == [
        {
            'pipeline_uuid': 'one',
            'state': 'activation_pending',
            'code': 'commit_outcome_unknown' if reconcile_failure else 'operation_cancelled',
        },
        {'pipeline_uuid': 'two', 'state': 'failed', 'code': 'operation_cancelled'},
    ]
    env.ap.pipeline_mgr.prepare_pipeline.assert_awaited_once()
    env.ap.pipeline_mgr.publish_pipeline.assert_not_called()
    assert 'synthetic-secret' not in str(task.task_context.metadata)


@pytest.mark.asyncio
async def test_cancel_during_prepare_keeps_original_and_stops_batch(env):
    async def cancel_prepare(*args):
        asyncio.current_task().cancel()
        await asyncio.sleep(0)

    env.ap.pipeline_mgr.prepare_pipeline.side_effect = cancel_prepare
    task = await execute(env, await selection(env, ('one', 'two')))
    configs, backups = await rows(env)
    assert configs['one'] == configs['two'] == SOURCE and not backups
    assert all(
        r['state'] == 'failed' and r['code'] == 'operation_cancelled' for r in task.task_context.metadata['results']
    )
    env.ap.pipeline_mgr.prepare_pipeline.assert_awaited_once()
    env.ap.pipeline_mgr.publish_pipeline.assert_not_called()


async def execute_all(env, install_plugins=True):
    response = await env.svc.execute(context(), {'confirmed': True, 'all': True, 'install_plugins': install_plugins})
    task = env.ap.task_mgr.get_task_by_id(response['task_id'])
    await task.task
    return response, task.task_context.metadata


@pytest.mark.asyncio
async def test_all_mode_migrates_workspace_and_skips_completed_on_retry(env):
    response, metadata = await execute_all(env)
    assert response['pipeline_uuids'] == ['one', 'two']
    assert [r['state'] for r in metadata['results']] == ['migrated', 'migrated']
    configs, backups = await rows(env)
    assert configs['foreign'] == SOURCE
    assert len(backups) == 2
    with pytest.raises(env.m.MigrationError, match='nothing_to_migrate'):
        await execute_all(env)


@pytest.mark.asyncio
async def test_all_data_only_without_plugins_never_contacts_runtime_or_marketplace(env):
    async with env.engine.begin() as conn:
        await conn.execute(sa.delete(PluginSetting))
    env.ap.runner_registry.list_runners.side_effect = AssertionError('offline must not query runtime')
    env.ap.plugin_connector.install_plugin = AsyncMock(side_effect=AssertionError('offline must not install'))
    _, metadata = await execute_all(env, install_plugins=False)
    assert [r['state'] for r in metadata['results']] == ['migrated', 'migrated']
    assert all(r['code'] == 'data_only' for r in metadata['results'])
    configs, backups = await rows(env)
    assert len(backups) == 2
    assert configs['one']['ai']['runner']['id'] == RID
    assert configs['foreign'] == SOURCE
    env.ap.plugin_connector.install_plugin.assert_not_awaited()
    env.ap.runner_registry.list_runners.assert_not_awaited()
    assert env.ap.pipeline_mgr.publish_pipeline.call_count == 2


@pytest.mark.asyncio
async def test_all_mode_installs_missing_plugin_once_then_migrates_both(env):
    async with env.engine.begin() as conn:
        await conn.execute(sa.delete(PluginSetting))

    async def install(source, info, task_context):
        assert info['plugin_version'] == '1.0'
        async with env.engine.begin() as conn:
            await conn.execute(
                sa.insert(PluginSetting).values(
                    workspace_uuid=WS, plugin_author='langbot-team', plugin_name='TestAgent', enabled=True
                )
            )

    env.ap.plugin_connector.install_plugin = AsyncMock(side_effect=install)
    _, metadata = await execute_all(env)
    assert [r['state'] for r in metadata['results']] == ['migrated', 'migrated']
    env.ap.plugin_connector.install_plugin.assert_awaited_once()


@pytest.mark.asyncio
async def test_all_install_failure_preserves_sources_and_never_exposes_upstream_error(env):
    async with env.engine.begin() as conn:
        await conn.execute(sa.delete(PluginSetting))
    env.ap.plugin_connector.install_plugin = AsyncMock(side_effect=RuntimeError('secret-token'))
    _, metadata = await execute_all(env)
    assert all(r['code'] == 'plugin_install_failed' for r in metadata['results'])
    assert 'secret-token' not in str(metadata)
    configs, backups = await rows(env)
    assert configs['one'] == SOURCE and not backups
    env.ap.plugin_connector.install_plugin.assert_awaited_once()


@pytest.mark.asyncio
async def test_all_installation_cannot_migrate_edits_made_while_installing(env):
    async with env.engine.begin() as conn:
        await conn.execute(sa.delete(PluginSetting))

    async def install(*args, **kwargs):
        async with env.engine.begin() as conn:
            await conn.execute(
                sa.insert(PluginSetting).values(
                    workspace_uuid=WS, plugin_author='langbot-team', plugin_name='TestAgent', enabled=True
                )
            )
            await conn.execute(sa.update(LegacyPipeline).where(LegacyPipeline.uuid == 'one').values(name='edited'))

    env.ap.plugin_connector.install_plugin = AsyncMock(side_effect=install)
    _, metadata = await execute_all(env)
    assert metadata['results'][0]['code'] == 'preview_stale'
    assert metadata['results'][1]['state'] == 'migrated'
    configs, backups = await rows(env)
    assert configs['one'] == SOURCE
    assert len(backups) == 1


@pytest.mark.asyncio
async def test_all_mode_has_no_fifty_pipeline_limit(env):
    async with env.engine.begin() as conn:
        await conn.execute(
            sa.insert(LegacyPipeline),
            [
                dict(
                    uuid=f'extra-{i}',
                    workspace_uuid=WS,
                    name=f'extra-{i}',
                    description='bulk fixture',
                    for_version='4.10',
                    stages=[],
                    config=SOURCE,
                    extensions_preferences={'enable_all_plugins': True},
                )
                for i in range(51)
            ],
        )
    response, metadata = await execute_all(env, install_plugins=False)
    assert len(response['pipeline_uuids']) == 53
    assert all(r['state'] == 'migrated' for r in metadata['results'])


@pytest.mark.asyncio
async def test_all_mode_rejects_duplicate_tasks_and_unconfirmed_requests(env):
    for body in [
        {'all': True, 'confirmed': False, 'install_plugins': True},
        {'all': True, 'confirmed': True, 'install_plugins': 'false'},
        {'all': True, 'confirmed': True, 'install_plugins': False, 'workspace_uuid': OTHER},
    ]:
        with pytest.raises(env.m.MigrationError):
            await env.svc.execute(context(), body)
    env.svc._all_tasks.add(WS)
    with pytest.raises(env.m.MigrationError, match='migration_running'):
        await execute_all(env)
    env.svc._all_tasks.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize('stage', ['discovery', 'install', 'validation'])
async def test_disconnected_runtime_has_specific_error_without_modifying_sources(env, stage):
    from langbot.pkg.plugin.connector import PluginRuntimeNotConnectedError

    error = PluginRuntimeNotConnectedError('private connection diagnostics')
    if stage == 'discovery':
        env.ap.runner_registry.list_runners.side_effect = error
    elif stage == 'install':
        async with env.engine.begin() as conn:
            await conn.execute(sa.delete(PluginSetting))
        env.ap.plugin_connector.install_plugin = AsyncMock(side_effect=error)
    else:
        env.svc._verify_runtime = AsyncMock(side_effect=error)
    _, metadata = await execute_all(env)
    assert all(r['code'] == 'plugin_runtime_unavailable' for r in metadata['results'])
    assert 'private connection diagnostics' not in str(metadata)
    configs, backups = await rows(env)
    assert configs['one'] == SOURCE and configs['two'] == SOURCE
    assert not backups


def test_install_progress_records_stages_without_exposing_diagnostics():
    from langbot.pkg.api.http.service.pipeline_migration import MigrationInstallContext

    ctx = MigrationInstallContext({'author': 'team', 'name': 'Runner', 'version': '1.0'})
    ctx.trace('private-token', action='downloading plugin package')
    ctx.metadata.update(download_current=120, download_total=240, progress_percent=15, url='private-token')
    ctx.set_current_action('validating plugin package')
    ctx.metadata['progress_percent'] = float('nan')
    ctx.finish('plugin_install_failed')
    assert ctx.progress['download_current'] == 120
    assert ctx.progress['progress_percent'] == 15
    assert [step['stage'] for step in ctx.progress['steps']] == ['checking', 'downloading', 'validating']
    assert all(step['finished_at'] is not None for step in ctx.progress['steps'])
    assert ctx.progress['status'] == 'failed'
    assert 'private-token' not in str(ctx.progress)


@pytest.mark.asyncio
async def test_install_progress_visible_while_download_is_running(env):
    import asyncio

    async with env.engine.begin() as conn:
        await conn.execute(sa.delete(PluginSetting))
    started, release = asyncio.Event(), asyncio.Event()

    async def install(source, info, task_context):
        task_context.set_current_action('downloading plugin package')
        task_context.metadata.update(download_current=123, download_total=456)
        started.set()
        await release.wait()
        raise RuntimeError('private-token')

    env.ap.plugin_connector.install_plugin = AsyncMock(side_effect=install)
    response = await env.svc.execute(context(), {'confirmed': True, 'all': True, 'install_plugins': True})
    task = env.ap.task_mgr.get_task_by_id(response['task_id'])
    try:
        await asyncio.wait_for(started.wait(), 3)
        await asyncio.sleep(0.25)
        progress = task.task_context.metadata['installations'][0]
        assert progress['status'] == 'installing'
        assert progress['download_current'] == 123
        assert progress['stage'] == 'downloading'
    finally:
        release.set()
        await task.task
    assert len(task.task_context.metadata['installations']) == 1
    assert progress['status'] == 'failed'
    assert 'private-token' not in str(task.task_context.to_dict())


@pytest.mark.asyncio
async def test_missing_marketplace_release_has_specific_migration_result(env):
    from langbot.pkg.plugin.connector import MarketplacePluginVersionNotFoundError

    async with env.engine.begin() as conn:
        await conn.execute(sa.delete(PluginSetting))
    env.ap.plugin_connector.install_plugin = AsyncMock(
        side_effect=MarketplacePluginVersionNotFoundError('private-token')
    )
    _, metadata = await execute_all(env)
    assert all(r['code'] == 'plugin_version_unavailable' for r in metadata['results'])
    assert metadata['installations'][0]['code'] == 'plugin_version_unavailable'
    assert 'private-token' not in str(metadata)
