"""Security tests for the LangBot-to-Space OAuth redirect boundary."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlsplit

import pytest
import quart

from langbot.pkg.api.http.controller.groups.user import UserRouterGroup


pytestmark = pytest.mark.integration
WORKSPACE_UUID = '11111111-1111-4111-8111-111111111111'


@pytest.fixture
async def space_oauth_api():
    account = SimpleNamespace(uuid='account-a', user='owner@example.com')
    access = SimpleNamespace(
        workspace=SimpleNamespace(uuid=WORKSPACE_UUID),
        membership=SimpleNamespace(uuid='member-a', role='owner', projection_revision=1),
        execution=SimpleNamespace(instance_uuid='instance-a', placement_generation=1),
    )
    application = Mock()
    application.user_service.get_authenticated_account = AsyncMock(return_value=account)
    application.user_service.issue_space_oauth_state = AsyncMock(
        side_effect=lambda purpose, **_: f'opaque-{purpose}-state'
    )
    local_account = SimpleNamespace(
        uuid='account-a',
        user='owner@example.com',
        account_type='local',
    )
    bound_account = SimpleNamespace(
        uuid='account-a',
        user='owner@example.com',
        account_type='space',
    )
    application.user_service.consume_space_oauth_state = AsyncMock(
        side_effect=lambda state, purpose: (
            local_account if (state, purpose) == ('opaque-bind-state', 'bind') else None
        )
    )
    application.user_service.bind_space_account = AsyncMock(return_value=bound_account)
    application.user_service.generate_jwt_token = AsyncMock(return_value='rotated-account-token')
    application.user_service.authenticate_space_user = AsyncMock(return_value=('space-login-token', bound_account))
    application.user_service.verify_jwt_token = AsyncMock()
    application.workspace_collaboration_service.resolve_account_workspace = AsyncMock(return_value=access)
    application.space_service.get_oauth_authorize_url = Mock(
        side_effect=lambda redirect_uri, state: f'https://space.example/authorize?state={state}'
    )
    application.space_service.exchange_oauth_code = AsyncMock(
        return_value={
            'access_token': 'space-access-token',
            'refresh_token': 'space-refresh-token',
            'expires_in': 3600,
        }
    )
    application.instance_config.data = {
        'api': {'webui_url': 'http://localhost'},
        'system': {'allow_modify_login_info': True},
    }

    quart_app = quart.Quart(__name__)
    router = UserRouterGroup(application, quart_app)
    await router.initialize()
    return application, quart_app.test_client()


@pytest.mark.asyncio
async def test_public_login_state_is_server_issued(space_oauth_api):
    application, client = space_oauth_api
    response = await client.get(
        '/api/v1/user/space/authorize-url',
        query_string={'redirect_uri': 'http://localhost/auth/space/callback'},
        headers={'Origin': 'http://localhost'},
    )

    assert response.status_code == 200
    authorize_url = (await response.get_json())['data']['authorize_url']
    assert parse_qs(urlsplit(authorize_url).query)['state'] == ['opaque-login-state']
    application.user_service.issue_space_oauth_state.assert_awaited_once_with('login')


@pytest.mark.asyncio
async def test_public_login_rejects_caller_supplied_state(space_oauth_api):
    application, client = space_oauth_api
    response = await client.get(
        '/api/v1/user/space/authorize-url',
        query_string={
            'redirect_uri': 'http://localhost/auth/space/callback',
            'state': 'jwt.must-not-be-used',
        },
        headers={'Origin': 'http://localhost'},
    )

    assert response.status_code == 200
    assert (await response.get_json())['code'] == 1
    application.space_service.get_oauth_authorize_url.assert_not_called()


@pytest.mark.asyncio
async def test_bind_state_is_account_bound_and_requires_authentication(space_oauth_api):
    application, client = space_oauth_api
    path = '/api/v1/user/space/bind-authorize-url'
    query = {'redirect_uri': 'http://localhost/auth/space/callback?mode=bind'}

    unauthorized = await client.get(path, query_string=query, headers={'Origin': 'http://localhost'})
    response = await client.get(
        path,
        query_string=query,
        headers={
            'Origin': 'http://localhost',
            'Authorization': 'Bearer user-token',
            'X-Workspace-Id': WORKSPACE_UUID,
        },
    )

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    application.user_service.issue_space_oauth_state.assert_awaited_once_with('bind', account_uuid='account-a')


@pytest.mark.asyncio
async def test_redirect_origin_and_callback_path_are_restricted(space_oauth_api):
    _, client = space_oauth_api

    wrong_origin = await client.get(
        '/api/v1/user/space/authorize-url',
        query_string={'redirect_uri': 'https://evil.example/auth/space/callback'},
        headers={'Origin': 'http://localhost'},
    )
    wrong_path = await client.get(
        '/api/v1/user/space/authorize-url',
        query_string={'redirect_uri': 'http://localhost/arbitrary'},
        headers={'Origin': 'http://localhost'},
    )
    forged_origin = await client.get(
        '/api/v1/user/space/authorize-url',
        query_string={'redirect_uri': 'https://evil.example/auth/space/callback'},
        headers={'Origin': 'https://evil.example'},
    )
    forged_host = await client.get(
        '/api/v1/user/space/authorize-url',
        query_string={'redirect_uri': 'https://evil.example/auth/space/callback'},
        headers={'Host': 'evil.example'},
    )

    assert (await wrong_origin.get_json())['code'] == 1
    assert (await wrong_path.get_json())['code'] == 1
    assert (await forged_origin.get_json())['code'] == 1
    assert (await forged_host.get_json())['code'] == 1


@pytest.mark.asyncio
async def test_explicit_server_side_webui_origin_supports_split_dev_server(space_oauth_api):
    application, client = space_oauth_api
    application.instance_config.data['api'] = {'webui_url': 'http://localhost:5173'}

    response = await client.get(
        '/api/v1/user/space/authorize-url',
        query_string={'redirect_uri': 'http://localhost:5173/auth/space/callback'},
        headers={'Origin': 'https://irrelevant.example'},
    )

    assert response.status_code == 200
    assert (await response.get_json())['code'] == 0


@pytest.mark.asyncio
async def test_server_side_webhook_origin_supports_bundled_ui(space_oauth_api):
    application, client = space_oauth_api
    application.instance_config.data['api'] = {
        'webui_url': '',
        'webhook_prefix': 'https://langbot.example/base/path',
    }

    response = await client.get(
        '/api/v1/user/space/authorize-url',
        query_string={'redirect_uri': 'https://langbot.example/auth/space/callback'},
        headers={'Host': 'attacker.example'},
    )

    assert response.status_code == 200
    assert (await response.get_json())['code'] == 0


@pytest.mark.asyncio
async def test_login_callback_requires_and_consumes_server_state(space_oauth_api):
    application, client = space_oauth_api

    missing = await client.post('/api/v1/user/space/callback', json={'code': 'oauth-code'})
    response = await client.post(
        '/api/v1/user/space/callback',
        json={'code': 'oauth-code', 'state': 'opaque-login-state'},
    )

    assert (await missing.get_json())['code'] == 1
    assert response.status_code == 200
    assert (await response.get_json())['data']['token'] == 'space-login-token'
    application.user_service.consume_space_oauth_state.assert_awaited_once_with('opaque-login-state', 'login')
    application.space_service.exchange_oauth_code.assert_awaited_once_with('oauth-code')


@pytest.mark.asyncio
async def test_bind_callback_uses_opaque_state_and_never_treats_it_as_jwt(space_oauth_api):
    application, client = space_oauth_api
    application.user_service.consume_space_oauth_state.reset_mock()
    application.user_service.consume_space_oauth_state.side_effect = [
        ValueError('invalid state'),
        SimpleNamespace(
            uuid='account-a',
            user='owner@example.com',
            account_type='local',
        ),
    ]

    rejected = await client.post(
        '/api/v1/user/bind-space',
        json={'code': 'attacker-code', 'state': 'jwt.must-not-be-used'},
    )
    response = await client.post(
        '/api/v1/user/bind-space',
        json={'code': 'oauth-code', 'state': 'opaque-bind-state'},
    )

    assert rejected.status_code == 401
    assert response.status_code == 200
    assert (await response.get_json())['data']['token'] == 'rotated-account-token'
    application.user_service.verify_jwt_token.assert_not_awaited()
    application.user_service.bind_space_account.assert_awaited_once_with('owner@example.com', 'oauth-code')
