"""Actual planner + artifact descriptors + migration service + SQLite snapshots.

Vendor calls and runtime publication are fixtures. Database writes, snapshots,
scoped service validation, and converter output are real. Browser tests consume
this same synthetic contract, without requiring Python or a sibling checkout.
"""

import copy
import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest
import sqlalchemy as sa
import yaml

from langbot.pkg.agent.runner.descriptor import RunnerDescriptor
from langbot.pkg.entity.persistence.model import LLMModel, ModelProvider
from langbot.pkg.pipeline.legacy_config_migration import PLANNER_VERSION, plan_legacy_pipeline
from tests.unit_tests.api.service import test_pipeline_migration as base

ROOT = Path(__file__).parents[4]
CONTRACT = json.loads((ROOT / 'web/tests/e2e/fixtures/runner-migration-contract.json').read_text())
env = base.env


@pytest.mark.parametrize('case', CONTRACT['cases'], ids=lambda case: case['legacy_runner'])
def test_portable_browser_contract_matches_actual_converter(case):
    assert CONTRACT['planner_version'] == PLANNER_VERSION
    assert plan_legacy_pipeline(case['source']) == case['plan']
    assert len(CONTRACT['cases']) == len(CONTRACT['plugins']) == 9
    for name in ('ai', 'output'):
        schema = yaml.safe_load((ROOT / f'src/langbot/templates/metadata/pipeline/{name}.yaml').read_text())
        assert CONTRACT[f'{name}_schema'] == schema


@pytest.mark.asyncio
@pytest.mark.parametrize('source_mode', ['local', 'cloud_projection'])
@pytest.mark.parametrize('case', CONTRACT['cases'], ids=lambda case: case['legacy_runner'])
async def test_all_runner_service_roundtrip_retains_complete_backup(env, monkeypatch, case, source_mode):
    monkeypatch.setattr(env.m, 'plan_legacy_pipeline', plan_legacy_pipeline)
    source = copy.deepcopy(case['source'])
    plan = plan_legacy_pipeline(source)
    target = plan['target_plugin']
    artifact = next(
        item for item in CONTRACT['plugins'].values() if item['manifest']['metadata']['name'] == target['name']
    )
    schema = artifact['component']['spec']
    env.ap.runner_registry.list_runners.return_value = [
        RunnerDescriptor(
            id=plan['target_runner_id'],
            source='plugin',
            label={},
            plugin_author=target['author'],
            plugin_name=target['name'],
            plugin_version=target['version'],
            runner_name='default',
            usages=schema['usages'],
            config_schema=schema['config'],
            capabilities=schema.get('capabilities', {}),
            permissions=schema.get('permissions', {}),
        )
    ]
    env.ap.logger = Mock()
    env.ap.tool_mgr = NS(
        get_resolved_tool_catalog=AsyncMock(return_value=[]), get_tool_schema=AsyncMock(return_value=('', {}))
    )
    async with env.engine.begin() as conn:
        await conn.run_sync(
            lambda c: ModelProvider.metadata.create_all(c, tables=[ModelProvider.__table__, LLMModel.__table__])
        )
        await conn.execute(
            sa.insert(ModelProvider).values(
                uuid='fixture-provider',
                workspace_uuid=base.WS,
                name='fixture',
                requester='test',
                base_url='https://synthetic.invalid',
            )
        )
        await conn.execute(
            sa.insert(LLMModel).values(
                uuid='synthetic-model', workspace_uuid=base.WS, name='fixture', provider_uuid='fixture-provider'
            )
        )
        await conn.execute(sa.update(base.Workspace).where(base.Workspace.uuid == base.WS).values(source=source_mode))
        await conn.execute(
            sa.update(base.LegacyPipeline).where(base.LegacyPipeline.uuid == 'one').values(config=source)
        )
        await conn.execute(
            sa.insert(base.PluginSetting).values(
                workspace_uuid=base.WS,
                plugin_author=target['author'],
                plugin_name=target['name'],
                enabled=True,
                install_info={'version': target['version']},
            )
        )
    before, snapshots = await base.rows(env)
    assert not snapshots
    preview = await env.svc.preview(base.context())
    selected = next(row for row in preview['items'] if row['pipeline_uuid'] == 'one')
    assert selected['state'] == 'ready', selected['blockers']
    assert selected['preview_token']
    assert await base.rows(env) == (before, snapshots)
    task = await base.execute(
        env, {'confirmed': True, 'items': [{key: selected[key] for key in ('pipeline_uuid', 'preview_token')}]}
    )
    assert task.task_context.metadata['results'] == [{'pipeline_uuid': 'one', 'state': 'migrated', 'code': None}]
    configs, backups = await base.rows(env)
    assert configs['one'] == plan['config']
    assert set(configs['one']['ai']) == {'runner', 'runner_config'}
    assert configs['two'] == before['two'] and configs['foreign'] == before['foreign']
    assert len(backups) == 1
    assert backups[0]['source_snapshot']['config'] == source
    assert set(backups[0]['source_snapshot']['config']['ai']) == {'runner', *CONTRACT['legacy_sections']}
    assert backups[0]['state'] == 'active'
    env.ap.pipeline_mgr.publish_pipeline.assert_called_once()
