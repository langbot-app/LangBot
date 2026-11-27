"""Persist Harness instance key transitions and per-device acknowledgements."""

import sqlalchemy as sa
from alembic import op

revision = '0065_harness_key_rotation'
down_revision = '0064_harness_processor_bots'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if 'transition' not in {column['name'] for column in inspector.get_columns('harness_instance_keys')}:
        op.add_column('harness_instance_keys', sa.Column('transition', sa.JSON()))
    if not inspector.has_table('harness_key_acks'):
        op.create_table(
            'harness_key_acks',
            sa.Column('rotation_id', sa.String(36), primary_key=True),
            sa.Column('device_id', sa.String(36), primary_key=True),
        )


def downgrade():
    # Downgrading cannot safely represent an overlapping key pair.
    conn = op.get_bind()
    if conn.execute(sa.text("SELECT 1 FROM harness_instance_keys WHERE status = 'overlap'")).first():
        raise RuntimeError('Complete the Harness key rotation before downgrading')
    op.drop_table('harness_key_acks')
    op.drop_column('harness_instance_keys', 'transition')
