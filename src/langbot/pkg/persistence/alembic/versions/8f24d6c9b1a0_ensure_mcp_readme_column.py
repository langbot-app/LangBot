"""ensure mcp_servers readme column exists

Revision ID: 8f24d6c9b1a0
Revises: 7b2c1d9e4f30
Create Date: 2026-06-13
"""

from alembic import op
import sqlalchemy as sa


revision = '8f24d6c9b1a0'
down_revision = '7b2c1d9e4f30'
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    return column_name in {column['name'] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    if not _table_exists('mcp_servers') or _column_exists('mcp_servers', 'readme'):
        return
    with op.batch_alter_table('mcp_servers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('readme', sa.Text(), nullable=False, server_default=''))


def downgrade() -> None:
    if not _table_exists('mcp_servers') or not _column_exists('mcp_servers', 'readme'):
        return
    with op.batch_alter_table('mcp_servers', schema=None) as batch_op:
        batch_op.drop_column('readme')
