"""Shared admission and real embedded artifact schema regressions."""

import copy
import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
import sqlalchemy as sa
from tests.unit_tests.api.service.test_pipeline_migration import (
    env as migration_env,
    execute,
    WS,
    SOURCE,
    RID,
    planner,
)
from langbot.pkg.agent.runner.interaction_store import InteractionStore, InteractionScopeError
from langbot.pkg.entity.persistence.agent_interaction import AgentInteraction


@pytest.fixture
async def env(tmp_path, monkeypatch):
    async for value in migration_env.__wrapped__(tmp_path, monkeypatch):
        yield value


async def request(env, **kwargs):
    return await InteractionStore(env.pm.get_db_engine()).create_request(
        interaction_id='form',
        run_id='run',
        binding_id='binding',
        runner_id=RID,
        processor_type='pipeline',
        processor_id='one',
        workspace_id=WS,
        request={},
        delivery_target={},
        expected_config=copy.deepcopy(SOURCE),
        authority_check=lambda: True,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_stale_writer_after_commit_rejected(env):
    original = env.svc._activate

    async def activate(*args):
        with pytest.raises(InteractionScopeError):
            await request(env)
        return await original(*args)

    env.svc._activate = activate
    task = await execute(env)
    assert task.task_context.metadata['results'][0]['state'] == 'migrated'
    with pytest.raises(InteractionScopeError):
        await request(env)
    async with env.engine.connect() as conn:
        assert not (await conn.execute(sa.select(AgentInteraction))).all()


@pytest.mark.asyncio
async def test_writer_requires_pipeline_authority(env):
    with pytest.raises(InteractionScopeError):
        await InteractionStore(env.engine).create_request(
            interaction_id='form',
            run_id='run',
            binding_id='binding',
            runner_id=RID,
            processor_type='pipeline',
            processor_id='one',
            workspace_id=WS,
            request={},
            delivery_target={},
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'folder,field,good,bad',
    [
        ('LangflowAgent', 'tweaks', {'node': {'value': 1}}, ['not-an-object']),
        ('WeKnoraAgent', 'knowledge-base-ids', ['kb-a'], [1]),
    ],
)
async def test_embedded_artifact_schema_types(env, folder, field, good, bad):
    root = Path(__file__).parent / 'fixtures'
    artifact = 'langflow-agent' if folder == 'LangflowAgent' else 'weknora-agent'
    spec = {'config': json.loads((root / (artifact + '-artifact-schema.json')).read_text())}
    kind = 'json' if folder == 'LangflowAgent' else 'array[string]'
    schema = next(s for s in spec['config'] if s['type'] == kind)
    descriptor = env.ap.runner_registry.list_runners.return_value[0]
    descriptor.config_schema = [schema]
    plan = planner(SOURCE)
    plan['config']['ai']['runner_config'][RID] = {schema['name']: good}
    await env.svc._verify_runtime(NS(workspace_uuid=WS), plan)
    plan['config']['ai']['runner_config'][RID][schema['name']] = bad
    with pytest.raises(env.m.MigrationError, match='runner_schema_incompatible'):
        await env.svc._verify_runtime(NS(workspace_uuid=WS), plan)


def test_conversation_authority_is_captured_before_runner_returns():
    from langbot.pkg.agent.runner.interaction_manager import InteractionManager

    old, new = NS(), NS()
    config = planner(SOURCE)['config']
    query = NS(pipeline_config=config, pipeline_uuid='one', session=NS(using_conversation=new))
    binding = NS(
        processor_type='pipeline', processor_id='one', runner_id=RID, runner_config=config['ai']['runner_config'][RID]
    )
    authority = InteractionManager._pipeline_admission(
        binding,
        NS(id=RID),
        {
            '_query': query,
            '_pipeline_expected_config': copy.deepcopy(config),
            '_pipeline_conversation': old,
        },
    )
    assert authority['authority_check']() is False
