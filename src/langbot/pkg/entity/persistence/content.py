"""Immutable content and the mutable aliases used by existing storage APIs."""

import sqlalchemy as sa

from .base import Base


class ContentObject(Base):
    __tablename__ = 'content_objects'

    ref = sa.Column(sa.String(80), primary_key=True)
    workspace_uuid = sa.Column(sa.String(36), sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'), nullable=False)
    public_media = sa.Column(sa.Boolean, nullable=False, server_default=sa.false())
    public_key = sa.Column(sa.String(255), nullable=True)
    owner_type = sa.Column(sa.String(64), nullable=False)
    owner = sa.Column(sa.String(255), nullable=False)
    key = sa.Column(sa.Text, nullable=False)
    digest = sa.Column(sa.String(64), nullable=False)
    size = sa.Column(sa.BigInteger, nullable=False)
    backend = sa.Column(sa.String(128), nullable=False)
    locator = sa.Column(sa.JSON, nullable=True)
    value = sa.Column(sa.LargeBinary, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False, server_default=sa.func.now())
    __table_args__ = (
        sa.UniqueConstraint('workspace_uuid', 'ref', name='uq_content_objects_workspace_ref'),
        sa.Index('ix_content_objects_workspace', 'workspace_uuid'),
        sa.Index('ix_content_objects_public_key', 'public_key'),
        sa.CheckConstraint('size >= 0', name='ck_content_objects_size'),
    )


class ContentAlias(Base):
    __tablename__ = 'content_aliases'

    workspace_uuid = sa.Column(sa.String(36), sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'), primary_key=True)
    key = sa.Column(sa.String(512), primary_key=True)
    content_ref = sa.Column(sa.String(80), nullable=False)
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ['workspace_uuid', 'content_ref'],
            ['content_objects.workspace_uuid', 'content_objects.ref'],
            name='fk_content_alias_workspace_ref',
        ),
    )
