"""Persist daily Workspace message reservations."""

import sqlalchemy as sa
from alembic import op

revision = '0054_daily_message_usage'
down_revision = '0053_knowledge_artifact_sources'
branch_labels = None
depends_on = None

TABLE = 'workspace_message_usage_daily'


def upgrade():
    conn = op.get_bind()
    tables = sa.inspect(conn).get_table_names()
    if 'workspaces' not in tables:
        return
    if TABLE not in tables:
        op.create_table(
            TABLE,
            sa.Column(
                'workspace_uuid', sa.String(36), sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'), primary_key=True
            ),
            sa.Column('usage_date', sa.Date(), primary_key=True),
            sa.Column('message_count', sa.Integer(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
    if conn.dialect.name == 'postgresql':
        predicate = "workspace_uuid::text = NULLIF(current_setting('langbot.workspace_uuid', true), '')"
        op.execute(f'ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY')
        op.execute(f'DROP POLICY IF EXISTS langbot_workspace_isolation ON {TABLE}')
        op.execute(f'CREATE POLICY langbot_workspace_isolation ON {TABLE} USING ({predicate}) WITH CHECK ({predicate})')


def downgrade():
    if sa.inspect(op.get_bind()).has_table(TABLE):
        op.drop_table(TABLE)
