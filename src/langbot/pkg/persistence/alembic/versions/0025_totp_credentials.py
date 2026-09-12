"""add totp credentials table

Revision ID: 0025_totp_credentials
Revises: 0024_passkey_credentials
Create Date: 2026-09-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0025_totp_credentials'
down_revision = '0024_passkey_credentials'
branch_labels = None
depends_on = None

_TABLE_NAME = 'totp_credentials'


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
            sa.Column('secret_encrypted', sa.Text(), nullable=False),
            sa.Column('account_name', sa.String(320), nullable=False),
            sa.Column('enabled', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('recovery_codes', sa.Text(), nullable=True),
            sa.Column('last_used_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('uq_totp_credentials_uuid', _TABLE_NAME, ['uuid'], unique=True)
        op.create_index('uq_totp_credentials_account', _TABLE_NAME, ['account_uuid'], unique=True)


def downgrade() -> None:
    op.drop_index('uq_totp_credentials_account', table_name=_TABLE_NAME)
    op.drop_index('uq_totp_credentials_uuid', table_name=_TABLE_NAME)
    op.drop_table(_TABLE_NAME)
