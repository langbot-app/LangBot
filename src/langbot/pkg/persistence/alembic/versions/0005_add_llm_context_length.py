"""add llm model context length

Revision ID: 0005_add_llm_context_length
Revises: 0004_add_mcp_readme
Create Date: 2026-06-07
"""

import sqlalchemy as sa
from alembic import op

revision = '0005_add_llm_context_length'
down_revision = '0004_add_mcp_readme'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add ``context_length`` to llm_models if the table exists and the column is
    # missing. The table may have been created by create_all() with the column
    # already present on fresh installs, so guard against duplicate-add; it may
    # also be absent entirely (e.g. migrating a truly empty DB), so guard against
    # a missing table too.
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'llm_models' not in inspector.get_table_names():
        return
    columns = {column['name'] for column in inspector.get_columns('llm_models')}
    if 'context_length' not in columns:
        op.add_column('llm_models', sa.Column('context_length', sa.Integer(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'llm_models' not in inspector.get_table_names():
        return
    columns = {column['name'] for column in inspector.get_columns('llm_models')}
    if 'context_length' in columns:
        op.drop_column('llm_models', 'context_length')
