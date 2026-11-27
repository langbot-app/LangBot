from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.plugin.connector import PluginRuntimeNotConnectedError
from langbot.pkg.plugin import connector as connector_module
from unit_tests.plugin.test_connector_ping import make_connector


@pytest.mark.asyncio
@pytest.mark.parametrize('handshaking', [False, True])
async def test_workspace_dispatch_waits_for_reconnect(handshaking):
    connector = make_connector()
    execution = object()
    connector._validate_execution_context = AsyncMock(return_value=execution)
    connector._synchronize_workspace = AsyncMock(return_value=[])
    release = asyncio.Event()
    if handshaking:
        connector.handler = SimpleNamespace()
        connector._transport_task = asyncio.current_task()

    async def reconnect():
        await release.wait()
        connector.handler = SimpleNamespace()
        connector._connected.set()

    connector._reconnect_task = asyncio.create_task(reconnect())
    dispatch = asyncio.create_task(connector._prepare_workspace_context(execution))
    try:
        await asyncio.sleep(0.01)
        assert not dispatch.done()
        connector._synchronize_workspace.assert_not_awaited()
        release.set()
        assert await dispatch == (execution, [])
        connector._synchronize_workspace.assert_awaited_once_with(execution)
    finally:
        release.set()
        await asyncio.gather(connector._reconnect_task, dispatch, return_exceptions=True)


@pytest.mark.asyncio
async def test_disconnected_without_recovery_fails_explicitly():
    connector = make_connector()
    connector._validate_execution_context = AsyncMock(return_value=object())
    with pytest.raises(PluginRuntimeNotConnectedError, match='not connected'):
        await connector._prepare_workspace_context(object())


@pytest.mark.asyncio
async def test_disabled_plugins_do_not_wait_for_runtime():
    connector = make_connector()
    connector.is_enable_plugin = False
    execution = object()
    connector._validate_execution_context = AsyncMock(return_value=execution)
    assert await connector._prepare_workspace_context(execution) == (execution, None)


@pytest.mark.asyncio
@pytest.mark.parametrize('short_configured_timeout', [False, True])
async def test_reconnect_timeout_does_not_cancel_recovery(monkeypatch, short_configured_timeout):
    connector = make_connector()
    if short_configured_timeout:
        connector.ap.instance_config.data['plugin']['connect_timeout_seconds'] = 0.01
    else:
        monkeypatch.setattr(connector_module, '_RECONNECT_REQUEST_WAIT_SECONDS', 0.01)
    connector._validate_execution_context = AsyncMock(return_value=object())
    connector._synchronize_workspace = AsyncMock()
    connector._reconnect_task = asyncio.create_task(asyncio.Event().wait())
    try:
        with pytest.raises(PluginRuntimeNotConnectedError, match='reconnecting.*retry'):
            await connector._prepare_workspace_context(object())
        assert not connector._reconnect_task.done()
        connector._synchronize_workspace.assert_not_awaited()
    finally:
        connector._reconnect_task.cancel()
        await asyncio.gather(connector._reconnect_task, return_exceptions=True)


@pytest.mark.asyncio
async def test_cancelled_dispatch_does_not_cancel_recovery():
    connector = make_connector()
    connector._validate_execution_context = AsyncMock(return_value=object())
    connector._reconnect_task = asyncio.create_task(asyncio.Event().wait())
    dispatch = asyncio.create_task(connector._prepare_workspace_context(object()))
    try:
        await asyncio.sleep(0.01)
        dispatch.cancel()
        with pytest.raises(asyncio.CancelledError):
            await dispatch
        assert not connector._reconnect_task.done()
    finally:
        connector._reconnect_task.cancel()
        await asyncio.gather(connector._reconnect_task, dispatch, return_exceptions=True)
