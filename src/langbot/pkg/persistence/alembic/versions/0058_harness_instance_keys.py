"""Add encrypted Harness instance identity key storage."""

import sqlalchemy as sa
from alembic import op

revision = '0058_harness_instance_keys'
down_revision = '0057_agent_access'
branch_labels = None
depends_on = None


def upgrade():
    if 'harness_instance_keys' not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            'harness_instance_keys',
            sa.Column('kid', sa.String(128), primary_key=True),
            sa.Column('x25519_pub', sa.Text(), nullable=False),
            sa.Column('ed25519_pub', sa.Text(), nullable=False),
            sa.Column('priv_ciphertext', sa.Text(), nullable=False),
            sa.Column('status', sa.String(16), nullable=False, server_default='active'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('retired_at', sa.DateTime(timezone=True), nullable=True),
        )


def downgrade():
    if 'harness_instance_keys' in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table('harness_instance_keys')
