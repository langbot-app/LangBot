from __future__ import annotations

import sqlalchemy

from .base import Base


class DirectoryProjectionState(Base):
    """Durable cursor and lease for one verified Cloud directory."""

    __tablename__ = 'directory_projection_states'

    instance_uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    cursor = sqlalchemy.Column(sqlalchemy.BigInteger, nullable=False, server_default='0')
    snapshot_coverage_cursor = sqlalchemy.Column(sqlalchemy.BigInteger, nullable=False, server_default='0')
    snapshot_fingerprint = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    last_applied_at = sqlalchemy.Column(sqlalchemy.DateTime(timezone=True), nullable=False)
    lease_expires_at = sqlalchemy.Column(sqlalchemy.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        sqlalchemy.CheckConstraint('cursor >= 0', name='ck_directory_projection_state_cursor'),
        sqlalchemy.CheckConstraint(
            'snapshot_coverage_cursor >= 0 AND snapshot_coverage_cursor <= cursor',
            name='ck_directory_projection_state_snapshot_coverage',
        ),
        sqlalchemy.CheckConstraint(
            'length(snapshot_fingerprint) = 64',
            name='ck_directory_projection_state_fingerprint',
        ),
    )


class DirectoryProjectionInbox(Base):
    """Idempotency ledger for signed control-plane directory events."""

    __tablename__ = 'directory_projection_inbox'

    instance_uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    event_uuid = sqlalchemy.Column(sqlalchemy.String(36), primary_key=True)
    cursor = sqlalchemy.Column(sqlalchemy.BigInteger, nullable=False)
    event_type = sqlalchemy.Column(sqlalchemy.String(128), nullable=False)
    revision = sqlalchemy.Column(sqlalchemy.BigInteger, nullable=False)
    fingerprint = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    received_at = sqlalchemy.Column(
        sqlalchemy.DateTime(timezone=True),
        nullable=False,
        server_default=sqlalchemy.func.now(),
    )
    applied_at = sqlalchemy.Column(sqlalchemy.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        sqlalchemy.UniqueConstraint(
            'instance_uuid',
            'cursor',
            name='uq_directory_projection_inbox_cursor',
        ),
        sqlalchemy.Index(
            'ix_directory_projection_inbox_pending',
            'instance_uuid',
            'applied_at',
            'cursor',
        ),
        sqlalchemy.CheckConstraint('cursor > 0', name='ck_directory_projection_inbox_cursor'),
        sqlalchemy.CheckConstraint('revision > 0', name='ck_directory_projection_inbox_revision'),
        sqlalchemy.CheckConstraint(
            'length(fingerprint) = 64',
            name='ck_directory_projection_inbox_fingerprint',
        ),
    )
