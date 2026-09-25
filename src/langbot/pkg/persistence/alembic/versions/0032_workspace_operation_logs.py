"""add workspace operation logs for member/resource traceability

Revision ID: 0032_workspace_operation_logs
Revises: 0031_merge_totp_assistant
Create Date: 2026-09-25

The table is append-only and tenant-owned. Fresh installs already receive it
from SQLAlchemy ``create_all``; this revision makes the change safe for
existing databases and mirrors the shared Row Level Security contract so the
Cloud release validation can enforce it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0032_workspace_operation_logs'
down_revision = '0031_merge_totp_assistant'
branch_labels = None
depends_on = None


_TABLE_NAME = 'workspace_operation_logs'
_POLICY_NAME = 'langbot_workspace_isolation'
_TENANT_SETTING = 'langbot.workspace_uuid'


def _setting(name: str) -> str:
    return f"NULLIF(current_setting('{name}', true), '')"


def _quote(conn: sa.Connection, identifier: str) -> str:
    return conn.dialect.identifier_preparer.quote(identifier)


def upgrade() -> None:
    conn = op.get_bind()
    existing_tables = set(sa.inspect(conn).get_table_names())
    if _TABLE_NAME not in existing_tables:
        op.create_table(
            _TABLE_NAME,
            sa.Column('id', sa.BigInteger().with_variant(sa.Integer, 'sqlite'), nullable=False),
            sa.Column(
                'workspace_uuid',
                sa.String(36),
                sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
                nullable=False,
            ),
            sa.Column('actor_account_uuid', sa.String(36), nullable=True),
            sa.Column('actor_name', sa.String(255), nullable=True),
            sa.Column('actor_role', sa.String(32), nullable=True),
            sa.Column('principal_type', sa.String(32), nullable=True),
            sa.Column('api_key_uuid', sa.String(255), nullable=True),
            sa.Column('auth_type', sa.String(32), nullable=True),
            sa.Column('request_id', sa.String(128), nullable=True),
            sa.Column('http_method', sa.String(12), nullable=True),
            sa.Column('route', sa.String(512), nullable=True),
            sa.Column('action', sa.String(64), nullable=True),
            sa.Column('resource_type', sa.String(64), nullable=True),
            sa.Column('resource_id', sa.String(255), nullable=True),
            sa.Column('level', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('outcome', sa.String(16), nullable=False, server_default='ok'),
            sa.Column('status_code', sa.Integer(), nullable=True),
            sa.Column('summary', sa.Text(), nullable=True),
            sa.Column('changes', sa.Text(), nullable=True),
            sa.Column('detail', sa.Text(), nullable=True),
            sa.Column('client_ip', sa.String(64), nullable=True),
            sa.Column('user_agent', sa.String(512), nullable=True),
            sa.Column('duration_ms', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
            sa.CheckConstraint('level IN (0, 1, 2)', name='ck_workspace_operation_logs_level'),
            sa.CheckConstraint(
                "outcome IN ('ok', 'denied', 'error')",
                name='ck_workspace_operation_logs_outcome',
            ),
        )
        op.create_index(
            'ix_workspace_operation_logs_workspace_created',
            _TABLE_NAME,
            ['workspace_uuid', 'created_at'],
            unique=False,
        )
        op.create_index(
            'ix_workspace_operation_logs_workspace_resource',
            _TABLE_NAME,
            ['workspace_uuid', 'resource_type', 'created_at'],
            unique=False,
        )
        op.create_index(
            'ix_workspace_operation_logs_workspace_uuid',
            _TABLE_NAME,
            ['workspace_uuid'],
            unique=False,
        )
        op.create_index('ix_workspace_operation_logs_created_at', _TABLE_NAME, ['created_at'], unique=False)
        op.create_index('ix_workspace_operation_logs_action', _TABLE_NAME, ['action'], unique=False)
        op.create_index('ix_workspace_operation_logs_resource_type', _TABLE_NAME, ['resource_type'], unique=False)
        op.create_index('ix_workspace_operation_logs_level', _TABLE_NAME, ['level'], unique=False)

    if conn.dialect.name != 'postgresql':
        return

    table = _quote(conn, _TABLE_NAME)
    policy = _quote(conn, _POLICY_NAME)
    expression = f'workspace_uuid::text = {_setting(_TENANT_SETTING)}'
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
    if conn.dialect.name == 'postgresql':
        table = _quote(conn, _TABLE_NAME)
        policy = _quote(conn, _POLICY_NAME)
        op.execute(sa.text(f'DROP POLICY IF EXISTS {policy} ON {table}'))
    op.drop_index('ix_workspace_operation_logs_level', table_name=_TABLE_NAME)
    op.drop_index('ix_workspace_operation_logs_resource_type', table_name=_TABLE_NAME)
    op.drop_index('ix_workspace_operation_logs_action', table_name=_TABLE_NAME)
    op.drop_index('ix_workspace_operation_logs_created_at', table_name=_TABLE_NAME)
    op.drop_index('ix_workspace_operation_logs_workspace_uuid', table_name=_TABLE_NAME)
    op.drop_index('ix_workspace_operation_logs_workspace_resource', table_name=_TABLE_NAME)
    op.drop_index('ix_workspace_operation_logs_workspace_created', table_name=_TABLE_NAME)
    op.drop_table(_TABLE_NAME)
