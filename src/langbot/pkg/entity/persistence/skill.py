"""Workspace-owned Skill catalog and retained immutable publications."""

import sqlalchemy

from .base import Base


class SkillRegistry(Base):
    __tablename__ = 'skill_registry'

    uuid = sqlalchemy.Column(sqlalchemy.String(36), primary_key=True)
    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36), sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'), nullable=False
    )
    instance_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    name = sqlalchemy.Column(sqlalchemy.String(64), nullable=False)
    current_revision = sqlalchemy.Column(sqlalchemy.String(71), nullable=False)
    skill_json = sqlalchemy.Column(sqlalchemy.JSON, nullable=False)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now(), onupdate=sqlalchemy.func.now()
    )

    __table_args__ = (
        sqlalchemy.UniqueConstraint('workspace_uuid', 'instance_uuid', 'name', name='uq_skill_registry_scope_name'),
    )


class SkillVersion(Base):
    __tablename__ = 'skill_versions'

    uuid = sqlalchemy.Column(sqlalchemy.String(36), primary_key=True)
    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36), sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'), nullable=False
    )
    instance_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    name = sqlalchemy.Column(sqlalchemy.String(64), nullable=False)
    revision = sqlalchemy.Column(sqlalchemy.String(71), nullable=False)
    manifest_json = sqlalchemy.Column(sqlalchemy.JSON, nullable=False)
    skill_json = sqlalchemy.Column(sqlalchemy.JSON, nullable=False)
    content_ref = sqlalchemy.Column(sqlalchemy.String(80), nullable=False)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())

    __table_args__ = (
        sqlalchemy.UniqueConstraint(
            'workspace_uuid', 'instance_uuid', 'name', 'revision', name='uq_skill_versions_scope_name_revision'
        ),
        sqlalchemy.ForeignKeyConstraint(
            ['workspace_uuid', 'content_ref'],
            ['content_objects.workspace_uuid', 'content_objects.ref'],
            ondelete='RESTRICT',
            name='fk_skill_versions_content_scope',
        ),
    )
