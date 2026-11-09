from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.box import connector as connector_module
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


def make_app(logger: Mock, runtime_endpoint: str = '', *, cloud: bool = False):
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
        deployment=SimpleNamespace(mode='cloud' if cloud else 'oss'),
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


@pytest.mark.parametrize('platform_name', ['win32', 'linux', 'darwin'])
def test_box_runtime_connector_stdio_on_every_local_platform(monkeypatch: pytest.MonkeyPatch, platform_name):
    """A Core-launched Box uses stdio on Windows exactly as on Linux/macOS."""
    monkeypatch.setattr('langbot.pkg.utils.platform.get_platform', lambda: platform_name)
    monkeypatch.setattr('langbot.pkg.utils.platform.standalone_box', False)
    connector = BoxRuntimeConnector(make_app(Mock()))

    assert connector.uses_websocket() is False


@pytest.mark.parametrize(
    ('platform_name', 'standalone', 'endpoint'),
    [
        ('docker', False, ''),
        ('win32', True, ''),
        ('win32', False, 'ws://box-runtime:5410'),
    ],
)
def test_box_runtime_connector_ws_for_external_runtime_on_windows(
    monkeypatch: pytest.MonkeyPatch, platform_name, standalone, endpoint
):
    monkeypatch.setattr('langbot.pkg.utils.platform.get_platform', lambda: platform_name)
    monkeypatch.setattr('langbot.pkg.utils.platform.standalone_box', standalone)
    connector = BoxRuntimeConnector(make_app(Mock(), runtime_endpoint=endpoint))

    assert connector.uses_websocket() is True


@pytest.mark.asyncio
@pytest.mark.parametrize('use_reconnect', [False, True])
async def test_box_runtime_connector_windows_initialize_uses_stdio(monkeypatch: pytest.MonkeyPatch, use_reconnect):
    monkeypatch.setattr('langbot.pkg.utils.platform.get_platform', lambda: 'win32')
    monkeypatch.setattr('langbot.pkg.utils.platform.standalone_box', False)
    connector = BoxRuntimeConnector(make_app(Mock()))
    connector._start_local_stdio = AsyncMock()
    connector._connect_remote_ws = AsyncMock()

    await (connector.reconnect() if use_reconnect else connector.initialize())

    connector._start_local_stdio.assert_awaited_once()
    connector._connect_remote_ws.assert_not_awaited()
    await connector.aclose()


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
async def test_box_runtime_connector_cleans_partial_transport_on_connect_failure(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr('langbot.pkg.utils.platform.get_platform', lambda: 'linux')
    monkeypatch.setattr('langbot.pkg.utils.platform.standalone_box', False)
    connector = BoxRuntimeConnector(make_app(Mock()))
    connector._start_local_stdio = AsyncMock(side_effect=RuntimeError('bind failed'))
    connector._stop_transport = AsyncMock()
    connector._close_local_subprocess = AsyncMock()

    with pytest.raises(RuntimeError, match='bind failed'):
        await connector.initialize()

    assert connector._stop_transport.await_count == 2
    connector._close_local_subprocess.assert_awaited_once()


@pytest.mark.asyncio
async def test_box_runtime_connector_starts_heartbeat_after_reconnect(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr('langbot.pkg.utils.platform.get_platform', lambda: 'linux')
    monkeypatch.setattr('langbot.pkg.utils.platform.standalone_box', False)
    connector = BoxRuntimeConnector(make_app(Mock()))
    connector._start_local_stdio = AsyncMock(side_effect=[RuntimeError('bind failed'), None])
    connector._stop_transport = AsyncMock()
    connector._close_local_subprocess = AsyncMock()

    with pytest.raises(RuntimeError, match='bind failed'):
        await connector.initialize()

    assert connector._heartbeat_task is None

    await connector.reconnect()

    assert connector._heartbeat_task is not None
    assert not connector._heartbeat_task.done()
    await connector.aclose()


@pytest.mark.asyncio
async def test_box_stdio_connection_does_not_capture_unconsumed_stderr(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr('langbot.pkg.utils.platform.get_platform', lambda: 'linux')
    monkeypatch.setattr('langbot.pkg.utils.platform.standalone_box', False)
    created = {}

    class FakeHandler:
        def __init__(self, connection):
            self.release = asyncio.Event()

        async def call_action(self, action, data):
            return None

        async def run(self):
            await self.release.wait()

        async def close(self):
            self.release.set()

    class FakeController:
        def __init__(self, **kwargs):
            created.update(kwargs)
            self.process = SimpleNamespace(returncode=0)

        async def run(self, callback):
            await callback(object())

        async def close(self):
            return None

    monkeypatch.setattr(connector_module, 'Handler', FakeHandler)
    monkeypatch.setattr(
        'langbot_plugin.runtime.io.controllers.stdio.client.StdioClientController',
        FakeController,
    )
    connector = BoxRuntimeConnector(make_app(Mock()))

    await connector.initialize()

    assert created['capture_stderr'] is False
    assert connector._handler is not None
    await connector.aclose()


@pytest.mark.asyncio
async def test_box_disconnect_notifies_once_and_clears_handler(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr('langbot.pkg.utils.platform.get_platform', lambda: 'linux')
    monkeypatch.setattr('langbot.pkg.utils.platform.standalone_box', False)
    disconnect = AsyncMock()

    class FakeHandler:
        def __init__(self, connection):
            pass

        async def call_action(self, action, data):
            return None

        async def run(self):
            return None

        async def close(self):
            return None

    class FakeController:
        def __init__(self, **kwargs):
            self.process = SimpleNamespace(returncode=0)

        async def run(self, callback):
            await callback(object())

        async def close(self):
            return None

    monkeypatch.setattr(connector_module, 'Handler', FakeHandler)
    monkeypatch.setattr(
        'langbot_plugin.runtime.io.controllers.stdio.client.StdioClientController',
        FakeController,
    )
    connector = BoxRuntimeConnector(make_app(Mock()), runtime_disconnect_callback=disconnect)

    await connector.initialize()
    await asyncio.sleep(0)

    disconnect.assert_awaited_once_with(connector)
    assert connector._handler is None
    await connector.aclose()


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


def test_external_box_runtime_control_headers_are_tokenless_when_secret_is_unset(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv(BOX_CONTROL_TOKEN_ENV, raising=False)
    connector = BoxRuntimeConnector(make_app(Mock(), runtime_endpoint='http://box-runtime:5410'))

    assert connector.get_control_headers() == {BOX_INSTANCE_HEADER: 'instance-a'}


def test_cloud_box_runtime_rejects_missing_control_secret(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(BOX_CONTROL_TOKEN_ENV, raising=False)
    connector = BoxRuntimeConnector(make_app(Mock(), runtime_endpoint='http://box-runtime:5410', cloud=True))

    with pytest.raises(BoxRuntimeUnavailableError, match=BOX_CONTROL_TOKEN_ENV):
        connector.get_control_headers()


def test_external_box_runtime_rejects_invalid_configured_control_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(BOX_CONTROL_TOKEN_ENV, 'too-short')
    connector = BoxRuntimeConnector(make_app(Mock(), runtime_endpoint='http://box-runtime:5410'))

    with pytest.raises(BoxRuntimeUnavailableError, match=BOX_CONTROL_TOKEN_ENV):
        connector.get_control_headers()


@pytest.mark.parametrize(
    ('core_id', 'configured_id', 'environment_id', 'expected_id'),
    [
        ('instance-a', None, None, 'instance-a'),
        ('instance_12345678-abcd', None, None, 'instance_12345678-abcd'),
        ('instance-a', None, 'env-id', 'env-id'),
        ('instance-a', 'config-id', 'env-id', 'config-id'),
    ],
)
async def test_local_stdio_injects_generated_token_and_trusted_instance(
    monkeypatch: pytest.MonkeyPatch,
    core_id,
    configured_id,
    environment_id,
    expected_id,
):
    monkeypatch.delenv(BOX_CONTROL_TOKEN_ENV, raising=False)
    if environment_id:
        monkeypatch.setenv('LANGBOT_BOX_INSTANCE_ID', environment_id)
    else:
        monkeypatch.delenv('LANGBOT_BOX_INSTANCE_ID', raising=False)
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
    app = make_app(Mock())
    app.workspace_service.instance_uuid = core_id
    if configured_id:
        app.instance_config.data['box']['instance_id'] = configured_id
    connector = BoxRuntimeConnector(app)

    def fake_callback(_transport_name, connected, _connect_error, _generation):
        async def callback(_connection):
            connected.set()

        return callback

    monkeypatch.setattr(connector, '_make_connection_callback', fake_callback)

    await connector._start_local_stdio()

    assert len(captured['env'][BOX_CONTROL_TOKEN_ENV]) >= 32
    assert captured['env'][BOX_TRUSTED_INSTANCE_ENV] == core_id
    assert captured['env']['LANGBOT_BOX_INSTANCE_ID'] == expected_id


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

    def fake_callback(_transport_name, connected, _connect_error, _generation):
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
