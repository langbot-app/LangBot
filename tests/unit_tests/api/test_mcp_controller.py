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


async def _create_test_client(mcp_service: SimpleNamespace, *, role: str = 'owner'):
    app = quart.Quart(__name__)
    user_service = SimpleNamespace(
        verify_jwt_token=AsyncMock(return_value='test@example.com'),
        get_user_by_email=AsyncMock(
            return_value=SimpleNamespace(
                user='test@example.com',
                uuid='account-a',
            )
        ),
    )
    workspace_collaboration_service = SimpleNamespace(
        resolve_account_workspace=AsyncMock(
            return_value=SimpleNamespace(
                execution=SimpleNamespace(
                    instance_uuid='instance-a',
                    placement_generation=1,
                ),
                workspace=SimpleNamespace(uuid='workspace-a'),
                membership=SimpleNamespace(
                    uuid='membership-a',
                    role=role,
                    projection_revision=1,
                ),
            )
        )
    )
    ap = SimpleNamespace(
        mcp_service=mcp_service,
        user_service=user_service,
        workspace_collaboration_service=workspace_collaboration_service,
    )
    MCPRouterGroup = import_module('langbot.pkg.api.http.controller.groups.resources.mcp').MCPRouterGroup
    group = MCPRouterGroup(ap, app)
    await group.initialize()
    return app.test_client()


async def test_viewer_cannot_read_mcp_runtime_logs():
    mcp_service = SimpleNamespace(
        get_mcp_server_logs=AsyncMock(return_value=['private runtime line']),
    )
    client = await _create_test_client(mcp_service, role='viewer')

    response = await client.get(
        '/api/v1/mcp/servers/example/logs',
        headers={
            'Authorization': 'Bearer test-token',
            'X-Workspace-Id': 'workspace-a',
        },
    )

    assert response.status_code == 403
    assert (await response.get_json())['code'] == 'permission_denied'
    mcp_service.get_mcp_server_logs.assert_not_awaited()


async def test_mcp_server_route_accepts_encoded_slash_name():
    mcp_service = SimpleNamespace(
        get_mcp_server_by_name=AsyncMock(
            return_value={
                'uuid': 'test-uuid',
                'name': 'pab1it0/prometheus',
                'enable': True,
                'mode': 'stdio',
                'extra_args': {},
            }
        )
    )
    client = await _create_test_client(mcp_service)

    response = await client.get(
        '/api/v1/mcp/servers/pab1it0%2Fprometheus',
        headers={
            'Authorization': 'Bearer test-token',
            'X-Workspace-Id': 'workspace-a',
        },
    )

    assert response.status_code == 200
    mcp_service.get_mcp_server_by_name.assert_awaited_once()
    context, server_name = mcp_service.get_mcp_server_by_name.await_args.args
    assert context.workspace_uuid == 'workspace-a'
    assert server_name == 'pab1it0/prometheus'
    payload = await response.get_json()
    assert payload['data']['server']['name'] == 'pab1it0/prometheus'


async def test_mcp_resource_route_accepts_encoded_slash_name():
    mcp_service = SimpleNamespace(
        get_mcp_server_by_name=AsyncMock(),
        get_mcp_server_resources=AsyncMock(return_value=[]),
        get_mcp_server_resource_templates=AsyncMock(return_value=[]),
        get_runtime_info=AsyncMock(return_value={'resource_capabilities': {'subscribe': False}}),
    )
    client = await _create_test_client(mcp_service)

    response = await client.get(
        '/api/v1/mcp/servers/pab1it0%2Fprometheus/resources',
        headers={
            'Authorization': 'Bearer test-token',
            'X-Workspace-Id': 'workspace-a',
        },
    )

    assert response.status_code == 200
    mcp_service.get_mcp_server_by_name.assert_not_awaited()
    mcp_service.get_mcp_server_resources.assert_awaited_once()
    context, server_name = mcp_service.get_mcp_server_resources.await_args.args
    assert context.workspace_uuid == 'workspace-a'
    assert server_name == 'pab1it0/prometheus'
    payload = await response.get_json()
    assert payload['data']['resource_capabilities'] == {'subscribe': False}
