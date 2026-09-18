import sqlalchemy as sa

from .base import Base


class AssistantConversation(Base):
    """Private management-assistant history and confirmation state."""

    __tablename__ = 'assistant_conversations'

    uuid = sa.Column(sa.String(36), primary_key=True)
    workspace_uuid = sa.Column(sa.String(36), sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'), nullable=False)
    account_uuid = sa.Column(sa.String(36), sa.ForeignKey('users.uuid', ondelete='CASCADE'), nullable=False)
    revision = sa.Column(sa.Integer, nullable=False, default=0)
    status = sa.Column(sa.String(20), nullable=False, default='ready')
    messages = sa.Column(sa.JSON, nullable=False, default=list)
    error = sa.Column(sa.Text, nullable=True)
    model_name = sa.Column(sa.String(255), nullable=True)
    model_uuid = sa.Column(sa.String(36), nullable=True)
    updated_at = sa.Column(sa.DateTime, nullable=False, server_default=sa.func.now())
