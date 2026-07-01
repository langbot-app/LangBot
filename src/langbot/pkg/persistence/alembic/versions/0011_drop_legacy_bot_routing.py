"""drop legacy bot pipeline routing columns

Revision ID: 0011_drop_legacy_bot_routing
Revises: 0010_merge_mcp_resource_agent_heads
Create Date: 2026-07-01
"""

from alembic import op
import sqlalchemy as sa


revision = '0011_drop_legacy_bot_routing'
down_revision = '0010_merge_mcp_resource_agent_heads'
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return column_name in {column['name'] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    if not _table_exists('bots'):
        return
    existing_columns = {column['name'] for column in sa.inspect(op.get_bind()).get_columns('bots')}
    columns_to_drop = [
        column_name
        for column_name in ('use_pipeline_name', 'use_pipeline_uuid', 'pipeline_routing_rules')
        if column_name in existing_columns
    ]
    if not columns_to_drop:
        return

    with op.batch_alter_table('bots', schema=None) as batch_op:
        for column_name in columns_to_drop:
            batch_op.drop_column(column_name)


def downgrade() -> None:
    if not _table_exists('bots'):
        return

    with op.batch_alter_table('bots', schema=None) as batch_op:
        if not _column_exists('bots', 'use_pipeline_name'):
            batch_op.add_column(sa.Column('use_pipeline_name', sa.String(255), nullable=True))
        if not _column_exists('bots', 'use_pipeline_uuid'):
            batch_op.add_column(sa.Column('use_pipeline_uuid', sa.String(255), nullable=True))
        if not _column_exists('bots', 'pipeline_routing_rules'):
            batch_op.add_column(sa.Column('pipeline_routing_rules', sa.JSON(), nullable=False, server_default='[]'))
