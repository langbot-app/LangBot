from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio

import pytest

from langbot.libs.slack_api.api import SlackClient


def thread_payload(**overrides):
    return {
        'event': {
            'type': 'message',
            'channel_type': 'channel',
            'channel': 'C-1',
            'user': 'U-1',
            'ts': '1710003600.000100',
            'thread_ts': '1710003600.000001',
            'parent_user_id': 'B-1',
            'text': 'reply without mention',
            **overrides,
        }
    }


@pytest.mark.asyncio
@pytest.mark.parametrize('channel_type', ['channel', 'group'])
@pytest.mark.parametrize('subtype', [None, 'file_share', 'thread_broadcast'])
async def test_bot_thread_replies_dispatch_without_mention(channel_type, subtype):
    bot = SlackClient('test', '', SimpleNamespace(), unified_mode=True)
    received = AsyncMock()
    bot.on_message('channel')(received)
    payload = thread_payload(channel_type=channel_type, subtype=subtype)
    payload['authorizations'] = [{'is_bot': True, 'user_id': 'B-1'}]
    await bot.handle_payload(payload)
    received.assert_awaited_once()
    assert received.await_args.args[0]['event']['thread_ts'] == '1710003600.000001'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'overrides',
    [
        {'parent_user_id': 'other-user'},
        {'parent_user_id': None},
        {'thread_ts': None},
        {'bot_id': 'B-2'},
    ],
)
async def test_unrelated_channel_messages_are_ignored(overrides):
    bot = SlackClient('test', '', SimpleNamespace(), unified_mode=True)
    bot.bot_user_id = 'B-1'
    bot._handle_message = AsyncMock()
    await bot.handle_payload(thread_payload(**overrides))
    bot._handle_message.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('kinds', [('message', 'app_mention'), ('app_mention', 'message')])
async def test_bot_thread_mention_is_dispatched_once(kinds):
    bot = SlackClient('test', '', SimpleNamespace(), unified_mode=True)
    bot.bot_user_id = 'B-1'
    received = AsyncMock()
    bot.on_message('channel')(received)
    for kind in kinds:
        payload = thread_payload(type=kind, text='<@B-1> reply')
        payload['event_id'] = kind
        await bot.handle_payload(payload)
    received.assert_awaited_once()
    await bot.handle_payload(thread_payload(channel='C-2'))
    assert received.await_count == 2


@pytest.mark.asyncio
async def test_thread_edits_keep_event_dispatch():
    bot = SlackClient('test', '', SimpleNamespace(), unified_mode=True)
    bot.bot_user_id = 'B-1'
    bot._handle_message = AsyncMock()
    await bot.handle_payload(thread_payload(subtype='message_changed'))
    assert bot._handle_message.await_args.args[1] == 'event'


@pytest.mark.asyncio
async def test_socket_ack_dedup_and_backpressure():
    bot = SlackClient('test', '', SimpleNamespace(warning=AsyncMock(), error=AsyncMock()), unified_mode=True)
    client = SimpleNamespace(send_socket_mode_response=AsyncMock())
    req = SimpleNamespace(type='events_api', envelope_id='envelope', payload={'event_id': 'event'})
    await bot._socket_request(client, req)
    await bot._socket_request(client, req)
    assert client.send_socket_mode_response.await_count == 2
    assert bot.socket_queue.qsize() == 1
    for i in range(99):
        bot.socket_queue.put_nowait({'id': i})
    req.payload = {'event_id': 'another'}
    await bot._socket_request(client, req)
    assert client.send_socket_mode_response.await_count == 2
    assert 'another' not in bot.socket_seen
    await bot.close_socket()
    assert bot.socket_queue.empty()


@pytest.mark.asyncio
async def test_bot_events_do_not_loop():
    bot = SlackClient('test', '', SimpleNamespace(), unified_mode=True)
    bot._handle_message = AsyncMock()
    await bot.handle_payload({'event': {'bot_id': 'other-bot', 'channel_type': 'im'}})
    bot._handle_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_socket_lifecycle_closes_sdk_and_worker(monkeypatch):
    connected = asyncio.Event()
    client = SimpleNamespace(
        socket_mode_request_listeners=[], connect=AsyncMock(side_effect=connected.set), close=AsyncMock()
    )
    monkeypatch.setattr('slack_sdk.socket_mode.aiohttp.SocketModeClient', lambda **kwargs: client)
    bot = SlackClient('test', '', SimpleNamespace(info=AsyncMock()), unified_mode=True)
    task = asyncio.create_task(bot.run_socket('app-token'))
    await asyncio.wait_for(connected.wait(), 1)
    await bot.close_socket()
    await asyncio.wait_for(task, 1)
    client.close.assert_awaited_once()
    assert bot.socket_worker is None


@pytest.mark.asyncio
async def test_socket_connect_failure_cleans_resources(monkeypatch):
    client = SimpleNamespace(
        socket_mode_request_listeners=[], connect=AsyncMock(side_effect=ValueError('invalid_auth')), close=AsyncMock()
    )
    monkeypatch.setattr('slack_sdk.socket_mode.aiohttp.SocketModeClient', lambda **kwargs: client)
    bot = SlackClient('test', '', SimpleNamespace(info=AsyncMock()), unified_mode=True)
    with pytest.raises(ValueError):
        await bot.run_socket('app-token')
    client.close.assert_awaited_once()
    assert bot.socket_worker is None
