from __future__ import annotations

import base64
import xml.etree.ElementTree as ET
from unittest.mock import AsyncMock

import pytest

from langbot.libs.official_account_api.api import OAClient, OAClientForLongerResponse
from langbot.libs.wecom_api.WXBizMsgCrypt3 import WXBizMsgCrypt


@pytest.fixture(params=[OAClient, OAClientForLongerResponse])
def client(request):
    kwargs = {
        'token': 'test-token',
        'EncodingAESKey': base64.b64encode(b'a' * 32).decode().rstrip('='),
        'AppID': 'test-app',
        'Appsecret': 'test-secret',
        'logger': AsyncMock(),
    }
    if request.param is OAClientForLongerResponse:
        kwargs['LoadingMessage'] = 'working'
    return request.param(**kwargs)


@pytest.fixture(params=['standalone', 'unified'])
def callback(client, request):
    if request.param == 'standalone':
        return client.app.test_client(), '/callback/command'

    async def unified():
        from quart import request as callback_request

        return await client.handle_unified_webhook(callback_request)

    client.app.add_url_rule('/unified', 'unified', unified, methods=['POST'])
    return client.app.test_client(), '/unified'


def encrypted_message(client):
    message = (
        '<xml><ToUserName>bot</ToUserName><FromUserName>user</FromUserName>'
        '<CreateTime>123</CreateTime><MsgType>text</MsgType>'
        '<Content>hello</Content><MsgId>456</MsgId></xml>'
    )
    crypt = WXBizMsgCrypt(client.token, client.aes, client.appid)
    ret, body = crypt.EncryptMsg(message, 'nonce', '123')
    assert ret == 0
    root = ET.fromstring(body)
    return body.encode(), {
        'msg_signature': root.findtext('MsgSignature'),
        'timestamp': '123',
        'nonce': 'nonce',
    }


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['signature', 'body'])
async def test_callback_rejects_failed_decryption(client, callback, failure):
    http, path = callback
    body, args = encrypted_message(client)
    if failure == 'signature':
        args['msg_signature'] = 'invalid-signature'
    else:
        body = b'<xml></xml>'

    response = await http.post(path, data=body, query_string=args)

    assert response.status_code == 403
    assert await response.get_data(as_text=True) == 'message decryption failed'
    assert 'ret=' in client.logger.error.call_args.args[0]


@pytest.mark.asyncio
async def test_callback_still_returns_generated_response(client, callback):
    @client.on_message('text')
    async def reply(event):
        if isinstance(client, OAClientForLongerResponse):
            await client.set_message(event.user_id, event.message_id, 'answer')
        else:
            await client.set_message(event.message_id, 'answer')

    http, path = callback
    body, args = encrypted_message(client)
    response = await http.post(path, data=body, query_string=args)

    assert response.status_code == 200
    root = ET.fromstring(await response.get_data())
    if isinstance(client, OAClientForLongerResponse):
        assert root.findtext('Content') == 'working'
        response = await http.post(path, data=body, query_string=args)
        assert response.status_code == 200
        root = ET.fromstring(await response.get_data())
    assert root.findtext('Content') == 'answer'
    client.logger.error.assert_not_called()


@pytest.mark.asyncio
async def test_callback_returns_explicit_error_when_handler_fails(client, callback):
    @client.on_message('text')
    async def fail(event):
        raise RuntimeError('handler failed')

    http, path = callback
    body, args = encrypted_message(client)
    response = await http.post(path, data=body, query_string=args)

    assert response.status_code == 500
    assert await response.get_data(as_text=True) == 'callback processing failed'
    assert 'handler failed' in client.logger.error.call_args.args[0]
