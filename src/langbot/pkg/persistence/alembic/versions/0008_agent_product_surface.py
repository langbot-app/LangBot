"""Add Agent product surface tables.

Revision ID: 0008_agent_product_surface
Revises: 0007_merge_agent_mcp_heads
Create Date: 2026-06-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '0008_agent_product_surface'
down_revision = '0007_merge_agent_mcp_heads'
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(column['name'] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, 'agents'):
        op.create_table(
            'agents',
            sa.Column('uuid', sa.String(length=255), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('description', sa.String(length=255), nullable=False, server_default=''),
            sa.Column('emoji', sa.String(length=10), nullable=True),
            sa.Column('kind', sa.String(length=50), nullable=False, server_default='agent'),
            sa.Column('component_ref', sa.String(length=255), nullable=True),
            sa.Column('config', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('supported_event_patterns', sa.JSON(), nullable=False, server_default='["*"]'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint('uuid'),
            sa.UniqueConstraint('uuid'),
        )

    if _table_exists(inspector, 'bots') and not _column_exists(inspector, 'bots', 'event_bindings'):
        with op.batch_alter_table('bots') as batch_op:
            batch_op.add_column(sa.Column('event_bindings', sa.JSON(), nullable=False, server_default='[]'))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, 'bots') and _column_exists(inspector, 'bots', 'event_bindings'):
        with op.batch_alter_table('bots') as batch_op:
            batch_op.drop_column('event_bindings')

    if _table_exists(inspector, 'agents'):
        op.drop_table('agents')
