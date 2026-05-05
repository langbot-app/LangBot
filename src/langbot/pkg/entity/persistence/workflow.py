"""Workflow persistence entities"""
import sqlalchemy

from .base import Base


class Workflow(Base):
    """Workflow definition"""

    __tablename__ = 'workflows'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    description = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    emoji = sqlalchemy.Column(sqlalchemy.String(10), nullable=True, default='🔄')
    version = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=1)
    is_enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True)
    
    # Workflow definition stored as JSON
    # Contains: nodes, edges, variables, settings
    definition = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default={})
    
    # Global config (inherited from Pipeline capabilities)
    # Contains: safety, output configs
    global_config = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default={})
    
    # Extensions preferences (same as Pipeline)
    extensions_preferences = sqlalchemy.Column(
        sqlalchemy.JSON,
        nullable=False,
        default={'enable_all_plugins': True, 'enable_all_mcp_servers': True, 'plugins': [], 'mcp_servers': []},
    )
    
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )


class WorkflowVersion(Base):
    """Workflow version history"""

    __tablename__ = 'workflow_versions'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    workflow_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    version = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)
    definition = sqlalchemy.Column(sqlalchemy.JSON, nullable=False)
    global_config = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default={})
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    created_by = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)

    __table_args__ = (
        sqlalchemy.UniqueConstraint('workflow_uuid', 'version', name='uq_workflow_version'),
    )


class WorkflowTrigger(Base):
    """Workflow trigger configuration"""

    __tablename__ = 'workflow_triggers'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    workflow_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    type = sqlalchemy.Column(sqlalchemy.String(50), nullable=False)  # message, cron, event, webhook
    config = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default={})
    is_enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True)
    priority = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=0)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )


class WorkflowExecution(Base):
    """Workflow execution record"""

    __tablename__ = 'workflow_executions'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    workflow_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    workflow_version = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)
    status = sqlalchemy.Column(sqlalchemy.String(20), nullable=False)  # pending, running, completed, failed, cancelled
    trigger_type = sqlalchemy.Column(sqlalchemy.String(50), nullable=True)
    trigger_data = sqlalchemy.Column(sqlalchemy.JSON, nullable=True)
    variables = sqlalchemy.Column(sqlalchemy.JSON, nullable=True)
    start_time = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    end_time = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    error = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())


class WorkflowNodeExecution(Base):
    """Workflow node execution record"""

    __tablename__ = 'workflow_node_executions'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
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


class ScheduledJob(Base):
    """Scheduled job for cron triggers"""

    __tablename__ = 'workflow_scheduled_jobs'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    trigger_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    cron_expression = sqlalchemy.Column(sqlalchemy.String(100), nullable=True)
    next_run_time = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    last_run_time = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    is_enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True)
