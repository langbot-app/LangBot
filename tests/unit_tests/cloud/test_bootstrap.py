from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest

from langbot.pkg.cloud.bootstrap import (
    CloudBootstrapError,
    CloudManifestRefreshService,
    CloudRuntimeUnavailableError,
    DeploymentAdmissionGuard,
    OpenSourceDeployment,
    VerifiedCloudDeployment,
    resolve_deployment,
)
from langbot.pkg.cloud.entitlements import EntitlementSnapshot


pytestmark = pytest.mark.asyncio


class _Entitlements:
    async def get_workspace_entitlement(self, workspace_uuid: str) -> EntitlementSnapshot:
        return EntitlementSnapshot(
            instance_uuid='instance-a',
            workspace_uuid=workspace_uuid,
            entitlement_revision=1,
            status='active',
            not_before=1,
            expires_at=4_000_000_000,
            features={'managed_sandbox': True},
            limits={'managed_sandbox_sessions': 1},
        )


class _Directory:
    async def fetch_snapshot(self, instance_uuid: str):
        del instance_uuid
        raise AssertionError('not used by bootstrap contract tests')

    async def fetch_events(self, instance_uuid: str, after_cursor: int, limit: int):
        del instance_uuid, after_cursor, limit
        raise AssertionError('not used by bootstrap contract tests')

    async def fetch_workspaces(self, instance_uuid: str, workspace_uuids: tuple[str, ...]):
        del instance_uuid, workspace_uuids
        raise AssertionError('not used by bootstrap contract tests')


class _Manifest:
    def __init__(self):
        self.candidate = None
        self.closed = False

    async def refresh_manifest(self):
        if self.candidate is None:
            raise AssertionError('no refreshed Manifest was configured')
        return self.candidate

    async def aclose(self) -> None:
        self.closed = True


class _Provider:
    def __init__(self):
        self.manifest_provider = _Manifest()

    async def fetch_model_catalog(self, instance_uuid: str):
        del instance_uuid
        raise AssertionError('not used by bootstrap contract tests')

    def bootstrap(self, *, instance_uuid: str, instance_config: dict):
        del instance_config
        return VerifiedCloudDeployment(
            instance_uuid=instance_uuid,
            manifest_jti='manifest-a',
            manifest_generation=3,
            expires_at=4_000_000_000,
            release='cloud-v2',
            capabilities=frozenset({'multi_workspace_v2'}),
            tenant_isolation_version=2,
            entitlement_provider=_Entitlements(),
            directory_provider=_Directory(),
            manifest_provider=self.manifest_provider,
            model_catalog_provider=self,
            verification_key_id='root-2026',
        )


class _EntryPoint:
    def __init__(self, value):
        self.value = value

    def load(self):
        return self.value


class _EntryPoints(list):
    def select(self, *, group: str):
        return self if group == 'langbot.cloud_bootstrap' else []


def _cloud_config() -> dict:
    return {
        'database': {'use': 'postgresql'},
        'vdb': {
            'use': 'pgvector',
            'pgvector': {
                'use_business_database': True,
                'allowed_dimensions': [384, 768, 1536, 3072],
            },
        },
        'mcp': {'stdio': {'enabled': False}},
        'plugin': {'worker': {'require_hard_limits': True}},
        'box': {
            'enabled': True,
            'backend': 'nsjail',
            'runtime': {'endpoint': 'ws://langbot-box:5410'},
            'admission': {
                'required': True,
                'logical_session_id': 'global',
                'required_backend': 'nsjail',
                'max_sessions': 1,
                'max_managed_processes': 0,
                'max_grant_ttl_sec': 300,
                'workspace_quota_mb': 32,
            },
            'local': {
                'host_root': '/var/lib/langbot/box',
                'default_workspace': '/var/lib/langbot/box/workspaces',
                'allowed_mount_roots': ['/var/lib/langbot/box'],
            },
        },
        # Proves mutable product metadata does not participate in selection.
        'system': {'edition': 'community'},
    }


async def test_no_closed_entry_point_selects_oss_singleton_even_if_edition_says_cloud():
    deployment = await resolve_deployment(
        instance_uuid='instance-a',
        instance_config={'system': {'edition': 'cloud'}},
        entry_points=lambda: _EntryPoints(),
    )

    assert isinstance(deployment, OpenSourceDeployment)
    assert deployment.multi_workspace_enabled is False


async def test_verified_closed_entry_point_activates_cloud_policy():
    deployment = await resolve_deployment(
        instance_uuid='instance-a',
        instance_config=_cloud_config(),
        entry_points=lambda: _EntryPoints([_EntryPoint(_Provider)]),
        now=1_000,
    )

    assert isinstance(deployment, VerifiedCloudDeployment)
    assert deployment.multi_workspace_enabled is True
    assert deployment.persistence_mode == 'cloud_runtime'


@pytest.mark.parametrize(
    ('field', 'value', 'message'),
    [
        ('database', {'use': 'sqlite'}, 'database.use=postgresql'),
        ('vdb', {'use': 'chroma'}, 'vdb.use=pgvector'),
        ('mcp', {'stdio': {'enabled': True}}, 'mcp.stdio.enabled=false'),
        ('plugin', {'worker': {'require_hard_limits': False}}, 'plugin.worker.require_hard_limits=true'),
    ],
)
async def test_cloud_runtime_config_is_fail_closed(field, value, message):
    config = _cloud_config()
    config[field] = value

    with pytest.raises(CloudBootstrapError, match=message):
        await resolve_deployment(
            instance_uuid='instance-a',
            instance_config=config,
            entry_points=lambda: _EntryPoints([_EntryPoint(_Provider())]),
            now=1_000,
        )


@pytest.mark.parametrize(
    ('directory_config', 'message'),
    [
        ({'max_active_workspaces': 0}, 'greater than or equal to 1'),
        ({'max_active_workspaces': True}, 'must be an integer'),
        (
            {
                'max_active_workspaces': 10,
                'max_snapshot_workspaces': 9,
            },
            'max_snapshot_workspaces',
        ),
        ({'max_response_bytes': 64 * 1024 * 1024 + 1}, 'less than or equal to'),
    ],
)
async def test_cloud_directory_capacity_contract_is_fail_closed(directory_config, message):
    config = _cloud_config()
    config['cloud'] = {'directory': directory_config}

    with pytest.raises(CloudBootstrapError, match=message):
        await resolve_deployment(
            instance_uuid='instance-a',
            instance_config=config,
            entry_points=lambda: _EntryPoints([_EntryPoint(_Provider())]),
            now=1_000,
        )


@pytest.mark.parametrize(
    ('pgvector_config', 'message'),
    [
        ({'use_business_database': False, 'allowed_dimensions': [1536]}, 'use_business_database=true'),
        ({'use_business_database': True, 'allowed_dimensions': []}, 'allowed_dimensions'),
        ({'use_business_database': True, 'allowed_dimensions': [True]}, 'allowed_dimensions'),
    ],
)
async def test_cloud_pgvector_contract_is_fail_closed(pgvector_config, message):
    config = _cloud_config()
    config['vdb']['pgvector'] = pgvector_config

    with pytest.raises(CloudBootstrapError, match=message):
        await resolve_deployment(
            instance_uuid='instance-a',
            instance_config=config,
            entry_points=lambda: _EntryPoints([_EntryPoint(_Provider())]),
            now=1_000,
        )


async def test_cloud_runtime_allows_explicitly_disabled_box():
    config = _cloud_config()
    config['box']['enabled'] = False

    deployment = await resolve_deployment(
        instance_uuid='instance-a',
        instance_config=config,
        entry_points=lambda: _EntryPoints([_EntryPoint(_Provider())]),
        now=1_000,
    )

    assert isinstance(deployment, VerifiedCloudDeployment)


@pytest.mark.parametrize(
    ('mutate', 'message'),
    [
        (lambda config: config['box'].update(backend='docker'), 'box.backend=nsjail'),
        (lambda config: config['box']['runtime'].update(endpoint=''), 'box.runtime.endpoint'),
        (
            lambda config: config['box']['admission'].update(max_sessions=2),
            'grant-enforced Box admission',
        ),
        (
            lambda config: config['box']['admission'].update(max_managed_processes=1),
            'zero managed processes',
        ),
        (
            lambda config: config['box']['admission'].update(max_grant_ttl_sec=301),
            'max_grant_ttl_sec',
        ),
        (
            lambda config: config['box']['admission'].update(workspace_quota_mb=0),
            'workspace_quota_mb must be a positive integer',
        ),
        (
            lambda config: config['box']['admission'].update(workspace_quota_mb=True),
            'workspace_quota_mb must be a positive integer',
        ),
        (
            lambda config: config['box']['local'].update(default_workspace='relative/workspaces'),
            'default_workspace must be an absolute',
        ),
        (
            lambda config: config['box']['local'].update(
                default_workspace='/other/workspaces',
            ),
            'under allowed_mount_roots',
        ),
    ],
)
async def test_cloud_box_contract_is_fail_closed(mutate, message):
    config = _cloud_config()
    mutate(config)

    with pytest.raises(CloudBootstrapError, match=message):
        await resolve_deployment(
            instance_uuid='instance-a',
            instance_config=config,
            entry_points=lambda: _EntryPoints([_EntryPoint(_Provider())]),
            now=1_000,
        )


async def test_invalid_provider_never_falls_back_to_oss():
    provider = SimpleNamespace(bootstrap=lambda **_: object())

    with pytest.raises(CloudBootstrapError, match='must return VerifiedCloudDeployment'):
        await resolve_deployment(
            instance_uuid='instance-a',
            instance_config=_cloud_config(),
            entry_points=lambda: _EntryPoints([_EntryPoint(provider)]),
            now=1_000,
        )


async def test_duplicate_closed_providers_fail_closed():
    with pytest.raises(CloudBootstrapError, match='Exactly one'):
        await resolve_deployment(
            instance_uuid='instance-a',
            instance_config=_cloud_config(),
            entry_points=lambda: _EntryPoints([_EntryPoint(_Provider()), _EntryPoint(_Provider())]),
            now=1_000,
        )


async def test_deployment_admission_expires_even_after_wall_clock_rollback():
    wall = [1_000.0]
    monotonic = [50.0]
    deployment = dataclasses.replace(
        _Provider().bootstrap(instance_uuid='instance-a', instance_config={}),
        expires_at=1_010,
    )
    guard = DeploymentAdmissionGuard(
        'instance-a',
        deployment,
        wall_time=lambda: wall[0],
        monotonic_time=lambda: monotonic[0],
    )

    assert guard.require_active() is deployment
    wall[0] = 900.0
    monotonic[0] = 60.0
    with pytest.raises(CloudRuntimeUnavailableError, match='expired'):
        guard.require_active()


async def test_deployment_admission_accepts_only_monotonic_non_conflicting_renewal():
    wall = [1_000.0]
    monotonic = [50.0]
    current = dataclasses.replace(
        _Provider().bootstrap(instance_uuid='instance-a', instance_config={}),
        expires_at=1_010,
    )
    guard = DeploymentAdmissionGuard(
        'instance-a',
        current,
        wall_time=lambda: wall[0],
        monotonic_time=lambda: monotonic[0],
    )
    renewed = dataclasses.replace(
        current,
        manifest_jti='manifest-b',
        manifest_generation=4,
        expires_at=2_000,
    )
    guard.replace(renewed)
    assert guard.require_active() is renewed

    rollback = dataclasses.replace(current, manifest_generation=2)
    with pytest.raises(CloudRuntimeUnavailableError, match='rolled back'):
        guard.replace(rollback)

    conflicting = dataclasses.replace(renewed, manifest_jti='different')
    with pytest.raises(CloudRuntimeUnavailableError, match='conflicting'):
        guard.replace(conflicting)


async def test_manifest_refresh_replaces_receipt_before_short_ttl_expires():
    wall = [1_000.0]
    provider = _Provider()
    current = dataclasses.replace(
        provider.bootstrap(instance_uuid='instance-a', instance_config={}),
        expires_at=1_300,
    )
    guard = DeploymentAdmissionGuard('instance-a', current, wall_time=lambda: wall[0])
    renewed = dataclasses.replace(
        current,
        manifest_jti='manifest-renewed',
        manifest_generation=current.manifest_generation + 1,
        expires_at=2_000,
    )
    provider.manifest_provider.candidate = renewed
    service = CloudManifestRefreshService(
        guard,
        provider.manifest_provider,
        SimpleNamespace(exception=lambda *_: None),
        wall_time=lambda: wall[0],
    )

    assert service.next_refresh_delay() == 120
    assert await service.refresh_once() is renewed
    assert guard.deployment is renewed
