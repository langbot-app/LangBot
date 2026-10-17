"""Remove independent API-key permission scopes."""

from alembic import op
import sqlalchemy as sa

revision = '0035_api_key_user_permissions'
down_revision = '0034_monitoring_execution_links'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('api_keys') and 'scopes' in {c['name'] for c in inspector.get_columns('api_keys')}:
        with op.batch_alter_table('api_keys') as batch_op:
            batch_op.drop_column('scopes')


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('api_keys') and 'scopes' not in {c['name'] for c in inspector.get_columns('api_keys')}:
        op.add_column('api_keys', sa.Column('scopes', sa.JSON(), nullable=False, server_default='[]'))
