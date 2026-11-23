from __future__ import annotations

import datetime as dt
import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot_plugin.box.models import SandboxAdmissionPolicy

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.box.admission import (
    BoxAdmissionError,
    SandboxAdmissionController,
    require_cloud_admission_policy,
)
from langbot.pkg.box.service import BoxService
from langbot.pkg.cloud.entitlements import (
    EntitlementResolver,
    EntitlementSnapshot,
    EntitlementUnavailableError,
)


_UTC = dt.timezone.utc
_CONTEXT = ExecutionContext(
    instance_uuid='instance-a',
    workspace_uuid='workspace-a',
    placement_generation=3,
    entitlement_revision=7,
)


def _snapshot(
    *,
    revision: int = 7,
    managed: bool = True,
    sessions: int = 1,
    expires_at: int = 2_000,
) -> EntitlementSnapshot:
    return EntitlementSnapshot(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        entitlement_revision=revision,
        status='active',
        not_before=1,
        expires_at=expires_at,
        features={'managed_sandbox': managed},
        limits={'managed_sandbox_sessions': sessions},
    )


def _controller(snapshot: EntitlementSnapshot, *, now: float = 1_000.25):
    provider = SimpleNamespace(get_workspace_entitlement=AsyncMock(return_value=snapshot))
    resolver = EntitlementResolver('instance-a', provider)
    client = SimpleNamespace(
        upsert_sandbox_admission_grant=AsyncMock(
            side_effect=lambda grant: {
                'installed': True,
                'workspace_uuid': grant.workspace_uuid,
                'execution_generation': grant.execution_generation,
                'entitlement_revision': grant.entitlement_revision,
                'max_sessions': grant.max_sessions,
                'max_managed_processes': grant.max_managed_processes,
            }
        ),
        revoke_sandbox_admission_grant=AsyncMock(
            side_effect=lambda revocation: {
                'revoked': True,
                'workspace_uuid': revocation.workspace_uuid,
                'entitlement_revision': revocation.entitlement_revision,
            }
        ),
    )
    app = SimpleNamespace(entitlement_resolver=resolver, logger=Mock())
    controller = SandboxAdmissionController(
        app,
        client,
        policy=SandboxAdmissionPolicy(required=True, max_grant_ttl_sec=300),
        wall_time=lambda: now,
    )
    return controller, client, provider


def test_cloud_admission_policy_requires_positive_workspace_quota():
    with pytest.raises(BoxAdmissionError, match='workspace quota must be a positive integer'):
        require_cloud_admission_policy(
            {
                'required': True,
                'workspace_quota_mb': 0,
            }
        )

    policy = require_cloud_admission_policy(
        {
            'required': True,
            'workspace_quota_mb': 32,
        }
    )
    assert policy.workspace_quota_mb == 32


@pytest.mark.asyncio
async def test_active_generic_entitlement_installs_short_lived_numeric_grant():
    controller, client, provider = _controller(_snapshot())

    grant = await controller.require(_CONTEXT)

    assert grant.instance_uuid == _CONTEXT.instance_uuid
    assert grant.workspace_uuid == _CONTEXT.workspace_uuid
    assert grant.execution_generation == _CONTEXT.placement_generation
    assert grant.entitlement_revision == 7
    assert grant.max_sessions == 1
    assert grant.max_managed_processes == 0
    assert grant.expires_at == dt.datetime.fromtimestamp(1_300, tz=_UTC)
    assert (grant.expires_at - dt.datetime.fromtimestamp(1_000.25, tz=_UTC)).total_seconds() < 300
    provider.get_workspace_entitlement.assert_awaited_once_with('workspace-a')
    client.upsert_sandbox_admission_grant.assert_awaited_once_with(grant)
    client.revoke_sandbox_admission_grant.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'snapshot',
    [
        _snapshot(managed=False),
        _snapshot(sessions=0),
        _snapshot(sessions=2),
    ],
)
async def test_non_eligible_entitlement_revokes_and_fails_closed(snapshot):
    controller, client, _provider = _controller(snapshot)

    with pytest.raises(EntitlementUnavailableError):
        await controller.require(_CONTEXT)

    client.upsert_sandbox_admission_grant.assert_not_awaited()
    revocation = client.revoke_sandbox_admission_grant.await_args.args[0]
    assert revocation.entitlement_revision == snapshot.entitlement_revision


@pytest.mark.asyncio
async def test_transient_entitlement_failure_does_not_tombstone_valid_revision():
    controller, client, provider = _controller(_snapshot())
    await controller.require(_CONTEXT)
    provider.get_workspace_entitlement.side_effect = RuntimeError('control plane unavailable')

    with pytest.raises(RuntimeError, match='control plane unavailable'):
        await controller.require(_CONTEXT)

    client.revoke_sandbox_admission_grant.assert_not_awaited()

    provider.get_workspace_entitlement.side_effect = None
    provider.get_workspace_entitlement.return_value = _snapshot()
    recovered = await controller.require(_CONTEXT)
    assert recovered.entitlement_revision == 7


@pytest.mark.asyncio
async def test_runtime_receipt_mismatch_is_revoked_and_never_admitted():
    controller, client, _provider = _controller(_snapshot())
    client.upsert_sandbox_admission_grant.return_value = {'installed': True, 'workspace_uuid': 'other'}
    client.upsert_sandbox_admission_grant.side_effect = None

    with pytest.raises(Exception, match='invalid sandbox admission receipt'):
        await controller.require(_CONTEXT)

    client.revoke_sandbox_admission_grant.assert_not_awaited()


@pytest.mark.asyncio
async def test_authoritative_cancelled_revision_is_revoked():
    cancelled = _snapshot(revision=8).model_copy(update={'status': 'cancelled'})
    controller, client, _provider = _controller(cancelled)

    with pytest.raises(EntitlementUnavailableError, match='not active'):
        await controller.require(_CONTEXT)

    revocation = client.revoke_sandbox_admission_grant.await_args.args[0]
    assert revocation.entitlement_revision == 8


@pytest.mark.asyncio
async def test_cloud_box_readiness_failure_aborts_service_initialization(tmp_path):
    workspace_root = tmp_path / 'box' / 'workspaces'
    workspace_root.mkdir(parents=True)
    box_config = {
        'enabled': True,
        'backend': 'nsjail',
        'runtime': {'endpoint': 'ws://box:5410'},
        'local': {
            'host_root': str(tmp_path / 'box'),
            'default_workspace': str(workspace_root),
            'allowed_mount_roots': [str(tmp_path / 'box')],
        },
        'admission': {
            'required': True,
            'logical_session_id': 'global',
            'required_backend': 'nsjail',
            'max_sessions': 1,
            'max_managed_processes': 0,
            'max_grant_ttl_sec': 300,
            'workspace_quota_mb': 32,
        },
    }
    client = SimpleNamespace(
        initialize=AsyncMock(),
        verify_shared_workspace=AsyncMock(
            side_effect=lambda marker_name: {
                'marker_name': marker_name,
                'size': (workspace_root / marker_name).stat().st_size,
                'sha256': hashlib.sha256((workspace_root / marker_name).read_bytes()).hexdigest(),
            }
        ),
        get_backend_info=AsyncMock(return_value={'name': 'docker', 'available': True}),
    )
    app = SimpleNamespace(
        logger=Mock(),
        deployment=SimpleNamespace(multi_workspace_enabled=True),
        entitlement_resolver=Mock(),
        workspace_service=SimpleNamespace(instance_uuid='instance-a'),
        instance_config=SimpleNamespace(data={'box': box_config}),
    )
    service = BoxService(app, client=client)

    with pytest.raises(Exception, match='nsjail isolation readiness failed'):
        await service.initialize()

    assert service.available is False
