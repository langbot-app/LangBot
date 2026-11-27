"""Host-owned authorization to publish a producer's outputs to one named principal."""

import sqlalchemy as sa

from .base import Base


class ArtifactPublication(Base):
    __tablename__ = 'artifact_publications'

    workspace_uuid = sa.Column(sa.String(36), sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'), primary_key=True)
    producer_type = sa.Column(sa.String(32), primary_key=True)
    producer_id = sa.Column(sa.String(255), primary_key=True)
    manager_type = sa.Column(sa.String(16), nullable=False)
    manager_id = sa.Column(sa.String(36), nullable=False)
    revision = sa.Column(sa.String(36), nullable=False)
    enabled = sa.Column(sa.Boolean, nullable=False, default=False)
    created_at = sa.Column(sa.DateTime, nullable=False, server_default=sa.func.now())
    updated_at = sa.Column(sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now())
    __table_args__ = (
        sa.CheckConstraint(
            "producer_type IN ('agent', 'pipeline', 'event_processor')", name='ck_artifact_publication_producer'
        ),
        sa.CheckConstraint("manager_type IN ('account', 'api_key')", name='ck_artifact_publication_manager'),
    )
