import types

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

    async def fake_get_default_config(context):
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
