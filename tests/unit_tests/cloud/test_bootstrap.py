from __future__ import annotations

from types import SimpleNamespace

import pytest

from langbot.pkg.cloud.bootstrap import (
    CloudBootstrapError,
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


class _Provider:
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
        'vdb': {'use': 'pgvector'},
        'mcp': {'stdio': {'enabled': False}},
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
