"""Runner startup waits preserve installation and permission boundaries."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from langbot.pkg.plugin.connector import PluginRuntimeConnector


def connector_for(setting):
    connector = PluginRuntimeConnector(
        SimpleNamespace(logger=Mock(), instance_config=SimpleNamespace(data={})), AsyncMock()
    )
    connector._setting_for_plugin = AsyncMock(return_value=(None, setting))
    connector.get_plugin_info = AsyncMock(return_value={'status': 'initialized'})
    return connector


@pytest.mark.parametrize('pending', [True, False])
async def test_disabled_installation_does_not_wait_or_enable(pending):
    setting = SimpleNamespace(enabled=False)
    connector = connector_for(setting)
    with (
        patch(
            'langbot.pkg.api.application.plugin_permissions.permission_status',
            return_value={'pending_confirmation': pending},
        ),
        pytest.raises(ValueError, match='permission confirmation' if pending else 'disabled'),
    ):
        await connector.wait_for_runner_plugin('author', 'plugin')
    connector.get_plugin_info.assert_not_awaited()
    assert setting.enabled is False


async def test_absent_installation_fails_immediately_with_recovery_steps():
    connector = connector_for(None)
    connector._setting_for_plugin.side_effect = ValueError('Plugin author/plugin is not installed in this Workspace')
    with pytest.raises(ValueError, match='Open Plugins to install it'):
        await connector.wait_for_runner_plugin('author', 'plugin')
    connector.get_plugin_info.assert_not_awaited()


async def test_plugin_system_disabled_does_not_query_installations():
    connector = connector_for(None)
    connector.is_enable_plugin = False
    with pytest.raises(ValueError, match='plugin system is disabled'):
        await connector.wait_for_runner_plugin('author', 'plugin')
    connector._setting_for_plugin.assert_not_awaited()


async def test_wait_observes_initialization():
    connector = connector_for(SimpleNamespace(enabled=True))
    connector.get_plugin_info.side_effect = [None, {'status': 'mounted'}, {'status': 'initialized'}]
    await connector.wait_for_runner_plugin('author', 'plugin')
    assert connector.get_plugin_info.await_count == 3


async def test_readiness_deadline_cancels_a_stalled_runtime_call():
    connector = connector_for(SimpleNamespace(enabled=True))
    cancelled = asyncio.Event()

    async def stalled(*args):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    connector.get_plugin_info.side_effect = stalled
    real_timeout = asyncio.timeout
    with patch('langbot.pkg.plugin.connector.asyncio.timeout', side_effect=lambda _: real_timeout(0.01)):
        with pytest.raises(RuntimeError, match='runtime logs'):
            await connector.wait_for_runner_plugin('author', 'plugin')
    assert cancelled.is_set()


async def test_request_cancellation_propagates():
    connector = connector_for(SimpleNamespace(enabled=True))
    connector.get_plugin_info.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await connector.wait_for_runner_plugin('author', 'plugin')
