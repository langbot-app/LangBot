"""Add Workspace-owned workflow processor tables."""

import sqlalchemy as sa
from alembic import op

revision = '0043_workflow_tables'
down_revision = '0042_sqlite_incremental_vacuum'
branch_labels = None
depends_on = None

TABLES = ('workflows', 'workflow_versions', 'workflow_executions', 'workflow_node_executions')


def _workspace_column() -> sa.Column:
    return sa.Column(
        'workspace_uuid', sa.String(36), sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'), nullable=False
    )


def upgrade() -> None:
    conn = op.get_bind()
    existing = set(sa.inspect(conn).get_table_names())

    if 'workflows' not in existing:
        op.create_table(
            'workflows',
            sa.Column('uuid', sa.String(255), primary_key=True),
            _workspace_column(),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('description', sa.Text),
            sa.Column('emoji', sa.String(10)),
            sa.Column('version', sa.Integer, nullable=False, server_default='1'),
            sa.Column('is_enabled', sa.Boolean, nullable=False, server_default=sa.true()),
            sa.Column('definition', sa.JSON, nullable=False),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_workflows_workspace_uuid', 'workflows', ['workspace_uuid'])

    if 'workflow_versions' not in existing:
        op.create_table(
            'workflow_versions',
            sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
            _workspace_column(),
            sa.Column('workflow_uuid', sa.String(255), nullable=False),
            sa.Column('version', sa.Integer, nullable=False),
            sa.Column('definition', sa.JSON, nullable=False),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('workflow_uuid', 'version', name='uq_workflow_version'),
        )
        op.create_index('ix_workflow_versions_workspace_uuid', 'workflow_versions', ['workspace_uuid'])
        op.create_index('ix_workflow_versions_workflow_uuid', 'workflow_versions', ['workflow_uuid'])

    if 'workflow_executions' not in existing:
        op.create_table(
            'workflow_executions',
            sa.Column('uuid', sa.String(255), primary_key=True),
            _workspace_column(),
            sa.Column('workflow_uuid', sa.String(255), nullable=False),
            sa.Column('workflow_version', sa.Integer, nullable=False),
            sa.Column('status', sa.String(20), nullable=False),
            sa.Column('trigger_type', sa.String(50)),
            sa.Column('trigger_data', sa.JSON),
            sa.Column('bot_uuid', sa.String(255)),
            sa.Column('variables', sa.JSON),
            sa.Column('start_time', sa.DateTime),
            sa.Column('end_time', sa.DateTime),
            sa.Column('error', sa.Text),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_workflow_executions_workspace_uuid', 'workflow_executions', ['workspace_uuid'])
        op.create_index('ix_workflow_executions_workflow_uuid', 'workflow_executions', ['workflow_uuid'])

    if 'workflow_node_executions' not in existing:
        op.create_table(
            'workflow_node_executions',
            sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
            _workspace_column(),
            sa.Column('execution_uuid', sa.String(255), nullable=False),
            sa.Column('node_id', sa.String(100), nullable=False),
            sa.Column('node_type', sa.String(50), nullable=False),
            sa.Column('status', sa.String(20), nullable=False),
            sa.Column('inputs', sa.JSON),
            sa.Column('outputs', sa.JSON),
            sa.Column('start_time', sa.DateTime),
            sa.Column('end_time', sa.DateTime),
            sa.Column('error', sa.Text),
            sa.Column('retry_count', sa.Integer, nullable=False, server_default='0'),
        )
        op.create_index('ix_workflow_node_executions_workspace_uuid', 'workflow_node_executions', ['workspace_uuid'])
        op.create_index('ix_workflow_node_executions_execution_uuid', 'workflow_node_executions', ['execution_uuid'])

    if conn.dialect.name == 'postgresql':
        for table in TABLES:
            op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
            op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
            op.execute(f'DROP POLICY IF EXISTS langbot_workspace_isolation ON {table}')
            op.execute(f"""CREATE POLICY langbot_workspace_isolation ON {table}
                USING (workspace_uuid::text = NULLIF(current_setting('langbot.workspace_uuid', true), ''))
                WITH CHECK (workspace_uuid::text = NULLIF(current_setting('langbot.workspace_uuid', true), ''))""")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
