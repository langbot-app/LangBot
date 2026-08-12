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
