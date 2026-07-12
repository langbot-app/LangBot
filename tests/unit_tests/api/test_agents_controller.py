from __future__ import annotations

import sys
import types
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import quart

core_app_module = types.ModuleType('langbot.pkg.core.app')
core_app_module.Application = object
sys.modules.setdefault('langbot.pkg.core.app', core_app_module)


pytestmark = pytest.mark.asyncio


async def _create_test_client(agent_service: SimpleNamespace):
    app = quart.Quart(__name__)
    user_service = SimpleNamespace(
        verify_jwt_token=AsyncMock(return_value='test@example.com'),
        get_user_by_email=AsyncMock(return_value=SimpleNamespace(user='test@example.com')),
    )
    ap = SimpleNamespace(agent_service=agent_service, user_service=user_service)
    AgentsRouterGroup = import_module('langbot.pkg.api.http.controller.groups.agents').AgentsRouterGroup
    group = AgentsRouterGroup(ap, app)
    await group.initialize()
    return app.test_client()


async def test_create_agent_returns_bad_request_for_invalid_runner_config():
    message = 'agent config runner_config must be an object'
    agent_service = SimpleNamespace(create_agent=AsyncMock(side_effect=ValueError(message)))
    client = await _create_test_client(agent_service)

    response = await client.post(
        '/api/v1/agents',
        json={'name': 'Invalid Agent', 'config': {'runner_config': []}},
        headers={'Authorization': 'Bearer test-token'},
    )

    assert response.status_code == 400
    assert await response.get_json() == {'code': -1, 'msg': message}
    agent_service.create_agent.assert_awaited_once_with(
        {'name': 'Invalid Agent', 'config': {'runner_config': []}},
    )


async def test_update_agent_returns_bad_request_for_invalid_runner_config():
    message = 'agent config runner.id must be a string'
    agent_service = SimpleNamespace(update_agent=AsyncMock(side_effect=ValueError(message)))
    client = await _create_test_client(agent_service)

    response = await client.put(
        '/api/v1/agents/agent-1',
        json={'config': {'runner': {'id': 7}}},
        headers={'Authorization': 'Bearer test-token'},
    )

    assert response.status_code == 400
    assert await response.get_json() == {'code': -1, 'msg': message}
    agent_service.update_agent.assert_awaited_once_with(
        'agent-1',
        {'config': {'runner': {'id': 7}}},
    )
