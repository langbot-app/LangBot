"""A callback that raises must answer with a status, not ``None``.

Both official-account callback handlers catch the exception to keep serving
later callbacks, then fell through to an implicit ``None``. Quart rejects that
with ``TypeError: The response value returned by the view function cannot be
None``, so a single bad callback (signature mismatch, malformed XML, a message
without ``FromUserName``) surfaced as a 500 -- the traceback in the report.
"""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest

from langbot.libs.official_account_api.api import OAClient, OAClientForLongerResponse

TOKEN = 'webhook-token'


class DummyLogger:
    def __init__(self):
        self.errors: list[str] = []

    async def info(self, *args, **kwargs):
        pass

    async def error(self, message, *args, **kwargs):
        self.errors.append(message)


def make_client(cls, **kwargs):
    common = {
        'token': TOKEN,
        'EncodingAESKey': 'encoding-key',
        'AppID': 'app-id',
        'Appsecret': 'app-secret',
        'logger': DummyLogger(),
        'unified_mode': True,
    }
    if cls is OAClientForLongerResponse:
        common['LoadingMessage'] = ''
    return cls(**common, **kwargs)


def signed_request(body: bytes, *, msg_id: int = 1, signature: str | None = None):
    timestamp, nonce = '1700000000', str(msg_id)
    if signature is None:
        signature = hashlib.sha1(''.join(sorted([TOKEN, timestamp, nonce])).encode()).hexdigest()

    async def data():
        return body

    return SimpleNamespace(
        method='POST',
        args={'signature': signature, 'timestamp': timestamp, 'nonce': nonce, 'echostr': '', 'msg_signature': ''},
        data=data(),
    )


VALID_BODY = (
    '<xml>'
    '<ToUserName><![CDATA[gh_bot]]></ToUserName>'
    '<FromUserName><![CDATA[openid-1]]></FromUserName>'
    '<CreateTime>1700000000</CreateTime>'
    '<MsgType><![CDATA[text]]></MsgType>'
    '<Content><![CDATA[hi]]></Content>'
    '<MsgId>1</MsgId>'
    '</xml>'
).encode()

CLIENTS = [OAClient, OAClientForLongerResponse]
IDS = ['dispatch', 'passive']


@pytest.mark.asyncio
@pytest.mark.parametrize('client_cls', CLIENTS, ids=IDS)
async def test_valid_callback_still_returns_200(client_cls):
    response = await make_client(client_cls).handle_unified_webhook(signed_request(VALID_BODY))

    assert response == 'success'


@pytest.mark.asyncio
@pytest.mark.parametrize('client_cls', CLIENTS, ids=IDS)
async def test_rejected_signature_answers_400_instead_of_none(client_cls):
    client = make_client(client_cls)

    response = await client.handle_unified_webhook(signed_request(VALID_BODY, signature='deadbeef'))

    assert response == ('error', 400)
    assert client.logger.errors


@pytest.mark.asyncio
@pytest.mark.parametrize('client_cls', CLIENTS, ids=IDS)
@pytest.mark.parametrize('body', [b'not xml at all', b''], ids=['malformed', 'empty'])
async def test_unparsable_body_answers_400_instead_of_none(client_cls, body):
    """The reported traceback: the XML helper raises and the handler returned None."""

    response = await make_client(client_cls).handle_unified_webhook(signed_request(body))

    assert response == ('error', 400)


@pytest.mark.asyncio
@pytest.mark.parametrize('client_cls', CLIENTS, ids=IDS)
async def test_missing_from_user_answers_400_instead_of_none(client_cls):
    body = b'<xml><ToUserName><![CDATA[gh_bot]]></ToUserName><MsgId>3</MsgId></xml>'

    response = await make_client(client_cls).handle_unified_webhook(signed_request(body))

    assert response == ('error', 400)
