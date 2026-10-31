"""Add isolated server-only Codex credentials and tenant RLS.

Revision ID: 0022_codex_credentials
Revises: 0021_merge_reasoning_config
"""

from alembic import op
import sqlalchemy as sa

revision = '0022_codex_credentials'
down_revision = '0021_merge_reasoning_config'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    # Fresh startup creates ORM metadata before running Alembic.
    if 'codex_credentials' not in sa.inspect(conn).get_table_names():
        op.create_table(
            'codex_credentials',
            sa.Column('provider_uuid', sa.String(255), primary_key=True),
            sa.Column('workspace_uuid', sa.String(36), nullable=False),
            sa.Column('payload', sa.JSON(), nullable=False),
            sa.Column('version', sa.Integer(), nullable=False),
            sa.Column('lease_owner', sa.String(64), nullable=True),
            sa.Column('lease_until', sa.Float(), nullable=False),
            sa.ForeignKeyConstraint(
                ['workspace_uuid', 'provider_uuid'],
                ['model_providers.workspace_uuid', 'model_providers.uuid'],
                name='fk_codex_credentials_workspace_provider',
                ondelete='CASCADE',
            ),
        )
        op.create_index('ix_codex_credentials_workspace', 'codex_credentials', ['workspace_uuid'])
    if conn.dialect.name == 'postgresql':
        op.execute('ALTER TABLE codex_credentials ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE codex_credentials FORCE ROW LEVEL SECURITY')
        op.execute('DROP POLICY IF EXISTS langbot_workspace_isolation ON codex_credentials')
        expression = "workspace_uuid::text = NULLIF(current_setting('langbot.workspace_uuid', true), '')"
        op.execute(
            f'CREATE POLICY langbot_workspace_isolation ON codex_credentials '
            f'FOR ALL USING ({expression}) WITH CHECK ({expression})'
        )


def downgrade() -> None:
    op.drop_table('codex_credentials')
