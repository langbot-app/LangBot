"""add llm model context length

Revision ID: 0004_add_llm_model_context_length
Revises: 0003_add_rerank_models
Create Date: 2026-06-07
"""

import sqlalchemy as sa
from alembic import op

revision = '0004_add_llm_model_context_length'
down_revision = '0003_add_rerank_models'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = {column['name'] for column in inspector.get_columns('llm_models')}
    if 'context_length' not in columns:
        op.add_column('llm_models', sa.Column('context_length', sa.Integer(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = {column['name'] for column in inspector.get_columns('llm_models')}
    if 'context_length' in columns:
        op.drop_column('llm_models', 'context_length')
