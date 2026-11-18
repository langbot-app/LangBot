"""Workspace failure alerts: settings, incidents and the delivery log.

All three tables are tenant-owned and covered by the shared Row Level
Security contract. ``alert_incidents`` allows at most one firing incident per
``(workspace_uuid, fingerprint)``, so concurrent replicas cannot open the
same alert twice.
"""

from __future__ import annotations

import sqlalchemy

from .base import Base


INCIDENT_FIRING = 'firing'
INCIDENT_RESOLVED = 'resolved'


class AlertSetting(Base):
    __tablename__ = 'alert_settings'

    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        primary_key=True,
    )
    enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True)
    # auto | instance | space | off
    email_channel = sqlalchemy.Column(sqlalchemy.String(16), nullable=False, default='auto')
    rules = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=dict)
    webhook_ids = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=list)
    extra_recipients = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=list)
    muted_account_uuids = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=list)
    notify_resolved = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True)
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

    __table_args__ = (
        sqlalchemy.CheckConstraint(
            "email_channel IN ('auto', 'instance', 'space', 'off')",
            name='ck_alert_settings_email_channel',
        ),
    )


class AlertIncident(Base):
    __tablename__ = 'alert_incidents'

    id = sqlalchemy.Column(sqlalchemy.String(36), primary_key=True)
    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        nullable=False,
    )
    rule = sqlalchemy.Column(sqlalchemy.String(32), nullable=False)
    fingerprint = sqlalchemy.Column(sqlalchemy.String(320), nullable=False)
    subject_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    subject_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, default='')
    state = sqlalchemy.Column(sqlalchemy.String(16), nullable=False, default=INCIDENT_FIRING)
    event_count = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=0)
    error_type = sqlalchemy.Column(sqlalchemy.String(128), nullable=True)
    error_summary = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    opened_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False)
    last_seen_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False)
    resolved_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    # Delivery bookkeeping. Each pass claims rows with a compare-and-set on
    # these columns so only one replica notifies.
    notified_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    last_notified_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    reminder_count = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=0)
    resolved_notified_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)

    __table_args__ = (
        sqlalchemy.Index(
            'uq_alert_incidents_firing_fingerprint',
            'workspace_uuid',
            'fingerprint',
            unique=True,
            sqlite_where=sqlalchemy.text("state = 'firing'"),
            postgresql_where=sqlalchemy.text("state = 'firing'"),
        ),
        sqlalchemy.Index('ix_alert_incidents_workspace_state_opened', 'workspace_uuid', 'state', 'opened_at'),
        sqlalchemy.CheckConstraint("state IN ('firing', 'resolved')", name='ck_alert_incidents_state'),
    )


class AlertDelivery(Base):
    __tablename__ = 'alert_deliveries'

    id = sqlalchemy.Column(sqlalchemy.BigInteger().with_variant(sqlalchemy.Integer, 'sqlite'), primary_key=True)
    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        nullable=False,
    )
    kind = sqlalchemy.Column(sqlalchemy.String(16), nullable=False)  # fired | reminder | resolved | test
    channel = sqlalchemy.Column(sqlalchemy.String(16), nullable=False)  # email | space | webhook
    target = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, default='')
    status = sqlalchemy.Column(sqlalchemy.String(16), nullable=False)  # sent | failed | rate_limited | skipped
    error = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    incident_count = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=0)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())

    __table_args__ = (sqlalchemy.Index('ix_alert_deliveries_workspace_created', 'workspace_uuid', 'created_at'),)
