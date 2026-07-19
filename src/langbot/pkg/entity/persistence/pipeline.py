import sqlalchemy

from .base import Base


class LegacyPipeline(Base):
    """Legacy pipeline"""

    __tablename__ = 'legacy_pipelines'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        nullable=False,
    )
    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    description = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    emoji = sqlalchemy.Column(sqlalchemy.String(10), nullable=True, default='⚙️')
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )
    for_version = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    is_default = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=False)
    stages = sqlalchemy.Column(sqlalchemy.JSON, nullable=False)
    config = sqlalchemy.Column(sqlalchemy.JSON, nullable=False)
    extensions_preferences = sqlalchemy.Column(
        sqlalchemy.JSON,
        nullable=False,
        default={
            'enable_all_plugins': True,
            'enable_all_mcp_servers': True,
            'plugins': [],
            'mcp_servers': [],
            'mcp_resources': [],
            'mcp_resource_agent_read_enabled': True,
        },
    )

    __table_args__ = (
        sqlalchemy.UniqueConstraint(
            'workspace_uuid',
            'uuid',
            name='uq_legacy_pipelines_workspace_uuid',
        ),
        sqlalchemy.Index('ix_legacy_pipelines_workspace_name', 'workspace_uuid', 'name'),
        sqlalchemy.Index('ix_legacy_pipelines_workspace_default', 'workspace_uuid', 'is_default'),
    )


class PipelineRunRecord(Base):
    """Pipeline run record"""

    __tablename__ = 'pipeline_run_records'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        nullable=False,
    )
    pipeline_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    status = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )
    started_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False)
    finished_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False)
    result = sqlalchemy.Column(sqlalchemy.JSON, nullable=False)
    knowledge_base_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)

    __table_args__ = (
        sqlalchemy.ForeignKeyConstraint(
            ['workspace_uuid', 'pipeline_uuid'],
            ['legacy_pipelines.workspace_uuid', 'legacy_pipelines.uuid'],
            name='fk_pipeline_run_records_workspace_pipeline',
            ondelete='CASCADE',
        ),
        sqlalchemy.Index(
            'ix_pipeline_run_records_workspace_pipeline',
            'workspace_uuid',
            'pipeline_uuid',
        ),
        sqlalchemy.Index(
            'ix_pipeline_run_records_workspace_created',
            'workspace_uuid',
            'created_at',
        ),
    )
