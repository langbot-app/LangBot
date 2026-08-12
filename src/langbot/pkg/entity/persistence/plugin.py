import hashlib
import uuid

import sqlalchemy

from .base import Base


class PluginSetting(Base):
    """Plugin setting"""

    __tablename__ = 'plugin_settings'

    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        primary_key=True,
    )
    plugin_author = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    plugin_name = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    installation_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )
    artifact_digest = sqlalchemy.Column(
        sqlalchemy.String(64),
        nullable=False,
        default=lambda: hashlib.sha256(f'pending:{uuid.uuid4()}'.encode()).hexdigest(),
    )
    runtime_revision = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=1)
    enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True)
    priority = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=0)
    config = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=dict)
    install_source = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, default='github')
    install_info = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=dict)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

    __table_args__ = (
        sqlalchemy.UniqueConstraint('installation_uuid', name='uq_plugin_settings_installation_uuid'),
        sqlalchemy.CheckConstraint('runtime_revision >= 1', name='ck_plugin_settings_runtime_revision_positive'),
        sqlalchemy.CheckConstraint('length(artifact_digest) = 64', name='ck_plugin_settings_artifact_digest_length'),
        sqlalchemy.Index('ix_plugin_settings_workspace_enabled', 'workspace_uuid', 'enabled'),
        sqlalchemy.Index(
            'ix_plugin_settings_workspace_installation',
            'workspace_uuid',
            'installation_uuid',
            unique=True,
        ),
    )
