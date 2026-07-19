from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from langbot_plugin.box.client import ActionRPCBoxClient
from langbot_plugin.box.errors import BoxRuntimeUnavailableError
from langbot_plugin.box.security import (
    BOX_CONTROL_TOKEN_ENV,
    BOX_CONTROL_TOKEN_HEADER,
    BOX_INSTANCE_HEADER,
    BOX_PLACEMENT_GENERATION_HEADER,
    BOX_TRUSTED_INSTANCE_ENV,
    BOX_WORKSPACE_HEADER,
)
from langbot_plugin.entities.io.context import ActionContext
from langbot.pkg.box.connector import BoxRuntimeConnector


_CONTROL_TOKEN = 'box-control-token-that-is-longer-than-32-bytes'


def make_app(logger: Mock, runtime_endpoint: str = ''):
    return SimpleNamespace(
        logger=logger,
        workspace_service=SimpleNamespace(instance_uuid='instance-a'),
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


def test_box_runtime_connector_builds_host_control_headers(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(BOX_CONTROL_TOKEN_ENV, _CONTROL_TOKEN)
    connector = BoxRuntimeConnector(make_app(Mock(), runtime_endpoint='http://box-runtime:5410'))

    headers = connector.get_control_headers()

    assert headers == {
        BOX_CONTROL_TOKEN_HEADER: _CONTROL_TOKEN,
        BOX_INSTANCE_HEADER: 'instance-a',
    }
    assert _CONTROL_TOKEN not in connector._resolve_rpc_ws_url()


def test_box_runtime_connector_builds_placement_scoped_relay_headers(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(BOX_CONTROL_TOKEN_ENV, _CONTROL_TOKEN)
    connector = BoxRuntimeConnector(make_app(Mock(), runtime_endpoint='http://box-runtime:5410'))

    headers = connector.get_relay_headers(
        ActionContext(
            instance_uuid='instance-a',
            workspace_uuid='workspace-a',
            placement_generation=7,
        )
    )

    assert headers == {
        BOX_CONTROL_TOKEN_HEADER: _CONTROL_TOKEN,
        BOX_INSTANCE_HEADER: 'instance-a',
        BOX_WORKSPACE_HEADER: 'workspace-a',
        BOX_PLACEMENT_GENERATION_HEADER: '7',
    }


def test_box_runtime_connector_rejects_relay_context_from_other_instance(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(BOX_CONTROL_TOKEN_ENV, _CONTROL_TOKEN)
    connector = BoxRuntimeConnector(make_app(Mock(), runtime_endpoint='http://box-runtime:5410'))

    with pytest.raises(BoxRuntimeUnavailableError, match='another LangBot instance'):
        connector.get_relay_headers(
            ActionContext(
                instance_uuid='instance-b',
                workspace_uuid='workspace-a',
                placement_generation=1,
            )
        )


def test_external_box_runtime_fails_closed_without_control_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(BOX_CONTROL_TOKEN_ENV, raising=False)
    connector = BoxRuntimeConnector(make_app(Mock(), runtime_endpoint='http://box-runtime:5410'))

    with pytest.raises(BoxRuntimeUnavailableError, match=BOX_CONTROL_TOKEN_ENV):
        connector.get_control_headers()


async def test_local_stdio_injects_generated_token_and_trusted_instance(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv(BOX_CONTROL_TOKEN_ENV, raising=False)
    captured = {}

    class FakeStdioClientController:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.process = Mock()

        async def run(self, callback):
            await callback(None)

    monkeypatch.setattr(
        'langbot_plugin.runtime.io.controllers.stdio.client.StdioClientController',
        FakeStdioClientController,
    )
    connector = BoxRuntimeConnector(make_app(Mock()))

    def fake_callback(_transport_name, connected, _connect_error):
        async def callback(_connection):
            connected.set()

        return callback

    monkeypatch.setattr(connector, '_make_connection_callback', fake_callback)

    await connector._start_local_stdio()

    assert len(captured['env'][BOX_CONTROL_TOKEN_ENV]) >= 32
    assert captured['env'][BOX_TRUSTED_INSTANCE_ENV] == 'instance-a'


async def test_websocket_controller_receives_control_headers(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(BOX_CONTROL_TOKEN_ENV, _CONTROL_TOKEN)
    captured = {}

    class FakeWebSocketClientController:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def run(self, callback):
            await callback(None)

    monkeypatch.setattr(
        'langbot_plugin.runtime.io.controllers.ws.client.WebSocketClientController',
        FakeWebSocketClientController,
    )
    connector = BoxRuntimeConnector(make_app(Mock(), runtime_endpoint='http://box-runtime:5410'))

    def fake_callback(_transport_name, connected, _connect_error):
        async def callback(_connection):
            connected.set()

        return callback

    monkeypatch.setattr(connector, '_make_connection_callback', fake_callback)

    await connector._connect_ws('ws://box-runtime:5410/rpc/ws', 'WebSocket')

    assert captured['additional_headers'] == {
        BOX_CONTROL_TOKEN_HEADER: _CONTROL_TOKEN,
        BOX_INSTANCE_HEADER: 'instance-a',
    }
    assert _CONTROL_TOKEN not in captured['ws_url']
