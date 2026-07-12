"""add monitoring tool calls

Revision ID: 0012_monitoring_tool_calls
Revises: 0011_drop_legacy_bot_routing
Create Date: 2026-07-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0012_monitoring_tool_calls'
down_revision = '0011_drop_legacy_bot_routing'
branch_labels = None
depends_on = None


_INDEXES = {
    'ix_monitoring_tool_calls_timestamp': ['timestamp'],
    'ix_monitoring_tool_calls_bot_id': ['bot_id'],
    'ix_monitoring_tool_calls_pipeline_id': ['pipeline_id'],
    'ix_monitoring_tool_calls_session_id': ['session_id'],
    'ix_monitoring_tool_calls_message_id': ['message_id'],
}


def _table_exists() -> bool:
    return 'monitoring_tool_calls' in sa.inspect(op.get_bind()).get_table_names()


def _index_names() -> set[str]:
    if not _table_exists():
        return set()
    return {index['name'] for index in sa.inspect(op.get_bind()).get_indexes('monitoring_tool_calls')}


def upgrade() -> None:
    if not _table_exists():
        op.create_table(
            'monitoring_tool_calls',
            sa.Column('id', sa.String(255), primary_key=True),
            sa.Column('timestamp', sa.DateTime(), nullable=False),
            sa.Column('tool_name', sa.String(255), nullable=False),
            sa.Column('tool_source', sa.String(50), nullable=False),
            sa.Column('duration', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(50), nullable=False),
            sa.Column('bot_id', sa.String(255), nullable=False),
            sa.Column('bot_name', sa.String(255), nullable=False),
            sa.Column('pipeline_id', sa.String(255), nullable=False),
            sa.Column('pipeline_name', sa.String(255), nullable=False),
            sa.Column('session_id', sa.String(255), nullable=True),
            sa.Column('message_id', sa.String(255), nullable=True),
            sa.Column('arguments', sa.Text(), nullable=True),
            sa.Column('result', sa.Text(), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
        )

    existing_indexes = _index_names()
    for index_name, columns in _INDEXES.items():
        if index_name not in existing_indexes:
            op.create_index(index_name, 'monitoring_tool_calls', columns, unique=False)


def downgrade() -> None:
    if _table_exists():
        op.drop_table('monitoring_tool_calls')
