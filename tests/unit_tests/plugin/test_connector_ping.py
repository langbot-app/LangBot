from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.plugin.connector import PluginRuntimeConnector, PluginRuntimeNotConnectedError


def make_connector() -> PluginRuntimeConnector:
    app = SimpleNamespace(instance_config=SimpleNamespace(data={'plugin': {'enable': True}}))
    return PluginRuntimeConnector(app, AsyncMock())


@pytest.mark.asyncio
async def test_ping_plugin_runtime_raises_specific_error_when_not_connected():
    connector = make_connector()

    with pytest.raises(PluginRuntimeNotConnectedError, match='Plugin runtime is not connected'):
        await connector.ping_plugin_runtime()


@pytest.mark.asyncio
async def test_ping_plugin_runtime_delegates_to_connected_handler():
    connector = make_connector()
    connector.handler = SimpleNamespace(ping=AsyncMock(return_value='pong'))

    result = await connector.ping_plugin_runtime()

    assert result == 'pong'
    connector.handler.ping.assert_awaited_once()
