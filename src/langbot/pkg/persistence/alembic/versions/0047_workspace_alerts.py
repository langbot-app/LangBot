"""add Workspace failure alert tables

Revision ID: 0047_workspace_alerts
Revises: 0046_execution_lease_scopes
Create Date: 2026-11-12

Settings, incidents and the delivery log are tenant-owned. Fresh installs get
them from ``create_all``; this revision creates them on existing databases and
applies the shared Row Level Security policy on PostgreSQL.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0047_workspace_alerts'
down_revision = '0046_execution_lease_scopes'
branch_labels = None
depends_on = None


_POLICY_NAME = 'langbot_workspace_isolation'
_TENANT_SETTING = 'langbot.workspace_uuid'
_TABLES = ('alert_settings', 'alert_incidents', 'alert_deliveries')


def _workspace_fk() -> sa.Column:
    return sa.Column(
        'workspace_uuid',
        sa.String(36),
        sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        nullable=False,
    )


def upgrade() -> None:
    conn = op.get_bind()
    existing = set(sa.inspect(conn).get_table_names())
    if 'workspaces' not in existing:
        # Partial legacy schemas (upgrade fixtures) have no tenancy kernel to
        # reference; real installs always do, and create_all covers fresh ones.
        return

    if 'alert_settings' not in existing:
        op.create_table(
            'alert_settings',
            sa.Column(
                'workspace_uuid',
                sa.String(36),
                sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
                primary_key=True,
            ),
            sa.Column('enabled', sa.Boolean(), nullable=False),
            sa.Column('email_channel', sa.String(16), nullable=False),
            sa.Column('rules', sa.JSON(), nullable=False),
            sa.Column('webhook_ids', sa.JSON(), nullable=False),
            sa.Column('extra_recipients', sa.JSON(), nullable=False),
            sa.Column('muted_account_uuids', sa.JSON(), nullable=False),
            sa.Column('notify_resolved', sa.Boolean(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint(
                "email_channel IN ('auto', 'instance', 'space', 'off')",
                name='ck_alert_settings_email_channel',
            ),
        )

    if 'alert_incidents' not in existing:
        op.create_table(
            'alert_incidents',
            sa.Column('id', sa.String(36), primary_key=True),
            _workspace_fk(),
            sa.Column('rule', sa.String(32), nullable=False),
            sa.Column('fingerprint', sa.String(320), nullable=False),
            sa.Column('subject_id', sa.String(255), nullable=False),
            sa.Column('subject_name', sa.String(255), nullable=False),
            sa.Column('state', sa.String(16), nullable=False),
            sa.Column('event_count', sa.Integer(), nullable=False),
            sa.Column('error_type', sa.String(128), nullable=True),
            sa.Column('error_summary', sa.Text(), nullable=True),
            sa.Column('opened_at', sa.DateTime(), nullable=False),
            sa.Column('last_seen_at', sa.DateTime(), nullable=False),
            sa.Column('resolved_at', sa.DateTime(), nullable=True),
            sa.Column('notified_at', sa.DateTime(), nullable=True),
            sa.Column('last_notified_at', sa.DateTime(), nullable=True),
            sa.Column('reminder_count', sa.Integer(), nullable=False),
            sa.Column('resolved_notified_at', sa.DateTime(), nullable=True),
            sa.CheckConstraint("state IN ('firing', 'resolved')", name='ck_alert_incidents_state'),
        )
        op.create_index(
            'uq_alert_incidents_firing_fingerprint',
            'alert_incidents',
            ['workspace_uuid', 'fingerprint'],
            unique=True,
            sqlite_where=sa.text("state = 'firing'"),
            postgresql_where=sa.text("state = 'firing'"),
        )
        op.create_index(
            'ix_alert_incidents_workspace_state_opened',
            'alert_incidents',
            ['workspace_uuid', 'state', 'opened_at'],
        )

    if 'alert_deliveries' not in existing:
        op.create_table(
            'alert_deliveries',
            sa.Column('id', sa.BigInteger().with_variant(sa.Integer, 'sqlite'), primary_key=True),
            _workspace_fk(),
            sa.Column('kind', sa.String(16), nullable=False),
            sa.Column('channel', sa.String(16), nullable=False),
            sa.Column('target', sa.String(255), nullable=False),
            sa.Column('status', sa.String(16), nullable=False),
            sa.Column('error', sa.String(255), nullable=True),
            sa.Column('incident_count', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index(
            'ix_alert_deliveries_workspace_created',
            'alert_deliveries',
            ['workspace_uuid', 'created_at'],
        )

    if conn.dialect.name != 'postgresql':
        return

    preparer = conn.dialect.identifier_preparer
    policy = preparer.quote(_POLICY_NAME)
    expression = f"workspace_uuid::text = NULLIF(current_setting('{_TENANT_SETTING}', true), '')"
    for table_name in _TABLES:
        table = preparer.quote(table_name)
        op.execute(sa.text(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'DROP POLICY IF EXISTS {policy} ON {table}'))
        op.execute(
            sa.text(
                f'CREATE POLICY {policy} ON {table} AS PERMISSIVE FOR ALL TO PUBLIC '
                f'USING ({expression}) WITH CHECK ({expression})'
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    existing = set(sa.inspect(conn).get_table_names())
    for table_name in reversed(_TABLES):
        if table_name in existing:
            op.drop_table(table_name)
