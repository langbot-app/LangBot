"""add llm reasoning config

Revision ID: 0018_llm_reasoning_config
Revises: 0017_oss_workspace_identity
Create Date: 2026-07-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0018_llm_reasoning_config'
down_revision = '0017_oss_workspace_identity'
branch_labels = None
depends_on = None


_LLM_MODELS = sa.table(
    'llm_models',
    sa.column('reasoning_config', sa.JSON()),
)


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'llm_models' not in inspector.get_table_names():
        return

    columns = {column['name'] for column in inspector.get_columns('llm_models')}
    if 'reasoning_config' in columns:
        return

    op.add_column(
        'llm_models',
        sa.Column(
            'reasoning_config',
            sa.JSON(),
            nullable=True,
            server_default=sa.text('\'{"level":"provider_default"}\''),
        ),
    )
    conn.execute(_LLM_MODELS.update().values(reasoning_config={'level': 'provider_default'}))
    with op.batch_alter_table('llm_models') as batch_op:
        batch_op.alter_column('reasoning_config', existing_type=sa.JSON(), nullable=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'llm_models' not in inspector.get_table_names():
        return
    columns = {column['name'] for column in inspector.get_columns('llm_models')}
    if 'reasoning_config' in columns:
        with op.batch_alter_table('llm_models') as batch_op:
            batch_op.drop_column('reasoning_config')
