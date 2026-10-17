import asyncio
from types import SimpleNamespace

import pytest

from langbot.pkg.cloud.entitlements import EntitlementSnapshot, EntitlementUnavailableError
from langbot.pkg.api.http.service.workspace_limits import workspace_limits


def test_oss_retains_instance_limits():
    ap = SimpleNamespace(instance_config=SimpleNamespace(data={'system': {'limitation': {'max_bots': 7}}}))
    assert asyncio.run(workspace_limits(ap, 'one')) == {'max_bots': 7}


def test_cloud_uses_signed_workspace_limits():
    class Resolver:
        async def resolve(self, workspace_uuid, **kwargs):
            assert workspace_uuid == 'one'
            return EntitlementSnapshot(
                instance_uuid='i',
                workspace_uuid='one',
                entitlement_revision=1,
                status='active',
                not_before=0,
                expires_at=9999999999,
                limits={'bots.max': 2, 'pipelines.max': 3, 'plugins.max': 4, 'knowledge_bases.max': 5},
            )

    ap = SimpleNamespace(deployment=SimpleNamespace(mode='cloud'), entitlement_resolver=Resolver())
    assert asyncio.run(workspace_limits(ap, 'one')) == {
        'max_bots': 2,
        'max_pipelines': 3,
        'max_extensions': 4,
        'max_knowledge_bases': 5,
    }


def test_cloud_missing_resolver_fails_closed():
    ap = SimpleNamespace(deployment=SimpleNamespace(mode='cloud'))
    with pytest.raises(EntitlementUnavailableError):
        asyncio.run(workspace_limits(ap, 'one'))
