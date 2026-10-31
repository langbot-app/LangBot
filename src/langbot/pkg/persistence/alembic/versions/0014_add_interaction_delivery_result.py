"""Persist interaction presentation handles for in-place updates.

Revision ID: 0014_interaction_delivery
Revises: 0013_agent_interactions
"""

from alembic import op
import sqlalchemy as sa


revision = '0014_interaction_delivery'
down_revision = '0013_agent_interactions'
branch_labels = None
depends_on = None


def _column_names() -> set[str]:
    bind = op.get_bind()
    if 'agent_interaction' not in sa.inspect(bind).get_table_names():
        return set()
    return {column['name'] for column in sa.inspect(bind).get_columns('agent_interaction')}


def upgrade() -> None:
    columns = _column_names()
    if not columns:
        return
    if 'delivery_result_json' not in columns:
        op.add_column('agent_interaction', sa.Column('delivery_result_json', sa.Text(), nullable=True))
    if 'replaces_interaction_id' not in columns:
        op.add_column(
            'agent_interaction',
            sa.Column('replaces_interaction_id', sa.String(length=255), nullable=True),
        )


def downgrade() -> None:
    columns = _column_names()
    if 'replaces_interaction_id' in columns:
        op.drop_column('agent_interaction', 'replaces_interaction_id')
    if 'delivery_result_json' in columns:
        op.drop_column('agent_interaction', 'delivery_result_json')
