"""Add Workspace-owned workflow processor tables."""

import sqlalchemy as sa
from alembic import op

revision = '0061_workflow_tables'
down_revision = '0060_bot_plugin_selection'
branch_labels = None
depends_on = None

TABLES = ('workflows', 'workflow_executions', 'workflow_execution_steps', 'workflow_memory')


def upgrade() -> None:
    conn = op.get_bind()
    existing = set(sa.inspect(conn).get_table_names())
    if 'workspaces' not in existing:
        return

    if 'workflows' not in existing:
        op.create_table(
            'workflows',
            sa.Column('uuid', sa.String(255), primary_key=True),
            sa.Column(
                'workspace_uuid',
                sa.String(36),
                sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
                index=True,
                nullable=False,
            ),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('description', sa.Text),
            sa.Column('emoji', sa.String(255)),
            sa.Column('graph', sa.JSON, nullable=False),
            sa.Column('trigger', sa.JSON, nullable=False, server_default='{"type":"message"}'),
            sa.Column('is_enabled', sa.Boolean, nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        )
    if 'workflow_executions' not in existing:
        op.create_table(
            'workflow_executions',
            sa.Column('uuid', sa.String(255), primary_key=True),
            sa.Column(
                'workspace_uuid',
                sa.String(36),
                sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
                index=True,
                nullable=False,
            ),
            sa.Column('workflow_uuid', sa.String(255), nullable=False, index=True),
            sa.Column('status', sa.String(255), nullable=False),
            sa.Column('trigger', sa.String(255), nullable=False),
            sa.Column('bot_uuid', sa.String(255)),
            sa.Column('session_id', sa.String(255), nullable=False),
            sa.Column('input_text', sa.Text, nullable=False),
            sa.Column('handoff', sa.JSON),
            sa.Column('error', sa.Text),
            sa.Column('started_at', sa.DateTime, nullable=False),
            sa.Column('finished_at', sa.DateTime),
        )
    if 'workflow_execution_steps' not in existing:
        op.create_table(
            'workflow_execution_steps',
            sa.Column(
                'workspace_uuid',
                sa.String(36),
                sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
                index=True,
                nullable=False,
            ),
            sa.Column('execution_uuid', sa.String(255), primary_key=True),
            sa.Column('seq', sa.Integer, primary_key=True),
            sa.Column('node_id', sa.String(255), nullable=False),
            sa.Column('node_type', sa.String(255), nullable=False),
            sa.Column('node_name', sa.String(255), nullable=False),
            sa.Column('status', sa.String(255), nullable=False),
            sa.Column('branch', sa.String(255)),
            sa.Column('inputs', sa.Text, nullable=False),
            sa.Column('outputs', sa.Text, nullable=False),
            sa.Column('error', sa.Text),
            sa.Column('started_at', sa.DateTime, nullable=False),
            sa.Column('finished_at', sa.DateTime),
        )
    if 'workflow_memory' not in existing:
        op.create_table(
            'workflow_memory',
            sa.Column(
                'workspace_uuid',
                sa.String(36),
                sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
                index=True,
                primary_key=True,
            ),
            sa.Column('workflow_uuid', sa.String(255), primary_key=True),
            sa.Column('session_id', sa.String(255), primary_key=True),
            sa.Column('key', sa.String(255), primary_key=True),
            sa.Column('value', sa.Text, nullable=False),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        )

    if conn.dialect.name == 'postgresql':
        for table in TABLES:
            op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
            op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
            op.execute(f'DROP POLICY IF EXISTS langbot_workspace_isolation ON {table}')
            op.execute(f"""CREATE POLICY langbot_workspace_isolation ON {table}
                USING (workspace_uuid::text = NULLIF(current_setting('langbot.workspace_uuid', true), ''))
                WITH CHECK (workspace_uuid::text = NULLIF(current_setting('langbot.workspace_uuid', true), ''))""")


def downgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    for table in reversed(TABLES):
        if table in existing:
            op.drop_table(table)
