"""add temporary support-admin sessions

Revision ID: 0016_support_admin_sessions
Revises: 0015_cloud_core_collab
Create Date: 2026-07-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0016_support_admin_sessions'
down_revision = '0015_cloud_core_collab'
branch_labels = None
depends_on = None


_TABLE_NAME = 'support_admin_temporary_sessions'
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
            sa.Column('grant_jti_hash', sa.String(64), nullable=False),
            sa.Column(
                'workspace_uuid',
                sa.String(36),
                sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
                nullable=False,
            ),
            sa.Column('actor_account_uuid', sa.String(36), nullable=False),
            sa.Column('issued_at', sa.DateTime(), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('revoked_at', sa.DateTime(), nullable=True),
            sa.Column('last_used_at', sa.DateTime(), nullable=True),
            sa.CheckConstraint(
                'length(grant_jti_hash) = 64',
                name='ck_support_admin_sessions_grant_jti_hash',
            ),
            sa.PrimaryKeyConstraint('grant_jti_hash'),
        )
        op.create_index(
            'ix_support_admin_sessions_workspace_expiry',
            _TABLE_NAME,
            ['workspace_uuid', 'expires_at'],
            unique=False,
        )

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
    op.drop_index('ix_support_admin_sessions_workspace_expiry', table_name=_TABLE_NAME)
    op.drop_table(_TABLE_NAME)
