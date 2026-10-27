"""Resolve resource limits at the Workspace service boundary."""

from ....cloud.entitlements import EntitlementUnavailableError

LIMIT_KEYS = {
    'max_bots': 'bots.max',
    'max_pipelines': 'pipelines.max',
    'max_extensions': 'plugins.max',
    'max_knowledge_bases': 'knowledge_bases.max',
}


async def workspace_limits(ap, workspace_uuid: str, *, minimum_revision: int = 0) -> dict[str, int]:
    if getattr(getattr(ap, 'deployment', None), 'mode', None) != 'cloud':
        return dict(ap.instance_config.data.get('system', {}).get('limitation', {}))
    resolver = getattr(ap, 'entitlement_resolver', None)
    if resolver is None:
        raise EntitlementUnavailableError('Workspace entitlement resolver is unavailable')
    snapshot = await resolver.resolve(workspace_uuid, minimum_revision=minimum_revision)
    return {config_key: snapshot.limit(limit_key) for config_key, limit_key in LIMIT_KEYS.items()}
