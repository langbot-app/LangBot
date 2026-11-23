"""add rerank_models table

Revision ID: 0003_add_rerank_models
Revises: 0002_sample
Create Date: 2026-04-19
"""

import sqlalchemy as sa
from alembic import op

revision = '0003_add_rerank_models'
down_revision = '0002_sample'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if table already exists (may have been created by create_all())
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'rerank_models' not in inspector.get_table_names():
        op.create_table(
            'rerank_models',
            sa.Column('uuid', sa.String(255), primary_key=True, unique=True),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('provider_uuid', sa.String(255), nullable=False),
            sa.Column('extra_args', sa.JSON, nullable=False, server_default='{}'),
            sa.Column('prefered_ranking', sa.Integer, nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table('rerank_models')
