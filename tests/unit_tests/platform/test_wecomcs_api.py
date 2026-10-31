from __future__ import annotations

import httpx
import pytest

from langbot.libs.wecom_customer_service_api.api import WecomCSClient
from langbot_plugin.api.entities.builtin.platform.message import Image


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('method', 'args'),
    [
        ('send_text_msg', ('kf', 'user', 'msg', 'hello')),
        ('send_image_msg', ('kf', 'user', 'msg', 'media')),
        ('send_event_text', ('code', 'msg', 'hello')),
        ('send_image', ('user', 1, 'media')),
        ('change_service_status', ('user', 'kf', 'servicer')),
        ('get_pic_url', ('media',)),
        ('upload_to_work', (Image(base64='aW1hZ2U='),)),
        ('get_detailed_message_list', ('<xml><Token>token</Token><OpenKfId>kf</OpenKfId></xml>',)),
    ],
)
@pytest.mark.parametrize('errcode', [95002, 40014])
async def test_api_failures_preserve_provider_diagnostics(method, args, errcode):
    def handle_request(request):
        if request.url.path.endswith('/gettoken'):
            return httpx.Response(200, json={'access_token': 'refreshed-token'})
        return httpx.Response(200, json={'errcode': errcode, 'errmsg': 'provider detail, rid: trace-123'})

    client = WecomCSClient('corp', 'secret', 'token', 'aes', None, unified_mode=True)
    client.access_token = 'access-token'
    client._http_client = httpx.AsyncClient(transport=httpx.MockTransport(handle_request))
    try:
        with pytest.raises(Exception) as error:
            await getattr(client, method)(*args)
        assert str(errcode) in str(error.value)
        assert 'provider detail, rid: trace-123' in str(error.value)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_upload_returns_media_after_token_refresh():
    uploads = 0

    def handle_request(request):
        nonlocal uploads
        if request.url.path.endswith('/gettoken'):
            return httpx.Response(200, json={'access_token': 'refreshed-token'})
        uploads += 1
        if uploads == 1:
            return httpx.Response(200, json={'errcode': 42001, 'errmsg': 'token expired'})
        return httpx.Response(200, json={'media_id': 'uploaded-media'})

    client = WecomCSClient('corp', 'secret', 'token', 'aes', None, unified_mode=True)
    client.access_token = 'access-token'
    client._http_client = httpx.AsyncClient(transport=httpx.MockTransport(handle_request))
    try:
        assert await client.upload_to_work(Image(base64='aW1hZ2U=')) == 'uploaded-media'
        assert uploads == 2
    finally:
        await client.close()


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
