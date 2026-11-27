"""Gateway websockets must reuse one TLS client context.

Without an explicit ``ssl=``, ``websockets.connect()`` builds a fresh
``ssl.create_default_context()`` (the whole system CA store) for every
``wss://`` connection. Reconnecting platform gateways on a multi-tenant Core
turned that into the dominant source of RSS growth (Cloud OOMKill, LANG-715).
"""

from __future__ import annotations

import asyncio
import ssl
from unittest.mock import AsyncMock

import pytest
import websockets

from langbot.libs.qq_official_api.api import QQOfficialClient
from langbot.pkg.utils import httpclient


def test_client_ssl_context_is_shared_and_verifying():
    ctx = httpclient.client_ssl_context()

    assert httpclient.client_ssl_context() is ctx
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True


@pytest.mark.parametrize('url', ['wss://api.sgroup.qq.com/websocket', 'WSS://example.com/ws'])
def test_websocket_connect_kwargs_reuses_context_for_wss(url):
    kwargs = httpclient.websocket_connect_kwargs(url)

    assert kwargs == {'ssl': httpclient.client_ssl_context()}


def test_websocket_connect_kwargs_omits_ssl_for_plain_ws():
    # websockets rejects ``ssl=`` for ws:// URIs.
    assert httpclient.websocket_connect_kwargs('ws://127.0.0.1:5140/v1/events') == {}


@pytest.mark.asyncio
async def test_qq_official_gateway_reconnects_share_one_tls_context(monkeypatch):
    client = QQOfficialClient('secret', 'token', 'app-id', AsyncMock())
    client.get_gateway_url = AsyncMock(return_value='wss://api.sgroup.qq.com/websocket')
    monkeypatch.setattr(asyncio, 'sleep', AsyncMock())

    seen_ssl = []

    async def fake_connect(url, **kwargs):
        seen_ssl.append(kwargs.get('ssl'))
        if len(seen_ssl) >= 3:
            raise asyncio.CancelledError
        raise OSError('gateway unavailable')

    monkeypatch.setattr(websockets, 'connect', fake_connect)

    with pytest.raises(asyncio.CancelledError):
        await client.connect_gateway(on_event=lambda *_: None)

    assert len(seen_ssl) == 3
    assert all(ctx is httpclient.client_ssl_context() for ctx in seen_ssl)
