from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio

import pytest

from langbot.libs.slack_api.api import SlackClient


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
