"""Public plugin Webhook ingress: URL resolution and HTTP mapping."""

from __future__ import annotations

import base64
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import quart

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.api.http.controller.groups.plugin_webhooks import (
    MAX_WEBHOOK_BODY_BYTES,
    PluginWebhookRouterGroup,
)
from langbot.pkg.plugin.connector import PluginRuntimeConnector
from langbot.pkg.workspace.errors import WorkspaceNotFoundError
from langbot_plugin.entities.io.context import InstallationBinding, PluginInstallationDesiredState
from langbot_plugin.entities.io.errors import ActionCallTimeoutError

pytestmark = pytest.mark.asyncio

INSTALLATION = '11111111-1111-4111-8111-111111111111'


def _binding() -> InstallationBinding:
    return InstallationBinding(
        instance_uuid='instance',
        workspace_uuid='workspace',
        placement_generation=3,
        installation_uuid=INSTALLATION,
        runtime_revision=1,
        artifact_digest='a' * 64,
    )


def _setting(enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        plugin_author='author',
        plugin_name='notifier',
        installation_uuid=INSTALLATION,
        enabled=enabled,
    )


def _connector(*, mode: str = 'cloud', enabled: bool = True, known: bool = True) -> PluginRuntimeConnector:
    app = SimpleNamespace(
        instance_config=SimpleNamespace(
            data={
                'plugin': {'enable': True},
                'api': {'webhook_prefix': 'https://bot.example.com/', 'extra_webhook_prefix': ''},
            }
        ),
        deployment=SimpleNamespace(mode=mode),
        logger=Mock(),
        workspace_service=SimpleNamespace(
            get_local_execution_binding=AsyncMock(
                return_value=SimpleNamespace(
                    instance_uuid='instance', workspace_uuid='workspace', placement_generation=3
                )
            )
        ),
    )
    connector = PluginRuntimeConnector(app, AsyncMock())
    connector.handler = SimpleNamespace(
        installation_scope=Mock(side_effect=lambda _binding: nullcontext()),
        handle_webhook_request=AsyncMock(return_value={'response': {'status': 200}}),
    )
    connector._runtime_available = Mock(return_value=True)
    if known:
        connector._known_desired_states[INSTALLATION] = PluginInstallationDesiredState(
            binding=_binding(), enabled=enabled
        )
    context = ExecutionContext(instance_uuid='instance', workspace_uuid='workspace', placement_generation=3)
    connector._prepare_workspace_context = AsyncMock(return_value=(context, [_setting(enabled)]))
    connector._target_binding = AsyncMock(return_value=_binding())
    return connector


async def test_public_webhook_routes_by_installation_uuid_only():
    connector = _connector()

    result = await connector.handle_public_webhook(INSTALLATION.upper(), 'orders', {'method': 'POST'})

    assert result == {'response': {'status': 200}}
    prepared = connector._prepare_workspace_context.await_args.args[0]
    assert (prepared.instance_uuid, prepared.workspace_uuid, prepared.placement_generation) == (
        'instance',
        'workspace',
        3,
    )
    connector._target_binding.assert_awaited_once_with('author', 'notifier')
    connector.handler.handle_webhook_request.assert_awaited_once_with(
        'author', 'notifier', 'orders', {'method': 'POST'}
    )


@pytest.mark.parametrize('route_key', ['not-a-uuid', '', '22222222-2222-4222-8222-222222222222'])
async def test_public_webhook_unknown_installation_is_not_found(route_key):
    connector = _connector()

    assert await connector.handle_public_webhook(route_key, 'orders', {}) is None
    connector.handler.handle_webhook_request.assert_not_awaited()


async def test_public_webhook_cloud_never_falls_back_to_a_local_workspace():
    connector = _connector(known=False)

    assert await connector.handle_public_webhook(INSTALLATION, 'orders', {}) is None
    connector.ap.workspace_service.get_local_execution_binding.assert_not_awaited()


async def test_public_webhook_oss_resolves_local_workspace_before_first_sync():
    connector = _connector(mode='oss', known=False)

    result = await connector.handle_public_webhook(INSTALLATION, 'orders', {})

    assert result == {'response': {'status': 200}}
    connector.ap.workspace_service.get_local_execution_binding.assert_awaited_once()


async def test_public_webhook_disabled_plugin_is_reported():
    connector = _connector(enabled=False)

    assert await connector.handle_public_webhook(INSTALLATION, 'orders', {}) == {'error': 'plugin_disabled'}
    connector.handler.handle_webhook_request.assert_not_awaited()


async def test_public_webhook_stale_workspace_binding_is_not_found():
    connector = _connector()
    connector._prepare_workspace_context = AsyncMock(side_effect=WorkspaceNotFoundError('gone'))

    assert await connector.handle_public_webhook(INSTALLATION, 'orders', {}) is None


async def test_list_plugin_webhooks_builds_urls_from_webhook_components():
    connector = _connector()
    connector._setting_for_plugin = AsyncMock(return_value=(None, _setting()))
    connector.get_plugin_info = AsyncMock(
        return_value={
            'components': [
                {'manifest': {'manifest': {'kind': 'Tool', 'metadata': {'name': 'lookup'}}}},
                {
                    'manifest': {
                        'manifest': {
                            'kind': 'Webhook',
                            'metadata': {'name': 'orders', 'label': {'en_US': 'Orders'}},
                        }
                    }
                },
            ]
        }
    )

    webhooks = await connector.list_plugin_webhooks('author', 'notifier')

    assert webhooks == [
        {
            'name': 'orders',
            'label': {'en_US': 'Orders'},
            'description': {},
            'webhook_url': f'/plugins/webhooks/{INSTALLATION}/orders',
            'webhook_full_url': f'https://bot.example.com/plugins/webhooks/{INSTALLATION}/orders',
            'extra_webhook_full_url': '',
            'enabled': True,
        }
    ]


async def _client(result=None, side_effect=None):
    application = SimpleNamespace(
        logger=Mock(),
        plugin_connector=SimpleNamespace(handle_public_webhook=AsyncMock(return_value=result, side_effect=side_effect)),
    )
    quart_app = quart.Quart(__name__)
    await PluginWebhookRouterGroup(application, quart_app).initialize()
    return application, quart_app.test_client()


async def test_route_forwards_raw_request_and_returns_plugin_response():
    plugin_response = {
        'response': {
            'status': 201,
            'headers': {'content-type': 'application/json', 'set-cookie': 'x=1', 'x-handled': 'yes'},
            'body_base64': base64.b64encode(b'{"ok":true}').decode(),
        }
    }
    application, client = await _client(plugin_response)

    response = await client.post(
        f'/plugins/webhooks/{INSTALLATION}/orders/github/push?delivery=7',
        data=b'{"zen":"hi"}',
        headers={'X-Hub-Signature-256': 'sha256=abc', 'Cookie': 'session=secret', 'Content-Type': 'application/json'},
    )

    assert response.status_code == 201
    assert await response.get_data() == b'{"ok":true}'
    assert response.headers['x-handled'] == 'yes'
    assert 'set-cookie' not in response.headers
    installation, name, payload = application.plugin_connector.handle_public_webhook.await_args.args
    assert (installation, name) == (INSTALLATION, 'orders')
    assert payload['method'] == 'POST'
    assert payload['path'] == '/github/push'
    assert payload['query'] == {'delivery': '7'}
    assert payload['headers']['x-hub-signature-256'] == 'sha256=abc'
    assert 'cookie' not in payload['headers']
    assert base64.b64decode(payload['body_base64']) == b'{"zen":"hi"}'


@pytest.mark.parametrize(
    ('result', 'side_effect', 'status'),
    [
        (None, None, 404),
        ({'error': 'webhook_not_found'}, None, 404),
        ({'error': 'plugin_disabled'}, None, 403),
        ({'error': 'plugin_runtime_unavailable'}, None, 503),
        ({'error': 'webhook_handler_failed'}, None, 502),
        ({'response': {'status': 9000}}, None, 502),
        (None, ActionCallTimeoutError('slow'), 504),
        (None, RuntimeError('token=do-not-return'), 502),
    ],
)
async def test_route_maps_failures(result, side_effect, status):
    _application, client = await _client(result, side_effect)

    response = await client.post(f'/plugins/webhooks/{INSTALLATION}/orders', data=b'{}')

    assert response.status_code == status
    assert 'do-not-return' not in await response.get_data(as_text=True)


async def test_route_rejects_oversized_body_and_bad_names_before_dispatch():
    application, client = await _client({'response': {'status': 200}})

    too_large = await client.post(
        f'/plugins/webhooks/{INSTALLATION}/orders',
        data=b'x' * (MAX_WEBHOOK_BODY_BYTES + 1),
    )
    bad_name = await client.get(f'/plugins/webhooks/{INSTALLATION}/bad%20name')

    assert too_large.status_code == 413
    assert bad_name.status_code == 404
    application.plugin_connector.handle_public_webhook.assert_not_awaited()
