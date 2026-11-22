"""Unit tests for plugin config save readback verification in handler and HTTP router."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import quart

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.api.http.controller.groups.plugins import PluginsRouterGroup
from langbot.pkg.plugin.handler import RuntimeConnectionHandler


WORKSPACE_UUID = '11111111-1111-4111-8111-111111111111'
ACTION_CONTEXT = ExecutionContext(
    instance_uuid='instance-a',
    workspace_uuid=WORKSPACE_UUID,
    placement_generation=1,
)


def _make_handler(execute_side_effect) -> RuntimeConnectionHandler:
    handler = object.__new__(RuntimeConnectionHandler)
    handler.ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock(side_effect=execute_side_effect)),
    )
    handler.require_outbound_installation_context = lambda: ACTION_CONTEXT

    async def fake_restart(*_args, **_kwargs):
        yield {'ok': True}

    handler.call_action_generator = fake_restart
    return handler


@pytest.mark.asyncio
async def test_handler_set_plugin_config_returns_verified_config():
    expected = {'token': 'secret-val', 'enabled': True}
    handler = _make_handler(
        [
            SimpleNamespace(rowcount=1),
            SimpleNamespace(first=lambda: SimpleNamespace(config=dict(expected))),
        ]
    )

    result = await handler.set_plugin_config('author', 'demo', expected)

    assert result == {'config': expected}
    assert handler.ap.persistence_mgr.execute_async.await_count == 2


@pytest.mark.asyncio
async def test_handler_set_plugin_config_rejects_missing_setting():
    handler = _make_handler([SimpleNamespace(rowcount=0)])

    with pytest.raises(ValueError, match='Plugin setting not found: author/demo'):
        await handler.set_plugin_config('author', 'demo', {'a': 1})

    assert handler.ap.persistence_mgr.execute_async.await_count == 1


@pytest.mark.asyncio
async def test_handler_set_plugin_config_rejects_disappeared_setting():
    handler = _make_handler(
        [
            SimpleNamespace(rowcount=1),
            SimpleNamespace(first=lambda: None),
        ]
    )

    with pytest.raises(ValueError, match='Plugin setting disappeared after save: author/demo'):
        await handler.set_plugin_config('author', 'demo', {'a': 1})


@pytest.mark.asyncio
async def test_handler_set_plugin_config_rejects_mismatched_readback():
    handler = _make_handler(
        [
            SimpleNamespace(rowcount=1),
            SimpleNamespace(first=lambda: SimpleNamespace(config={'a': 2})),
        ]
    )

    with pytest.raises(RuntimeError, match='Plugin config save verification failed for author/demo'):
        await handler.set_plugin_config('author', 'demo', {'a': 1})


def _make_router_app(stored_configs: list[dict]) -> tuple[quart.Quart, PluginsRouterGroup]:
    iterator = iter(stored_configs)
    manager = SimpleNamespace(uuid='manager-account', user='manager@example.com')
    access = SimpleNamespace(
        workspace=SimpleNamespace(uuid=WORKSPACE_UUID),
        membership=SimpleNamespace(
            uuid='membership-manager',
            role='developer',
            projection_revision=1,
        ),
        execution=SimpleNamespace(instance_uuid='instance-a', placement_generation=1),
    )
    connector = SimpleNamespace(
        require_workspace_context=AsyncMock(return_value=ACTION_CONTEXT),
        get_plugin_info=AsyncMock(
            return_value={
                'author': 'author',
                'name': 'demo',
                'plugin_config': {},
            }
        ),
        set_plugin_config=AsyncMock(return_value={}),
    )
    ap = SimpleNamespace(
        _message_language_cache=None,
        deployment=SimpleNamespace(multi_workspace_enabled=False),
        plugin_connector=connector,
        user_service=SimpleNamespace(
            get_authenticated_account=AsyncMock(return_value=manager),
        ),
        workspace_collaboration_service=SimpleNamespace(
            resolve_account_workspace=AsyncMock(return_value=access),
        ),
        apikey_service=SimpleNamespace(
            verify_api_key=AsyncMock(return_value=False),
        ),
        logger=SimpleNamespace(
            info=lambda *_a, **_k: None,
            warning=lambda *_a, **_k: None,
            error=lambda *_a, **_k: None,
            debug=lambda *_a, **_k: None,
        ),
    )
    quart_app = quart.Quart(__name__)
    router = PluginsRouterGroup(ap, quart_app)
    router._get_stored_plugin_config = AsyncMock(side_effect=lambda *_a, **_k: next(iterator))
    return quart_app, router


def _auth_headers() -> dict[str, str]:
    return {
        'Authorization': 'Bearer manager-token',
        'X-Workspace-Id': WORKSPACE_UUID,
    }


@pytest.mark.asyncio
async def test_http_put_plugin_config_returns_redacted_verified_config():
    quart_app, router = _make_router_app(
        [
            {'api_key': 'old-secret', 'mode': 'fast'},
            {'api_key': 'old-secret', 'mode': 'accurate'},
        ]
    )
    await router.initialize()

    response = await quart_app.test_client().put(
        '/api/v1/plugins/author/demo/config',
        headers=_auth_headers(),
        json={'api_key': '***', 'mode': 'accurate'},
    )

    assert response.status_code == 200
    payload = await response.get_json()
    assert payload['code'] == 0
    assert payload['data']['config'] == {'api_key': '***', 'mode': 'accurate'}


@pytest.mark.asyncio
async def test_http_put_plugin_config_fails_when_readback_differs():
    quart_app, router = _make_router_app(
        [
            {'mode': 'fast'},
            {'mode': 'stale'},
        ]
    )
    await router.initialize()

    response = await quart_app.test_client().put(
        '/api/v1/plugins/author/demo/config',
        headers=_auth_headers(),
        json={'mode': 'accurate'},
    )

    assert response.status_code == 500
    payload = await response.get_json()
    assert payload['code'] != 0
    assert payload['msg'] == 'Internal server error'
    assert router._get_stored_plugin_config.await_count == 2
