"""A failed outbound heartbeat must unblock the WebSocket receive loop."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.libs.wecom_ai_bot_api.ws_client import WecomBotWsClient


@pytest.mark.asyncio
async def test_heartbeat_send_failure_closes_socket_for_reconnect():
    logger = SimpleNamespace(warning=AsyncMock())
    client = WecomBotWsClient(
        'bot-id', 'secret', logger, heartbeat_interval=0,
    )
    socket = SimpleNamespace(
        closed=False,
        send_str=AsyncMock(side_effect=ConnectionResetError('socket write failed')),
        close=AsyncMock(),
    )
    client._ws = socket
    client._running = True

    await asyncio.wait_for(client._heartbeat_loop(), timeout=1.0)

    socket.send_str.assert_awaited_once()
    socket.close.assert_awaited_once()
    logger.warning.assert_awaited_once()
    assert client._missed_pong_count == 1


@pytest.mark.asyncio
async def test_successful_heartbeat_does_not_close_socket():
    logger = SimpleNamespace(warning=AsyncMock())
    client = WecomBotWsClient(
        'bot-id', 'secret', logger, heartbeat_interval=0,
    )

    async def sent_ping(_frame):
        client._running = False

    socket = SimpleNamespace(
        closed=False,
        send_str=AsyncMock(side_effect=sent_ping),
        close=AsyncMock(),
    )
    client._ws = socket
    client._running = True

    await asyncio.wait_for(client._heartbeat_loop(), timeout=1.0)

    socket.send_str.assert_awaited_once()
    socket.close.assert_not_awaited()
    logger.warning.assert_not_awaited()
