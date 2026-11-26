"""Add Agent access mode and scoped access grants."""

import sqlalchemy as sa
from alembic import op

revision = '0057_agent_access'
down_revision = '0056_daily_usage_quota_warning'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'agents' in inspector.get_table_names():
        columns = {column['name'] for column in inspector.get_columns('agents')}
        if 'access_mode' not in columns:
            with op.batch_alter_table('agents') as batch:
                batch.add_column(sa.Column('access_mode', sa.String(32), nullable=False, server_default='all_members'))
    tables = set(inspector.get_table_names())
    if 'agent_access_grants' not in tables and {'agents', 'workspaces'} <= tables:
        op.create_table(
            'agent_access_grants',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column(
                'workspace_uuid', sa.String(36), sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'), nullable=False
            ),
            sa.Column('agent_uuid', sa.String(255), sa.ForeignKey('agents.uuid', ondelete='CASCADE'), nullable=False),
            sa.Column('subject_type', sa.String(16), nullable=False),
            sa.Column('subject_id', sa.String(255), nullable=False),
            sa.Column('can_use', sa.Boolean(), nullable=False),
            sa.UniqueConstraint(
                'workspace_uuid', 'agent_uuid', 'subject_type', 'subject_id', name='uq_agent_access_grant_subject'
            ),
        )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if 'agent_access_grants' in inspector.get_table_names():
        op.drop_table('agent_access_grants')
    if 'agents' in inspector.get_table_names():
        columns = {column['name'] for column in inspector.get_columns('agents')}
        if 'access_mode' in columns:
            with op.batch_alter_table('agents') as batch:
                batch.drop_column('access_mode')
