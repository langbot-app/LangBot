"""Record which runner or plugin handled each monitored message."""

from alembic import op
import sqlalchemy as sa

revision = '0045_monitoring_handled_by'
down_revision = '0044_plugin_permissions'
branch_labels = None
depends_on = None

INDEX = 'ix_monitoring_messages_handled_by'


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('monitoring_messages'):
        return
    columns = {c['name'] for c in inspector.get_columns('monitoring_messages')}
    indexes = {i['name'] for i in inspector.get_indexes('monitoring_messages')}
    if 'handled_by' not in columns:
        op.add_column('monitoring_messages', sa.Column('handled_by', sa.String(255), nullable=True))
    if INDEX not in indexes:
        op.create_index(INDEX, 'monitoring_messages', ['handled_by'])


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('monitoring_messages'):
        return
    columns = {c['name'] for c in inspector.get_columns('monitoring_messages')}
    indexes = {i['name'] for i in inspector.get_indexes('monitoring_messages')}
    if INDEX in indexes:
        op.drop_index(INDEX, table_name='monitoring_messages')
    if 'handled_by' in columns:
        op.drop_column('monitoring_messages', 'handled_by')
