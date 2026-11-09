"""`media/get` download for inbound WeCom MediaIds (#2835)."""

from __future__ import annotations

import pytest

from langbot.libs.wecom_api import api as wecom_api


class Logger:
    async def info(self, message):
        return None

    async def warning(self, message):
        return None

    async def error(self, message):
        return None


def make_client() -> wecom_api.WecomClient:
    client = wecom_api.WecomClient(
        corpid='corp-id',
        secret='secret',
        token='token',
        EncodingAESKey='encoding-key',
        contacts_secret='',
        logger=Logger(),
        api_base_url='https://qyapi.weixin.qq.com/cgi-bin',
    )
    client.access_token = 'access-token'
    return client


class FakeResponse:
    def __init__(self, body: bytes, content_type: str):
        self._body = body
        self.headers = {'Content-Type': content_type, 'Content-Length': str(len(body))}

    def raise_for_status(self):
        return None

    async def aread(self):
        return self._body

    async def aiter_bytes(self):
        yield self._body


class FakeStream:
    def __init__(self, response: FakeResponse):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *exc):
        return False


class FakeClient:
    def __init__(self, responses: list[FakeResponse], calls: list[str]):
        self._responses = responses
        self._calls = calls

    def stream(self, method, url):
        self._calls.append(url)
        return FakeStream(self._responses.pop(0))


def patch_client(monkeypatch, client, response, calls):
    responses = response if isinstance(response, list) else [response]

    class _Ctx:
        async def __aenter__(self):
            return FakeClient(responses, calls)

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(client, '_http_client_context', lambda **kwargs: _Ctx())


@pytest.mark.asyncio
async def test_media_id_download_returns_the_stream(monkeypatch):
    client = make_client()
    calls: list[str] = []
    patch_client(monkeypatch, client, FakeResponse(b'%PDF-1.4 body', 'application/pdf'), calls)

    data = await client.download_media_id_to_bytes('file-media-id')

    assert data == b'%PDF-1.4 body'
    assert calls == ['https://qyapi.weixin.qq.com/cgi-bin/media/get?access_token=access-token&media_id=file-media-id']


@pytest.mark.asyncio
async def test_media_id_download_quotes_the_id(monkeypatch):
    client = make_client()
    calls: list[str] = []
    patch_client(monkeypatch, client, FakeResponse(b'x', 'image/png'), calls)

    await client.download_media_id_to_bytes('a/b+c=')

    assert calls[0].endswith('media_id=a%2Fb%2Bc%3D')


@pytest.mark.asyncio
async def test_media_id_download_refreshes_a_rejected_token(monkeypatch):
    client = make_client()
    calls: list[str] = []
    error_body = b'{"errcode": 42001, "errmsg": "access_token expired"}'
    patch_client(
        monkeypatch,
        client,
        [FakeResponse(error_body, 'application/json'), FakeResponse(b'%PDF decrypted', 'application/pdf')],
        calls,
    )
    refreshed: list[str] = []

    async def get_access_token(secret):
        refreshed.append(secret)
        client.access_token = 'new-token'
        return 'new-token'

    monkeypatch.setattr(client, 'get_access_token', get_access_token)

    data = await client.download_media_id_to_bytes('file-media-id')

    # Exactly one refresh, and the second request carries the new token.
    assert refreshed == ['secret']
    assert data == b'%PDF decrypted'
    assert calls[0].endswith('access_token=access-token&media_id=file-media-id')
    assert calls[1].endswith('access_token=new-token&media_id=file-media-id')


@pytest.mark.asyncio
async def test_media_id_download_raises_on_a_real_error(monkeypatch):
    client = make_client()
    calls: list[str] = []
    patch_client(
        monkeypatch, client, FakeResponse(b'{"errcode": 40007, "errmsg": "bad media"}', 'application/json'), calls
    )

    with pytest.raises(Exception, match='bad media'):
        await client.download_media_id_to_bytes('file-media-id')


@pytest.mark.asyncio
async def test_media_id_download_requires_an_id():
    with pytest.raises(ValueError, match='media_id'):
        await make_client().download_media_id_to_bytes('')
