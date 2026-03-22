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


def patch_platform(monkeypatch: pytest.MonkeyPatch, value: str):
    monkeypatch.setattr('langbot.pkg.box.connector.platform.get_platform', lambda: value)


def test_box_runtime_connector_manages_local_when_no_url(monkeypatch: pytest.MonkeyPatch):
    patch_platform(monkeypatch, 'linux')
    connector = BoxRuntimeConnector(make_app(Mock()))

    assert connector.manages_local_runtime is True
    assert isinstance(connector.client, ActionRPCBoxClient)


def test_box_runtime_connector_remote_when_url_configured():
    logger = Mock()
    connector = BoxRuntimeConnector(make_app(logger, runtime_url='http://box-runtime:5410'))

    assert connector.manages_local_runtime is False
    assert isinstance(connector.client, ActionRPCBoxClient)


def test_box_runtime_connector_remote_when_docker(monkeypatch: pytest.MonkeyPatch):
    patch_platform(monkeypatch, 'docker')
    connector = BoxRuntimeConnector(make_app(Mock()))

    assert connector.manages_local_runtime is False
    assert connector.ws_relay_base_url == 'http://langbot_box_runtime:5410'


def test_box_runtime_connector_ws_relay_url_default(monkeypatch: pytest.MonkeyPatch):
    patch_platform(monkeypatch, 'linux')
    connector = BoxRuntimeConnector(make_app(Mock()))

    assert connector.ws_relay_base_url == 'http://127.0.0.1:5410'


def test_box_runtime_connector_ws_relay_url_explicit():
    connector = BoxRuntimeConnector(make_app(Mock(), runtime_url='http://box-runtime:5410'))
    assert connector.ws_relay_base_url == 'http://box-runtime:5410'


def test_box_runtime_connector_dispose_terminates_subprocess():
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
