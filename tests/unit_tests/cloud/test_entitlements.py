from __future__ import annotations

import asyncio

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


@pytest.mark.asyncio
async def test_resolver_checks_deployment_admission_before_and_after_provider_call():
    checks = 0

    def require_admission() -> None:
        nonlocal checks
        checks += 1
        if checks == 2:
            raise RuntimeError('manifest expired during provider call')

    provider = AsyncMock()
    provider.get_workspace_entitlement = AsyncMock(return_value=_snapshot())
    resolver = EntitlementResolver(
        'instance-a',
        provider,
        deployment_admission=require_admission,
    )

    with pytest.raises(RuntimeError, match='expired during provider call'):
        await resolver.resolve('workspace-a', now=150)
    assert checks == 2


@pytest.mark.asyncio
async def test_directory_activity_reconciliation_drops_historical_snapshots():
    provider = AsyncMock()
    provider.get_workspace_entitlement = AsyncMock(return_value=_snapshot())
    resolver = EntitlementResolver('instance-a', provider)
    await resolver.reconcile_active_workspaces({'workspace-a', 'workspace-b'})
    await resolver.resolve('workspace-a', now=150)

    await resolver.reconcile_active_workspaces({'workspace-b'})

    assert resolver.snapshot_counts() == {
        'active_workspaces': 1,
        'cached_snapshots': 0,
    }
    with pytest.raises(EntitlementUnavailableError, match='directory projection'):
        await resolver.resolve('workspace-a', now=150)
    provider.get_workspace_entitlement.assert_awaited_once()


@pytest.mark.asyncio
async def test_directory_fence_wins_race_with_inflight_entitlement_fetch():
    provider_started = asyncio.Event()
    release_provider = asyncio.Event()

    async def fetch(_workspace_uuid: str) -> EntitlementSnapshot:
        provider_started.set()
        await release_provider.wait()
        return _snapshot()

    provider = AsyncMock()
    provider.get_workspace_entitlement = AsyncMock(side_effect=fetch)
    resolver = EntitlementResolver('instance-a', provider)
    await resolver.reconcile_active_workspaces({'workspace-a'})
    resolve_task = asyncio.create_task(resolver.resolve('workspace-a', now=150))
    await provider_started.wait()

    await resolver.update_workspace_activity(
        active_workspace_uuids=set(),
        inactive_workspace_uuids={'workspace-a'},
    )
    release_provider.set()

    with pytest.raises(EntitlementUnavailableError, match='directory projection'):
        await resolve_task
    assert resolver.snapshot_counts() == {
        'active_workspaces': 0,
        'cached_snapshots': 0,
    }
