import asyncio
import logging

import pytest

from langbot.libs.wecom_customer_service_api.api import WecomCSClient, WecomCSInvalidSyncMsgTokenError
import langbot.libs.wecom_customer_service_api.api as wecomcs_api


class DummyLogger:
    async def error(self, *args, **kwargs):
        return None

    async def info(self, *args, **kwargs):
        return None

    async def debug(self, *args, **kwargs):
        return None


class DummyRequest:
    def __init__(self, method: str, payload: bytes = b'<xml></xml>'):
        self.method = method
        self.args = {
            'msg_signature': 'signature',
            'timestamp': '123',
            'nonce': '456',
            'echostr': 'echo',
        }
        self._payload = payload

    @property
    async def data(self):
        return self._payload


class FakeWXBizMsgCrypt:
    def __init__(self, token, aes, corpid):
        self.token = token
        self.aes = aes
        self.corpid = corpid

    def VerifyURL(self, msg_signature, timestamp, nonce, echostr):
        return 0, echostr

    def DecryptMsg(self, encrypt_msg, msg_signature, timestamp, nonce):
        return 0, '<xml><Token><![CDATA[token-1]]></Token><OpenKfId><![CDATA[kf-1]]></OpenKfId></xml>'


@pytest.fixture
def client():
    return WecomCSClient(
        corpid='corp-id',
        secret='secret',
        token='token',
        EncodingAESKey='aes',
        logger=DummyLogger(),
        unified_mode=True,
    )


@pytest.mark.asyncio
async def test_callback_returns_success_and_processes_all_messages_in_background(monkeypatch, client):
    handled_events: list[tuple[str, str]] = []

    @client.on_message('text')
    async def handle_text(event):
        handled_events.append((event.type, event.user_id))

    @client.on_message('image')
    async def handle_image(event):
        handled_events.append((event.type, event.user_id))

    async def fake_get_detailed_message_list(xml_msg: str):
        # 中文注释：这里模拟企业微信一次 sync_msg 返回多条消息，验证不会只处理最后一条。
        await asyncio.sleep(0)
        return [
            {
                'msgtype': 'text',
                'external_userid': 'user-1',
                'open_kfid': 'kf-1',
                'msgid': 'msg-1',
                'send_time': 111,
                'text': {'content': 'hello'},
            },
            {
                'msgtype': 'event',
                'external_userid': 'user-1',
                'open_kfid': 'kf-1',
                'msgid': 'msg-2',
                'send_time': 112,
            },
            {
                'msgtype': 'image',
                'external_userid': 'user-2',
                'open_kfid': 'kf-1',
                'msgid': 'msg-3',
                'send_time': 113,
                'picurl': 'data:image/png;base64,ZmFrZQ==',
            },
        ]

    monkeypatch.setattr(wecomcs_api, 'WXBizMsgCrypt', FakeWXBizMsgCrypt)
    monkeypatch.setattr(client, 'get_detailed_message_list', fake_get_detailed_message_list)

    response = await client._handle_callback_internal(DummyRequest(method='POST'))

    assert response == 'success'

    if client._background_tasks:
        await asyncio.gather(*list(client._background_tasks))

    assert handled_events == [('text', 'user-1'), ('image', 'user-2')]


@pytest.mark.asyncio
async def test_send_text_msg_refreshes_token_after_expired_response(monkeypatch, client):
    client.access_token = 'stale-token'
    client.token_cache._local_cache = {
        'access_token': 'stale-token',
        'expires_at': 4102444800,
    }
    request_urls: list[str] = []
    refresh_called = 0

    async def fake_refresh_access_token():
        nonlocal refresh_called
        refresh_called += 1
        client.access_token = 'fresh-token'
        client.token_cache._local_cache = {
            'access_token': 'fresh-token',
            'expires_at': 4102444800,
        }
        return client.access_token

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, json=None, headers=None, content=None):
            request_urls.append(url)
            if 'stale-token' in url:
                return FakeResponse({'errcode': 42001, 'errmsg': 'token expired'})
            return FakeResponse({'errcode': 0, 'errmsg': 'ok'})

    monkeypatch.setattr(client, 'refresh_access_token', fake_refresh_access_token)
    monkeypatch.setattr(wecomcs_api.httpx, 'AsyncClient', FakeAsyncClient)

    result = await client.send_text_msg(
        open_kfid='kf-1',
        external_userid='user-1',
        msgid='msg-1',
        content='reply',
    )

    assert result == {'errcode': 0, 'errmsg': 'ok'}
    assert refresh_called == 1
    assert len(request_urls) == 2
    assert 'stale-token' in request_urls[0]
    assert 'fresh-token' in request_urls[1]


@pytest.mark.asyncio
async def test_get_detailed_message_list_returns_all_messages(monkeypatch, client):
    client.access_token = 'token-1'

    async def fake_ensure_access_token():
        return client.access_token

    async def fake_get_pic_url(media_id: str):
        return f'data:image/png;base64,{media_id}'

    class FakeResponse:
        def json(self):
            return {
                'errcode': 0,
                'errmsg': 'ok',
                'msg_list': [
                    {
                        'msgtype': 'text',
                        'external_userid': 'user-1',
                        'open_kfid': 'kf-1',
                        'msgid': 'msg-1',
                        'send_time': 111,
                        'text': {'content': 'hello'},
                    },
                    {
                        'msgtype': 'image',
                        'external_userid': 'user-2',
                        'open_kfid': 'kf-1',
                        'msgid': 'msg-2',
                        'send_time': 112,
                        'image': {'media_id': 'media-1'},
                    },
                ],
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, json=None, headers=None, content=None):
            return FakeResponse()

    monkeypatch.setattr(client, 'ensure_access_token', fake_ensure_access_token)
    monkeypatch.setattr(client, 'get_pic_url', fake_get_pic_url)
    monkeypatch.setattr(wecomcs_api.httpx, 'AsyncClient', FakeAsyncClient)

    xml = '<xml><Token><![CDATA[token-1]]></Token><OpenKfId><![CDATA[kf-1]]></OpenKfId></xml>'
    result = await client.get_detailed_message_list(xml)

    assert len(result) == 2
    assert result[0]['msgtype'] == 'text'
    assert result[1]['msgtype'] == 'image'
    assert result[1]['picurl'] == 'data:image/png;base64,media-1'


@pytest.mark.asyncio
async def test_callback_publishes_pull_trigger_when_scheduler_enabled(monkeypatch, client):
    published: list[tuple[str, str, int | None]] = []

    class FakePublisher:
        async def publish_from_xml(self, bot_uuid: str, xml_msg: str, webhook_received_at: int | None = None):
            published.append((bot_uuid, xml_msg, webhook_received_at))
            return 'wecomcs:bot-1:pull-trigger:0', {'open_kfid': 'kf-1', 'webhook_received_at': str(webhook_received_at or '')}

    monkeypatch.setattr(wecomcs_api, 'WXBizMsgCrypt', FakeWXBizMsgCrypt)
    client.scheduler_enabled = True
    client.bot_uuid = 'bot-1'
    client.pull_trigger_publisher = FakePublisher()

    response = await client._handle_callback_internal(DummyRequest(method='POST'))

    assert response == 'success'
    assert len(published) == 1
    assert published[0][0] == 'bot-1'
    assert isinstance(published[0][2], int)
    assert client._background_tasks == set()


@pytest.mark.asyncio
async def test_fetch_sync_msg_page_raises_invalid_sync_msg_token_error(monkeypatch, client):
    client.access_token = 'token-1'

    async def fake_ensure_access_token():
        return client.access_token

    class FakeResponse:
        def json(self):
            return {
                'errcode': 95007,
                'errmsg': 'invalid msg token',
                'msg_list': [],
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, json=None, headers=None, content=None):
            return FakeResponse()

    monkeypatch.setattr(client, 'ensure_access_token', fake_ensure_access_token)
    monkeypatch.setattr(wecomcs_api.httpx, 'AsyncClient', FakeAsyncClient)

    with pytest.raises(WecomCSInvalidSyncMsgTokenError):
        await client.fetch_sync_msg_page('callback-token', 'kf-1', 'cursor-1')


@pytest.mark.asyncio
async def test_get_customer_info_returns_none_for_invalid_external_userid(monkeypatch, client):
    client.access_token = 'token-1'

    async def fake_ensure_access_token():
        return client.access_token

    class FakeResponse:
        def json(self):
            return {
                'errcode': 0,
                'errmsg': 'ok',
                'customer_list': [],
                'invalid_external_userid': ['user-1'],
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, json=None, headers=None, content=None):
            return FakeResponse()

    monkeypatch.setattr(client, 'ensure_access_token', fake_ensure_access_token)
    monkeypatch.setattr(wecomcs_api.httpx, 'AsyncClient', FakeAsyncClient)

    result = await client.get_customer_info('user-1')

    assert result is None


@pytest.mark.asyncio
async def test_get_customer_info_returns_none_when_customer_list_empty(monkeypatch, client):
    client.access_token = 'token-1'

    async def fake_ensure_access_token():
        return client.access_token

    class FakeResponse:
        def json(self):
            return {
                'errcode': 0,
                'errmsg': 'ok',
                'customer_list': [],
                'invalid_external_userid': [],
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, json=None, headers=None, content=None):
            return FakeResponse()

    monkeypatch.setattr(client, 'ensure_access_token', fake_ensure_access_token)
    monkeypatch.setattr(wecomcs_api.httpx, 'AsyncClient', FakeAsyncClient)

    result = await client.get_customer_info('user-1')

    assert result is None


@pytest.mark.asyncio
async def test_get_customer_info_logs_elapsed_time(monkeypatch, client, caplog):
    client.access_token = 'token-1'

    async def fake_ensure_access_token():
        return client.access_token

    class FakeResponse:
        def json(self):
            return {
                'errcode': 0,
                'errmsg': 'ok',
                'customer_list': [
                    {
                        'external_userid': 'user-1',
                        'nickname': 'Tester',
                    }
                ],
                'invalid_external_userid': [],
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, json=None, headers=None, content=None):
            return FakeResponse()

    perf_values = iter([10.0, 10.0, 10.2, 10.2, 10.45, 10.45])

    monkeypatch.setattr(client, 'ensure_access_token', fake_ensure_access_token)
    monkeypatch.setattr(wecomcs_api.httpx, 'AsyncClient', FakeAsyncClient)
    monkeypatch.setattr(wecomcs_api.time, 'perf_counter', lambda: next(perf_values))

    with caplog.at_level(logging.DEBUG, logger='langbot'):
        result = await client.get_customer_info('user-1')

    assert result == {'external_userid': 'user-1', 'nickname': 'Tester'}
    assert 'token_elapsed_ms=200.00' in caplog.text
    assert 'request_elapsed_ms=250.00' in caplog.text
    assert 'total_elapsed_ms=450.00' in caplog.text


@pytest.mark.asyncio
async def test_get_customer_info_uses_sender_cache_within_ten_minutes(monkeypatch, client):
    client.access_token = 'token-1'

    async def fake_ensure_access_token():
        return client.access_token

    request_count = 0

    class FakeResponse:
        def json(self):
            return {
                'errcode': 0,
                'errmsg': 'ok',
                'customer_list': [
                    {
                        'external_userid': 'user-1',
                        'nickname': 'Tester',
                    }
                ],
                'invalid_external_userid': [],
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            return None

        async def post(self, url, json=None, headers=None, content=None):
            nonlocal request_count
            request_count += 1
            return FakeResponse()

    current_time = {'value': 1000.0}

    monkeypatch.setattr(client, 'ensure_access_token', fake_ensure_access_token)
    monkeypatch.setattr(wecomcs_api.httpx, 'AsyncClient', FakeAsyncClient)
    monkeypatch.setattr(wecomcs_api.time, 'time', lambda: current_time['value'])

    first = await client.get_customer_info('user-1')
    current_time['value'] = 1000.0 + 599
    second = await client.get_customer_info('user-1')

    assert first == {'external_userid': 'user-1', 'nickname': 'Tester'}
    assert second == first
    assert request_count == 1


@pytest.mark.asyncio
async def test_wecomcs_http_client_reused_within_same_loop(monkeypatch, client):
    client.access_token = 'token-1'

    async def fake_ensure_access_token():
        return client.access_token

    create_count = 0

    class FakeResponse:
        def __init__(self, payload=None, headers=None, content=b''):
            self._payload = payload or {'errcode': 0, 'errmsg': 'ok'}
            self.headers = headers or {'Content-Type': 'application/json'}
            self.content = content
            self.status_code = 200

        def json(self):
            return self._payload

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            nonlocal create_count
            create_count += 1
            self.is_closed = False

        async def post(self, url, json=None, headers=None, content=None):
            if '/kf/sync_msg' in url:
                return FakeResponse({'errcode': 0, 'errmsg': 'ok', 'msg_list': [], 'next_cursor': 'cursor-2', 'has_more': False})
            if '/kf/customer/batchget' in url:
                return FakeResponse({'errcode': 0, 'errmsg': 'ok', 'customer_list': [{'external_userid': 'user-1', 'nickname': 'Tester'}], 'invalid_external_userid': []})
            if '/kf/send_msg' in url:
                return FakeResponse({'errcode': 0, 'errmsg': 'ok'})
            return FakeResponse()

        async def get(self, url):
            return FakeResponse({'errcode': 0, 'errmsg': 'ok'})

        async def aclose(self):
            self.is_closed = True

    monkeypatch.setattr(client, 'ensure_access_token', fake_ensure_access_token)
    monkeypatch.setattr(wecomcs_api.httpx, 'AsyncClient', FakeAsyncClient)

    await client.fetch_sync_msg_page('callback-token', 'kf-1', 'cursor-1')
    await client.get_customer_info('user-1')
    await client.send_text_msg('kf-1', 'user-1', 'msg-1', 'reply')

    assert create_count == 1



def test_wecomcs_diag_context_contains_bot_and_secret_fingerprint(client):
    client.bot_uuid = 'bot-123'
    diag = client._diag_context(open_kfid='kf-123')

    assert 'bot_uuid=bot-123' in diag
    assert 'open_kfid=kf-123' in diag
    assert 'corpid=corp-id' in diag
    assert 'secret_fp=' in diag


@pytest.mark.asyncio
async def test_send_text_msg_treats_repeated_msgid_as_idempotent_success(monkeypatch, client):
    client.access_token = 'token-1'
    client.token_cache._local_cache = {
        'access_token': 'token-1',
        'expires_at': 4102444800,
    }

    class FakeResponse:
        def json(self):
            return {'errcode': 95033, 'errmsg': 'repeated msgid'}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, json=None, headers=None, content=None):
            return FakeResponse()

    monkeypatch.setattr(wecomcs_api.httpx, 'AsyncClient', FakeAsyncClient)

    result = await client.send_text_msg(
        open_kfid='kf-1',
        external_userid='user-1',
        msgid='stable-outbound-msg-1',
        content='reply',
    )

    assert result == {'errcode': 95033, 'errmsg': 'repeated msgid'}
