from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from langbot.pkg.cloud.entitlements import EntitlementResolver, EntitlementSnapshot, EntitlementUnavailableError


def _snapshot(**overrides) -> EntitlementSnapshot:
    values = {
        'instance_uuid': 'instance-a',
        'workspace_uuid': 'workspace-a',
        'entitlement_revision': 7,
        'status': 'active',
        'not_before': 100,
        'expires_at': 200,
        'features': {'managed_sandbox': True, 'mcp_stdio': False},
        'limits': {'managed_sandbox_sessions': 1},
    }
    values.update(overrides)
    return EntitlementSnapshot(**values)


def test_active_snapshot_exposes_only_generic_features_and_limits():
    snapshot = _snapshot().require_active(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        now=150,
    )

    snapshot.require_feature('managed_sandbox')
    assert snapshot.limit('managed_sandbox_sessions') == 1
    assert 'plan' not in snapshot.model_fields


@pytest.mark.parametrize(
    'snapshot,now',
    [
        (_snapshot(status='suspended'), 150),
        (_snapshot(), 99),
        (_snapshot(), 200),
    ],
)
def test_inactive_or_expired_snapshot_fails_closed(snapshot, now):
    with pytest.raises(EntitlementUnavailableError):
        snapshot.require_active(
            instance_uuid='instance-a',
            workspace_uuid='workspace-a',
            now=now,
        )


def test_scope_mismatch_fails_closed():
    with pytest.raises(EntitlementUnavailableError, match='scope'):
        _snapshot().require_active(
            instance_uuid='instance-a',
            workspace_uuid='workspace-b',
            now=150,
        )


@pytest.mark.asyncio
async def test_resolver_rejects_revision_rollback():
    provider = AsyncMock()
    provider.get_workspace_entitlement = AsyncMock(side_effect=[_snapshot(), _snapshot(entitlement_revision=6)])
    resolver = EntitlementResolver('instance-a', provider)

    await resolver.resolve('workspace-a', now=150)
    with pytest.raises(EntitlementUnavailableError, match='rolled back'):
        await resolver.resolve('workspace-a', now=150)


@pytest.mark.asyncio
async def test_resolver_rejects_same_revision_with_different_contents():
    provider = AsyncMock()
    provider.get_workspace_entitlement = AsyncMock(
        side_effect=[
            _snapshot(),
            _snapshot(features={'managed_sandbox': False}),
        ]
    )
    resolver = EntitlementResolver('instance-a', provider)

    await resolver.resolve('workspace-a', now=150)
    with pytest.raises(EntitlementUnavailableError, match='conflicting contents'):
        await resolver.resolve('workspace-a', now=150)
