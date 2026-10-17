"""Bound host lease maintenance to active executions within each Workspace."""

from alembic import op
import sqlalchemy as sa

revision = '0039_execution_lease_indexes'
down_revision = '0038_llm_call_details'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for table, workspace_column in (
        ('agent_run', 'workspace_id'),
        ('monitoring_messages', 'workspace_uuid'),
    ):
        index = f'ix_{table}_workspace_status_lease'
        # Fresh installations create these indexes from ORM metadata before migrations.
        if index not in {item['name'] for item in inspector.get_indexes(table)}:
            op.create_index(index, table, [workspace_column, 'status', 'execution_lease_expires_at'])


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for table in ('agent_run', 'monitoring_messages'):
        index = f'ix_{table}_workspace_status_lease'
        if index in {item['name'] for item in inspector.get_indexes(table)}:
            op.drop_index(index, table_name=table)
