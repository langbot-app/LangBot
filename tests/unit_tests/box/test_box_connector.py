from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot_plugin.box.client import ActionRPCBoxClient
from langbot.pkg.box.connector import BoxRuntimeConnector


def make_app(logger: Mock, runtime_endpoint: str = ''):
    return SimpleNamespace(
        logger=logger,
        instance_config=SimpleNamespace(
            data={
                'box': {
                    'backend': 'local',
                    'runtime': {'endpoint': runtime_endpoint},
                    'local': {
                        'profile': 'default',
                        'allowed_mount_roots': [],
                        'default_workspace': '',
                    },
                    'e2b': {'api_key': '', 'api_url': '', 'template': ''},
                }
            }
        ),
    )


def test_box_runtime_connector_stdio_when_no_url(monkeypatch: pytest.MonkeyPatch):
    """Without runtime.endpoint, on a non-Docker Unix platform, use stdio."""
    monkeypatch.setattr('langbot.pkg.utils.platform.get_platform', lambda: 'linux')
    monkeypatch.setattr('langbot.pkg.utils.platform.standalone_box', False)
    connector = BoxRuntimeConnector(make_app(Mock()))

    assert connector._uses_websocket() is False
    assert isinstance(connector.client, ActionRPCBoxClient)


def test_box_runtime_connector_ws_when_url_configured(monkeypatch: pytest.MonkeyPatch):
    """With an explicit runtime.endpoint, always use WebSocket."""
    monkeypatch.setattr('langbot.pkg.utils.platform.get_platform', lambda: 'linux')
    monkeypatch.setattr('langbot.pkg.utils.platform.standalone_box', False)
    logger = Mock()
    connector = BoxRuntimeConnector(make_app(logger, runtime_endpoint='http://box-runtime:5410'))

    assert connector._uses_websocket() is True
    assert isinstance(connector.client, ActionRPCBoxClient)


def test_box_runtime_connector_ws_in_docker(monkeypatch: pytest.MonkeyPatch):
    """Inside Docker (no explicit URL), use WebSocket to reach a sibling container."""
    monkeypatch.setattr('langbot.pkg.utils.platform.get_platform', lambda: 'docker')
    monkeypatch.setattr('langbot.pkg.utils.platform.standalone_box', False)
    connector = BoxRuntimeConnector(make_app(Mock()))

    assert connector._uses_websocket() is True
    assert connector.ws_relay_base_url == 'http://langbot_box:5410'


def test_box_runtime_connector_ws_with_standalone_flag(monkeypatch: pytest.MonkeyPatch):
    """With --standalone-box flag, use WebSocket even on a local Unix platform."""
    monkeypatch.setattr('langbot.pkg.utils.platform.get_platform', lambda: 'linux')
    monkeypatch.setattr('langbot.pkg.utils.platform.standalone_box', True)
    connector = BoxRuntimeConnector(make_app(Mock()))

    assert connector._uses_websocket() is True


def test_box_runtime_connector_ws_relay_url_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr('langbot.pkg.utils.platform.get_platform', lambda: 'linux')
    monkeypatch.setattr('langbot.pkg.utils.platform.standalone_box', False)
    connector = BoxRuntimeConnector(make_app(Mock()))

    assert connector.ws_relay_base_url == 'http://127.0.0.1:5410'


def test_box_runtime_connector_ws_relay_url_explicit(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr('langbot.pkg.utils.platform.get_platform', lambda: 'linux')
    monkeypatch.setattr('langbot.pkg.utils.platform.standalone_box', False)
    connector = BoxRuntimeConnector(make_app(Mock(), runtime_endpoint='http://box-runtime:5410'))
    assert connector.ws_relay_base_url == 'http://box-runtime:5410'


def test_box_runtime_connector_dispose_terminates_subprocess(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr('langbot.pkg.utils.platform.get_platform', lambda: 'linux')
    monkeypatch.setattr('langbot.pkg.utils.platform.standalone_box', False)
    logger = Mock()
    connector = BoxRuntimeConnector(make_app(logger))
    subprocess = Mock()
    subprocess.returncode = None
    handler_task = Mock()
    ctrl_task = Mock()
    connector._subprocess = subprocess
    connector._handler_task = handler_task
    connector._ctrl_task = ctrl_task

    connector.dispose()

    subprocess.terminate.assert_called_once()
    handler_task.cancel.assert_called_once()
    ctrl_task.cancel.assert_called_once()
    assert connector._handler_task is None
    assert connector._ctrl_task is None


@pytest.mark.asyncio
async def test_box_runtime_connector_heartbeat_failure_requests_reconnect(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr('langbot.pkg.box.connector._HEARTBEAT_INTERVAL_SEC', 0)
    disconnected = asyncio.Event()
    callbacks = []

    async def on_disconnect(connector):
        callbacks.append(connector)
        disconnected.set()

    connector = BoxRuntimeConnector(make_app(Mock()), runtime_disconnect_callback=on_disconnect)
    connector._handler = SimpleNamespace(call_action=AsyncMock(side_effect=TimeoutError('silent runtime')))

    heartbeat = asyncio.create_task(connector._heartbeat_loop())
    await asyncio.wait_for(disconnected.wait(), timeout=1)
    await heartbeat

    assert callbacks == [connector]
