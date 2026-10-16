from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.cloud.entitlements import EntitlementFeatureUnavailableError, EntitlementUnavailableError
from langbot.pkg.cloud.plan_policy import require_workspace_platform, workspace_history_retention_days


def cloud_app():
    snapshots = {
        'restricted': SimpleNamespace(features={'platform.telegram': False}, limits={'chat_history.retention_days': 7}, entitlement_revision=2),
        'open': SimpleNamespace(features={}, limits={'chat_history.retention_days': 90}, entitlement_revision=3),
    }
    return SimpleNamespace(deployment=SimpleNamespace(mode='cloud'), entitlement_resolver=SimpleNamespace(resolve=AsyncMock(side_effect=lambda ws: snapshots[ws])))


@pytest.mark.asyncio
async def test_platform_policy_is_scoped_and_covers_aliases():
    ap = cloud_app()
    for adapter in ['telegram', 'telegram-omni', 'telegram-eba']:
        with pytest.raises(EntitlementFeatureUnavailableError):
            await require_workspace_platform(ap, 'restricted', adapter)
        await require_workspace_platform(ap, 'open', adapter)
    await require_workspace_platform(ap, 'restricted', 'discord')


@pytest.mark.asyncio
async def test_retention_uses_workspace_entitlement():
    ap = cloud_app()
    assert await workspace_history_retention_days(ap, 'restricted', 100) == 7
    assert await workspace_history_retention_days(ap, 'open', 100) == 90


@pytest.mark.asyncio
async def test_oss_and_unavailable_projection():
    ap = SimpleNamespace(deployment=SimpleNamespace(mode='local'))
    await require_workspace_platform(ap, 'any', 'telegram')
    assert await workspace_history_retention_days(ap, 'any', 60) == 60
    ap.deployment.mode = 'cloud'
    with pytest.raises(EntitlementUnavailableError):
        await require_workspace_platform(ap, 'any', 'telegram')
    with pytest.raises(EntitlementUnavailableError):
        await workspace_history_retention_days(ap, 'any')
