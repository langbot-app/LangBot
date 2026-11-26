import sqlalchemy
import uuid

from .base import Base


class AgentAccessGrant(Base):
    """Account or role grant controlling access to a Workspace Agent."""

    __tablename__ = 'agent_access_grants'

    id = sqlalchemy.Column(sqlalchemy.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36), sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'), nullable=False
    )
    agent_uuid = sqlalchemy.Column(
        sqlalchemy.String(255), sqlalchemy.ForeignKey('agents.uuid', ondelete='CASCADE'), nullable=False
    )
    subject_type = sqlalchemy.Column(sqlalchemy.String(16), nullable=False)
    subject_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    can_use = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False)

    __table_args__ = (
        sqlalchemy.UniqueConstraint(
            'workspace_uuid', 'agent_uuid', 'subject_type', 'subject_id', name='uq_agent_access_grant_subject'
        ),
    )
