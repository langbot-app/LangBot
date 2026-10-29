"""Narrow write scopes retain HTTP audit snapshots without acquiring read access."""

import json

import pytest
import quart
import sqlalchemy as sa

from langbot.pkg.api.http.controller.groups.knowledge.base import KnowledgeBaseRouterGroup
from langbot.pkg.api.http.controller.groups.pipelines.pipelines import PipelinesRouterGroup
from langbot.pkg.api.http.controller.groups.provider.models import LLMModelsRouterGroup
from langbot.pkg.api.http.controller.groups.provider.providers import ModelProvidersRouterGroup
from langbot.pkg.api.http.controller.groups.skills import SkillsRouterGroup
from langbot.pkg.api.http.service.skill import SkillService
from langbot.pkg.entity.persistence.operation_log import WorkspaceOperationLog
from langbot.pkg.operation_trace import service as tracing
from langbot.pkg.skill.repository import SkillRepository
from tests.integration.api.test_application_foundation import context, foundation  # noqa: F401
from tests.integration.api.test_application_resources import resources  # noqa: F401


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('kind', ['pipeline', 'pipeline_extensions', 'provider', 'model', 'knowledge', 'skill'])
async def test_write_only_keys_preserve_before_values_and_one_redacted_audit(resources, tmp_path, monkeypatch, kind):  # noqa: F811
    api, ap, engine = resources
    ap.application_api = api
    scope = 'provider_secret.manage' if kind in {'provider', 'model'} else 'resource.manage'
    key = (await ap.apikey_service.create_api_key(context(), 'writer', scopes=[scope]))['key']
    empty_key = (await ap.apikey_service.create_api_key(context(), 'empty', scopes=[]))['key']
    body = {'name': 'after'}
    expected_change = {'field': 'name', 'before': 'before', 'after': 'after'}
    if kind.startswith('pipeline'):
        identity = await api.execute(
            'pipeline.create',
            context(),
            {
                'pipeline_data': {
                    'name': 'before',
                    'config': {'ai': {'api_key': 'old-secret'}},
                    'extensions_preferences': {'enable_all_plugins': False, 'plugins': []},
                }
            },
        )
        endpoint = '/api/v1/pipelines/' + identity
        router = PipelinesRouterGroup
        if kind == 'pipeline_extensions':
            endpoint += '/extensions'
            body = {'enable_all_plugins': True}
            expected_change = {'field': 'enable_all_plugins', 'before': False, 'after': True}
        else:
            body['config'] = {'ai': {'api_key': 'new-secret'}}
    elif kind in {'provider', 'model'}:
        provider = await api.execute(
            'provider.create',
            context(),
            {
                'provider_data': {
                    'name': 'before',
                    'requester': 'test-requester',
                    'base_url': 'https://example.test/v1',
                    'api_keys': ['old-secret'],
                }
            },
        )
        if kind == 'provider':
            endpoint = '/api/v1/provider/providers/' + provider
            router = ModelProvidersRouterGroup
            body['api_keys'] = ['new-secret']
        else:
            identity = await api.execute(
                'model.llm.create',
                context(),
                {'model_data': {'name': 'before', 'provider_uuid': provider, 'extra_args': {'api_key': 'old-secret'}}},
            )
            endpoint = '/api/v1/provider/models/llm/' + identity
            router = LLMModelsRouterGroup
            body['extra_args'] = {'api_key': 'new-secret'}
    elif kind == 'knowledge':
        identity = await api.execute(
            'knowledge.base.create',
            context(),
            {
                'kb_data': {
                    'name': 'before',
                    'knowledge_engine_plugin_id': 'test/engine',
                    'defer_initialization': True,
                    'creation_settings': {'api_key': 'old-secret'},
                }
            },
        )
        endpoint = '/api/v1/knowledge/bases/' + identity
        router = KnowledgeBaseRouterGroup
    else:
        ap.instance_config.data['skills'] = {'root': str(tmp_path / 'skills')}
        ap.skill_repository = SkillRepository(ap)
        ap.skill_service = SkillService(ap)
        skill = await api.execute(
            'skill.create',
            context(),
            {'data': {'name': 'audit-skill', 'description': 'before', 'instructions': 'Read me'}},
        )
        endpoint = '/api/v1/skills/audit-skill'
        router = SkillsRouterGroup
        body = {'description': 'after', 'base_revision': skill['revision']}
        expected_change = {'field': 'description', 'before': 'before', 'after': 'after'}
    monkeypatch.setattr(tracing, '_global_enabled', False)
    audit = ap.workspace_settings_service = tracing.WorkspaceSettingsService(ap)
    await audit.set_operation_level('workspace-a', tracing.OPERATION_LEVEL_MUTATION, dedupe_window_seconds=0)
    app = quart.Quart(__name__)
    await router(ap, app).initialize()
    client = app.test_client()
    headers = {'X-API-Key': key}
    assert (await client.get(endpoint, headers=headers)).status_code == 403
    assert (await client.put(endpoint, headers={'X-API-Key': empty_key}, json=body)).status_code == 403
    response = await client.put(endpoint, headers={**headers, 'X-Request-Id': 'write-audit'}, json=body)
    assert response.status_code == 200, await response.get_data(as_text=True)
    await audit.flush_pending()
    async with engine.connect() as connection:
        rows = (
            (
                await connection.execute(
                    sa.select(WorkspaceOperationLog).where(WorkspaceOperationLog.request_id == 'write-audit')
                )
            )
            .mappings()
            .all()
        )
    assert len(rows) == 1
    assert rows[0]['status_code'] == 200 and rows[0]['outcome'] == 'ok'
    assert expected_change in json.loads(rows[0]['changes'])
    assert 'old-secret' not in str(rows[0]) and 'new-secret' not in str(rows[0])
    assert (await client.get(endpoint, headers=headers)).status_code == 403
