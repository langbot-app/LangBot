from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import quart

from langbot.pkg.api.http.controller.groups.platform.commands import PlatformCommandsRouterGroup


@pytest.mark.asyncio
@pytest.mark.parametrize('role,status', [('developer', 200), ('viewer', 403)])
async def test_sync_route_requires_resource_manage_and_passes_workspace_context(role, status):
    application = quart.Quart(__name__)
    access = SimpleNamespace(
        workspace=SimpleNamespace(uuid='workspace-test'),
        membership=SimpleNamespace(uuid='membership-test', role=role, projection_revision=1),
        execution=SimpleNamespace(instance_uuid='instance-test', placement_generation=1),
    )
    service = SimpleNamespace(sync_platform_commands=AsyncMock(return_value={'hash': 'synced', 'error': None}))
    ap = SimpleNamespace(
        bot_service=service,
        user_service=SimpleNamespace(
            get_authenticated_account=AsyncMock(
                return_value=SimpleNamespace(uuid='account-test', user='test@example.com')
            )
        ),
        apikey_service=SimpleNamespace(authenticate_api_key=AsyncMock(return_value=None)),
        workspace_collaboration_service=SimpleNamespace(resolve_account_workspace=AsyncMock(return_value=access)),
    )
    group = PlatformCommandsRouterGroup(ap, application)
    await group.initialize()
    response = await application.test_client().post(
        '/api/v1/bots/bot-one/platform-commands/sync', json={}, headers={'Authorization': 'Bearer token'}
    )
    assert response.status_code == status
    if status == 200:
        context, bot_uuid = service.sync_platform_commands.await_args.args
        assert context.workspace_uuid == 'workspace-test'
        assert bot_uuid == 'bot-one'
    else:
        service.sync_platform_commands.assert_not_awaited()
