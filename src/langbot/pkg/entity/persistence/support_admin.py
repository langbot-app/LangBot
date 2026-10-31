from __future__ import annotations

import sqlalchemy

from .base import Base


class SupportAdminTemporarySession(Base):
    """Temporary support-admin Workspace access session."""

    __tablename__ = 'support_admin_temporary_sessions'

    grant_jti_hash = sqlalchemy.Column(sqlalchemy.String(64), primary_key=True)
    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        nullable=False,
    )
    actor_account_uuid = sqlalchemy.Column(sqlalchemy.String(36), nullable=False)
    issued_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False)
    expires_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False)
    revoked_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    last_used_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)

    __table_args__ = (
        sqlalchemy.Index(
            'ix_support_admin_sessions_workspace_expiry',
            'workspace_uuid',
            'expires_at',
        ),
        sqlalchemy.CheckConstraint(
            'length(grant_jti_hash) = 64',
            name='ck_support_admin_sessions_grant_jti_hash',
        ),
    )
