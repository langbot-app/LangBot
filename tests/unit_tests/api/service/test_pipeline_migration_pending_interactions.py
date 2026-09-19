"""Migration must not abandon native or durable human-input requests."""

import copy
import sys
from types import SimpleNamespace as NS

import pytest
import sqlalchemy as sa

from tests.unit_tests.api.service import test_pipeline_migration as existing
from tests.unit_tests.api.service.test_pipeline_migration import (
    context,
    selection,
    execute,
    rows,
    WS,
    OTHER,
    SOURCE,
)
from langbot.pkg.entity.persistence.agent_interaction import AgentInteraction

env = existing.env
NATIVE = 'langbot.pkg.provider.runners.difysvapi'


@pytest.fixture(autouse=True)
async def interaction_schema(env):
    async with env.engine.begin() as conn:
        await conn.run_sync(lambda c: AgentInteraction.__table__.create(c, checkfirst=True))


async def add_request(env, status='pending', workspace=WS, pipeline='one'):
    async with env.engine.begin() as conn:
        await conn.execute(
            sa.insert(AgentInteraction).values(
                interaction_id='form',
                run_id=f'{workspace}-{pipeline}-{status}',
                binding_id='binding',
                runner_id='plugin:langbot-team/DifyAgent/default',
                processor_type='pipeline',
                processor_id=pipeline,
                workspace_id=workspace,
                status=status,
                request_json='{"secret":"private-form"}',
                callback_token_hash=f'{workspace}-{pipeline}-{status}',
            )
        )


def native(monkeypatch, workspace=WS, pipeline='one', instance='instance'):
    forms = {
        (instance, workspace, 1, 'bot', pipeline, 'adapter', 'person', 'actor'): {
            'private-token': {'inputs': {'secret': 'private-form'}}
        }
    }
    monkeypatch.setitem(sys.modules, NATIVE, NS(_PENDING_FORMS=forms))
    return forms


@pytest.mark.asyncio
@pytest.mark.parametrize('source', ['native', 'durable'])
async def test_pending_preview_readonly_secret_free(env, monkeypatch, source):
    cache = native(monkeypatch) if source == 'native' else None
    if source == 'durable':
        await add_request(env)
    before = copy.deepcopy(cache)
    writes = []

    def observe(_conn, _cursor, statement, *_args):
        if statement.lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
            writes.append(statement)

    sa.event.listen(env.engine.sync_engine, 'before_cursor_execute', observe)
    result = await env.svc.preview(context())
    item = result['items'][0]
    assert item['state'] == 'blocked'
    assert {'code': 'runtime.pending_interaction'} in item['blockers']
    assert item['preview_token'] is None
    assert result['items'][1]['state'] == 'ready'
    assert 'private-' not in str(result)
    assert cache == before and not writes
    env.ap.pipeline_mgr.prepare_pipeline.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['submitted', 'cancelled', 'expired', 'delivery_failed'])
async def test_terminal_requests_allow_migration(env, status):
    await add_request(env, status)
    task = await execute(env)
    assert task.task_context.metadata['results'][0]['state'] == 'migrated'


@pytest.mark.asyncio
@pytest.mark.parametrize('source', ['native', 'durable'])
async def test_other_scope_does_not_block(env, monkeypatch, source):
    if source == 'native':
        native(monkeypatch, workspace=OTHER)
    else:
        await add_request(env, workspace=OTHER)
        await add_request(env, pipeline='two')
    task = await execute(env)
    assert task.task_context.metadata['results'][0]['state'] == 'migrated'


@pytest.mark.asyncio
@pytest.mark.parametrize('source', ['native', 'durable'])
async def test_request_after_preview_stales_token(env, monkeypatch, source):
    body = await selection(env)
    if source == 'native':
        native(monkeypatch)
    else:
        await add_request(env)
    with pytest.raises(env.m.MigrationError, match='preview_stale'):
        await env.svc.execute(context(), body)
    assert not env.ap.task_mgr.tasks


@pytest.mark.asyncio
@pytest.mark.parametrize('source', ['native', 'durable'])
async def test_new_request_during_prepare_prevents_snapshot_and_reset(env, monkeypatch, source):
    conversation = NS(pipeline_uuid='one')
    session = NS(workspace_uuid=WS, instance_uuid='instance', using_conversation=conversation)
    env.ap.sess_mgr.session_list = [session]

    async def prepare(*args):
        if source == 'native':
            native(monkeypatch)
        else:
            await add_request(env)
        return 'candidate'

    env.ap.pipeline_mgr.prepare_pipeline.side_effect = prepare
    task = await execute(env)
    configs, snapshots = await rows(env)
    assert configs['one'] == SOURCE and not snapshots
    assert session.using_conversation is conversation
    assert task.task_context.metadata['results'][0]['state'] == 'stale'
    env.ap.pipeline_mgr.publish_pipeline.assert_not_called()


@pytest.mark.asyncio
async def test_activation_boundary_catches_new_request(env, monkeypatch):
    original = env.svc._commit

    async def commit(*args):
        result = await original(*args)
        await add_request(env)
        return result

    monkeypatch.setattr(env.svc, '_commit', commit)
    task = await execute(env)
    assert task.task_context.metadata['results'][0] == {
        'pipeline_uuid': 'one',
        'state': 'activation_pending',
        'code': 'runtime.pending_interaction',
    }
    env.ap.pipeline_mgr.publish_pipeline.assert_not_called()
    _, snapshots = await rows(env)
    assert snapshots[0]['state'] == 'activation_pending'


@pytest.mark.asyncio
async def test_activation_retry_cannot_erase_pending_form(env):
    env.ap.pipeline_mgr.publish_pipeline.side_effect = RuntimeError('activation failed')
    await execute(env)
    body = await selection(env)
    before = await rows(env)
    await add_request(env)
    with pytest.raises(env.m.MigrationError, match='preview_stale'):
        await env.svc.execute(context(), body)
    assert await rows(env) == before
    assert (await env.svc.preview(context()))['items'][0]['state'] == 'blocked'


@pytest.mark.asyncio
async def test_missing_interaction_table_fails_closed(env):
    async with env.engine.begin() as conn:
        await conn.run_sync(lambda c: AgentInteraction.__table__.drop(c))
    result = await env.svc.preview(context())
    assert result['items'][0]['state'] == 'blocked'
    assert {'code': 'runtime.pending_interaction'} in result['items'][0]['blockers']


@pytest.mark.asyncio
async def test_unknown_native_scope_fails_closed_without_payload(env, monkeypatch):
    native(monkeypatch, workspace='')
    result = await env.svc.preview(context())
    assert result['items'][0]['state'] == 'blocked'
    assert 'private-' not in str(result)


@pytest.mark.asyncio
async def test_terminal_state_change_requires_fresh_preview(env):
    await add_request(env, 'submitted')
    body = await selection(env)
    async with env.engine.begin() as conn:
        await conn.execute(sa.update(AgentInteraction).values(status='cancelled'))
    with pytest.raises(env.m.MigrationError, match='preview_stale'):
        await env.svc.execute(context(), body)


@pytest.mark.asyncio
async def test_unsupported_atomic_boundary_not_advertised_ready(env, monkeypatch):
    from unittest.mock import AsyncMock

    monkeypatch.setattr(env.pm, 'get_db_engine', lambda: NS(dialect=NS(name='unsupported')))
    monkeypatch.setattr(env.pm, 'execute_async', AsyncMock(return_value=NS(all=lambda: [])))
    _, blocked = await env.svc._interaction_state(context(), 'one')
    assert blocked


@pytest.mark.asyncio
async def test_native_form_arriving_during_cas_rolls_back(env, monkeypatch):
    original = env.pm.execute_async

    async def execute_sql(statement, *args, **kwargs):
        result = await original(statement, *args, **kwargs)
        if isinstance(statement, sa.sql.dml.Insert) and statement.table.name == 'pipeline_migration_snapshots':
            native(monkeypatch)
        return result

    monkeypatch.setattr(env.pm, 'execute_async', execute_sql)
    await execute(env)
    configs, snapshots = await rows(env)
    assert configs['one'] == SOURCE and not snapshots
    env.ap.pipeline_mgr.publish_pipeline.assert_not_called()


# Also exercise the unchanged regression assertions with this module's
# interaction-schema fixture. The original tests remain in their own module.

for _name, _test in vars(existing).items():
    if _name.startswith('test_') and callable(_test):
        globals()['test_existing_' + _name[5:]] = _test
