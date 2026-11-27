"""Single authority for processor access decisions."""

import sqlalchemy

from ..entity.persistence import agent as persistence_agent
from ..entity.persistence import agent_access as persistence_agent_access
from ..entity.persistence import workspace as persistence_workspace
from ..api.http.context import RequestContext


def _grant_allows(grants, account_uuid: str, role: str) -> bool:
    """Resolve grants with account-over-role precedence and deny-overrides."""
    account_grants = [grant for grant in grants if grant.subject_type == 'account' and grant.subject_id == account_uuid]
    selected = account_grants or [
        grant for grant in grants if grant.subject_type == 'role' and grant.subject_id == role
    ]
    return bool(selected) and any(grant.can_use for grant in selected) and all(grant.can_use for grant in selected)


async def can_use_processor(ap, ctx: RequestContext, processor_uuid: str) -> bool:
    """Return whether the active Workspace member may use an Agent processor.

    Account-specific grants take precedence over role grants. A deny grant
    overrides an allow grant at the same precedence level. Processors default
    to all active members for backwards compatibility.
    """
    return bool(await list_usable_processors(ap, ctx, processor_uuid=processor_uuid))


async def list_usable_processors(ap, ctx: RequestContext, *, processor_uuid: str | None = None) -> list[dict]:
    """List Agent identities under the same live membership and grant policy as dispatch."""
    account_uuid = ctx.account_uuid
    if not account_uuid:
        return []

    membership_result = await ap.persistence_mgr.execute_async(
        sqlalchemy.select(persistence_workspace.WorkspaceMembership.role).where(
            persistence_workspace.WorkspaceMembership.workspace_uuid == ctx.workspace_uuid,
            persistence_workspace.WorkspaceMembership.account_uuid == account_uuid,
            persistence_workspace.WorkspaceMembership.status == 'active',
        )
    )
    membership = membership_result.first()
    if membership is None:
        return []

    agent = persistence_agent.Agent
    query = sqlalchemy.select(agent.uuid, agent.name, agent.access_mode).where(
        agent.workspace_uuid == ctx.workspace_uuid, agent.kind == 'agent',
    )
    if processor_uuid is not None:
        query = query.where(agent.uuid == processor_uuid)
    agents = (await ap.persistence_mgr.execute_async(query.order_by(agent.name, agent.uuid))).all()
    restricted = [row.uuid for row in agents if row.access_mode == 'restricted']
    grants = {}
    if restricted:
        g = persistence_agent_access.AgentAccessGrant
        grant_query = sqlalchemy.select(g.agent_uuid, g.subject_type, g.subject_id, g.can_use).where(
            g.workspace_uuid == ctx.workspace_uuid,
            g.agent_uuid.in_(restricted),
            sqlalchemy.or_(
                sqlalchemy.and_(g.subject_type == 'account', g.subject_id == account_uuid),
                sqlalchemy.and_(g.subject_type == 'role', g.subject_id == membership.role),
            ),
        )
        result = await ap.persistence_mgr.execute_async(grant_query)
        for row in result.all():
            grants.setdefault(row.agent_uuid, []).append(row)

    return [
        {'id': row.uuid, 'label': row.name} for row in agents
        if row.access_mode == 'all_members' or (
            row.access_mode == 'restricted' and _grant_allows(grants.get(row.uuid, []), account_uuid, membership.role)
        )
    ]
