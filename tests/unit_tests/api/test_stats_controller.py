from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import quart

from langbot.pkg.api.http.controller.groups.stats import StatsRouterGroup


pytestmark = pytest.mark.asyncio


def session(
    workspace_uuid: str,
    *,
    placement_generation: int = 1,
    conversation_count: int = 0,
):
    return SimpleNamespace(
        instance_uuid='instance-test',
        workspace_uuid=workspace_uuid,
        placement_generation=placement_generation,
        conversations=[object() for _ in range(conversation_count)],
    )


async def create_client(*, role='viewer'):
    quart_app = quart.Quart(__name__)
    account = SimpleNamespace(uuid='account-test', user='test@example.com')
    user_service = SimpleNamespace(
        get_authenticated_account=AsyncMock(return_value=account),
    )
    access = SimpleNamespace(
        execution=SimpleNamespace(
            instance_uuid='instance-test',
            placement_generation=1,
        ),
        workspace=SimpleNamespace(uuid='workspace-a'),
        membership=SimpleNamespace(
            uuid='membership-test',
            role=role,
            projection_revision=1,
        ),
    )
    collaboration_service = SimpleNamespace(
        resolve_account_workspace=AsyncMock(return_value=access),
    )

    def get_query_count(context):
        assert context.instance_uuid == 'instance-test'
        assert context.workspace_uuid == 'workspace-a'
        assert context.placement_generation == 1
        return 7

    ap = SimpleNamespace(
        user_service=user_service,
        workspace_collaboration_service=collaboration_service,
        sess_mgr=SimpleNamespace(
            session_list=[
                session('workspace-a', conversation_count=2),
                session('workspace-b', conversation_count=5),
                session(
                    'workspace-a',
                    placement_generation=2,
                    conversation_count=3,
                ),
                SimpleNamespace(conversations=[object()] * 11),
            ]
        ),
        query_pool=SimpleNamespace(get_query_count=get_query_count),
    )
    router = StatsRouterGroup(ap, quart_app)
    await router.initialize()
    return quart_app.test_client(), collaboration_service


async def test_basic_stats_are_scoped_to_selected_workspace_placement():
    client, collaboration_service = await create_client()

    response = await client.get(
        '/api/v1/stats/basic',
        headers={
            'Authorization': 'Bearer test-token',
            'X-Workspace-Id': 'workspace-a',
        },
    )

    assert response.status_code == 200
    payload = await response.get_json()
    assert payload['data'] == {
        'active_session_count': 1,
        'conversation_count': 2,
        'query_count': 7,
    }
    collaboration_service.resolve_account_workspace.assert_awaited_once_with('account-test', 'workspace-a')


async def test_basic_stats_requires_resource_view_permission():
    client, _ = await create_client(role='unknown-role')

    response = await client.get(
        '/api/v1/stats/basic',
        headers={'Authorization': 'Bearer test-token'},
    )

    assert response.status_code == 403
    payload = await response.get_json()
    assert payload['code'] == 'permission_denied'
