"""Tenant-owned original configurations; never expose through public serialization."""

import sqlalchemy as sa

from .base import Base


class PipelineMigrationSnapshot(Base):
    __tablename__ = 'pipeline_migration_snapshots'

    uuid = sa.Column(sa.String(36), primary_key=True)
    workspace_uuid = sa.Column(sa.String(36), sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'), nullable=False)
    pipeline_uuid = sa.Column(sa.String(255), nullable=False)
    source_fingerprint = sa.Column(sa.String(64), nullable=False)
    target_fingerprint = sa.Column(sa.String(64), nullable=False)
    planner_version = sa.Column(sa.String(64), nullable=False)
    source_snapshot = sa.Column(sa.JSON, nullable=False)
    state = sa.Column(sa.String(32), nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False, server_default=sa.func.now())

    __table_args__ = (
        sa.ForeignKeyConstraint(
            ['workspace_uuid', 'pipeline_uuid'],
            ['legacy_pipelines.workspace_uuid', 'legacy_pipelines.uuid'],
            name='fk_pipeline_migration_workspace_pipeline',
            ondelete='CASCADE',
        ),
        sa.UniqueConstraint(
            'workspace_uuid', 'pipeline_uuid', 'source_fingerprint', name='uq_pipeline_migration_source'
        ),
        sa.CheckConstraint("state IN ('activation_pending', 'active')", name='ck_pipeline_migration_state'),
        sa.Index('ix_pipeline_migration_workspace_pipeline', 'workspace_uuid', 'pipeline_uuid'),
    )
