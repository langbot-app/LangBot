import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import quart

from langbot.pkg.api.http.controller.groups.platform import adapters


pytestmark = pytest.mark.asyncio


class HttpExchange:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        pass

    def get(self, *_args, **_kwargs):
        return self

    post = get


@pytest.fixture
def worker_inputs(monkeypatch):
    reader = AsyncMock()
    monkeypatch.setattr(adapters.httpclient, 'read_json_limited', reader)
    http = SimpleNamespace(
        ClientTimeout=lambda **_kwargs: None,
        ClientSession=lambda **_kwargs: HttpExchange(),
        ContentTypeError=ValueError,
    )
    router = adapters.AdaptersRouterGroup(SimpleNamespace(), quart.Quart(__name__))
    router._WECOMBOT_SESSION_TTL = 300
    router._QQOFFICIAL_SESSION_TTL = 300
    return router, http, reader


async def run_worker(kind, router, http, session, now, sleep):
    if kind == 'dingtalk':
        await router._run_device_flow(http, 'https://ding.test', session, now, sleep)
    elif kind == 'wecombot':
        await router._run_qr_flow(http, 'https://wecom.test/create', 'https://wecom.test/poll', session, now, sleep)
    else:
        await router._run_qr_binding(http, 'https://qq.test', 'encoded-key', b'private-key', session, now, sleep)


def initial_responses(kind):
    if kind == 'dingtalk':
        return [
            {'errcode': 0, 'nonce': 'nonce'},
            {'errcode': 0, 'device_code': 'device', 'verification_uri_complete': 'qr', 'interval': 5},
        ]
    if kind == 'wecombot':
        return [{'data': {'scode': 'code', 'auth_url': 'qr'}}]
    return [{'retcode': 0, 'data': {'task_id': 'task'}}]


@pytest.mark.parametrize('kind', ['dingtalk', 'wecombot', 'qqofficial'])
async def test_device_workers_publish_credentials_only_on_success(worker_inputs, monkeypatch, kind):
    router, http, reader = worker_inputs
    decrypt = Mock(return_value='decrypted-secret')
    monkeypatch.setattr(adapters, '_decrypt_qqofficial_secret', decrypt)
    terminal = {
        'dingtalk': {'errcode': 0, 'status': 'SUCCESS', 'client_id': 'id', 'client_secret': 'secret'},
        'wecombot': {'data': {'status': 'success', 'bot_info': {'botid': 'id', 'secret': 'secret'}}},
        'qqofficial': {'retcode': 0, 'data': {'status': 2, 'bot_appid': 'id', 'bot_encrypt_secret': 'encrypted'}},
    }
    reader.side_effect = initial_responses(kind) + [terminal[kind]]
    session = {'status': 'pending', 'interval': 2}
    sleep = AsyncMock()

    await run_worker(kind, router, http, session, lambda: 100, sleep)

    assert session['status'] == 'success'
    assert session[{'dingtalk': 'client_id', 'wecombot': 'botid', 'qqofficial': 'appid'}[kind]] == 'id'
    assert session[{'dingtalk': 'client_secret', 'wecombot': 'secret', 'qqofficial': 'secret'}[kind]] == (
        'decrypted-secret' if kind == 'qqofficial' else 'secret'
    )
    sleep.assert_awaited_once_with({'dingtalk': 5, 'wecombot': 3, 'qqofficial': 2}[kind])
    if kind == 'qqofficial':
        decrypt.assert_called_once_with('encrypted', b'private-key')
    else:
        decrypt.assert_not_called()


@pytest.mark.parametrize('kind', ['dingtalk', 'wecombot', 'qqofficial'])
async def test_device_workers_preserve_platform_expiry_status(worker_inputs, kind):
    router, http, reader = worker_inputs
    reader.side_effect = initial_responses(kind)
    clock = iter([100, 100, 10000])
    session = {'status': 'pending', 'interval': 2}
    sleep = AsyncMock()

    await run_worker(kind, router, http, session, lambda: next(clock), sleep)

    assert session['status'] == ('expired' if kind == 'qqofficial' else 'error')
    assert session['error'] == 'QR code expired'
    assert not any(key in session for key in ['secret', 'client_secret'])
    sleep.assert_not_awaited()


@pytest.mark.parametrize('kind', ['dingtalk', 'wecombot', 'qqofficial'])
async def test_invalid_initial_response_is_visible_without_credentials(worker_inputs, kind):
    router, http, reader = worker_inputs
    reader.side_effect = ValueError('invalid JSON')
    session = {'status': 'pending', 'interval': 2}
    sleep = AsyncMock()

    await run_worker(kind, router, http, session, lambda: 100, sleep)

    assert session['status'] == 'error'
    assert session['error'].startswith('Invalid response from ')
    assert not any(key in session for key in ['secret', 'client_secret'])
    sleep.assert_not_awaited()


@pytest.mark.parametrize('kind', ['dingtalk', 'wecombot', 'qqofficial'])
async def test_cancelled_exchange_does_not_publish_credentials(worker_inputs, kind):
    router, http, reader = worker_inputs
    reader.side_effect = asyncio.CancelledError
    session = {'status': 'pending', 'interval': 2}

    await run_worker(kind, router, http, session, lambda: 100, AsyncMock())

    assert session == {'status': 'pending', 'interval': 2}


async def test_weixin_worker_closes_client_and_keeps_expiry_semantics(worker_inputs):
    router, _, _ = worker_inputs
    client = SimpleNamespace(login=AsyncMock(side_effect=RuntimeError('QR expired')), close=AsyncMock())
    session = {'status': 'pending'}

    await router._run_login(client, asyncio.get_running_loop(), session, lambda: 100)

    assert session == {'status': 'expired', 'error': 'QR code expired'}
    client.close.assert_awaited_once()


async def test_lark_worker_preserves_denial_error(worker_inputs):
    router, _, _ = worker_inputs

    class Denied(Exception):
        pass

    class Expired(Exception):
        pass

    sdk = SimpleNamespace(aregister_app=AsyncMock(side_effect=Denied))
    session = {'status': 'waiting'}

    await router._run_registration(sdk, Denied, Expired, Mock(), session)

    assert session == {'status': 'error', 'error': 'User denied authorization'}


async def test_ttl_cleanup_preserves_live_and_boundary_sessions(worker_inputs, monkeypatch):
    router, _, _ = worker_inputs
    monkeypatch.setattr('time.time', lambda: 1000)
    old_task = SimpleNamespace(done=Mock(return_value=False), cancel=Mock())
    live_task = SimpleNamespace(done=Mock(return_value=False), cancel=Mock())
    sessions = {
        'expired': {'created_at': 699, 'task': old_task},
        'boundary': {'created_at': 700, 'task': live_task},
        'live': {'created_at': 999},
    }

    router._cleanup_sessions(sessions, 300)

    assert set(sessions) == {'boundary', 'live'}
    old_task.cancel.assert_called_once_with()
    live_task.cancel.assert_not_called()


@pytest.mark.parametrize('kind', ['wecombot', 'qqofficial'])
async def test_success_without_credentials_remains_an_error(worker_inputs, kind):
    router, http, reader = worker_inputs
    terminal = {
        'wecombot': {'data': {'status': 'success', 'bot_info': {'botid': 'id'}}},
        'qqofficial': {'retcode': 0, 'data': {'status': 2, 'bot_appid': 'id'}},
    }
    reader.side_effect = initial_responses(kind) + [terminal[kind]]
    session = {'status': 'pending', 'interval': 2}

    await run_worker(kind, router, http, session, lambda: 100, AsyncMock())

    assert session['status'] == 'error'
    assert 'secret' not in session
    assert (
        session['error']
        == {
            'wecombot': 'Scan succeeded but bot info is incomplete',
            'qqofficial': 'Incomplete credential payload',
        }[kind]
    )
