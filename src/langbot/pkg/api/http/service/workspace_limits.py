"""Resolve resource limits at the Workspace service boundary."""

from ....cloud.entitlements import EntitlementSnapshot, EntitlementUnavailableError

LIMIT_KEYS = {
    'max_bots': 'bots.max',
    'max_pipelines': 'pipelines.max',
    'max_extensions': 'plugins.max',
    'max_knowledge_bases': 'knowledge_bases.max',
}

MEMBER_LIMIT_KEY = 'members.max'


def member_limit(snapshot: EntitlementSnapshot) -> int:
    """Return the member seat limit, or -1 when the plan does not cap members.

    The Cloud control plane treats an absent or non-positive ``members.max``
    as unlimited, so Core mirrors that contract instead of the ``-1`` sentinel
    used by the other resource limits.
    """

    value = snapshot.limits.get(MEMBER_LIMIT_KEY)
    return value if value is not None and value > 0 else -1


def entitlement_limitation(snapshot: EntitlementSnapshot) -> dict[str, int]:
    """Project one entitlement snapshot into the WebUI ``limitation`` shape."""

    limitation = {config_key: snapshot.limit(limit_key) for config_key, limit_key in LIMIT_KEYS.items()}
    limitation['max_members'] = member_limit(snapshot)
    return limitation


async def workspace_limits(ap, workspace_uuid: str, *, minimum_revision: int = 0) -> dict[str, int]:
    if getattr(getattr(ap, 'deployment', None), 'mode', None) != 'cloud':
        return dict(ap.instance_config.data.get('system', {}).get('limitation', {}))
    resolver = getattr(ap, 'entitlement_resolver', None)
    if resolver is None:
        raise EntitlementUnavailableError('Workspace entitlement resolver is unavailable')
    snapshot = await resolver.resolve(workspace_uuid, minimum_revision=minimum_revision)
    return entitlement_limitation(snapshot)
