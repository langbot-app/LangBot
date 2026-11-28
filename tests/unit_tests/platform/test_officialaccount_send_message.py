from __future__ import annotations

import traceback
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from langbot.pkg.platform.adapters.officialaccount.adapter import OfficialAccountAdapter
from langbot.pkg.platform.adapters.officialaccount.errors import NotSupportedError, OfficialAccountSendError
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction
from tests.unit_tests.platform.test_officialaccount_eba_adapter import DummyLogger
from tests.unit_tests.plugin.test_handler_actions import make_handler


def make_adapter(mode='auto'):
    return OfficialAccountAdapter(
        {
            'token': 'webhook-token',
            'EncodingAESKey': 'encoding-key',
            'AppID': 'app-id',
            'AppSecret': 'test-app-secret',
            'Mode': mode,
        },
        DummyLogger(),
    )


def text_message(*parts):
    return platform_message.MessageChain([platform_message.Plain(text=part) for part in parts])


@pytest.mark.asyncio
@pytest.mark.parametrize('target_type', ['person', 'friend', 'private'])
async def test_send_uses_shared_customer_service(target_type):
    adapter = make_adapter()
    service = adapter.bot.customer_service
    service.send = AsyncMock(return_value=0)

    result = await adapter.send_message(target_type, 'openid-1', text_message('hello', ' world'))

    service.send.assert_awaited_once_with('openid-1', 'hello world')
    assert adapter.bot.customer_service is service
    assert isinstance(result, platform_events.MessageResult)
    assert result.raw == {'errcode': 0}
    assert adapter.bot.msg_queue == {}


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['drop', 'passive'])
async def test_send_requires_auto_mode(mode):
    adapter = make_adapter(mode)
    with pytest.raises(NotSupportedError, match='auto'):
        await adapter.send_message('private', 'openid-1', text_message('hello'))


@pytest.mark.parametrize('mode', ['drop', 'passive', 'auto'])
def test_supported_apis_depend_on_mode(mode):
    assert ('send_message' in make_adapter(mode).get_supported_apis()) == (mode == 'auto')


@pytest.mark.asyncio
@pytest.mark.parametrize('target_type', ['group', 'channel', 'unknown'])
async def test_send_rejects_unsupported_target(target_type):
    adapter = make_adapter()
    adapter.bot.customer_service.send = AsyncMock()
    with pytest.raises(NotSupportedError):
        await adapter.send_message(target_type, 'target', text_message('hello'))
    adapter.bot.customer_service.send.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('parts', [[], [''], [' ', '\n']])
async def test_send_rejects_empty_text(parts):
    adapter = make_adapter()
    adapter.bot.customer_service.send = AsyncMock()
    with pytest.raises(ValueError, match='non-empty'):
        await adapter.send_message('private', 'openid-1', text_message(*parts))
    adapter.bot.customer_service.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_rejects_non_text_without_partial_delivery():
    adapter = make_adapter()
    adapter.bot.customer_service.send = AsyncMock()
    message = platform_message.MessageChain(
        [platform_message.Plain(text='hello'), platform_message.Image(url='https://example.test/image.png')]
    )
    with pytest.raises(ValueError, match='Plain'):
        await adapter.send_message('private', 'openid-1', message)
    adapter.bot.customer_service.send.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('errcode', 'reason'),
    [(45015, '48-hour'), (45047, 'quota'), (48001, 'permission'), (43004, 'not following'), (99999, 'rejected')],
)
async def test_send_rejects_error_codes_without_queueing(errcode, reason):
    adapter = make_adapter()
    adapter.bot.customer_service.send = AsyncMock(return_value=errcode)
    with pytest.raises(OfficialAccountSendError, match=reason) as caught:
        await adapter.send_message('private', 'openid-1', text_message('hello'))
    assert caught.value.errcode == errcode
    assert str(errcode) in str(caught.value)
    assert adapter.bot.msg_queue == {}
    assert adapter.bot.user_msg_queue == {}


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [httpx.ConnectError, RuntimeError])
async def test_send_sanitizes_transport_errors(failure):
    adapter = make_adapter()
    adapter.bot.customer_service.send = AsyncMock(
        side_effect=failure('https://example.test?access_token=test-access-token&secret=test-app-secret')
    )
    with pytest.raises(RuntimeError, match=failure.__name__) as caught:
        await adapter.send_message('private', 'openid-1', text_message('hello'))
    formatted = ''.join(traceback.format_exception(caught.value))
    assert 'test-access-token' not in formatted
    assert 'test-app-secret' not in formatted
    assert adapter.bot.msg_queue == {}


@pytest.mark.asyncio
@pytest.mark.parametrize('final_code', [0, 40001])
async def test_send_refreshes_rejected_token_once(monkeypatch, final_code):
    adapter = make_adapter()
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.get.side_effect = [
        httpx.Response(200, json={'access_token': 'first-token', 'expires_in': 7200}),
        httpx.Response(200, json={'access_token': 'second-token', 'expires_in': 7200}),
    ]
    client.post.side_effect = [
        httpx.Response(200, json={'errcode': 40001}),
        httpx.Response(200, json={'errcode': final_code}),
    ]
    monkeypatch.setattr(
        'langbot.libs.official_account_api.customer_service.httpx.AsyncClient', Mock(return_value=client)
    )

    if final_code:
        with pytest.raises(OfficialAccountSendError) as caught:
            await adapter.send_message('private', 'openid-1', text_message('hello', ' world'))
        assert caught.value.errcode == final_code
    else:
        result = await adapter.send_message('private', 'openid-1', text_message('hello', ' world'))
        assert result.raw == {'errcode': 0}

    assert client.get.await_count == 2
    assert client.post.await_count == 2
    for call, token in zip(client.post.await_args_list, ['first-token', 'second-token']):
        assert call.kwargs['params'] == {'access_token': token}
        assert call.kwargs['json'] == {'touser': 'openid-1', 'msgtype': 'text', 'text': {'content': 'hello world'}}
    assert adapter.bot.msg_queue == {}


@pytest.mark.asyncio
@pytest.mark.usefixtures('installed_legacy_plugin')
@pytest.mark.parametrize('errcode', [0, 45015])
async def test_plugin_send_message_action_reaches_adapter(errcode):
    adapter = make_adapter()
    adapter.bot.customer_service.send = AsyncMock(return_value=errcode)
    app = Mock()
    app.platform_mgr.get_bot_by_uuid = AsyncMock(return_value=SimpleNamespace(adapter=adapter))
    runtime_handler = make_handler(app)
    runtime_handler._resource_exists = AsyncMock(return_value=True)
    # The bot belongs to the plugin installation's Workspace.
    app.persistence_mgr.execute_async = AsyncMock(return_value=SimpleNamespace(first=lambda: ('bot-1',)))
    data = {
        'bot_uuid': 'bot-1',
        # Plugins address users with the SDK target type; the adapter accepts it.
        'target_type': 'person',
        'target_id': 'openid-1',
        'message_chain': text_message('hello', ' world').model_dump(),
    }

    if errcode:
        with pytest.raises(OfficialAccountSendError) as caught:
            await runtime_handler.actions[PluginToRuntimeAction.SEND_MESSAGE.value](data)
        assert caught.value.errcode == errcode
    else:
        response = await runtime_handler.actions[PluginToRuntimeAction.SEND_MESSAGE.value](data)
        assert response.code == 0
        assert response.data['result']['raw'] == {'errcode': 0}
    adapter.bot.customer_service.send.assert_awaited_once_with('openid-1', 'hello world')
    assert adapter.bot.msg_queue == {}
