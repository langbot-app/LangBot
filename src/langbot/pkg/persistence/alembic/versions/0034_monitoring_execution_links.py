"""Link monitoring inputs and deliveries to events and runs."""

from alembic import op
import sqlalchemy as sa

revision = '0034_monitoring_execution_links'
down_revision = '0033_operation_traceability'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('monitoring_messages'):
        return
    columns = {c['name'] for c in inspector.get_columns('monitoring_messages')}
    indexes = {i['name'] for i in inspector.get_indexes('monitoring_messages')}
    for name in ('event_id', 'run_id', 'parent_message_id'):
        if name not in columns:
            op.add_column('monitoring_messages', sa.Column(name, sa.String(255), nullable=True))
        index = f'ix_monitoring_messages_{name}'
        if index not in indexes:
            op.create_index(index, 'monitoring_messages', [name])


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('monitoring_messages'):
        return
    columns = {c['name'] for c in inspector.get_columns('monitoring_messages')}
    indexes = {i['name'] for i in inspector.get_indexes('monitoring_messages')}
    for name in ('parent_message_id', 'run_id', 'event_id'):
        if f'ix_monitoring_messages_{name}' in indexes:
            op.drop_index(f'ix_monitoring_messages_{name}', table_name='monitoring_messages')
        if name in columns:
            op.drop_column('monitoring_messages', name)
