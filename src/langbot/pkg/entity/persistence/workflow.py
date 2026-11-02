"""Workflow persistence entities"""

import sqlalchemy

from .base import Base


def _workspace_column() -> sqlalchemy.Column:
    return sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )


class Workflow(Base):
    """Workflow definition, usable as an event route processor."""

    __tablename__ = 'workflows'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    workspace_uuid = _workspace_column()
    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    description = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    emoji = sqlalchemy.Column(sqlalchemy.String(10), nullable=True, default='🔄')
    version = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=1)
    is_enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True)

    # Contains: nodes, edges, variables, settings
    definition = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default={})

    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )


class WorkflowVersion(Base):
    """Workflow definition history"""

    __tablename__ = 'workflow_versions'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    workspace_uuid = _workspace_column()
    workflow_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    version = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)
    definition = sqlalchemy.Column(sqlalchemy.JSON, nullable=False)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())

    __table_args__ = (sqlalchemy.UniqueConstraint('workflow_uuid', 'version', name='uq_workflow_version'),)


class WorkflowExecution(Base):
    """Workflow execution record"""

    __tablename__ = 'workflow_executions'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    workspace_uuid = _workspace_column()
    workflow_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    workflow_version = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)
    status = sqlalchemy.Column(sqlalchemy.String(20), nullable=False)  # running, completed, failed, cancelled
    trigger_type = sqlalchemy.Column(sqlalchemy.String(50), nullable=True)  # event, manual, workflow
    trigger_data = sqlalchemy.Column(sqlalchemy.JSON, nullable=True)
    bot_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    variables = sqlalchemy.Column(sqlalchemy.JSON, nullable=True)
    start_time = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    end_time = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    error = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())


class WorkflowNodeExecution(Base):
    """Workflow node execution record"""

    __tablename__ = 'workflow_node_executions'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    workspace_uuid = _workspace_column()
    execution_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    node_id = sqlalchemy.Column(sqlalchemy.String(100), nullable=False)
    node_type = sqlalchemy.Column(sqlalchemy.String(50), nullable=False)
    status = sqlalchemy.Column(sqlalchemy.String(20), nullable=False)  # pending, running, completed, failed, skipped
    inputs = sqlalchemy.Column(sqlalchemy.JSON, nullable=True)
    outputs = sqlalchemy.Column(sqlalchemy.JSON, nullable=True)
    start_time = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    end_time = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    error = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    retry_count = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=0)
