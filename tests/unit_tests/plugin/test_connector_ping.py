from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.plugin import connector as connector_module
from langbot.pkg.plugin.connector import PluginRuntimeConnector, PluginRuntimeNotConnectedError
from langbot_plugin.runtime.security import (
    PLUGIN_RUNTIME_CONTROL_TOKEN_ENV,
    PLUGIN_RUNTIME_CONTROL_TOKEN_HEADER,
)


def make_connector(*, cloud: bool = False) -> PluginRuntimeConnector:
    app = SimpleNamespace(
        logger=Mock(),
        instance_config=SimpleNamespace(
            data={
                'plugin': {
                    'enable': True,
                    'worker': {
                        'max_cpus': 1.0,
                        'max_memory_mb': 512,
                        'max_pids': 128,
                        'max_open_files': 256,
                        'max_file_size_mb': 512,
                        'require_hard_limits': False,
                    },
                },
                'space': {'url': ''},
            }
        ),
        deployment=SimpleNamespace(mode='cloud' if cloud else 'oss'),
    )
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


@pytest.mark.asyncio
async def test_stop_transport_tolerates_handler_callback_removing_attribute():
    connector = make_connector()

    class Handler:
        async def close(self):
            del connector.handler

    connector.handler = Handler()

    await connector._stop_transport()

    assert not hasattr(connector, 'handler')


@pytest.mark.asyncio
async def test_stdio_runtime_connection_does_not_capture_unconsumed_stderr(
    monkeypatch: pytest.MonkeyPatch,
):
    connector = make_connector()
    connector._prepare_connected_runtime = AsyncMock()
    created = {}
    monkeypatch.setattr(connector_module.constants, 'instance_id', 'instance-a')

    class FakeRuntimeHandler:
        def __init__(self, connection, disconnect_callback, ap):
            self.release = asyncio.Event()

        async def ping(self):
            return None

        async def set_runtime_config(self, **kwargs):
            return None

        async def run(self):
            await self.release.wait()

        async def close(self):
            self.release.set()

    class FakeController:
        def __init__(self, **kwargs):
            created.update(kwargs)

        async def run(self, callback):
            await callback(object())

        async def close(self):
            return None

    monkeypatch.setattr(connector_module.platform, 'get_platform', lambda: 'linux')
    monkeypatch.setattr(
        connector_module.platform,
        'use_websocket_to_connect_plugin_runtime',
        lambda: False,
    )
    monkeypatch.setattr(
        connector_module.handler,
        'RuntimeConnectionHandler',
        FakeRuntimeHandler,
    )
    monkeypatch.setattr(
        connector_module.stdio_client_controller,
        'StdioClientController',
        FakeController,
    )

    await connector.initialize()

    assert created['capture_stderr'] is False
    assert connector._connected.is_set()
    connector._prepare_connected_runtime.assert_awaited_once()
    await connector.aclose()


@pytest.mark.asyncio
async def test_invalid_connect_timeout_is_rejected_before_transport_startup(
    monkeypatch: pytest.MonkeyPatch,
):
    connector = make_connector()
    connector.ap.instance_config.data['plugin']['connect_timeout_seconds'] = 0
    stdio_controller = Mock()
    websocket_controller = Mock()
    create_task = Mock()
    get_platform = Mock(return_value='linux')
    use_websocket = Mock(return_value=False)
    connector._start_runtime_subprocess = AsyncMock()
    monkeypatch.setattr(connector_module.constants, 'instance_id', 'instance-a')
    monkeypatch.setattr(connector_module.asyncio, 'create_task', create_task)
    monkeypatch.setattr(connector_module.platform, 'get_platform', get_platform)
    monkeypatch.setattr(
        connector_module.platform,
        'use_websocket_to_connect_plugin_runtime',
        use_websocket,
    )
    monkeypatch.setattr(
        connector_module.stdio_client_controller,
        'StdioClientController',
        stdio_controller,
    )
    monkeypatch.setattr(
        connector_module.ws_client_controller,
        'WebSocketClientController',
        websocket_controller,
    )

    with pytest.raises(ValueError, match='plugin.connect_timeout_seconds'):
        await connector.initialize()

    get_platform.assert_not_called()
    use_websocket.assert_not_called()
    stdio_controller.assert_not_called()
    websocket_controller.assert_not_called()
    connector._start_runtime_subprocess.assert_not_awaited()
    create_task.assert_not_called()
    assert connector._transport_task is None


@pytest.mark.asyncio
async def test_runtime_disconnect_notifies_once_and_clears_handler(
    monkeypatch: pytest.MonkeyPatch,
):
    disconnect = AsyncMock()
    connector = PluginRuntimeConnector(make_connector().ap, disconnect)
    connector._prepare_connected_runtime = AsyncMock()
    monkeypatch.setattr(connector_module.constants, 'instance_id', 'instance-a')

    class FakeRuntimeHandler:
        def __init__(self, connection, disconnect_callback, ap):
            self.disconnect_callback = disconnect_callback

        async def ping(self):
            return None

        async def set_runtime_config(self, **kwargs):
            return None

        async def run(self):
            await self.disconnect_callback(self)

        async def close(self):
            return None

    class FakeController:
        def __init__(self, **kwargs):
            pass

        async def run(self, callback):
            await callback(object())

        async def close(self):
            return None

    monkeypatch.setattr(connector_module.platform, 'get_platform', lambda: 'linux')
    monkeypatch.setattr(
        connector_module.platform,
        'use_websocket_to_connect_plugin_runtime',
        lambda: False,
    )
    monkeypatch.setattr(
        connector_module.handler,
        'RuntimeConnectionHandler',
        FakeRuntimeHandler,
    )
    monkeypatch.setattr(
        connector_module.stdio_client_controller,
        'StdioClientController',
        FakeController,
    )

    await connector.initialize()
    await asyncio.sleep(0)

    disconnect.assert_awaited_once_with(connector)
    assert not hasattr(connector, 'handler')
    await connector.aclose()


@pytest.mark.asyncio
async def test_disabled_connector_validates_workspace_without_runtime_handler():
    app = SimpleNamespace(
        instance_config=SimpleNamespace(data={'plugin': {'enable': False}}),
        workspace_service=SimpleNamespace(
            get_execution_binding=AsyncMock(
                return_value=SimpleNamespace(
                    instance_uuid='instance-a',
                    workspace_uuid='workspace-a',
                    placement_generation=3,
                )
            )
        ),
    )
    connector = PluginRuntimeConnector(app, AsyncMock())
    request_context = ExecutionContext(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=3,
    )

    result = await connector.require_workspace_context(request_context)

    assert result == request_context
    app.workspace_service.get_execution_binding.assert_awaited_once_with(
        'workspace-a',
        expected_generation=3,
    )


@pytest.mark.asyncio
async def test_enabled_connector_reports_not_connected_after_workspace_validation():
    connector = make_connector()
    connector.ap.workspace_service = SimpleNamespace(
        get_execution_binding=AsyncMock(
            return_value=SimpleNamespace(
                instance_uuid='instance-a',
                workspace_uuid='workspace-a',
                placement_generation=3,
            )
        )
    )
    request_context = ExecutionContext(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=3,
    )

    with pytest.raises(PluginRuntimeNotConnectedError, match='Plugin runtime is not connected'):
        await connector.require_workspace_context(request_context)


@pytest.mark.asyncio
async def test_oss_connector_resolves_singleton_only_for_legacy_callers():
    connector = make_connector()
    connector.ap.workspace_service = SimpleNamespace(
        get_local_execution_binding=AsyncMock(
            return_value=SimpleNamespace(
                instance_uuid='instance-a',
                workspace_uuid='workspace-a',
                placement_generation=3,
            )
        )
    )

    assert await connector._current_execution_context() == ExecutionContext(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=3,
    )


def test_edition_metadata_cannot_enable_shared_runtime_profile():
    connector = make_connector()
    connector.ap.instance_config.data['system'] = {'edition': 'cloud'}

    assert connector.runtime_profile == 'oss_dev'


def test_closed_deployment_selects_instance_scoped_shared_profile():
    app = SimpleNamespace(
        instance_config=SimpleNamespace(data={'plugin': {'enable': True}}),
        deployment=SimpleNamespace(mode='cloud'),
    )

    connector = PluginRuntimeConnector(app, AsyncMock())

    assert connector.runtime_profile == 'shared'


def test_external_runtime_control_headers_are_empty_when_secret_is_unset(monkeypatch):
    monkeypatch.delenv(PLUGIN_RUNTIME_CONTROL_TOKEN_ENV, raising=False)
    connector = make_connector()

    assert connector._control_headers(allow_generate=False) == {}


def test_cloud_runtime_rejects_missing_control_secret(monkeypatch):
    monkeypatch.delenv(PLUGIN_RUNTIME_CONTROL_TOKEN_ENV, raising=False)
    connector = make_connector(cloud=True)

    with pytest.raises(PluginRuntimeNotConnectedError, match=PLUGIN_RUNTIME_CONTROL_TOKEN_ENV):
        connector._control_headers(allow_generate=False)


def test_local_runtime_control_headers_generate_ephemeral_secret(monkeypatch):
    monkeypatch.delenv(PLUGIN_RUNTIME_CONTROL_TOKEN_ENV, raising=False)
    connector = make_connector()

    headers = connector._control_headers(allow_generate=True)

    assert len(headers[PLUGIN_RUNTIME_CONTROL_TOKEN_HEADER]) >= 32


@pytest.mark.asyncio
async def test_oss_legacy_fallback_fails_without_workspace_service():
    connector = make_connector()

    with pytest.raises(AttributeError):
        await connector._current_execution_context()


@pytest.mark.asyncio
async def test_cloud_connector_never_falls_back_to_ghost_local_workspace():
    app = SimpleNamespace(
        instance_config=SimpleNamespace(data={'plugin': {'enable': True}}),
        deployment=SimpleNamespace(mode='cloud'),
    )
    get_local_binding = AsyncMock()
    app.workspace_service = SimpleNamespace(
        get_local_execution_binding=get_local_binding,
    )
    connector = PluginRuntimeConnector(app, AsyncMock())

    with pytest.raises(Exception, match='Plugin resource not found'):
        await connector._current_execution_context()

    get_local_binding.assert_not_awaited()


def test_worker_policy_is_loaded_only_from_instance_configuration():
    app = SimpleNamespace(
        instance_config=SimpleNamespace(
            data={
                'plugin': {
                    'enable': True,
                    'worker': {
                        'max_cpus': 1.5,
                        'max_memory_mb': 768,
                        'max_pids': 64,
                        'max_open_files': 128,
                        'max_file_size_mb': 32,
                        'max_concurrent_restarts': 2,
                        'restart_failure_threshold': 12,
                        'restart_failure_window_seconds': 45,
                        'restart_circuit_open_seconds': 90,
                        'require_hard_limits': True,
                    },
                    # A plugin-controlled value at any other path is ignored.
                    'manifest': {'max_memory_mb': 99999},
                }
            }
        )
    )
    connector = PluginRuntimeConnector(app, AsyncMock())

    policy = connector._load_worker_policy()

    assert policy.max_cpus == 1.5
    assert policy.max_memory_mb == 768
    assert policy.max_pids == 64
    assert policy.max_open_files == 128
    assert policy.max_file_size_mb == 32
    assert policy.max_concurrent_restarts == 2
    assert policy.restart_failure_threshold == 12
    assert policy.restart_failure_window_seconds == 45
    assert policy.restart_circuit_open_seconds == 90
    assert policy.require_hard_limits is True


@pytest.mark.asyncio
async def test_explicit_cloud_binding_is_revalidated_against_projection():
    app = SimpleNamespace(
        instance_config=SimpleNamespace(
            data={
                'plugin': {'enable': True},
            }
        ),
        deployment=SimpleNamespace(mode='cloud'),
    )
    app.workspace_service = SimpleNamespace(
        get_execution_binding=AsyncMock(
            return_value=SimpleNamespace(
                instance_uuid='instance-a',
                workspace_uuid='workspace-cloud-a',
                placement_generation=7,
            )
        ),
    )
    connector = PluginRuntimeConnector(app, AsyncMock())
    connector.handler = SimpleNamespace()
    connector._synchronize_workspace = AsyncMock()
    configured = ExecutionContext(
        instance_uuid='instance-a',
        workspace_uuid='workspace-cloud-a',
        placement_generation=7,
    )

    assert await connector.require_workspace_context(configured) == configured
    app.workspace_service.get_execution_binding.assert_awaited_once_with(
        'workspace-cloud-a',
        expected_generation=7,
    )
    connector._synchronize_workspace.assert_awaited_once_with(configured)
