from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import lark_oapi
import pytest
import quart

from langbot.pkg.api.http.context import (
    PrincipalContext,
    PrincipalType,
    RequestContext,
    WorkspaceContext,
)
from langbot.pkg.api.http.controller.groups.platform.adapters import (
    AdaptersRouterGroup,
    _AdapterSessionScope,
    _bind_session_scope,
    _get_owned_session,
    _pop_owned_session,
)


pytestmark = pytest.mark.asyncio


SENSITIVE_ADAPTER_ROUTES = (
    ('post', '/api/v1/platform/adapters/lark/create-app'),
    ('get', '/api/v1/platform/adapters/lark/create-app/status/missing'),
    ('delete', '/api/v1/platform/adapters/lark/create-app/missing'),
    ('post', '/api/v1/platform/adapters/weixin/login'),
    ('get', '/api/v1/platform/adapters/weixin/login/status/missing'),
    ('delete', '/api/v1/platform/adapters/weixin/login/missing'),
    ('post', '/api/v1/platform/adapters/dingtalk/create-app'),
    ('get', '/api/v1/platform/adapters/dingtalk/create-app/status/missing'),
    ('delete', '/api/v1/platform/adapters/dingtalk/create-app/missing'),
    ('post', '/api/v1/platform/adapters/wecombot/create-bot'),
    ('get', '/api/v1/platform/adapters/wecombot/create-bot/status/missing'),
    ('delete', '/api/v1/platform/adapters/wecombot/create-bot/missing'),
    ('post', '/api/v1/platform/adapters/qqofficial/bind'),
    ('get', '/api/v1/platform/adapters/qqofficial/bind/status/missing'),
    ('delete', '/api/v1/platform/adapters/qqofficial/bind/missing'),
)


def _request_context(
    *,
    account_uuid: str = 'account-a',
    workspace_uuid: str = 'workspace-a',
    placement_generation: int = 1,
) -> RequestContext:
    return RequestContext(
        instance_uuid='instance-test',
        placement_generation=placement_generation,
        request_id='request-test',
        auth_type='user-token',
        principal=PrincipalContext(
            principal_type=PrincipalType.ACCOUNT,
            account_uuid=account_uuid,
        ),
        workspace=WorkspaceContext(
            workspace_uuid=workspace_uuid,
            membership_uuid='membership-test',
            role='developer',
            permissions=frozenset({'resource.manage'}),
        ),
    )


async def _create_client(*, role: str = 'developer'):
    quart_app = quart.Quart(__name__)
    accounts = {
        'owner-token': SimpleNamespace(uuid='account-a', user='owner@example.com'),
        'other-token': SimpleNamespace(uuid='account-b', user='other@example.com'),
    }

    async def get_authenticated_account(token: str):
        return accounts[token]

    async def resolve_account_workspace(account_uuid: str, requested_workspace_uuid: str | None):
        workspace_uuid = requested_workspace_uuid or 'workspace-a'
        return SimpleNamespace(
            execution=SimpleNamespace(
                instance_uuid='instance-test',
                placement_generation=1,
            ),
            workspace=SimpleNamespace(uuid=workspace_uuid),
            membership=SimpleNamespace(
                uuid=f'membership-{account_uuid}-{workspace_uuid}',
                role=role,
                projection_revision=1,
            ),
        )

    application = SimpleNamespace(
        user_service=SimpleNamespace(
            get_authenticated_account=AsyncMock(side_effect=get_authenticated_account),
        ),
        workspace_collaboration_service=SimpleNamespace(
            resolve_account_workspace=AsyncMock(side_effect=resolve_account_workspace),
        ),
        platform_mgr=SimpleNamespace(),
    )
    router = AdaptersRouterGroup(application, quart_app)
    await router.initialize()
    return quart_app.test_client()


@pytest.mark.parametrize(('method', 'path'), SENSITIVE_ADAPTER_ROUTES)
async def test_sensitive_adapter_flows_require_resource_manage(method: str, path: str):
    client = await _create_client(role='viewer')

    response = await getattr(client, method)(
        path,
        headers={'Authorization': 'Bearer owner-token'},
    )

    assert response.status_code == 403
    assert (await response.get_json())['code'] == 'permission_denied'


async def test_session_scope_matches_exact_tenant_placement_and_principal():
    owner_context = _request_context()
    sessions: dict[str, dict] = {'session-test': {'status': 'waiting'}}
    _bind_session_scope(sessions['session-test'], owner_context)

    assert sessions['session-test']['scope'] == _AdapterSessionScope.from_request_context(owner_context)
    assert _get_owned_session(sessions, 'session-test', owner_context) is sessions['session-test']

    for other_context in (
        _request_context(account_uuid='account-b'),
        _request_context(workspace_uuid='workspace-b'),
        _request_context(placement_generation=2),
    ):
        assert _get_owned_session(sessions, 'session-test', other_context) is None
        assert _pop_owned_session(sessions, 'session-test', other_context) is None
        assert 'session-test' in sessions

    assert _pop_owned_session(sessions, 'session-test', owner_context) is not None
    assert sessions == {}


async def test_lark_session_status_and_delete_hide_cross_scope_sessions(monkeypatch):
    registration_blocker = asyncio.Event()

    async def fake_register_app(*, on_qr_code, source: str):
        assert source == 'langbot'
        on_qr_code({'url': 'https://example.test/lark-qr'})
        await registration_blocker.wait()
        raise AssertionError('registration should have been cancelled')

    monkeypatch.setattr(lark_oapi, 'aregister_app', fake_register_app)
    client = await _create_client()
    owner_headers = {
        'Authorization': 'Bearer owner-token',
        'X-Workspace-Id': 'workspace-a',
    }

    create_response = await client.post(
        '/api/v1/platform/adapters/lark/create-app',
        headers=owner_headers,
    )
    assert create_response.status_code == 200
    session_id = (await create_response.get_json())['data']['session_id']
    status_path = f'/api/v1/platform/adapters/lark/create-app/status/{session_id}'
    delete_path = f'/api/v1/platform/adapters/lark/create-app/{session_id}'

    for headers in (
        {
            'Authorization': 'Bearer other-token',
            'X-Workspace-Id': 'workspace-a',
        },
        {
            'Authorization': 'Bearer owner-token',
            'X-Workspace-Id': 'workspace-b',
        },
    ):
        status_response = await client.get(status_path, headers=headers)
        delete_response = await client.delete(delete_path, headers=headers)
        assert status_response.status_code == 404
        assert delete_response.status_code == 404
        assert (await status_response.get_json())['msg'] == 'Session not found'
        assert (await delete_response.get_json())['msg'] == 'Session not found'

    owner_status_response = await client.get(status_path, headers=owner_headers)
    assert owner_status_response.status_code == 200
    assert (await owner_status_response.get_json())['data']['status'] == 'waiting'

    owner_delete_response = await client.delete(delete_path, headers=owner_headers)
    assert owner_delete_response.status_code == 200
    missing_delete_response = await client.delete(delete_path, headers=owner_headers)
    assert missing_delete_response.status_code == 404
    await asyncio.sleep(0)
