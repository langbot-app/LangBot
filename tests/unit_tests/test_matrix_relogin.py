"""Regression tests for the production Matrix ``!relogin`` command."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest

from langbot.pkg.platform.sources import matrix


@pytest.fixture
def bridge():
    bridge = matrix.BridgeState('@u:example.org', 'login', '', '', '')
    bridge.dm_room_id = '!bridge:example.org'
    bridge.logged_in = True
    return bridge


@pytest.fixture
def adapter(monkeypatch):
    adapter = matrix.MatrixAdapter.model_construct(
        client=SimpleNamespace(room_send=AsyncMock()),
        logger=None,
    )
    monkeypatch.setattr(matrix.asyncio, 'sleep', AsyncMock())
    monkeypatch.setattr(matrix.MatrixAdapter, '_restart_bridge_login', Mock())
    return adapter


async def test_configured_bridge_produces_logout_command_without_error(adapter, bridge) -> None:
    adapter._bridges = [bridge]

    await adapter._handle_relogin_command('!admin:example.org')

    assert adapter.client.room_send.await_count == 2
    assert adapter.client.room_send.await_args_list[0] == call(
        room_id='!bridge:example.org',
        message_type='m.room.message',
        content={'msgtype': 'm.text', 'body': 'logout'},
    )
    adapter._restart_bridge_login.assert_called_once_with(bridge)
    assert bridge.logged_in is False


async def test_configured_logout_command_is_used_verbatim(adapter, bridge) -> None:
    bridge.logout_command = 'leave'
    adapter._bridges = [bridge]

    await adapter._handle_relogin_command('!admin:example.org')

    assert adapter.client.room_send.await_count == 2
    assert adapter.client.room_send.await_args_list[0] == call(
        room_id='!bridge:example.org',
        message_type='m.room.message',
        content={'msgtype': 'm.text', 'body': 'leave'},
    )
    adapter._restart_bridge_login.assert_called_once_with(bridge)
    assert bridge.logged_in is False


async def test_skipped_bridge_is_ignored(adapter, bridge) -> None:
    bridge.dm_room_id = None
    adapter._bridges = [bridge]

    await adapter._handle_relogin_command('!admin:example.org')

    adapter.client.room_send.assert_awaited_once()
    assert adapter.client.room_send.await_args.kwargs['room_id'] == '!admin:example.org'
    adapter._restart_bridge_login.assert_not_called()
    assert bridge.logged_in is True


async def test_relogin_never_raises_for_mixed_configurations(adapter, bridge) -> None:
    missing_login = matrix.BridgeState('@skip:example.org', '', '', '', '')
    missing_login.dm_room_id = '!skip:example.org'
    missing_room = matrix.BridgeState('@skip2:example.org', 'login', '', '', '')
    adapter._bridges = [missing_login, bridge, missing_room]

    await adapter._handle_relogin_command('!admin:example.org')

    assert [sent.kwargs['room_id'] for sent in adapter.client.room_send.await_args_list] == [
        '!bridge:example.org',
        '!admin:example.org',
    ]
    assert adapter.client.room_send.await_args_list[0].kwargs['content']['body'] == 'logout'
    adapter._restart_bridge_login.assert_called_once_with(bridge)
    assert bridge.logged_in is False
