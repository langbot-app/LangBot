"""Runner selection must survive restricted extension preferences on disk."""

from types import SimpleNamespace as NS
import json
from unittest.mock import AsyncMock, Mock

import pytest
import sqlalchemy as sa

from langbot.pkg.api.http.service.pipeline import PipelineService
from langbot.pkg.entity.persistence.pipeline import LegacyPipeline
from langbot.pkg.workspace.errors import WorkspaceNotFoundError
from tests.unit_tests.api.service.test_pipeline_migration import env, context, RID  # noqa: F401


@pytest.mark.asyncio
async def test_http_and_mcp_share_real_persistence_without_expanding_extensions(env, monkeypatch):  # noqa: F811
    from quart import Quart
    from langbot.pkg.api.http.controller.groups.pipelines.pipelines import PipelinesRouterGroup
    from langbot.pkg.api.mcp.server import LangBotMCPServer

    monkeypatch.setattr('langbot.pkg.api.http.service.workspace_limits.workspace_limits', AsyncMock(return_value={}))
    monkeypatch.setattr('langbot.pkg.api.mcp.server.get_request_context', context)
    monkeypatch.setattr('langbot.pkg.api.mcp.server.get_workspace_language', AsyncMock(return_value='en_US'))
    monkeypatch.setattr('langbot.pkg.api.http.controller.group.get_workspace_language', AsyncMock(return_value='en_US'))
    env.ap.ver_mgr = NS(get_current_version=Mock(return_value='4.10'))
    env.ap.pipeline_mgr.load_pipeline = AsyncMock()
    env.ap.pipeline_mgr.remove_pipeline = AsyncMock()
    env.ap.pipeline_service = PipelineService(env.ap)
    app = Quart(__name__)
    routes = PipelinesRouterGroup(env.ap, app)
    monkeypatch.setattr(routes, '_authenticate_api_key', AsyncMock(return_value=context()))
    monkeypatch.setattr(routes, '_record_operation', AsyncMock())
    await routes.initialize()
    http = app.test_client()
    mcp = LangBotMCPServer(env.ap)
    headers = {'X-API-Key': 'isolated-test-key'}
    config = {
        'ai': {
            'runner': {'id': RID, 'expire-time': 0},
            'runner_config': {RID: {'unknown': {'keep': [None, False, '  raw  ']}}},
        }
    }
    prefs = {'enable_all_plugins': False, 'plugins': [], 'enable_all_mcp_servers': False, 'mcp_servers': []}
    async with env.engine.begin() as conn:
        await conn.execute(
            sa.update(LegacyPipeline)
            .where(LegacyPipeline.uuid == 'one')
            .values(config=config, extensions_preferences=prefs)
        )
    response = await http.put('/api/v1/pipelines/one', headers=headers, json={'config': config})
    assert response.status_code == 200, await response.get_data(as_text=True)
    assert (await response.get_json())['code'] == 0
    result = await mcp.mcp.call_tool('get_pipeline', {'pipeline_uuid': 'one'})
    saved = json.loads(result[0][0].text)
    assert saved['config'] == config
    assert saved['extensions_preferences'] == prefs
    config['ai']['runner_config'][RID]['edited'] = 'via MCP'
    result = await mcp.mcp.call_tool('update_pipeline', {'pipeline_uuid': 'one', 'pipeline_data': {'config': config}})
    assert json.loads(result[0][0].text) == {'ok': True}
    copied_response = await http.post('/api/v1/pipelines/one/copy', headers=headers)
    assert copied_response.status_code == 200, await copied_response.get_data(as_text=True)
    copied = (await copied_response.get_json())['data']['uuid']
    for pipeline_id in ('one', copied):
        response = await http.get(f'/api/v1/pipelines/{pipeline_id}', headers=headers)
        saved = (await response.get_json())['data']['pipeline']
        assert saved['config'] == config
        assert saved['extensions_preferences']['plugins'] == []
        assert saved['extensions_preferences']['enable_all_plugins'] is False
        async with env.engine.connect() as conn:
            row = (
                await conn.execute(
                    sa.select(LegacyPipeline.config, LegacyPipeline.extensions_preferences).where(
                        LegacyPipeline.uuid == pipeline_id
                    )
                )
            ).one()
        assert row.config == config
        assert row.extensions_preferences['plugins'] == []
        assert row.extensions_preferences['enable_all_plugins'] is False
    body = {'name': 'HTTP creation', 'description': '', 'config': config, 'extensions_preferences': prefs}
    response = await http.post('/api/v1/pipelines', headers=headers, json=body)
    assert response.status_code == 200, await response.get_data(as_text=True)
    http_id = (await response.get_json())['data']['uuid']
    body['name'] = 'MCP creation'
    result = await mcp.mcp.call_tool('create_pipeline', {'pipeline_data': body})
    mcp_id = json.loads(result[0][0].text)['uuid']
    for pipeline_id in (http_id, mcp_id):
        saved = await env.ap.pipeline_service.get_pipeline(context(), pipeline_id, include_secret=True)
        assert saved['config'] == config
        assert saved['extensions_preferences'] == prefs


@pytest.mark.asyncio
async def test_edit_and_copy_do_not_expand_extension_permissions(env, monkeypatch):  # noqa: F811
    monkeypatch.setattr(
        'langbot.pkg.api.http.service.workspace_limits.workspace_limits',
        AsyncMock(return_value={}),
    )
    env.ap.ver_mgr = NS(get_current_version=Mock(return_value='4.10'))
    env.ap.pipeline_mgr.load_pipeline = AsyncMock()
    env.ap.pipeline_mgr.remove_pipeline = AsyncMock()
    service = PipelineService(env.ap)
    config = {'ai': {'runner': {'id': RID}, 'runner_config': {RID: {}}}}
    prefs = {'enable_all_plugins': False, 'plugins': [], 'enable_all_mcp_servers': False, 'mcp_servers': []}
    # Existing, pre-fix configuration: selected Runner with no extensions.
    async with env.engine.begin() as conn:
        await conn.execute(
            sa.update(LegacyPipeline)
            .where(LegacyPipeline.uuid == 'one')
            .values(
                config=config,
                extensions_preferences=prefs,
            )
        )
    await service.update_pipeline(context(), 'one', {'config': config, 'name': 'Edited'})
    copied = await service.copy_pipeline(context(), 'one')
    for pid in ('one', copied):
        saved = await service.get_pipeline(context(), pid, include_secret=True)
        assert saved['config'] == config
        assert saved['extensions_preferences']['plugins'] == []
        assert saved['extensions_preferences']['enable_all_plugins'] is False
    with pytest.raises(WorkspaceNotFoundError):
        await service.copy_pipeline(context(), 'foreign')
