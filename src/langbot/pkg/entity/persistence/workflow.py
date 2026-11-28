import sqlalchemy as sa

from ...persistence.media import MediaReferenceText
from .base import Base


class Workflow(Base):
    __tablename__ = 'workflows'

    uuid = sa.Column(sa.String(255), primary_key=True)
    workspace_uuid = sa.Column(
        sa.String(36), sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'), index=True, nullable=False
    )
    name = sa.Column(sa.String(255), nullable=False)
    description = sa.Column(sa.Text)
    emoji = sa.Column(sa.String(255))
    graph = sa.Column(sa.JSON, nullable=False)
    trigger = sa.Column(sa.JSON, nullable=False, server_default='{"type":"message"}')
    is_enabled = sa.Column(sa.Boolean, nullable=False, server_default=sa.true())
    created_at = sa.Column(sa.DateTime, nullable=False, server_default=sa.func.now())
    updated_at = sa.Column(sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now())


class WorkflowExecution(Base):
    __tablename__ = 'workflow_executions'

    uuid = sa.Column(sa.String(255), primary_key=True)
    workspace_uuid = sa.Column(
        sa.String(36), sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'), index=True, nullable=False
    )
    workflow_uuid = sa.Column(sa.String(255), nullable=False, index=True)
    status = sa.Column(sa.String(255), nullable=False)
    trigger = sa.Column(sa.String(255), nullable=False)
    bot_uuid = sa.Column(sa.String(255))
    session_id = sa.Column(sa.String(255), nullable=False)
    input_text = sa.Column(MediaReferenceText(), nullable=False)
    handoff = sa.Column(sa.JSON)
    error = sa.Column(sa.Text)
    started_at = sa.Column(sa.DateTime, nullable=False)
    finished_at = sa.Column(sa.DateTime)


class WorkflowExecutionStep(Base):
    __tablename__ = 'workflow_execution_steps'

    workspace_uuid = sa.Column(
        sa.String(36), sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'), index=True, nullable=False
    )
    execution_uuid = sa.Column(sa.String(255), primary_key=True)
    seq = sa.Column(sa.Integer, primary_key=True)
    node_id = sa.Column(sa.String(255), nullable=False)
    node_type = sa.Column(sa.String(255), nullable=False)
    node_name = sa.Column(sa.String(255), nullable=False)
    status = sa.Column(sa.String(255), nullable=False)
    branch = sa.Column(sa.String(255))
    inputs = sa.Column(MediaReferenceText(), nullable=False)
    outputs = sa.Column(MediaReferenceText(), nullable=False)
    error = sa.Column(sa.Text)
    started_at = sa.Column(sa.DateTime, nullable=False)
    finished_at = sa.Column(sa.DateTime)


class WorkflowMemory(Base):
    __tablename__ = 'workflow_memory'

    workspace_uuid = sa.Column(
        sa.String(36), sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'), index=True, primary_key=True
    )
    workflow_uuid = sa.Column(sa.String(255), primary_key=True)
    session_id = sa.Column(sa.String(255), primary_key=True)
    key = sa.Column(sa.String(255), primary_key=True)
    value = sa.Column(MediaReferenceText(), nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now())
