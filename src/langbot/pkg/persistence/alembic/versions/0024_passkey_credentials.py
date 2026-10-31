"""add passkey credentials table

Revision ID: 0024_passkey_credentials
Revises: 0023_bot_scoped_sessions
Create Date: 2026-09-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0024_passkey_credentials'
down_revision = '0023_bot_scoped_sessions'
branch_labels = None
depends_on = None

_TABLE_NAME = 'passkey_credentials'


def upgrade() -> None:
    conn = op.get_bind()
    existing_tables = set(sa.inspect(conn).get_table_names())
    if _TABLE_NAME not in existing_tables:
        op.create_table(
            _TABLE_NAME,
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('uuid', sa.String(36), nullable=False),
            sa.Column(
                'account_uuid',
                sa.String(36),
                sa.ForeignKey('users.uuid', ondelete='CASCADE'),
                nullable=False,
            ),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('credential_id', sa.String(255), nullable=False),
            sa.Column('public_key', sa.Text(), nullable=False),
            sa.Column('sign_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('aaguid', sa.String(64), nullable=True),
            sa.Column('transports', sa.String(255), nullable=True),
            sa.Column('backed_up', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('last_used_at', sa.DateTime(), nullable=True),
        )
        op.create_index('uq_passkey_credentials_uuid', _TABLE_NAME, ['uuid'], unique=True)
        op.create_index('uq_passkey_credentials_cred_id', _TABLE_NAME, ['credential_id'], unique=True)
        op.create_index('ix_passkey_credentials_account', _TABLE_NAME, ['account_uuid'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_passkey_credentials_account', table_name=_TABLE_NAME)
    op.drop_index('uq_passkey_credentials_cred_id', table_name=_TABLE_NAME)
    op.drop_index('uq_passkey_credentials_uuid', table_name=_TABLE_NAME)
    op.drop_table(_TABLE_NAME)
