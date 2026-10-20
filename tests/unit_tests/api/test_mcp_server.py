from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from langbot.pkg.api.mcp import server as mcp_server
from langbot.pkg.api.mcp.server import LangBotMCPServer


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
    context = SimpleNamespace(workspace_uuid='workspace-1')
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
        app.monitoring_service.get_sessions.assert_awaited_once_with(context, limit=100, offset=0, **filters)
