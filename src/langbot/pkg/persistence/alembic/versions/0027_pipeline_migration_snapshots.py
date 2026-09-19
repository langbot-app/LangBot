"""Create the manual migration journal only; never convert pipeline JSON."""

from alembic import op
import sqlalchemy as sa

revision = '0027_pipeline_migration'
down_revision = '0026_merge_master_beta'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    table = 'pipeline_migration_snapshots'
    if not sa.inspect(bind).has_table(table):
        op.create_table(
            table,
            sa.Column('uuid', sa.String(36), primary_key=True),
            sa.Column(
                'workspace_uuid', sa.String(36), sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'), nullable=False
            ),
            sa.Column('pipeline_uuid', sa.String(255), nullable=False),
            sa.Column('source_fingerprint', sa.String(64), nullable=False),
            sa.Column('target_fingerprint', sa.String(64), nullable=False),
            sa.Column('planner_version', sa.String(64), nullable=False),
            sa.Column('source_snapshot', sa.JSON(), nullable=False),
            sa.Column('state', sa.String(32), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(
                ['workspace_uuid', 'pipeline_uuid'],
                ['legacy_pipelines.workspace_uuid', 'legacy_pipelines.uuid'],
                name='fk_pipeline_migration_workspace_pipeline',
                ondelete='CASCADE',
            ),
            sa.UniqueConstraint(
                'workspace_uuid', 'pipeline_uuid', 'source_fingerprint', name='uq_pipeline_migration_source'
            ),
            sa.CheckConstraint("state IN ('activation_pending', 'active')", name='ck_pipeline_migration_state'),
        )
        op.create_index('ix_pipeline_migration_workspace_pipeline', table, ['workspace_uuid', 'pipeline_uuid'])
    if bind.dialect.name == 'postgresql':
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(f'DROP POLICY IF EXISTS langbot_workspace_isolation ON {table}')
        expression = "workspace_uuid = NULLIF(current_setting('langbot.workspace_uuid', true), '')"
        op.execute(
            f'CREATE POLICY langbot_workspace_isolation ON {table} FOR ALL TO PUBLIC '
            f'USING ({expression}) WITH CHECK ({expression})'
        )


def downgrade():
    op.drop_table('pipeline_migration_snapshots')
