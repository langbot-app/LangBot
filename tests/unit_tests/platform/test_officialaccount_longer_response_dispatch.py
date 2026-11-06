from __future__ import annotations

import asyncio
import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.libs.official_account_api.api import OAClientForLongerResponse

TOKEN = 'webhook-token'


class DummyLogger:
    async def info(self, *args, **kwargs):
        pass

    async def error(self, *args, **kwargs):
        pass


def make_client(customer_service: bool, loading_message: str = '') -> OAClientForLongerResponse:
    return OAClientForLongerResponse(
        token=TOKEN,
        EncodingAESKey='encoding-key',
        AppID='app-id',
        Appsecret='app-secret',
        LoadingMessage=loading_message,
        logger=DummyLogger(),
        unified_mode=True,
        customer_service=customer_service,
    )


def signed_request(msg_id: int, text: str, user: str = 'openid-1'):
    timestamp, nonce = '1700000000', str(msg_id)
    signature = hashlib.sha1(''.join(sorted([TOKEN, timestamp, nonce])).encode()).hexdigest()
    body = (
        '<xml>'
        f'<ToUserName><![CDATA[gh_bot]]></ToUserName>'
        f'<FromUserName><![CDATA[{user}]]></FromUserName>'
        f'<CreateTime>{msg_id}</CreateTime>'
        '<MsgType><![CDATA[text]]></MsgType>'
        f'<Content><![CDATA[{text}]]></Content>'
        f'<MsgId>{msg_id}</MsgId>'
        '</xml>'
    ).encode()

    async def data():
        return body

    return SimpleNamespace(
        method='POST',
        args={'signature': signature, 'timestamp': timestamp, 'nonce': nonce, 'echostr': '', 'msg_signature': ''},
        data=data(),
    )


async def post(client, msg_id, text):
    response = await client.handle_unified_webhook(signed_request(msg_id, text))
    # Let the detached processing task run.
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    return response


def register_handler(client) -> AsyncMock:
    handler = AsyncMock()
    client.on_message('text')(handler)
    return handler


@pytest.mark.asyncio
async def test_auto_mode_dispatches_messages_that_never_got_a_reply():
    """A message handled without an AI reply must not block the user's next messages."""
    client = make_client(customer_service=True)
    handler = register_handler(client)

    # The first message is consumed by a plugin (e.g. human takeover), so no reply is set.
    assert await post(client, 1001, 'transfer to human') == 'success'
    # A human replies through send_message, which bypasses set_message.
    assert await post(client, 1002, 'are you there') == 'success'
    assert await post(client, 1003, 'hello again') == 'success'

    assert [call.args[0].message for call in handler.await_args_list] == [
        'transfer to human',
        'are you there',
        'hello again',
    ]


@pytest.mark.asyncio
async def test_auto_mode_returns_queued_fallback_reply_and_still_dispatches():
    """When customer service is unavailable, the queued reply is delivered on the next message."""
    client = make_client(customer_service=True, loading_message='loading')
    handler = register_handler(client)
    client.customer_service.send = AsyncMock(return_value=45015)

    await post(client, 2001, 'question')
    assert await client.set_message('openid-1', 2001, 'answer') is True
    response = await post(client, 2002, 'next')

    assert 'answer' in response
    assert handler.await_count == 1


@pytest.mark.asyncio
async def test_passive_mode_still_treats_follow_ups_as_fetch_requests():
    client = make_client(customer_service=False, loading_message='loading')
    handler = register_handler(client)

    first = await post(client, 3001, 'question')
    follow_up = await post(client, 3002, 'anything')

    assert 'loading' in first and 'loading' in follow_up
    assert handler.await_count == 1

    await client.set_message('openid-1', 3001, 'answer')
    assert 'answer' in await post(client, 3003, 'fetch')
