"""Account scoping for the passkey and password routes.

A passkey belongs to the Account, so these routes must answer for the Account the
caller authenticated as. They previously required a Workspace (which the WebUI
never sends for them) and then resolved the Account by looking the login name up
as an email address, so every Account whose login name is not its email answered
``404`` and the passkey feature was unreachable.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import quart

from langbot.pkg.api.http.controller.groups.user import UserRouterGroup

pytestmark = pytest.mark.integration

ACCOUNT_UUID = '1905ad7c-168f-49f4-893e-e43614e4c4bf'
LOGIN_NAME = 'dev'
ACCOUNT_EMAIL = 'dev@local.test'


@pytest.fixture
async def account_api():
    # The login name deliberately differs from the email: that is what made the
    # email lookup miss the authenticated Account.
    account = SimpleNamespace(
        uuid=ACCOUNT_UUID,
        user=LOGIN_NAME,
        normalized_email=ACCOUNT_EMAIL,
        password='',
        account_type='space',
    )
    application = Mock()
    application.deployment = SimpleNamespace(multi_workspace_enabled=False)
    application.instance_config.data = {'system': {'allow_modify_login_info': True}}
    application.persistence_mgr = SimpleNamespace(tenant_uow=None)
    application.user_service.get_authenticated_account = AsyncMock(return_value=account)
    application.user_service.get_user_by_email = AsyncMock(return_value=None)
    application.user_service.get_user_passkeys = AsyncMock(return_value=[])
    application.user_service.generate_passkey_registration_options = AsyncMock(
        return_value=({'challenge': 'probe'}, 'challenge-token')
    )
    application.user_service.verify_and_save_passkey_registration = AsyncMock(
        return_value=SimpleNamespace(uuid='credential-uuid', name='probe', created_at=None)
    )
    application.user_service.rename_user_passkey = AsyncMock(
        return_value=SimpleNamespace(uuid='credential-uuid', name='renamed')
    )
    application.user_service.delete_user_passkey = AsyncMock(return_value=True)
    application.user_service.set_password = AsyncMock()
    application.user_service.change_password = AsyncMock()

    quart_app = quart.Quart(__name__)
    router = UserRouterGroup(application, quart_app)
    await router.initialize()
    return application, quart_app.test_client()


def _headers() -> dict[str, str]:
    # The WebUI sends an account session and no Workspace for these routes.
    return {'Authorization': 'Bearer account-token'}


async def test_passkey_list_answers_without_a_workspace(account_api):
    application, client = account_api

    response = await client.get('/api/v1/user/passkeys', headers=_headers())

    assert response.status_code == 200, await response.get_data(as_text=True)
    application.user_service.get_user_passkeys.assert_awaited_once_with(ACCOUNT_UUID)
    application.user_service.get_user_by_email.assert_not_awaited()


async def test_passkey_registration_options_bind_the_authenticated_account(account_api):
    application, client = account_api

    response = await client.post(
        '/api/v1/user/passkey/register/options',
        json={'origin': 'http://localhost:3000'},
        headers=_headers(),
    )

    assert response.status_code == 200, await response.get_data(as_text=True)
    assert (await response.get_json())['data']['challenge_token'] == 'challenge-token'
    options_call = application.user_service.generate_passkey_registration_options.await_args
    assert options_call.kwargs['account_uuid'] == ACCOUNT_UUID
    assert options_call.kwargs['rp_id'] == 'localhost'
    application.user_service.get_user_by_email.assert_not_awaited()


async def test_passkey_verify_and_revoke_address_the_authenticated_account(account_api):
    application, client = account_api

    verified = await client.post(
        '/api/v1/user/passkey/register/verify',
        json={'challenge_token': 'challenge-token', 'credential': {'id': 'cred'}},
        headers=_headers(),
    )
    renamed = await client.patch(
        '/api/v1/user/passkey/credential-uuid',
        json={'name': 'renamed'},
        headers=_headers(),
    )
    deleted = await client.delete('/api/v1/user/passkey/credential-uuid', headers=_headers())

    assert verified.status_code == 200, await verified.get_data(as_text=True)
    assert renamed.status_code == 200, await renamed.get_data(as_text=True)
    assert deleted.status_code == 200, await deleted.get_data(as_text=True)
    assert application.user_service.rename_user_passkey.await_args.kwargs['account_uuid'] == ACCOUNT_UUID
    assert application.user_service.delete_user_passkey.await_args.kwargs['account_uuid'] == ACCOUNT_UUID
    application.user_service.get_user_by_email.assert_not_awaited()


async def test_password_routes_target_the_authenticated_account(account_api):
    application, client = account_api

    set_password = await client.post(
        '/api/v1/user/set-password',
        json={'new_password': 'new-secret'},
        headers=_headers(),
    )
    change_password = await client.post(
        '/api/v1/user/change-password',
        json={'current_password': 'old-secret', 'new_password': 'new-secret'},
        headers=_headers(),
    )

    assert set_password.status_code == 200, await set_password.get_data(as_text=True)
    assert change_password.status_code == 200, await change_password.get_data(as_text=True)
    # The service resolves the row by email, so the route hands it the email of the
    # account the token identified -- never the login name it was given.
    assert application.user_service.set_password.await_args.args[0] == ACCOUNT_EMAIL
    assert application.user_service.change_password.await_args.args[0] == ACCOUNT_EMAIL
    application.user_service.get_user_by_email.assert_not_awaited()
