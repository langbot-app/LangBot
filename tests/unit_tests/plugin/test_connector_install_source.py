"""Installed-plugin reads report the install source recorded by Core.

Shared Plugin Runtime slots (Cloud) build their container in the plugin
process, which never receives the install source, so the runtime echoes an
empty ``install_source``. The WebUI keys marketplace update detection and the
source badge on it, so Core must overlay its own record.
"""

from __future__ import annotations

import datetime
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.plugin.connector import PluginRuntimeConnector


def _runtime_plugin(name: str, *, debug: bool = False, install_source: str = '') -> dict:
    return {
        'manifest': {'manifest': {'metadata': {'author': 'author', 'name': name, 'version': '0.1.0'}}},
        'debug': debug,
        'install_source': install_source,
        'install_info': {},
        'components': [],
        'status': 'initialized',
    }


def _setting(name: str, install_source: str = 'marketplace') -> SimpleNamespace:
    return SimpleNamespace(
        plugin_author='author',
        plugin_name=name,
        enabled=True,
        permission_declaration=None,
        permission_snapshot={},
        created_at=datetime.datetime(2026, 1, 1),
        install_source=install_source,
        install_info={
            'plugin_author': 'author',
            'plugin_name': name,
            'plugin_version': '0.1.0',
            '_artifact_storage': 'tenant_binary_storage_v1',
            '_manifest': {'metadata': {}},
        },
    )


def _connector(runtime_plugins: list[dict], settings: list[SimpleNamespace]) -> PluginRuntimeConnector:
    app = SimpleNamespace(
        instance_config=SimpleNamespace(data={'plugin': {'enable': True}}),
        deployment=SimpleNamespace(mode='cloud'),
        logger=Mock(),
    )
    connector = PluginRuntimeConnector(app, AsyncMock())
    by_name = {p['manifest']['manifest']['metadata']['name']: p for p in runtime_plugins}
    connector.handler = SimpleNamespace(
        installation_scope=Mock(side_effect=lambda _binding: nullcontext()),
        list_plugins=AsyncMock(return_value=runtime_plugins),
        get_plugin_info=AsyncMock(side_effect=lambda _author, name: dict(by_name[name])),
    )
    context = ExecutionContext(instance_uuid='i', workspace_uuid='w', placement_generation=1)
    connector._current_execution_context = AsyncMock(return_value=context)
    connector._operation_bindings = AsyncMock(return_value=[object()])
    connector._load_workspace_settings = AsyncMock(return_value=settings)
    connector._target_binding = AsyncMock(return_value=object())
    return connector


@pytest.mark.asyncio
async def test_list_plugins_overlays_recorded_install_source_on_shared_runtime_echo():
    connector = _connector([_runtime_plugin('market')], [_setting('market')])

    [plugin] = await connector.list_plugins()

    assert plugin['install_source'] == 'marketplace'
    assert plugin['install_info'] == {
        'plugin_author': 'author',
        'plugin_name': 'market',
        'plugin_version': '0.1.0',
    }


@pytest.mark.asyncio
async def test_get_plugin_info_overlays_recorded_install_source():
    connector = _connector([_runtime_plugin('market')], [_setting('market')])

    info = await connector.get_plugin_info('author', 'market')

    assert info is not None
    assert info['install_source'] == 'marketplace'
    assert '_artifact_storage' not in info['install_info']


@pytest.mark.asyncio
async def test_debug_plugin_keeps_its_own_install_source():
    connector = _connector(
        [_runtime_plugin('market', debug=True, install_source='debug')],
        [_setting('market')],
    )

    [plugin] = await connector.list_plugins()

    assert plugin['install_source'] == 'debug'
