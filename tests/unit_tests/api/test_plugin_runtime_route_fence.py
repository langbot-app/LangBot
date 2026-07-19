from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import quart

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.workspace.errors import WorkspaceNotFoundError


CONTEXT = ExecutionContext(
    instance_uuid='instance-a',
    workspace_uuid='workspace-a',
    placement_generation=4,
)


@pytest.fixture(scope='module')
def plugin_router_cls():
    from tests.utils.import_isolation import MockLifecycleControlScope, isolated_sys_modules

    class FakeMinimalApplication:
        pass

    mock_app = Mock(Application=FakeMinimalApplication)
    mock_entities = Mock(LifecycleControlScope=MockLifecycleControlScope)
    clear = [
        'langbot.pkg.core.taskmgr',
        'langbot.pkg.api.http.controller.group',
        'langbot.pkg.api.http.controller.groups',
        'langbot.pkg.api.http.controller.groups.plugins',
        'langbot.pkg.api.http.controller.main',
    ]
    with isolated_sys_modules(
        mocks={
            'langbot.pkg.core.app': mock_app,
            'langbot.pkg.core.entities': mock_entities,
        },
        clear=clear,
    ):
        from langbot.pkg.api.http.controller.groups.plugins import PluginsRouterGroup

        yield PluginsRouterGroup


@pytest.mark.asyncio
async def test_public_plugin_asset_route_is_disabled_for_multi_workspace_policy(plugin_router_cls):
    connector = SimpleNamespace(
        get_plugin_icon=AsyncMock(),
        require_workspace_context=AsyncMock(),
    )
    ap = SimpleNamespace(
        plugin_connector=connector,
        workspace_service=SimpleNamespace(
            policy=SimpleNamespace(multi_workspace_enabled=True),
        ),
    )
    quart_app = quart.Quart(__name__)
    router = plugin_router_cls(ap, quart_app)
    await router.initialize()

    response = await quart_app.test_client().get('/api/v1/plugins/author/plugin/icon')

    assert response.status_code == 404
    connector.require_workspace_context.assert_not_awaited()
    connector.get_plugin_icon.assert_not_awaited()


@pytest.mark.asyncio
async def test_public_plugin_asset_uses_trusted_oss_singleton_binding(plugin_router_cls):
    connector = SimpleNamespace(
        require_workspace_context=AsyncMock(side_effect=lambda context: context),
    )
    binding = SimpleNamespace(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=4,
    )
    router = object.__new__(plugin_router_cls)
    router.ap = SimpleNamespace(
        plugin_connector=connector,
        workspace_service=SimpleNamespace(
            policy=SimpleNamespace(multi_workspace_enabled=False),
            get_local_execution_binding=AsyncMock(return_value=binding),
        ),
    )

    result = await router._require_public_plugin_runtime_context()

    assert result == CONTEXT
    connector.require_workspace_context.assert_awaited_once_with(CONTEXT)


@pytest.mark.asyncio
async def test_background_plugin_operation_refences_captured_generation(plugin_router_cls):
    operation = AsyncMock()
    connector = SimpleNamespace(
        require_workspace_context=AsyncMock(side_effect=WorkspaceNotFoundError('Plugin resource not found')),
    )
    router = object.__new__(plugin_router_cls)
    router.ap = SimpleNamespace(plugin_connector=connector)

    with pytest.raises(WorkspaceNotFoundError, match='Plugin resource not found'):
        await router._run_fenced_plugin_operation(CONTEXT, operation)

    operation.assert_not_awaited()
