from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.plugin.connector import PluginRuntimeConnector, PluginRuntimeNotConnectedError
from langbot_plugin.entities.io.context import ActionContext
from langbot_plugin.runtime.security import (
    PLUGIN_RUNTIME_CONTROL_TOKEN_ENV,
    PLUGIN_RUNTIME_CONTROL_TOKEN_HEADER,
)


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
async def test_connector_resolves_oss_singleton_binding_from_workspace_service():
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

    assert await connector._resolve_action_context() == ActionContext(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=3,
    )


@pytest.mark.asyncio
async def test_edition_metadata_cannot_enable_multi_workspace_runtime_binding():
    connector = make_connector()
    connector.ap.instance_config.data['system'] = {'edition': 'cloud'}
    connector.ap.workspace_service = SimpleNamespace(
        policy=SimpleNamespace(multi_workspace_enabled=False),
        get_local_execution_binding=AsyncMock(
            return_value=SimpleNamespace(
                instance_uuid='instance-a',
                workspace_uuid='workspace-a',
                placement_generation=1,
            )
        ),
    )

    context = await connector._resolve_action_context()

    assert context.workspace_uuid == 'workspace-a'


def test_external_runtime_control_headers_require_strong_secret(monkeypatch):
    monkeypatch.delenv(PLUGIN_RUNTIME_CONTROL_TOKEN_ENV, raising=False)
    connector = make_connector()

    with pytest.raises(PluginRuntimeNotConnectedError, match=PLUGIN_RUNTIME_CONTROL_TOKEN_ENV):
        connector._control_headers(allow_generate=False)


def test_local_runtime_control_headers_generate_ephemeral_secret(monkeypatch):
    monkeypatch.delenv(PLUGIN_RUNTIME_CONTROL_TOKEN_ENV, raising=False)
    connector = make_connector()

    headers = connector._control_headers(allow_generate=True)

    assert len(headers[PLUGIN_RUNTIME_CONTROL_TOKEN_HEADER]) >= 32


@pytest.mark.asyncio
async def test_connector_fails_closed_without_trusted_workspace_service():
    connector = make_connector()

    with pytest.raises(
        RuntimeError,
        match='Plugin Runtime Workspace binding is unavailable',
    ):
        await connector._resolve_action_context()


@pytest.mark.asyncio
async def test_cloud_connector_never_falls_back_to_ghost_local_workspace():
    connector = make_connector()
    connector.ap.instance_config.data['system'] = {'edition': 'cloud'}
    get_local_binding = AsyncMock()
    connector.ap.workspace_service = SimpleNamespace(
        policy=SimpleNamespace(multi_workspace_enabled=True),
        get_local_execution_binding=get_local_binding,
    )

    with pytest.raises(
        RuntimeError,
        match='require an explicit projected Workspace binding',
    ):
        await connector._resolve_action_context()

    get_local_binding.assert_not_awaited()


@pytest.mark.asyncio
async def test_cloud_connector_initialize_fails_before_opening_unbound_runtime():
    connector = make_connector()
    connector.ap.instance_config.data['system'] = {'edition': 'cloud'}
    connector.ap.workspace_service = SimpleNamespace(
        policy=SimpleNamespace(multi_workspace_enabled=True),
    )

    with pytest.raises(
        RuntimeError,
        match='require an explicit projected Workspace binding',
    ):
        await connector.initialize()


@pytest.mark.asyncio
async def test_explicit_cloud_binding_is_revalidated_against_projection():
    app = SimpleNamespace(
        instance_config=SimpleNamespace(
            data={
                'plugin': {'enable': True},
                'system': {'edition': 'cloud'},
            }
        )
    )
    configured = ActionContext(
        instance_uuid='instance-a',
        workspace_uuid='workspace-cloud-a',
        placement_generation=7,
    )
    app.workspace_service = SimpleNamespace(
        policy=SimpleNamespace(multi_workspace_enabled=True),
        get_execution_binding=AsyncMock(
            return_value=SimpleNamespace(
                instance_uuid='instance-a',
                workspace_uuid='workspace-cloud-a',
                placement_generation=7,
            )
        ),
        get_local_execution_binding=AsyncMock(),
    )
    connector = PluginRuntimeConnector(app, AsyncMock(), action_context=configured)

    assert await connector._resolve_action_context() == configured
    app.workspace_service.get_execution_binding.assert_awaited_once_with(
        'workspace-cloud-a',
        expected_generation=7,
    )
    app.workspace_service.get_local_execution_binding.assert_not_awaited()
