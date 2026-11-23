"""add readme column to mcp_servers

Revision ID: 0004_add_mcp_readme
Revises: 0003_add_rerank_models
Create Date: 2026-06-06
"""

import sqlalchemy as sa
from alembic import op

revision = '0004_add_mcp_readme'
down_revision = '0003_add_rerank_models'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add ``readme`` to mcp_servers if the table exists and the column is missing
    # (the table may have been created by create_all() with the column already
    # present on fresh installs, so guard against duplicate-add).
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'mcp_servers' not in inspector.get_table_names():
        return
    columns = {col['name'] for col in inspector.get_columns('mcp_servers')}
    if 'readme' not in columns:
        op.add_column(
            'mcp_servers',
            sa.Column('readme', sa.Text(), nullable=False, server_default=''),
        )


def downgrade() -> None:
    op.drop_column('mcp_servers', 'readme')
