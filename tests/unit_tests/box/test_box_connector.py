from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from langbot_plugin.box.client import ActionRPCBoxClient
from langbot.pkg.box.connector import BoxRuntimeConnector


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


def test_box_runtime_connector_stdio_when_no_url(monkeypatch: pytest.MonkeyPatch):
    """Without runtime_url, on a non-Docker Unix platform, use stdio."""
    monkeypatch.setattr('langbot.pkg.utils.platform.get_platform', lambda: 'linux')
    monkeypatch.setattr('langbot.pkg.utils.platform.standalone_box', False)
    connector = BoxRuntimeConnector(make_app(Mock()))

    assert connector._uses_websocket() is False
    assert isinstance(connector.client, ActionRPCBoxClient)


def test_box_runtime_connector_ws_when_url_configured(monkeypatch: pytest.MonkeyPatch):
    """With an explicit runtime_url, always use WebSocket."""
    monkeypatch.setattr('langbot.pkg.utils.platform.get_platform', lambda: 'linux')
    monkeypatch.setattr('langbot.pkg.utils.platform.standalone_box', False)
    logger = Mock()
    connector = BoxRuntimeConnector(make_app(logger, runtime_url='http://box-runtime:5410'))

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
    connector = BoxRuntimeConnector(make_app(Mock(), runtime_url='http://box-runtime:5410'))
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
