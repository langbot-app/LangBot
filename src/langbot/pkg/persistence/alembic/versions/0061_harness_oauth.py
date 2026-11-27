"""Persist device keys and device-bound Harness OAuth grants."""

import sqlalchemy as sa
from alembic import op

revision = '0061_harness_oauth'
down_revision = '0060_harness_registration'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('harness_devices'):
        op.create_table(
            'harness_devices',
            sa.Column('id', sa.String(64), primary_key=True),
            sa.Column('binding_id', sa.String(36), nullable=False, index=True),
            sa.Column('device_kid', sa.String(128), nullable=False),
            sa.Column('x25519_pub', sa.Text(), nullable=False),
            sa.Column('ed25519_pub', sa.Text(), nullable=False),
            sa.Column('platform', sa.String(32), nullable=False),
            sa.Column('account_uuid', sa.String(36), nullable=True, index=True),
            sa.Column('created_at', sa.BigInteger, nullable=False),
            sa.Column('revoked_at', sa.BigInteger),
            sa.UniqueConstraint('binding_id', 'device_kid', name='uq_harness_device_kid'),
        )
    if not inspector.has_table('harness_oauth_grants'):
        op.create_table(
            'harness_oauth_grants',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('binding_id', sa.String(36), nullable=False, index=True),
            sa.Column('device_id', sa.String(64), nullable=False, index=True),
            sa.Column('account_uuid', sa.String(36), nullable=False, index=True),
            sa.Column('workspace_uuid', sa.String(36), nullable=False, index=True),
            sa.Column('scope', sa.Text(), nullable=False, server_default=''),
            sa.Column('refresh_token_hash', sa.String(64), nullable=False, unique=True),
            sa.Column('refresh_generation', sa.Integer, nullable=False, server_default='0'),
            sa.Column('refresh_expires_at', sa.BigInteger, nullable=False),
            sa.Column('created_at', sa.BigInteger, nullable=False),
            sa.Column('revoked_at', sa.BigInteger),
        )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for name in ('harness_oauth_grants', 'harness_devices'):
        if inspector.has_table(name):
            op.drop_table(name)
