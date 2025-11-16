import sqlalchemy

from .base import Base


class LegacyPipeline(Base):
    """Legacy pipeline"""

    __tablename__ = 'legacy_pipelines'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    description = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
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
    extensions_preferences = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default={})


class PipelineRunRecord(Base):
    """Pipeline run record"""

    __tablename__ = 'pipeline_run_records'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
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
