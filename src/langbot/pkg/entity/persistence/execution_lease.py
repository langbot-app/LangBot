"""Host execution lease registry."""

from __future__ import annotations

import sqlalchemy

from .base import Base


class ExecutionLeaseScope(Base):
    """One Workspace in which one Host process may own live leased executions.

    This is a global (non-tenant) index that only names a Host owner and a
    Workspace. It lets lease maintenance touch the Workspaces with in-flight
    work instead of scanning every Workspace on the instance.
    """

    __tablename__ = 'execution_lease_scopes'

    owner_id = sqlalchemy.Column(sqlalchemy.String(36), primary_key=True)
    workspace_uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    expires_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, index=True)
    """Host liveness for this scope; renewed by the owner on every maintenance tick."""
    generation = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=0)
    """Bumped on every registration so removal never races a concurrent registration."""
