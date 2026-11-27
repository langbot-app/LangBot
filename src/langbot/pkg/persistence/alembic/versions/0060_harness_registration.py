"""Persist instance enrollment links and bindings."""

import sqlalchemy as sa
from alembic import op

revision = '0060_harness_registration'
down_revision = '0059_harness_workspace_bot'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('harness_registration_links'):
        op.create_table(
            'harness_registration_links',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
            sa.Column('instance_uuid', sa.String(36), nullable=False),
            sa.Column('issuer_workspace_uuid', sa.String(36), nullable=False, index=True),
            sa.Column('created_by_account_uuid', sa.String(36), nullable=False),
            sa.Column('kid', sa.String(128), nullable=False),
            sa.Column('preferred_auth', sa.String(16)),
            sa.Column('expires_at', sa.BigInteger, nullable=False),
            sa.Column('consumed_at', sa.BigInteger),
            sa.Column('revoked_at', sa.BigInteger),
        )
    if not inspector.has_table('harness_bindings'):
        op.create_table(
            'harness_bindings',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('instance_uuid', sa.String(36), nullable=False),
            sa.Column('issuer_workspace_uuid', sa.String(36), nullable=False, index=True),
            sa.Column('created_at', sa.BigInteger, nullable=False),
            sa.Column('revoked_at', sa.BigInteger),
        )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for name in ('harness_bindings', 'harness_registration_links'):
        if inspector.has_table(name):
            op.drop_table(name)
