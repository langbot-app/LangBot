from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import quart

from langbot.pkg.api.http.controller.groups.platform.bots import BotsRouterGroup


pytestmark = pytest.mark.asyncio

SECRET_CONFIG = {'token': 'tenant-secret', 'app_secret': 'also-secret'}


async def create_client(*, role: str):
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
        workspace=SimpleNamespace(uuid='workspace-test'),
        membership=SimpleNamespace(
            uuid='membership-test',
            role=role,
            projection_revision=1,
        ),
    )

    async def get_bots(_context, *, include_secret=False):
        bot = {'uuid': 'bot-test', 'name': 'Test Bot'}
        if include_secret:
            bot['adapter_config'] = SECRET_CONFIG
        return [bot]

    async def get_runtime_bot_info(_context, _bot_uuid, *, include_secret=False):
        bot = {'uuid': 'bot-test', 'name': 'Test Bot'}
        if include_secret:
            bot['adapter_config'] = SECRET_CONFIG
        return bot

    bot_service = SimpleNamespace(
        get_bots=AsyncMock(side_effect=get_bots),
        get_runtime_bot_info=AsyncMock(side_effect=get_runtime_bot_info),
        update_bot=AsyncMock(),
    )
    application = SimpleNamespace(
        user_service=user_service,
        apikey_service=SimpleNamespace(
            authenticate_api_key=AsyncMock(
                return_value=SimpleNamespace(
                    instance_uuid='instance-test',
                    placement_generation=1,
                    api_key_uuid='api-key-test',
                    workspace_uuid='workspace-test',
                    permissions=frozenset({'resource.view'}),
                )
            )
        ),
        workspace_collaboration_service=SimpleNamespace(resolve_account_workspace=AsyncMock(return_value=access)),
        bot_service=bot_service,
    )
    router = BotsRouterGroup(application, quart_app)
    await router.initialize()
    return quart_app.test_client(), bot_service


async def test_viewer_list_and_detail_never_receive_adapter_credentials():
    client, bot_service = await create_client(role='viewer')
    headers = {'Authorization': 'Bearer test-token'}

    list_response = await client.get('/api/v1/platform/bots', headers=headers)
    detail_response = await client.get('/api/v1/platform/bots/bot-test', headers=headers)

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert 'adapter_config' not in (await list_response.get_json())['data']['bots'][0]
    assert 'adapter_config' not in (await detail_response.get_json())['data']['bot']
    assert bot_service.get_bots.await_args.kwargs['include_secret'] is False
    assert bot_service.get_runtime_bot_info.await_args.kwargs['include_secret'] is False


async def test_resource_manager_can_read_adapter_credentials():
    client, bot_service = await create_client(role='developer')
    headers = {'Authorization': 'Bearer test-token'}

    list_response = await client.get('/api/v1/platform/bots', headers=headers)
    detail_response = await client.get('/api/v1/platform/bots/bot-test', headers=headers)

    assert (await list_response.get_json())['data']['bots'][0]['adapter_config'] == SECRET_CONFIG
    assert (await detail_response.get_json())['data']['bot']['adapter_config'] == SECRET_CONFIG
    assert bot_service.get_bots.await_args.kwargs['include_secret'] is True
    assert bot_service.get_runtime_bot_info.await_args.kwargs['include_secret'] is True


async def test_viewer_cannot_write_adapter_credentials():
    client, bot_service = await create_client(role='viewer')

    response = await client.put(
        '/api/v1/platform/bots/bot-test',
        headers={'Authorization': 'Bearer test-token'},
        json={'adapter_config': SECRET_CONFIG},
    )

    assert response.status_code == 403
    assert (await response.get_json())['code'] == 'permission_denied'
    bot_service.update_bot.assert_not_awaited()
