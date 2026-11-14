import types
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.api.http.service.pipeline import PipelineService


async def _noop(*args, **kwargs):
    return None


@pytest.mark.asyncio
async def test_create_pipeline_defaults_missing_description(monkeypatch):
    """legacy_pipelines.description is NOT NULL; omitting it must not 500."""
    captured = {}

    app = types.SimpleNamespace()
    app.persistence_mgr = types.SimpleNamespace()
    app.pipeline_mgr = types.SimpleNamespace(load_pipeline=_noop)
    app.ver_mgr = types.SimpleNamespace(get_current_version=lambda: 'v4.11.1')

    service = PipelineService.__new__(PipelineService)
    service.ap = app

    async def fake_get_default_config(context, runner_id=None):
        runner_id = 'plugin:langbot-team/LocalAgent/default'
        return {
            'ai': {
                'runner': {'id': runner_id},
                'runner_config': {runner_id: {'model': {'primary': '', 'fallbacks': []}}},
            }
        }

    async def fake_get_pipelines(context, *args, **kwargs):
        return []

    async def fake_get_pipeline(context, uuid_value, include_secret=True):
        return {'uuid': uuid_value}

    async def fake_insert(statement):
        captured['statement'] = statement

    async def fake_limits(*args, **kwargs):
        return {'max_pipelines': -1}

    monkeypatch.setattr(service, 'get_default_pipeline_config', fake_get_default_config)
    monkeypatch.setattr(service, 'get_pipelines', fake_get_pipelines)
    monkeypatch.setattr(service, 'get_pipeline', fake_get_pipeline)
    monkeypatch.setattr('langbot.pkg.api.http.service.workspace_limits.workspace_limits', fake_limits)
    app.persistence_mgr.execute_async = fake_insert

    await service.create_pipeline('workspace-a', {'name': 'de-agent-test'})

    params = captured['statement'].compile().params
    assert params.get('description') == ''
    assert params.get('workspace_uuid') == 'workspace-a'


@pytest.mark.asyncio
async def test_create_pipeline_rejects_unsupported_reasoning_level_before_insert(monkeypatch):
    async def fake_limits(*args, **kwargs):
        return {'max_pipelines': -1}

    capabilities = {'supported': True, 'levels': ['provider_default', 'disabled', 'low', 'high', 'max']}
    model = types.SimpleNamespace(
        model_entity=types.SimpleNamespace(name='deepseek-flash', abilities=['reasoning'], extra_args={}),
        provider=types.SimpleNamespace(
            provider_entity=types.SimpleNamespace(requester='deepseek-chat-completions'),
            requester=types.SimpleNamespace(get_reasoning_capabilities=lambda model: capabilities),
        ),
    )
    app = types.SimpleNamespace(
        persistence_mgr=types.SimpleNamespace(execute_async=AsyncMock()),
        pipeline_mgr=types.SimpleNamespace(load_pipeline=_noop),
        ver_mgr=types.SimpleNamespace(get_current_version=lambda: 'v4.11.1'),
        model_mgr=types.SimpleNamespace(get_model_by_uuid=AsyncMock(return_value=model)),
    )
    service = PipelineService(app)
    monkeypatch.setattr(service, 'get_pipeline', AsyncMock(return_value={'uuid': 'pipeline'}))
    monkeypatch.setattr('langbot.pkg.api.http.service.workspace_limits.workspace_limits', fake_limits)
    runner_id = 'plugin:langbot-team/LocalAgent/default'
    config = {
        'ai': {
            'runner': {'id': runner_id},
            'runner_config': {
                runner_id: {'model': {'primary': 'model', 'fallbacks': [], 'reasoning': {'model': 'medium'}}},
            },
        }
    }

    with pytest.raises(ValueError, match='not supported by model deepseek-flash'):
        await service.create_pipeline('workspace-a', {'name': 'bad-level', 'config': config})

    app.persistence_mgr.execute_async.assert_not_awaited()
