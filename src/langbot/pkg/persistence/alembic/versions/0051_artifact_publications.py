"""Record explicit caller-owned producer output publication policies."""

import sqlalchemy as sa
from alembic import op

revision = '0051_artifact_publications'
down_revision = '0050_artifact_managers'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    existing = set(sa.inspect(conn).get_table_names())
    if 'workspaces' not in existing:
        return
    if 'artifact_publications' not in existing:
        op.create_table(
            'artifact_publications',
            sa.Column(
                'workspace_uuid', sa.String(36), sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'), primary_key=True
            ),
            sa.Column('producer_type', sa.String(32), primary_key=True),
            sa.Column('producer_id', sa.String(255), primary_key=True),
            sa.Column('manager_type', sa.String(16), nullable=False),
            sa.Column('manager_id', sa.String(36), nullable=False),
            sa.Column('revision', sa.String(36), nullable=False),
            sa.Column('enabled', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint(
                "producer_type IN ('agent', 'pipeline', 'event_processor')", name='ck_artifact_publication_producer'
            ),
            sa.CheckConstraint("manager_type IN ('account', 'api_key')", name='ck_artifact_publication_manager'),
        )
    if conn.dialect.name == 'postgresql':
        tenant = "workspace_uuid::text = NULLIF(current_setting('langbot.workspace_uuid', true), '')"
        op.execute(sa.text('ALTER TABLE artifact_publications ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE artifact_publications FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text('DROP POLICY IF EXISTS langbot_workspace_isolation ON artifact_publications'))
        op.execute(
            sa.text(
                f'CREATE POLICY langbot_workspace_isolation ON artifact_publications USING ({tenant}) WITH CHECK ({tenant})'
            )
        )


def downgrade():
    conn = op.get_bind()
    if 'artifact_publications' in sa.inspect(conn).get_table_names():
        op.drop_table('artifact_publications')
