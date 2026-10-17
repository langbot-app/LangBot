from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import quart

from langbot.pkg.api.http.context import (
    ExecutionContext,
    PrincipalContext,
    PrincipalType,
    RequestContext,
    WorkspaceContext,
)
from langbot.pkg.api.http.controller.group import RouterGroup
from langbot.pkg.cloud.entitlements import EntitlementSnapshot, EntitlementUnavailableError
from langbot.pkg.cloud.entitlements import EntitlementResolver


class _Group(RouterGroup):
    async def initialize(self) -> None:
        return None


def _router(deployment) -> _Group:
    provider = getattr(deployment, 'entitlement_provider', None)
    resolver = EntitlementResolver('instance-a', provider) if provider is not None else None
    ap = SimpleNamespace(deployment=deployment, entitlement_resolver=resolver)
    return _Group(ap, quart.Quart(__name__))


@pytest.mark.asyncio
async def test_cloud_request_resolves_verified_entitlement_revision():
    snapshot = EntitlementSnapshot(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        entitlement_revision=9,
        status='active',
        not_before=1,
        expires_at=4_000_000_000,
        features={},
        limits={},
    )
    provider = SimpleNamespace(get_workspace_entitlement=AsyncMock(return_value=snapshot))
    router = _router(SimpleNamespace(multi_workspace_enabled=True, entitlement_provider=provider))

    revision = await router._resolve_entitlement_revision('instance-a', 'workspace-a')

    assert revision == 9
    provider.get_workspace_entitlement.assert_awaited_once_with('workspace-a')


@pytest.mark.asyncio
async def test_cloud_request_fails_closed_without_entitlement_provider():
    router = _router(SimpleNamespace(multi_workspace_enabled=True, entitlement_provider=None))

    with pytest.raises(EntitlementUnavailableError):
        await router._resolve_entitlement_revision('instance-a', 'workspace-a')


def test_execution_context_preserves_entitlement_revision():
    request = RequestContext(
        instance_uuid='instance-a',
        placement_generation=1,
        request_id='request-a',
        auth_type='user-token',
        principal=PrincipalContext(PrincipalType.ACCOUNT, account_uuid='account-a'),
        workspace=WorkspaceContext(
            workspace_uuid='workspace-a',
            membership_uuid='membership-a',
            role='owner',
            permissions=frozenset(),
        ),
        entitlement_revision=11,
    )

    assert ExecutionContext.from_request(request).entitlement_revision == 11


@pytest.mark.asyncio
async def test_handler_entitlement_denial_is_403_not_internal_error():
    from langbot.pkg.api.http.controller.group import AuthType
    from langbot.pkg.cloud.entitlements import EntitlementFeatureUnavailableError

    router = _router(SimpleNamespace(mode='cloud'))
    router.path = '/policy'
    router.name = 'policy'

    @router.route('', methods=['GET'], auth_type=AuthType.NONE)
    async def denied():
        raise EntitlementFeatureUnavailableError('platform.telegram', entitlement_revision=2)

    response = await router.quart_app.test_client().get('/policy')
    assert response.status_code == 403
    assert (await response.get_json())['code'] == 'entitlement_unavailable'
