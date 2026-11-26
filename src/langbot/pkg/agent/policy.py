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
    account_uuid = ctx.account_uuid
    if not account_uuid:
        return False

    membership_result = await ap.persistence_mgr.execute_async(
        sqlalchemy.select(persistence_workspace.WorkspaceMembership.role).where(
            persistence_workspace.WorkspaceMembership.workspace_uuid == ctx.workspace_uuid,
            persistence_workspace.WorkspaceMembership.account_uuid == account_uuid,
            persistence_workspace.WorkspaceMembership.status == 'active',
        )
    )
    membership = membership_result.first()
    if membership is None:
        return False

    agent_result = await ap.persistence_mgr.execute_async(
        sqlalchemy.select(persistence_agent.Agent.access_mode).where(
            persistence_agent.Agent.workspace_uuid == ctx.workspace_uuid,
            persistence_agent.Agent.uuid == processor_uuid,
        )
    )
    agent = agent_result.first()
    if agent is None:
        return False
    if agent.access_mode == 'all_members':
        return True
    if agent.access_mode != 'restricted':
        return False

    grant_result = await ap.persistence_mgr.execute_async(
        sqlalchemy.select(
            persistence_agent_access.AgentAccessGrant.subject_type,
            persistence_agent_access.AgentAccessGrant.can_use,
        ).where(
            persistence_agent_access.AgentAccessGrant.workspace_uuid == ctx.workspace_uuid,
            persistence_agent_access.AgentAccessGrant.agent_uuid == processor_uuid,
            sqlalchemy.or_(
                sqlalchemy.and_(
                    persistence_agent_access.AgentAccessGrant.subject_type == 'account',
                    persistence_agent_access.AgentAccessGrant.subject_id == account_uuid,
                ),
                sqlalchemy.and_(
                    persistence_agent_access.AgentAccessGrant.subject_type == 'role',
                    persistence_agent_access.AgentAccessGrant.subject_id == membership.role,
                ),
            ),
        )
    )
    grants = list(grant_result.all())
    return _grant_allows(grants, account_uuid, membership.role)
