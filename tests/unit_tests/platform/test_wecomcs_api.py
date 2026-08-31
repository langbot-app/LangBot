from __future__ import annotations

import httpx
import pytest

from langbot.libs.wecom_customer_service_api.api import WecomCSClient


@pytest.mark.asyncio
async def test_send_image_msg_posts_customer_service_image_payload() -> None:
    captured_request: httpx.Request | None = None

    def handle_request(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json={'errcode': 0})

    client = WecomCSClient(
        corpid='corp-id',
        secret='secret',
        token='token',
        EncodingAESKey='encoding-key',
        logger=None,
        unified_mode=True,
    )
    client.access_token = 'access-token'
    client._http_client = httpx.AsyncClient(transport=httpx.MockTransport(handle_request))

    try:
        await client.send_image_msg(
            open_kfid='kf-test',
            external_userid='external-user',
            msgid='a' * 32,
            media_id='media-id',
        )
    finally:
        await client.close()

    assert captured_request is not None
    assert captured_request.url.path == '/cgi-bin/kf/send_msg'
    assert captured_request.url.params['access_token'] == 'access-token'
    assert captured_request.method == 'POST'
    assert captured_request.read().decode() == (
        '{"touser":"external-user","open_kfid":"kf-test","msgid":"'
        + 'a' * 32
        + '","msgtype":"image","image":{"media_id":"media-id"}}'
    )
