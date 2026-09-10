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


async def _create_test_client(bot_service: SimpleNamespace):
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
        bot_service=bot_service,
        user_service=user_service,
        apikey_service=SimpleNamespace(authenticate_api_key=AsyncMock(return_value=None)),
        workspace_collaboration_service=SimpleNamespace(resolve_account_workspace=AsyncMock(return_value=access)),
    )
    BotsRouterGroup = import_module('langbot.pkg.api.http.controller.groups.platform.bots').BotsRouterGroup
    group = BotsRouterGroup(ap, app)
    await group.initialize()
    return app.test_client()


@pytest.mark.parametrize('method,path', [('post', '/api/v1/platform/bots'), ('put', '/api/v1/platform/bots/bot-1')])
async def test_bot_config_error_preserves_details(method, path):
    error = ValueError('Lark missing required config: app_id, app_secret, bot_name')
    service = SimpleNamespace(create_bot=AsyncMock(side_effect=error), update_bot=AsyncMock(side_effect=error))
    client = await _create_test_client(service)
    response = await getattr(client, method)(
        path, json={'adapter_config': {}}, headers={'Authorization': 'Bearer token'}
    )
    assert response.status_code == 400
    body = await response.get_json()
    assert body['code'] == 'invalid_bot_config'
    assert body['msg'] == str(error)


async def test_bot_apply_failure_identifies_persisted_record():
    from langbot.pkg.api.http.service.bot_errors import BotApplyError

    service = SimpleNamespace(create_bot=AsyncMock(side_effect=BotApplyError('Missing app_id', 'saved-bot')))
    client = await _create_test_client(service)
    response = await client.post('/api/v1/platform/bots', json={}, headers={'Authorization': 'Bearer token'})
    assert response.status_code == 400
    body = await response.get_json()
    assert body.pop('request_id')
    assert body == {
        'code': 'bot_apply_failed',
        'msg': 'Missing app_id',
        'data': {'uuid': 'saved-bot'},
    }


async def test_unexpected_failure_keeps_request_reference_without_exception_details():
    client = await _create_test_client(
        SimpleNamespace(update_bot=AsyncMock(side_effect=RuntimeError('database password')))
    )
    response = await client.put('/api/v1/platform/bots/bot-1', json={}, headers={'Authorization': 'Bearer token'})
    body = await response.get_json()
    assert response.status_code == 500
    assert body['request_id']
    assert 'database password' not in str(body)


async def test_invalid_request_body_is_actionable():
    service = SimpleNamespace(update_bot=AsyncMock())
    client = await _create_test_client(service)
    response = await client.put('/api/v1/platform/bots/bot-1', json=[], headers={'Authorization': 'Bearer token'})
    assert response.status_code == 400
    service.update_bot.assert_not_awaited()


async def test_runtime_error_redacts_persisted_secrets_on_partial_update():
    from langbot.pkg.api.http.service.bot import BotService
    from langbot.pkg.api.http.service.bot_errors import BotApplyError

    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock(return_value=SimpleNamespace(rowcount=1))),
        platform_mgr=SimpleNamespace(
            remove_bot=AsyncMock(),
            load_bot=AsyncMock(side_effect=ValueError('Invalid app_secret: persisted-secret-value')),
        ),
    )
    service = BotService(ap)
    service.get_bot = AsyncMock(
        return_value={'uuid': 'bot-1', 'adapter_config': {'app_secret': 'persisted-secret-value'}}
    )
    with pytest.raises(BotApplyError) as captured:
        await service.update_bot('workspace-test', 'bot-1', {'enable': True})
    assert str(captured.value) == 'Invalid app_secret: ***'
    assert captured.value.bot_uuid == 'bot-1'
    ap.persistence_mgr.execute_async.assert_awaited_once()


async def test_validation_error_does_not_include_input_values():
    import pydantic
    from langbot.pkg.api.http.service.bot_errors import bot_error_message

    class Config(pydantic.BaseModel):
        app_secret: int

    try:
        Config(app_secret='private-value')
    except pydantic.ValidationError as error:
        result = bot_error_message(error, {'app_secret': 'private-value'})
    assert 'app_secret' in result
    assert 'private-value' not in result
    assert 'input_value' not in result
