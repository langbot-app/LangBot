from __future__ import annotations

import sys
import types
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock

import pytest
import quart

core_app_module = types.ModuleType('langbot.pkg.core.app')
core_app_module.Application = object
sys.modules.setdefault('langbot.pkg.core.app', core_app_module)


pytestmark = pytest.mark.asyncio


async def _create_test_client(agent_service: SimpleNamespace):
    app = quart.Quart(__name__)
    account = SimpleNamespace(
        uuid='account-test',
        user='test@example.com',
    )
    user_service = SimpleNamespace(
        get_authenticated_account=AsyncMock(return_value=account),
    )
    access = SimpleNamespace(
        workspace=SimpleNamespace(uuid='workspace-test'),
        membership=SimpleNamespace(
            uuid='membership-test',
            role='developer',
            projection_revision=1,
        ),
        execution=SimpleNamespace(
            instance_uuid='instance-test',
            placement_generation=1,
        ),
    )
    ap = SimpleNamespace(
        agent_service=agent_service,
        user_service=user_service,
        apikey_service=SimpleNamespace(
            authenticate_api_key=AsyncMock(return_value=None)
        ),
        workspace_collaboration_service=SimpleNamespace(
            resolve_account_workspace=AsyncMock(return_value=access)
        ),
    )
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
        ANY,
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
        ANY,
        'agent-1',
        {'config': {'runner': {'id': 7}}},
    )
