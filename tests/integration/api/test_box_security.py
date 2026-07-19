"""Authorization tests for sensitive Box runtime observability."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import quart

from langbot.pkg.api.http.controller.groups.box import BoxRouterGroup
from langbot.pkg.cloud.entitlements import EntitlementUnavailableError


pytestmark = pytest.mark.integration
WORKSPACE_UUID = '11111111-1111-4111-8111-111111111111'


def _access(account_uuid: str):
    return SimpleNamespace(
        workspace=SimpleNamespace(uuid=WORKSPACE_UUID),
        membership=SimpleNamespace(
            uuid=f'member-{account_uuid}',
            role='viewer' if account_uuid == 'viewer-account' else 'owner',
            projection_revision=1,
        ),
        execution=SimpleNamespace(instance_uuid='instance-a', placement_generation=1),
    )


@pytest.fixture
async def box_security_api():
    accounts = {
        'viewer-token': SimpleNamespace(uuid='viewer-account', user='viewer@example.com'),
        'owner-token': SimpleNamespace(uuid='owner-account', user='owner@example.com'),
    }
    application = Mock()
    application.deployment = SimpleNamespace(multi_workspace_enabled=False)
    application.persistence_mgr = SimpleNamespace(tenant_uow=None)
    application.user_service.get_authenticated_account = AsyncMock(side_effect=lambda token: accounts[token])
    application.workspace_collaboration_service.resolve_account_workspace = AsyncMock(
        side_effect=lambda account_uuid, _workspace_uuid: _access(account_uuid)
    )
    application.box_service.get_status = AsyncMock(return_value={'enabled': True})
    application.box_service.get_sessions = AsyncMock(return_value=[{'session_id': 'private-session'}])
    application.box_service.get_recent_errors = Mock(return_value=[{'error': 'private error'}])
    application.box_service.managed_admission_required = False

    quart_app = quart.Quart(__name__)
    router = BoxRouterGroup(application, quart_app)
    await router.initialize()
    return application, quart_app.test_client()


def _headers(token: str) -> dict[str, str]:
    return {
        'Authorization': f'Bearer {token}',
        'X-Workspace-Id': WORKSPACE_UUID,
    }


@pytest.mark.asyncio
async def test_viewer_can_read_status_but_not_sessions_or_errors(box_security_api):
    application, client = box_security_api

    status = await client.get('/api/v1/box/status', headers=_headers('viewer-token'))
    sessions = await client.get('/api/v1/box/sessions', headers=_headers('viewer-token'))
    errors = await client.get('/api/v1/box/errors', headers=_headers('viewer-token'))

    assert status.status_code == 200
    assert sessions.status_code == 403
    assert errors.status_code == 403
    application.box_service.get_sessions.assert_not_awaited()
    application.box_service.get_recent_errors.assert_not_called()


@pytest.mark.asyncio
async def test_owner_can_audit_box_sessions_and_errors(box_security_api):
    application, client = box_security_api

    sessions = await client.get('/api/v1/box/sessions', headers=_headers('owner-token'))
    errors = await client.get('/api/v1/box/errors', headers=_headers('owner-token'))

    assert sessions.status_code == 200
    assert errors.status_code == 200
    application.box_service.get_sessions.assert_awaited_once()
    application.box_service.get_recent_errors.assert_called_once()


@pytest.mark.asyncio
async def test_box_status_returns_explicit_403_when_workspace_has_no_managed_sandbox(box_security_api):
    application, client = box_security_api
    application.box_service.get_status.side_effect = EntitlementUnavailableError(
        'Workspace entitlement does not grant managed_sandbox'
    )

    response = await client.get('/api/v1/box/status', headers=_headers('viewer-token'))

    assert response.status_code == 403
    payload = await response.get_json()
    assert payload['code'] == 'managed_sandbox_unavailable'
