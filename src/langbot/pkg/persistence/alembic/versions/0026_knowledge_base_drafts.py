"""Add deferred initialization state for knowledge bases."""

from alembic import op
import sqlalchemy as sa


revision = '0026_knowledge_base_drafts'
down_revision = '0025_bot_plugin_processors'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table('knowledge_bases'):
        return
    if 'initialized' not in {column['name'] for column in inspector.get_columns('knowledge_bases')}:
        op.add_column(
            'knowledge_bases',
            sa.Column('initialized', sa.Boolean(), nullable=False, server_default=sa.true()),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table('knowledge_bases'):
        return
    if 'initialized' in {column['name'] for column in inspector.get_columns('knowledge_bases')}:
        op.drop_column('knowledge_bases', 'initialized')
