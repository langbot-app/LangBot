"""Track the liveness of hosts owning direct executions."""

from alembic import op
import sqlalchemy as sa

revision = '0036_execution_host_leases'
down_revision = '0035_pipeline_received_only'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for table in ('agent_run', 'monitoring_messages'):
        if not inspector.has_table(table):
            continue
        columns = {c['name'] for c in inspector.get_columns(table)}
        indexes = {i['name'] for i in inspector.get_indexes(table)}
        for column, column_type in (
            ('execution_owner_id', sa.String(36)),
            ('execution_lease_expires_at', sa.DateTime()),
        ):
            if column not in columns:
                op.add_column(table, sa.Column(column, column_type, nullable=True))
            index = f'ix_{table}_{column}'
            if index not in indexes:
                op.create_index(index, table, [column])


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for table in ('agent_run', 'monitoring_messages'):
        if not inspector.has_table(table):
            continue
        columns = {c['name'] for c in inspector.get_columns(table)}
        indexes = {i['name'] for i in inspector.get_indexes(table)}
        for column in ('execution_owner_id', 'execution_lease_expires_at'):
            if f'ix_{table}_{column}' in indexes:
                op.drop_index(f'ix_{table}_{column}', table_name=table)
            if column in columns:
                op.drop_column(table, column)
