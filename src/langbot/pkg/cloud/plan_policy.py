"""Workspace plan policies evaluated from trusted entitlement projections."""

from .entitlements import EntitlementFeatureUnavailableError, EntitlementUnavailableError
from ..platform.adapter_names import canonical_adapter_name


def platform_feature_names(adapter: str) -> set[str]:
    canonical = canonical_adapter_name(adapter)
    names = {adapter, canonical}
    if adapter.lower() == 'line':
        names.update({'line', 'LINE'})
    if canonical.endswith('-omni'):
        names.add(canonical[:-5])
        names.add(canonical[:-5] + '-eba')
    return {'platform.' + name for name in names}


async def workspace_entitlement(ap, workspace_uuid: str):
    if getattr(getattr(ap, 'deployment', None), 'mode', None) != 'cloud':
        return None
    resolver = getattr(ap, 'entitlement_resolver', None)
    if resolver is None:
        raise EntitlementUnavailableError('Workspace entitlement resolver is unavailable')
    return await resolver.resolve(workspace_uuid)


async def require_workspace_platform(ap, workspace_uuid: str, adapter: str) -> None:
    snapshot = await workspace_entitlement(ap, workspace_uuid)
    if snapshot is None:
        return
    for feature in platform_feature_names(adapter):
        if snapshot.features.get(feature) is False:
            raise EntitlementFeatureUnavailableError(feature, entitlement_revision=snapshot.entitlement_revision)


async def workspace_history_retention_days(ap, workspace_uuid: str, fallback: int = 30) -> int:
    snapshot = await workspace_entitlement(ap, workspace_uuid)
    if snapshot is None:
        return fallback
    # Old signed snapshots inherit the existing 30-day policy. Never interpret
    # missing entitlement data as an unlimited retention policy.
    return max(1, snapshot.limits.get('chat_history.retention_days', 30))
