"""add TOTP credentials and recovery codes

Revision ID: 0025_totp_credentials
Revises: 0024_passkey_credentials
Create Date: 2026-09-22

The TOTP shared secret is stored only as a Fernet token keyed off the instance
JWT secret (HKDF-SHA256), and recovery codes are stored only as salted
PBKDF2-HMAC-SHA256 digests. No plaintext second-factor material is persisted.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0025_totp_credentials'
down_revision = '0024_passkey_credentials'
branch_labels = None
depends_on = None

_CREDENTIALS_TABLE = 'totp_credentials'
_RECOVERY_CODES_TABLE = 'totp_recovery_codes'
_LEGACY_CREDENTIALS_TABLE = 'totp_credentials_legacy_pre_0025'

# Columns this migration guarantees. A pre-existing table missing any of them is
# an incompatible abandoned shape and must not be silently reused.
_REQUIRED_CREDENTIAL_COLUMNS = frozenset(
    {'uuid', 'account_uuid', 'secret_ciphertext', 'key_version', 'algorithm', 'digits', 'period'}
)


def _retire_abandoned_credentials_table() -> None:
    """Move an incompatible `totp_credentials` aside without losing its data.

    The table is retained under a clearly labelled name for forensic recovery,
    but its indexes are dropped because they occupy the very names the supported
    schema needs (``uq_totp_credentials_uuid`` in particular).
    """

    inspector = sa.inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())
    if _LEGACY_CREDENTIALS_TABLE in existing_tables:
        op.drop_table(_LEGACY_CREDENTIALS_TABLE)

    op.rename_table(_CREDENTIALS_TABLE, _LEGACY_CREDENTIALS_TABLE)

    for index in sa.inspect(op.get_bind()).get_indexes(_LEGACY_CREDENTIALS_TABLE):
        name = index.get('name')
        if name:
            op.drop_index(name, table_name=_LEGACY_CREDENTIALS_TABLE)


def _create_credentials_table() -> None:
    op.create_table(
        _CREDENTIALS_TABLE,
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('uuid', sa.String(36), nullable=False),
        sa.Column(
            'account_uuid',
            sa.String(36),
            sa.ForeignKey('users.uuid', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('secret_ciphertext', sa.Text(), nullable=False),
        sa.Column('key_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('algorithm', sa.String(16), nullable=False, server_default='SHA1'),
        sa.Column('digits', sa.Integer(), nullable=False, server_default='6'),
        sa.Column('period', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('last_used_counter', sa.BigInteger(), nullable=True),
        sa.Column('disabled_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
    )
    op.create_index('uq_totp_credentials_uuid', _CREDENTIALS_TABLE, ['uuid'], unique=True)
    op.create_index('ix_totp_credentials_account', _CREDENTIALS_TABLE, ['account_uuid'], unique=False)


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if _CREDENTIALS_TABLE not in existing_tables:
        _create_credentials_table()
    else:
        columns = {column['name'] for column in inspector.get_columns(_CREDENTIALS_TABLE)}
        if not _REQUIRED_CREDENTIAL_COLUMNS.issubset(columns):
            # An abandoned table from an unrelated feature occupies the name and
            # cannot store a Fernet-wrapped secret. Preserve it under a clearly
            # labelled name (no data loss) and install the supported schema.
            _retire_abandoned_credentials_table()
            _create_credentials_table()

    if _RECOVERY_CODES_TABLE not in existing_tables:
        op.create_table(
            _RECOVERY_CODES_TABLE,
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('uuid', sa.String(36), nullable=False),
            sa.Column(
                'account_uuid',
                sa.String(36),
                sa.ForeignKey('users.uuid', ondelete='CASCADE'),
                nullable=False,
            ),
            sa.Column('code_id', sa.String(16), nullable=False),
            sa.Column('salt', sa.String(64), nullable=False),
            sa.Column('digest', sa.String(128), nullable=False),
            sa.Column(
                'algorithm',
                sa.String(32),
                nullable=False,
                server_default='pbkdf2_hmac_sha256',
            ),
            sa.Column('iterations', sa.Integer(), nullable=False),
            sa.Column('used_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('uq_totp_recovery_codes_uuid', _RECOVERY_CODES_TABLE, ['uuid'], unique=True)
        op.create_index('uq_totp_recovery_codes_code_id', _RECOVERY_CODES_TABLE, ['code_id'], unique=True)
        op.create_index('ix_totp_recovery_codes_account', _RECOVERY_CODES_TABLE, ['account_uuid'], unique=False)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())

    if _RECOVERY_CODES_TABLE in existing_tables:
        op.drop_index('ix_totp_recovery_codes_account', table_name=_RECOVERY_CODES_TABLE)
        op.drop_index('uq_totp_recovery_codes_code_id', table_name=_RECOVERY_CODES_TABLE)
        op.drop_index('uq_totp_recovery_codes_uuid', table_name=_RECOVERY_CODES_TABLE)
        op.drop_table(_RECOVERY_CODES_TABLE)

    if _CREDENTIALS_TABLE in existing_tables:
        op.drop_index('ix_totp_credentials_account', table_name=_CREDENTIALS_TABLE)
        op.drop_index('uq_totp_credentials_uuid', table_name=_CREDENTIALS_TABLE)
        op.drop_table(_CREDENTIALS_TABLE)
