from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import quart
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.controller.groups.extensions import ExtensionsRouterGroup
from langbot.pkg.persistence.mgr import PersistenceManager
from langbot.pkg.workspace.errors import WorkspaceNotFoundError


@pytest.mark.asyncio
async def test_extensions_route_hides_runtime_bound_to_another_workspace():
    account = SimpleNamespace(uuid='account-a', user='owner@example.com')
    connector = SimpleNamespace(
        is_enable_plugin=True,
        require_workspace_context=AsyncMock(side_effect=WorkspaceNotFoundError('Plugin resource not found')),
        list_plugins=AsyncMock(return_value=[]),
    )
    ap = SimpleNamespace(
        user_service=SimpleNamespace(
            get_authenticated_account=AsyncMock(return_value=account),
        ),
        workspace_collaboration_service=SimpleNamespace(
            resolve_account_workspace=AsyncMock(
                return_value=SimpleNamespace(
                    workspace=SimpleNamespace(uuid='workspace-a'),
                    membership=SimpleNamespace(uuid='membership-a', role='owner', projection_revision=0),
                    execution=SimpleNamespace(instance_uuid='instance-a', placement_generation=2),
                )
            )
        ),
        plugin_connector=connector,
        mcp_service=SimpleNamespace(get_mcp_servers=AsyncMock(return_value=[])),
        skill_service=SimpleNamespace(list_skills=AsyncMock(return_value=[])),
    )
    quart_app = quart.Quart(__name__)
    router = ExtensionsRouterGroup(ap, quart_app)
    await router.initialize()

    response = await quart_app.test_client().get(
        '/api/v1/extensions',
        headers={'Authorization': 'Bearer token'},
    )

    assert response.status_code == 404
    connector.list_plugins.assert_not_awaited()
    ap.mcp_service.get_mcp_servers.assert_not_awaited()
    ap.skill_service.list_skills.assert_not_awaited()


@pytest.mark.asyncio
async def test_extensions_route_redacts_plugin_secrets_without_mutating_runtime_data():
    account = SimpleNamespace(uuid='account-a', user='viewer@example.com')
    raw_plugin = {
        'plugin_config': {'apiKey': 'plugin-secret', 'nested': {'token': 'nested-secret'}},
        'debug': {'plugin_debug_key': 'debug-secret'},
    }
    connector = SimpleNamespace(
        is_enable_plugin=True,
        require_workspace_context=AsyncMock(),
        list_plugins=AsyncMock(return_value=[raw_plugin]),
    )
    ap = SimpleNamespace(
        user_service=SimpleNamespace(get_authenticated_account=AsyncMock(return_value=account)),
        workspace_collaboration_service=SimpleNamespace(
            resolve_account_workspace=AsyncMock(
                return_value=SimpleNamespace(
                    workspace=SimpleNamespace(uuid='workspace-a'),
                    membership=SimpleNamespace(uuid='membership-a', role='viewer', projection_revision=0),
                    execution=SimpleNamespace(instance_uuid='instance-a', placement_generation=2),
                )
            )
        ),
        plugin_connector=connector,
        mcp_service=SimpleNamespace(get_mcp_servers=AsyncMock(return_value=[])),
        skill_service=SimpleNamespace(list_skills=AsyncMock(return_value=[])),
    )
    quart_app = quart.Quart(__name__)
    router = ExtensionsRouterGroup(ap, quart_app)
    await router.initialize()

    response = await quart_app.test_client().get(
        '/api/v1/extensions',
        headers={'Authorization': 'Bearer token', 'X-Workspace-Id': 'workspace-a'},
    )

    assert response.status_code == 200
    plugin = (await response.get_json())['data']['extensions'][0]['plugin']
    assert plugin['plugin_config']['apiKey'] == '***'
    assert plugin['plugin_config']['nested']['token'] == '***'
    assert plugin['debug']['plugin_debug_key'] == '***'
    assert raw_plugin['plugin_config']['apiKey'] == 'plugin-secret'


@pytest.mark.asyncio
async def test_extensions_parallel_reads_open_explicit_child_task_scopes():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    account = SimpleNamespace(uuid='account-a', user='owner@example.com')
    ap = SimpleNamespace()
    ap.persistence_mgr = PersistenceManager(ap)
    ap.persistence_mgr.db = SimpleNamespace(get_engine=lambda: engine)
    ap.user_service = SimpleNamespace(get_authenticated_account=AsyncMock(return_value=account))
    ap.workspace_collaboration_service = SimpleNamespace(
        resolve_account_workspace=AsyncMock(
            return_value=SimpleNamespace(
                workspace=SimpleNamespace(uuid='workspace-a'),
                membership=SimpleNamespace(uuid='membership-a', role='owner', projection_revision=0),
                execution=SimpleNamespace(instance_uuid='instance-a', placement_generation=2),
            )
        )
    )
    ap.plugin_connector = SimpleNamespace(
        is_enable_plugin=False,
        list_plugins=AsyncMock(return_value=[]),
    )

    async def list_mcp_servers(_context, *, contain_runtime_info):
        await ap.persistence_mgr.execute_async(sqlalchemy.select(sqlalchemy.literal(1)))
        assert contain_runtime_info is True
        return [{'name': 'Scoped MCP'}]

    ap.mcp_service = SimpleNamespace(get_mcp_servers=AsyncMock(side_effect=list_mcp_servers))
    ap.skill_service = SimpleNamespace(list_skills=AsyncMock(return_value=[]))
    quart_app = quart.Quart(__name__)
    router = ExtensionsRouterGroup(ap, quart_app)
    await router.initialize()

    try:
        response = await quart_app.test_client().get(
            '/api/v1/extensions',
            headers={'Authorization': 'Bearer token', 'X-Workspace-Id': 'workspace-a'},
        )
    finally:
        await engine.dispose()

    assert response.status_code == 200
    assert (await response.get_json())['data']['extensions'] == [{'type': 'mcp', 'server': {'name': 'Scoped MCP'}}]
