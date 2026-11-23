"""Drop the obsolete Agent enabled state.

Revision ID: 0023_drop_agent_enabled
Revises: 0022_merge_agent_reasoning_heads
Create Date: 2026-08-25
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '0023_drop_agent_enabled'
down_revision = '0022_merge_agent_reasoning_heads'
branch_labels = None
depends_on = None


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if table_name not in inspector.get_table_names():
        return False
    return any(column['name'] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if _column_exists(inspector, 'agents', 'enabled'):
        with op.batch_alter_table('agents') as batch_op:
            batch_op.drop_column('enabled')


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'agents' in inspector.get_table_names() and not _column_exists(inspector, 'agents', 'enabled'):
        with op.batch_alter_table('agents') as batch_op:
            batch_op.add_column(sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()))
