from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from langbot.pkg.api.mcp import server as mcp_server
from langbot.pkg.api.mcp.server import LangBotMCPServer
from langbot.pkg.api.context import RequestContext, PrincipalContext, PrincipalType, WorkspaceContext
from langbot.pkg.api.authz import permissions_for_role
from tests.utils.application_api import bind_application_api


def _make_app() -> SimpleNamespace:
    app = SimpleNamespace()
    app.instance_config = SimpleNamespace(data={'system': {'edition': 'community', 'instance_id': 'inst-1'}})
    app.ver_mgr = SimpleNamespace(get_current_version=lambda: 'test-version')
    app.bot_service = SimpleNamespace(
        get_bots=AsyncMock(return_value=[]),
        get_bot=AsyncMock(return_value={'uuid': 'bot-1'}),
        create_bot=AsyncMock(return_value='bot-1'),
        update_bot=AsyncMock(),
        delete_bot=AsyncMock(),
        list_event_route_statuses=AsyncMock(return_value={'routes': [], 'unmatched_events': [], 'stale_routes': []}),
    )
    app.pipeline_service = SimpleNamespace(
        get_pipelines=AsyncMock(return_value=[]),
        get_pipeline=AsyncMock(return_value={}),
        create_pipeline=AsyncMock(return_value='pipeline-1'),
        update_pipeline=AsyncMock(),
        delete_pipeline=AsyncMock(),
    )
    app.agent_service = SimpleNamespace(
        get_agents=AsyncMock(return_value=[]),
        get_agent=AsyncMock(return_value={}),
        create_agent=AsyncMock(return_value={'uuid': 'agent-1', 'kind': 'agent'}),
        update_agent=AsyncMock(),
        delete_agent=AsyncMock(),
    )
    app.llm_model_service = SimpleNamespace(
        get_llm_models=AsyncMock(return_value=[]),
        get_llm_model=AsyncMock(return_value={}),
    )
    app.embedding_models_service = SimpleNamespace(get_embedding_models=AsyncMock(return_value=[]))
    app.provider_service = SimpleNamespace(get_providers=AsyncMock(return_value=[]))
    app.knowledge_service = SimpleNamespace(
        get_knowledge_bases=AsyncMock(return_value=[]),
        get_knowledge_base=AsyncMock(return_value={}),
        retrieve_knowledge_base=AsyncMock(return_value=[]),
    )
    app.mcp_service = SimpleNamespace(get_mcp_servers=AsyncMock(return_value=[]))
    app.skill_service = SimpleNamespace(
        list_skills=AsyncMock(return_value=[]),
        get_skill=AsyncMock(return_value={}),
    )
    return app


@pytest.mark.asyncio
async def test_mcp_server_exposes_bot_event_route_tools():
    app = _make_app()
    server = LangBotMCPServer(app)

    tools = await server.mcp.list_tools()
    tool_names = {tool.name for tool in tools}

    assert 'list_bot_event_route_statuses' in tool_names
    assert 'test_bot_event_route' not in tool_names
    assert 'list_processors' in tool_names
    assert 'list_agents' not in tool_names
    assert 'get_workspace_message_language' in tool_names
    language_tool = next(tool for tool in tools if tool.name == 'set_workspace_message_language')
    assert set(language_tool.inputSchema['properties']['language']['enum']) == {
        'en_US',
        'zh_Hans',
        'zh_Hant',
        'ja_JP',
        'es_ES',
        'ru_RU',
        'th_TH',
        'vi_VN',
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'filters', [{}, {'bot_ids': ['bot-1'], 'user_query': 'Alice'}, {'mode': 'real'}, {'execution_statuses': ['failed']}]
)
async def test_monitoring_sessions_accept_only_conversation_filters(monkeypatch, filters):
    app = _make_app()
    app.monitoring_service = SimpleNamespace(
        normalize_page_window=lambda limit, offset: (limit, offset),
        get_sessions=AsyncMock(return_value=([], 0)),
    )
    context = RequestContext(
        'instance',
        1,
        'request',
        'api_key',
        PrincipalContext(PrincipalType.API_KEY, api_key_uuid='key'),
        WorkspaceContext('workspace-1', None, 'developer', permissions_for_role('developer')),
    )
    bind_application_api(app, context)
    monkeypatch.setattr(mcp_server, 'get_request_context', lambda: context)
    monkeypatch.setattr(mcp_server, '_authorized', lambda permission: context)
    monkeypatch.setattr(mcp_server, 'get_workspace_language', AsyncMock(return_value='en_US'))
    server = LangBotMCPServer(app)

    arguments = {'kind': 'sessions', 'filters': filters}
    if set(filters) & {'mode', 'execution_statuses'}:
        with pytest.raises(ToolError, match='Unsupported monitoring filter'):
            await server.mcp.call_tool('get_monitoring_records', arguments)
        app.monitoring_service.get_sessions.assert_not_awaited()
    else:
        await server.mcp.call_tool('get_monitoring_records', arguments)
        app.monitoring_service.get_sessions.assert_awaited_once()
        args, kwargs = app.monitoring_service.get_sessions.call_args
        assert args == (context,)
        assert kwargs['limit'] == 100 and kwargs['offset'] == 0
        assert all(kwargs[key] == value for key, value in filters.items())


@pytest.mark.asyncio
async def test_mcp_application_binding_permissions_and_default_pipeline(monkeypatch):
    import json
    from dataclasses import replace

    app = _make_app()
    context = RequestContext(
        'instance',
        1,
        'request',
        'api_key',
        PrincipalContext(PrincipalType.API_KEY, api_key_uuid='key'),
        WorkspaceContext('workspace-1', None, 'developer', permissions_for_role('developer')),
    )
    bind_application_api(app, context)
    monkeypatch.setattr(mcp_server, 'get_request_context', lambda: context)
    server = LangBotMCPServer(app)
    result = await server.mcp.call_tool('create_pipeline', {'pipeline_data': {'name': 'Default', 'is_default': True}})
    assert json.loads(result[0][0].text) == {'uuid': 'pipeline-1'}
    assert app.pipeline_service.create_pipeline.call_args.kwargs['default'] is True
    assert app.pipeline_service.create_pipeline.call_args.kwargs['pipeline_data'] == {
        'name': 'Default',
        'is_default': True,
    }
    app.pipeline_service.create_pipeline.reset_mock()

    context = replace(
        context, workspace=replace(context.workspace, role='viewer', permissions=permissions_for_role('viewer'))
    )
    with pytest.raises(ToolError, match='resource.manage'):
        await server.mcp.call_tool('create_pipeline', {'pipeline_data': {'name': 'Denied'}})
    app.pipeline_service.create_pipeline.assert_not_awaited()

    app.workspace_service.get_execution_binding.return_value.instance_uuid = 'other-instance'
    with pytest.raises(ToolError, match='different instance'):
        await server.mcp.call_tool('list_pipelines', {})
    app.pipeline_service.get_pipelines.assert_not_awaited()
