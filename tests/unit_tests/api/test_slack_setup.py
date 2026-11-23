import asyncio
import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.api.http.service.slack_setup import SlackSetupService, SlackSetupError, callback_url


def context(workspace='one', principal='user'):
    return SimpleNamespace(instance_uuid='local', workspace_uuid=workspace, placement_generation=1, principal=principal)


def service():
    ap = SimpleNamespace(
        bot_service=SimpleNamespace(get_bot=AsyncMock(return_value={'adapter': 'slack-omni'})),
        workspace_service=SimpleNamespace(get_execution_binding=AsyncMock()),
        task_mgr=SimpleNamespace(
            create_user_task=lambda coro, **kwargs: SimpleNamespace(task=asyncio.create_task(coro))
        ),
    )
    obj = SlackSetupService(ap)
    obj.api = AsyncMock(
        side_effect=[
            {'app_id': 'A123', 'credentials': {'client_id': 'id', 'client_secret': 'secret', 'signing_secret': 'sign'}},
            {'ok': True},
            {'app_id': 'A123', 'token_type': 'bot', 'access_token': 'bot-token'},
        ]
    )
    return obj


async def start(obj, **kwargs):
    result = await obj.start(
        context(),
        bot_uuid='bot',
        access_token='access',
        refresh_token='refresh',
        webhook_url='https://example.com/bots/bot',
        **kwargs,
    )
    sid = result['session_id']
    await obj.sessions[sid]['task']
    return sid


@pytest.mark.asyncio
async def test_webhook_setup_oauth_and_scope():
    obj = service()
    sid = await start(obj)
    assert obj.status(context(), sid)['status'] == 'waiting'
    assert 'state=' + sid in obj.status(context(), sid)['authorize_url']
    for ctx in (context('two'), context(principal='other')):
        with pytest.raises(SlackSetupError):
            obj.status(ctx, sid)
    calls = obj.api.await_args_list
    assert 'event_subscriptions' not in json.loads(calls[0].kwargs['manifest'])['settings']
    assert json.loads(calls[1].kwargs['manifest'])['settings']['event_subscriptions']['request_url'].endswith(
        '/bots/bot'
    )
    await obj.finish(sid, 'code')
    assert obj.status(context(), sid)['config']['bot_token'] == 'bot-token'
    assert 'credentials' not in obj.sessions[sid]
    with pytest.raises(SlackSetupError):
        await obj.finish(sid, 'replay')
    obj.discard(sid)
    assert not obj.sessions


@pytest.mark.asyncio
async def test_socket_manifest_needs_no_public_webhook():
    obj = service()
    sid = await start(
        obj, socket_mode=True, redirect_url='http://localhost:5300/api/v1/platform/adapters/slack/setup/callback'
    )
    config = json.loads(obj.api.await_args_list[1].kwargs['manifest'])
    assert config['settings']['socket_mode_enabled']
    assert 'request_url' not in config['settings']['event_subscriptions']
    obj.discard(sid)


@pytest.mark.asyncio
async def test_expired_token_rotates_once():
    obj = service()
    obj.api.side_effect = [
        SlackSetupError('token_expired'),
        {'token': 'new-access', 'refresh_token': 'new-refresh'},
        {'app_id': 'A123', 'credentials': {'client_id': 'id', 'client_secret': 'secret', 'signing_secret': 'sign'}},
        {'ok': True},
    ]
    sid = await start(obj)
    assert obj.api.await_args_list[1].args == ('tooling.tokens.rotate',)
    assert obj.api.await_args_list[2].args == ('apps.manifest.create', 'new-access')
    assert 'refresh' not in obj.sessions[sid]
    obj.discard(sid)


@pytest.mark.asyncio
async def test_provisioning_error_is_visible_without_secrets():
    obj = service()
    obj.api.side_effect = RuntimeError('sensitive upstream text')
    sid = await start(obj)
    assert obj.status(context(), sid) == {'status': 'error', 'error': 'setup_failed'}
    obj.discard(sid)


@pytest.mark.asyncio
async def test_denied_authorization():
    obj = service()
    sid = await start(obj)
    with pytest.raises(SlackSetupError):
        await obj.finish(sid, '', 'access_denied')
    assert obj.status(context(), sid)['error'] == 'authorization_denied'
    assert 'credentials' not in obj.sessions[sid]
    obj.discard(sid)


@pytest.mark.asyncio
async def test_setup_webhook_only_accepts_signed_verification():
    obj = service()
    sid = await start(obj)
    body = json.dumps({'type': 'url_verification', 'challenge': 'test'}).encode()
    timestamp = str(int(time.time()))
    signature = 'v0=' + hmac.new(b'sign', b'v0:' + timestamp.encode() + b':' + body, hashlib.sha256).hexdigest()
    req = SimpleNamespace(
        get_data=AsyncMock(return_value=body),
        get_json=AsyncMock(return_value=json.loads(body)),
        headers={'X-Slack-Request-Timestamp': timestamp, 'X-Slack-Signature': signature},
    )
    assert await obj.challenge('bot', req) == {'challenge': 'test'}
    req.headers['X-Slack-Signature'] = 'forged'
    assert await obj.challenge('bot', req) is None
    obj.discard(sid)


@pytest.mark.parametrize(
    'url',
    [
        'http://example.com/bots/bot',
        'https://example.com/bots/other',
        'https://user:pass@example.com/bots/bot',
        'https://localhost/bots/bot',
        'https://127.0.0.1/bots/bot',
        'https://example.com/bots/bot?key=secret',
    ],
)
def test_invalid_callback_url(url):
    with pytest.raises(SlackSetupError):
        callback_url(url, 'bot')
