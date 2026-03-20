from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.box.client import RemoteBoxRuntimeClient
from langbot.pkg.box.connector import BoxRuntimeConnector
from langbot.pkg.box.errors import BoxRuntimeUnavailableError


def make_app(logger: Mock, runtime_url: str = ''):
    return SimpleNamespace(
        logger=logger,
        instance_config=SimpleNamespace(
            data={
                'box': {
                    'runtime_url': runtime_url,
                    'profile': 'default',
                    'allowed_host_mount_roots': [],
                    'default_host_workspace': '',
                }
            }
        ),
    )


def patch_platform(monkeypatch: pytest.MonkeyPatch, value: str):
    monkeypatch.setattr('langbot.pkg.box.client.platform.get_platform', lambda: value)
    monkeypatch.setattr('langbot.pkg.box.connector.platform.get_platform', lambda: value)


def test_box_runtime_connector_uses_explicit_runtime_url():
    logger = Mock()
    connector = BoxRuntimeConnector(make_app(logger, runtime_url='http://box-runtime:5410'))

    assert connector.runtime_url == 'http://box-runtime:5410'
    assert connector.manages_local_runtime is False
    assert isinstance(connector.client, RemoteBoxRuntimeClient)
    assert connector.client._base_url == 'http://box-runtime:5410'


def test_box_runtime_connector_uses_local_default_runtime_url(monkeypatch: pytest.MonkeyPatch):
    patch_platform(monkeypatch, 'linux')

    connector = BoxRuntimeConnector(make_app(Mock()))

    assert connector.runtime_url == 'http://127.0.0.1:5410'
    assert connector.manages_local_runtime is True
    assert connector.client._base_url == 'http://127.0.0.1:5410'


def test_box_runtime_connector_uses_docker_default_runtime_url(monkeypatch: pytest.MonkeyPatch):
    patch_platform(monkeypatch, 'docker')

    connector = BoxRuntimeConnector(make_app(Mock()))

    assert connector.runtime_url == 'http://langbot_box_runtime:5410'
    assert connector.manages_local_runtime is False
    assert connector.client._base_url == 'http://langbot_box_runtime:5410'


@pytest.mark.asyncio
async def test_box_runtime_connector_initialize_delegates_to_client_when_runtime_is_healthy(
    monkeypatch: pytest.MonkeyPatch,
):
    patch_platform(monkeypatch, 'linux')
    connector = BoxRuntimeConnector(make_app(Mock()))
    connector.client.initialize = AsyncMock()
    connector._start_local_runtime_process = AsyncMock()
    connector._wait_until_runtime_ready = AsyncMock()

    await connector.initialize()

    connector.client.initialize.assert_awaited_once()
    connector._start_local_runtime_process.assert_not_awaited()
    connector._wait_until_runtime_ready.assert_not_awaited()


@pytest.mark.asyncio
async def test_box_runtime_connector_initialize_autostarts_local_runtime_when_unavailable(
    monkeypatch: pytest.MonkeyPatch,
):
    patch_platform(monkeypatch, 'linux')
    connector = BoxRuntimeConnector(make_app(Mock()))
    connector.client.initialize = AsyncMock(side_effect=BoxRuntimeUnavailableError('down'))
    connector._start_local_runtime_process = AsyncMock()
    connector._wait_until_runtime_ready = AsyncMock()

    await connector.initialize()

    connector.client.initialize.assert_awaited_once()
    connector._start_local_runtime_process.assert_awaited_once()
    connector._wait_until_runtime_ready.assert_awaited_once()


@pytest.mark.asyncio
async def test_box_runtime_connector_initialize_remote_runtime_does_not_autostart():
    connector = BoxRuntimeConnector(make_app(Mock(), runtime_url='http://box-runtime:5410'))
    connector.client.initialize = AsyncMock()
    connector._start_local_runtime_process = AsyncMock()
    connector._wait_until_runtime_ready = AsyncMock()

    await connector.initialize()

    connector.client.initialize.assert_awaited_once()
    connector._start_local_runtime_process.assert_not_awaited()
    connector._wait_until_runtime_ready.assert_not_awaited()


def test_box_runtime_connector_dispose_terminates_local_runtime_process():
    logger = Mock()
    connector = BoxRuntimeConnector(make_app(logger))
    runtime_process = Mock()
    runtime_process.returncode = None
    runtime_task = Mock()
    connector.runtime_subprocess = runtime_process
    connector.runtime_subprocess_task = runtime_task

    connector.dispose()

    runtime_process.terminate.assert_called_once()
    runtime_task.cancel.assert_called_once()
    assert connector.runtime_subprocess_task is None
