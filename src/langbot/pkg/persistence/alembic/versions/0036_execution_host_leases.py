"""Track the liveness of hosts owning direct executions."""

from alembic import op
import sqlalchemy as sa

revision = '0036_execution_host_leases'
down_revision = '0035_pipeline_received_only'
branch_labels = None
depends_on = None


def upgrade():
    for table in ('agent_run', 'monitoring_messages'):
        op.add_column(table, sa.Column('execution_owner_id', sa.String(36), nullable=True))
        op.add_column(table, sa.Column('execution_lease_expires_at', sa.DateTime(), nullable=True))
        for column in ('execution_owner_id', 'execution_lease_expires_at'):
            op.create_index(f'ix_{table}_{column}', table, [column])


def downgrade():
    for table in ('agent_run', 'monitoring_messages'):
        for column in ('execution_owner_id', 'execution_lease_expires_at'):
            op.drop_index(f'ix_{table}_{column}', table_name=table)
            op.drop_column(table, column)
