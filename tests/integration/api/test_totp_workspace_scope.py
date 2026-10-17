"""Workspace scoping for the owner/admin second-factor oversight endpoints.

An owner or admin answers for the Accounts of its own Workspace. The oversight
endpoints must never list, revoke, or re-bind another tenant's Account.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import quart

from langbot.pkg.api.http.controller.groups.user import UserRouterGroup
from langbot.pkg.workspace.errors import WorkspaceNotFoundError

pytestmark = pytest.mark.integration

WORKSPACE_UUID = '11111111-1111-4111-8111-111111111111'
MEMBER_UUID = 'member-account'
FOREIGN_UUID = 'foreign-account'


def _access(account_uuid: str) -> SimpleNamespace:
    return SimpleNamespace(
        workspace=SimpleNamespace(uuid=WORKSPACE_UUID),
        membership=SimpleNamespace(
            uuid=f'membership-{account_uuid}',
            account_uuid=account_uuid,
            role='owner',
            projection_revision=1,
        ),
        execution=SimpleNamespace(instance_uuid='instance-a', placement_generation=1),
    )


async def _resolve(account_uuid: str, _workspace_uuid: str | None) -> SimpleNamespace:
    # The collaboration service hides Accounts that are not members here.
    if account_uuid == FOREIGN_UUID:
        raise WorkspaceNotFoundError('Workspace not found')
    return _access(account_uuid)


@pytest.fixture
async def totp_admin_api():
    accounts = {'member-token': SimpleNamespace(uuid=MEMBER_UUID, user='member@example.com')}
    application = Mock()
    application._message_language_cache = None
    application.deployment = SimpleNamespace(multi_workspace_enabled=False)
    application.instance_config.data = {'system': {'allow_modify_login_info': True}}
    application.persistence_mgr = SimpleNamespace(tenant_uow=None)
    application.user_service.get_authenticated_account = AsyncMock(
        side_effect=lambda token: accounts[token]
    )
    application.workspace_collaboration_service.resolve_account_workspace = AsyncMock(
        side_effect=_resolve
    )
    application.workspace_collaboration_service.list_members = AsyncMock(
        return_value=[SimpleNamespace(membership=SimpleNamespace(account_uuid=MEMBER_UUID))]
    )
    application.totp_service.list_account_states = AsyncMock(
        return_value=[{'account_uuid': MEMBER_UUID, 'user': 'member', 'enabled': False}]
    )
    application.totp_service.revoke_for_account = AsyncMock(return_value=True)
    application.totp_service.get_account = AsyncMock(
        return_value=SimpleNamespace(uuid=FOREIGN_UUID, user='foreign@example.com')
    )
    application.totp_service.begin_enrollment = AsyncMock()
    application.totp_service.confirm_enrollment = AsyncMock()

    quart_app = quart.Quart(__name__)
    router = UserRouterGroup(application, quart_app)
    await router.initialize()
    return application, quart_app.test_client()


def _headers() -> dict[str, str]:
    return {'Authorization': 'Bearer member-token', 'X-Workspace-Id': WORKSPACE_UUID}


async def test_account_list_covers_only_the_callers_workspace(totp_admin_api):
    application, client = totp_admin_api

    response = await client.get('/api/v1/user/totp/accounts', headers=_headers())

    assert response.status_code == 200
    payload = await response.get_json()
    assert [item['account_uuid'] for item in payload['data']['accounts']] == [MEMBER_UUID]
    application.totp_service.list_account_states.assert_awaited_once_with(
        account_uuids=[MEMBER_UUID]
    )


async def test_foreign_account_cannot_be_revoked(totp_admin_api):
    application, client = totp_admin_api

    response = await client.delete(
        f'/api/v1/user/totp/accounts/{FOREIGN_UUID}',
        headers=_headers(),
    )

    assert response.status_code == 404
    assert (await response.get_json())['code'] == 'account_not_found'
    application.totp_service.revoke_for_account.assert_not_awaited()


async def test_foreign_account_cannot_be_re_bound(totp_admin_api):
    application, client = totp_admin_api

    enroll = await client.post(
        f'/api/v1/user/totp/accounts/{FOREIGN_UUID}/enroll',
        headers=_headers(),
    )
    confirm = await client.post(
        f'/api/v1/user/totp/accounts/{FOREIGN_UUID}/enroll/confirm',
        json={'code': '123456'},
        headers=_headers(),
    )

    assert enroll.status_code == 404
    assert confirm.status_code == 404
    application.totp_service.begin_enrollment.assert_not_awaited()
    application.totp_service.confirm_enrollment.assert_not_awaited()
