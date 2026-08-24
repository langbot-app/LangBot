"""add transcript scope columns

Revision ID: 7b2c1d9e4f30
Revises: 6dfd3dd7f0c7
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa


revision = '7b2c1d9e4f30'
down_revision = '6dfd3dd7f0c7'
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    return column_name in {column['name'] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _index_exists(table_name: str, index_name: str) -> bool:
    return index_name in {index['name'] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not _table_exists(table_name) or _column_exists(table_name, column.name):
        return
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.add_column(column)


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    if not _table_exists(table_name) or _index_exists(table_name, index_name):
        return
    existing_columns = {column['name'] for column in sa.inspect(op.get_bind()).get_columns(table_name)}
    if not set(columns).issubset(existing_columns):
        return
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.create_index(index_name, columns)


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    if not _table_exists(table_name) or not _index_exists(table_name, index_name):
        return
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.drop_index(index_name)


def upgrade() -> None:
    _add_column_if_missing('transcript', sa.Column('bot_id', sa.String(255), nullable=True))
    _add_column_if_missing('transcript', sa.Column('workspace_id', sa.String(255), nullable=True))
    _create_index_if_missing('transcript', 'ix_transcript_bot_id', ['bot_id'])
    _create_index_if_missing(
        'transcript',
        'ix_transcript_scope_seq',
        ['bot_id', 'workspace_id', 'conversation_id', 'thread_id', 'seq'],
    )
    _drop_index_if_exists('agent_runner_state', 'ix_agent_runner_state_scope_key')
    _create_index_if_missing('agent_runner_state', 'ix_agent_runner_state_scope_key_lookup', ['scope_key'])


def downgrade() -> None:
    _drop_index_if_exists('agent_runner_state', 'ix_agent_runner_state_scope_key_lookup')
    _create_index_if_missing('agent_runner_state', 'ix_agent_runner_state_scope_key', ['scope_key'])
    _drop_index_if_exists('transcript', 'ix_transcript_scope_seq')
    _drop_index_if_exists('transcript', 'ix_transcript_bot_id')
    if not _table_exists('transcript'):
        return
    existing_columns = {column['name'] for column in sa.inspect(op.get_bind()).get_columns('transcript')}
    with op.batch_alter_table('transcript', schema=None) as batch_op:
        if 'workspace_id' in existing_columns:
            batch_op.drop_column('workspace_id')
        if 'bot_id' in existing_columns:
            batch_op.drop_column('bot_id')
