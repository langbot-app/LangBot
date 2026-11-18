"""Workspace assets and retention references; references do not grant access."""

import sqlalchemy as sa

from .base import Base


class Artifact(Base):
    __tablename__ = 'artifacts'

    id = sa.Column(sa.String(40), primary_key=True)
    workspace_uuid = sa.Column(sa.String(36), sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'), nullable=False)
    owner_type = sa.Column(sa.String(16), nullable=False)
    owner_id = sa.Column(sa.String(36), nullable=False)
    manager_type = sa.Column(sa.String(16), nullable=True)
    manager_id = sa.Column(sa.String(36), nullable=True)
    name = sa.Column(sa.String(255), nullable=False)
    mime_type = sa.Column(sa.String(255), nullable=False)
    size = sa.Column(sa.BigInteger, nullable=False)
    digest = sa.Column(sa.String(64), nullable=False)
    content_ref = sa.Column(sa.String(80), nullable=False)
    source_version_id = sa.Column(
        sa.String(36),
        sa.ForeignKey('skill_versions.uuid', ondelete='RESTRICT', name='fk_artifact_skill_version'),
        nullable=True,
    )
    source_revision = sa.Column(sa.String(71), nullable=True)
    source_path = sa.Column(sa.String(1024), nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False, server_default=sa.func.now())
    expires_at = sa.Column(sa.DateTime, nullable=True)
    deleted_at = sa.Column(sa.DateTime, nullable=True)
    __table_args__ = (
        sa.UniqueConstraint('workspace_uuid', 'id', name='uq_artifacts_workspace_id'),
        sa.ForeignKeyConstraint(
            ['workspace_uuid', 'content_ref'],
            ['content_objects.workspace_uuid', 'content_objects.ref'],
            ondelete='RESTRICT',
            name='fk_artifacts_content_scope',
        ),
        sa.CheckConstraint('size >= 0', name='ck_artifacts_size'),
        sa.CheckConstraint(
            '(source_version_id IS NULL AND source_revision IS NULL AND source_path IS NULL) OR '
            '(source_version_id IS NOT NULL AND source_revision IS NOT NULL AND source_path IS NOT NULL)',
            name='ck_artifact_skill_source',
        ),
        sa.Index('ix_artifacts_expiration', 'workspace_uuid', 'deleted_at', 'expires_at'),
    )


class ArtifactReference(Base):
    __tablename__ = 'artifact_references'

    workspace_uuid = sa.Column(sa.String(36), sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'), primary_key=True)
    artifact_id = sa.Column(sa.String(40), primary_key=True)
    holder_type = sa.Column(sa.String(64), primary_key=True)
    holder_id = sa.Column(sa.String(255), primary_key=True)
    expires_at = sa.Column(sa.DateTime, nullable=True)
    __table_args__ = (
        sa.CheckConstraint("expires_at IS NULL OR holder_type = 'read_lease'", name='ck_artifact_reference_lease_kind'),
        sa.ForeignKeyConstraint(
            ['workspace_uuid', 'artifact_id'],
            ['artifacts.workspace_uuid', 'artifacts.id'],
            ondelete='RESTRICT',
            name='fk_artifact_references_scope',
        ),
    )
