"""Security tests for the LangBot-to-Space OAuth redirect boundary."""

from __future__ import annotations

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlsplit

import pytest
import quart

from langbot.pkg.api.http.controller.groups.user import UserRouterGroup
from langbot.pkg.workspace.errors import WorkspaceNotFoundError


pytestmark = pytest.mark.integration
WORKSPACE_UUID = '11111111-1111-4111-8111-111111111111'
WORKSPACE_CREATED_AT = datetime.datetime(2026, 1, 2, 3, 4, 5, tzinfo=datetime.UTC)


@pytest.fixture
async def space_oauth_api():
    account = SimpleNamespace(uuid='account-a', user='owner@example.com')
    access = SimpleNamespace(
        workspace=SimpleNamespace(uuid=WORKSPACE_UUID),
        membership=SimpleNamespace(uuid='member-a', role='owner', projection_revision=1),
        execution=SimpleNamespace(instance_uuid='instance-a', placement_generation=1),
    )
    application = Mock()
    application.deployment = SimpleNamespace(multi_workspace_enabled=False, mode='oss')
    application.directory_projection_service = None
    application.persistence_mgr = None
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
    application.user_service.consume_space_oauth_state_details = AsyncMock(
        return_value=SimpleNamespace(launch_workspace_uuid=None)
    )
    application.user_service.bind_space_account = AsyncMock(return_value=bound_account)
    application.user_service.generate_jwt_token = AsyncMock(return_value='rotated-account-token')
    application.user_service.get_user_by_uuid = AsyncMock(return_value=bound_account)
    application.user_service.authenticate_space_user = AsyncMock(return_value=('space-login-token', bound_account))
    application.user_service.verify_jwt_token = AsyncMock()
    application.space_launch_service.consume_assertion = AsyncMock(
        return_value={'account_uuid': 'account-a', 'workspace_uuid': WORKSPACE_UUID}
    )
    application.workspace_collaboration_service.resolve_account_workspace = AsyncMock(return_value=access)
    application.workspace_service.get_execution_binding = AsyncMock(
        return_value=SimpleNamespace(
            workspace_uuid=WORKSPACE_UUID,
            workspace_created_at=WORKSPACE_CREATED_AT,
        )
    )
    application.space_service.get_oauth_authorize_url = Mock(
        side_effect=lambda redirect_uri, state: f'https://space.example/authorize?state={state}'
    )
    application.space_service.get_cloud_entry_url = Mock(return_value='https://space.example/cloud?environment=beta')
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
async def test_cloud_launch_state_is_server_issued_and_workspace_bound(space_oauth_api):
    application, client = space_oauth_api
    application.deployment.multi_workspace_enabled = True

    response = await client.get(
        '/api/v1/user/space/authorize-url',
        query_string={
            'redirect_uri': 'http://localhost/auth/space/callback',
            'launch_workspace_uuid': WORKSPACE_UUID,
        },
        headers={'Origin': 'http://localhost'},
    )

    assert response.status_code == 200
    authorize_url = (await response.get_json())['data']['authorize_url']
    assert parse_qs(urlsplit(authorize_url).query)['state'] == ['opaque-login-state']
    application.user_service.issue_space_oauth_state.assert_awaited_once_with(
        'login',
        launch_workspace_uuid=WORKSPACE_UUID,
    )


@pytest.mark.asyncio
async def test_cloud_login_entry_redirects_to_space_workspace_launcher(space_oauth_api):
    application, client = space_oauth_api
    application.deployment.mode = 'cloud'

    response = await client.get(
        '/api/v1/user/space/authorize-url',
        query_string={
            'redirect_uri': 'http://localhost/auth/space/callback',
            'cloud_entry': '1',
        },
        headers={'Origin': 'http://localhost'},
    )

    assert response.status_code == 200
    assert (await response.get_json())['data']['authorize_url'] == ('https://space.example/cloud?environment=beta')
    application.space_service.get_cloud_entry_url.assert_called_once_with()
    application.user_service.issue_space_oauth_state.assert_not_awaited()


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
async def test_redirect_allows_any_http_or_https_origin(space_oauth_api):
    _, client = space_oauth_api

    responses = [
        await client.get(
            '/api/v1/user/space/authorize-url',
            query_string={'redirect_uri': redirect_uri},
            headers={'Origin': 'https://irrelevant.example'},
        )
        for redirect_uri in (
            'https://langbot.example/auth/space/callback',
            'https://gateway.example:8443/auth/space/callback',
            'https://192.0.2.10/auth/space/callback',
            'http://localhost:5300/auth/space/callback',
            'http://127.0.0.1:5300/auth/space/callback',
            'http://[::1]:5300/auth/space/callback',
            'http://langbot.example/auth/space/callback',
            'http://192.0.2.10:5300/auth/space/callback',
        )
    ]

    assert all(response.status_code == 200 for response in responses)
    payloads = [await response.get_json() for response in responses]
    assert all(payload['code'] == 0 for payload in payloads)


@pytest.mark.asyncio
async def test_redirect_rejects_invalid_callback_shape(space_oauth_api):
    _, client = space_oauth_api

    responses = [
        await client.get(
            '/api/v1/user/space/authorize-url',
            query_string={'redirect_uri': redirect_uri},
        )
        for redirect_uri in (
            'https://langbot.example/arbitrary',
            'https://langbot.example/auth/space/callback?next=https://evil.example',
            'https://user@langbot.example/auth/space/callback',
            'https://langbot.example/auth/space/callback#fragment',
        )
    ]

    payloads = [await response.get_json() for response in responses]
    assert all(payload['code'] == 1 for payload in payloads)


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
    application.user_service.consume_space_oauth_state_details.assert_awaited_once_with('opaque-login-state', 'login')
    application.space_service.exchange_oauth_code.assert_awaited_once_with(
        'oauth-code',
        [WORKSPACE_UUID],
        {WORKSPACE_UUID: int(WORKSPACE_CREATED_AT.timestamp())},
    )


@pytest.mark.asyncio
async def test_login_callback_launch_state_selects_asserted_workspace(space_oauth_api):
    application, client = space_oauth_api
    application.user_service.consume_space_oauth_state_details.reset_mock()
    application.user_service.consume_space_oauth_state_details.return_value = SimpleNamespace(
        launch_workspace_uuid=WORKSPACE_UUID
    )

    response = await client.post(
        '/api/v1/user/space/callback',
        json={'code': 'oauth-code', 'state': 'opaque-login-state'},
    )

    assert response.status_code == 200
    data = (await response.get_json())['data']
    assert data['token'] == 'space-login-token'
    assert data['workspace_uuid'] == WORKSPACE_UUID
    application.workspace_collaboration_service.resolve_account_workspace.assert_awaited_with(
        'account-a',
        WORKSPACE_UUID,
    )


@pytest.mark.asyncio
async def test_space_credits_are_resolved_from_workspace_owner(space_oauth_api):
    application, client = space_oauth_api
    application.user_service.get_workspace_owner = AsyncMock(
        return_value=SimpleNamespace(user='owner@example.com', space_account_uuid='space-owner')
    )
    application.space_service.get_credits = AsyncMock(return_value=25000)

    response = await client.get(
        '/api/v1/user/space-credits',
        headers={'Authorization': 'Bearer account-token', 'X-Workspace-Id': WORKSPACE_UUID},
    )
    payload = await response.get_json()

    assert response.status_code == 200
    assert payload['data'] == {
        'credits': 25000,
        'owner_space_bound': True,
        'is_workspace_owner': True,
    }
    application.space_service.get_credits.assert_awaited_once_with('owner@example.com')


@pytest.mark.asyncio
async def test_oss_local_only_owner_requires_space_binding_for_langbot_models(space_oauth_api):
    application, client = space_oauth_api
    application.user_service.get_workspace_owner = AsyncMock(
        return_value=SimpleNamespace(user='owner@example.com', space_account_uuid=None)
    )
    application.space_service.get_credits = AsyncMock()

    response = await client.get(
        '/api/v1/user/space-credits',
        headers={'Authorization': 'Bearer account-token', 'X-Workspace-Id': WORKSPACE_UUID},
    )
    payload = await response.get_json()

    assert response.status_code == 200
    assert payload['data'] == {
        'credits': None,
        'owner_space_bound': False,
        'is_workspace_owner': True,
    }
    application.space_service.get_credits.assert_not_awaited()


@pytest.mark.asyncio
async def test_cloud_workspace_owner_is_always_space_bound_after_login(space_oauth_api):
    application, client = space_oauth_api
    application.deployment.mode = 'cloud'
    application.user_service.get_workspace_owner = AsyncMock(return_value=None)
    application.space_service.get_credits = AsyncMock()
    application.cloud_model_catalog_service = SimpleNamespace(
        get_workspace_credits=lambda workspace_uuid: 25000 if workspace_uuid == WORKSPACE_UUID else None
    )

    response = await client.get(
        '/api/v1/user/space-credits',
        headers={'Authorization': 'Bearer account-token', 'X-Workspace-Id': WORKSPACE_UUID},
    )
    payload = await response.get_json()

    assert response.status_code == 200
    assert payload['data'] == {
        'credits': 25000,
        'owner_space_bound': True,
        'is_workspace_owner': True,
    }
    application.space_service.get_credits.assert_not_awaited()


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


@pytest.mark.asyncio
async def test_direct_launch_assertion_does_not_consume_normal_oauth_state(space_oauth_api):
    application, client = space_oauth_api
    application.user_service.consume_space_oauth_state.reset_mock()
    application.space_service.exchange_oauth_code.reset_mock()

    response = await client.post(
        '/api/v1/user/space/callback',
        json={
            'state': 'space-generated-state-is-not-oauth-state',
            'workspace_uuid': WORKSPACE_UUID,
            'launch_assertion': 'signed-launch-token',
        },
    )

    assert response.status_code == 200
    data = (await response.get_json())['data']
    assert data['token'] == 'rotated-account-token'
    assert data['workspace_uuid'] == WORKSPACE_UUID
    application.space_launch_service.consume_assertion.assert_awaited_once_with(
        'signed-launch-token',
        expected_workspace_uuid=WORKSPACE_UUID,
    )
    application.user_service.consume_space_oauth_state.assert_not_awaited()
    application.space_service.exchange_oauth_code.assert_not_awaited()


@pytest.mark.asyncio
async def test_direct_launch_refreshes_new_workspace_projection_before_rejecting_account(space_oauth_api):
    application, client = space_oauth_api
    projected_account = SimpleNamespace(
        uuid='account-a',
        user='owner@example.com',
        account_type='space',
        status='active',
    )
    application.user_service.get_user_by_uuid = AsyncMock(side_effect=[None, None, projected_account])
    application.directory_projection_service = SimpleNamespace(sync_once=AsyncMock())

    response = await client.post(
        '/api/v1/user/space/callback',
        json={
            'workspace_uuid': WORKSPACE_UUID,
            'launch_assertion': 'signed-launch-token',
        },
    )

    assert response.status_code == 200
    assert (await response.get_json())['data']['workspace_uuid'] == WORKSPACE_UUID
    assert application.directory_projection_service.sync_once.await_count == 2
    assert application.user_service.get_user_by_uuid.await_count == 3


@pytest.mark.asyncio
async def test_direct_launch_refreshes_projection_when_account_exists_before_workspace(space_oauth_api):
    application, client = space_oauth_api
    projected_access = application.workspace_collaboration_service.resolve_account_workspace.return_value
    application.workspace_collaboration_service.resolve_account_workspace = AsyncMock(
        side_effect=[WorkspaceNotFoundError('Workspace not found'), projected_access]
    )
    application.directory_projection_service = SimpleNamespace(sync_once=AsyncMock())

    response = await client.post(
        '/api/v1/user/space/callback',
        json={
            'workspace_uuid': WORKSPACE_UUID,
            'launch_assertion': 'signed-launch-token',
        },
    )

    assert response.status_code == 200
    assert (await response.get_json())['data']['workspace_uuid'] == WORKSPACE_UUID
    application.directory_projection_service.sync_once.assert_awaited_once_with()
    assert application.workspace_collaboration_service.resolve_account_workspace.await_count == 2


@pytest.mark.asyncio
async def test_direct_launch_falls_back_to_snapshot_when_event_backlog_exceeds_page_budget(space_oauth_api):
    application, client = space_oauth_api
    projected_access = application.workspace_collaboration_service.resolve_account_workspace.return_value
    application.workspace_collaboration_service.resolve_account_workspace = AsyncMock(
        side_effect=[
            WorkspaceNotFoundError('Workspace not found'),
            WorkspaceNotFoundError('Workspace not found'),
            WorkspaceNotFoundError('Workspace not found'),
            WorkspaceNotFoundError('Workspace not found'),
            projected_access,
        ]
    )
    application.directory_projection_service = SimpleNamespace(
        sync_once=AsyncMock(),
        refresh_snapshot=AsyncMock(),
    )

    response = await client.post(
        '/api/v1/user/space/callback',
        json={
            'workspace_uuid': WORKSPACE_UUID,
            'launch_assertion': 'signed-launch-token',
        },
    )

    assert response.status_code == 200
    assert (await response.get_json())['data']['workspace_uuid'] == WORKSPACE_UUID
    assert application.directory_projection_service.sync_once.await_count == 3
    application.directory_projection_service.refresh_snapshot.assert_awaited_once_with()
    assert application.workspace_collaboration_service.resolve_account_workspace.await_count == 5
