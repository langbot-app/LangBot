from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

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
        dispatch_test_event_route=AsyncMock(
            return_value={
                'dispatched': True,
                'event_type': 'message.received',
                'suppressed_outputs': [],
                'route_status': {
                    'routes': [],
                    'unmatched_events': [],
                    'stale_routes': [],
                },
            }
        ),
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
    assert 'test_bot_event_route' in tool_names


@pytest.mark.asyncio
async def test_mcp_test_bot_event_route_calls_service_layer():
    app = _make_app()
    server = LangBotMCPServer(app)

    result_blocks, _ = await server.mcp.call_tool(
        'test_bot_event_route',
        {
            'bot_uuid': 'bot-1',
            'event_type': 'message.received',
            'payload': {'message_text': 'hello'},
        },
    )

    app.bot_service.dispatch_test_event_route.assert_awaited_once_with(
        bot_uuid='bot-1',
        event_type='message.received',
        payload={'message_text': 'hello'},
    )
    data = json.loads(result_blocks[0].text)
    assert data['dispatched'] is True
    assert data['event_type'] == 'message.received'
