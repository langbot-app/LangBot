"""add_event_log_and_transcript_tables

Revision ID: 58846a8d7a81
Revises: 0005_migrate_runner_config
Create Date: 2026-05-23 15:41:47.030841
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '58846a8d7a81'
down_revision = '0005_migrate_runner_config'
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    return index_name in {index['name'] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _column_exists(table_name: str, column_name: str) -> bool:
    return column_name in {column['name'] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not _table_exists(table_name) or _column_exists(table_name, column.name):
        return
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.add_column(column)


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str], *, unique: bool = False) -> None:
    if not _table_exists(table_name) or _index_exists(table_name, index_name):
        return
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.create_index(index_name, columns, unique=unique)


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    if not _table_exists(table_name) or not _index_exists(table_name, index_name):
        return
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.drop_index(index_name)


def upgrade() -> None:
    # Create event_log table
    if not _table_exists('event_log'):
        op.create_table(
            'event_log',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('event_id', sa.String(255), nullable=False, unique=True),
            sa.Column('event_type', sa.String(100), nullable=False),
            sa.Column('event_time', sa.DateTime(), nullable=True),
            sa.Column('source', sa.String(50), nullable=False),
            sa.Column('bot_id', sa.String(255), nullable=True),
            sa.Column('workspace_id', sa.String(255), nullable=True),
            sa.Column('conversation_id', sa.String(255), nullable=True),
            sa.Column('thread_id', sa.String(255), nullable=True),
            sa.Column('actor_type', sa.String(50), nullable=True),
            sa.Column('actor_id', sa.String(255), nullable=True),
            sa.Column('actor_name', sa.String(255), nullable=True),
            sa.Column('subject_type', sa.String(50), nullable=True),
            sa.Column('subject_id', sa.String(255), nullable=True),
            sa.Column('input_summary', sa.Text(), nullable=True),
            sa.Column('input_json', sa.Text(), nullable=True),
            sa.Column('raw_ref', sa.String(255), nullable=True),
            sa.Column('run_id', sa.String(255), nullable=True),
            sa.Column('runner_id', sa.String(255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.Column('metadata_json', sa.Text(), nullable=True),
        )

    # Create indexes for event_log
    _create_index_if_missing('event_log', 'ix_event_log_event_id', ['event_id'], unique=True)
    _create_index_if_missing('event_log', 'ix_event_log_event_type', ['event_type'])
    _create_index_if_missing('event_log', 'ix_event_log_bot_id', ['bot_id'])
    _create_index_if_missing('event_log', 'ix_event_log_conversation_id', ['conversation_id'])
    _create_index_if_missing('event_log', 'ix_event_log_run_id', ['run_id'])

    # Create transcript table
    if not _table_exists('transcript'):
        op.create_table(
            'transcript',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('transcript_id', sa.String(255), nullable=False, unique=True),
            sa.Column('event_id', sa.String(255), nullable=False),
            sa.Column('bot_id', sa.String(255), nullable=True),
            sa.Column('workspace_id', sa.String(255), nullable=True),
            sa.Column('conversation_id', sa.String(255), nullable=False),
            sa.Column('thread_id', sa.String(255), nullable=True),
            sa.Column('role', sa.String(50), nullable=False),
            sa.Column('item_type', sa.String(50), nullable=False, server_default='message'),
            sa.Column('content', sa.Text(), nullable=True),
            sa.Column('content_json', sa.Text(), nullable=True),
            sa.Column('artifact_refs_json', sa.Text(), nullable=True),
            sa.Column('seq', sa.Integer(), nullable=False),
            sa.Column('run_id', sa.String(255), nullable=True),
            sa.Column('runner_id', sa.String(255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.Column('metadata_json', sa.Text(), nullable=True),
        )
    else:
        _add_column_if_missing('transcript', sa.Column('bot_id', sa.String(255), nullable=True))
        _add_column_if_missing('transcript', sa.Column('workspace_id', sa.String(255), nullable=True))

    # Create indexes for transcript
    _create_index_if_missing('transcript', 'ix_transcript_transcript_id', ['transcript_id'], unique=True)
    _create_index_if_missing('transcript', 'ix_transcript_event_id', ['event_id'])
    _create_index_if_missing('transcript', 'ix_transcript_bot_id', ['bot_id'])
    _create_index_if_missing('transcript', 'ix_transcript_conversation_id', ['conversation_id'])
    _create_index_if_missing('transcript', 'ix_transcript_conversation_seq', ['conversation_id', 'seq'])
    _create_index_if_missing('transcript', 'ix_transcript_conversation_created', ['conversation_id', 'created_at'])
    _create_index_if_missing(
        'transcript',
        'ix_transcript_scope_seq',
        ['bot_id', 'workspace_id', 'conversation_id', 'thread_id', 'seq'],
    )
    _create_index_if_missing('transcript', 'ix_transcript_run_id', ['run_id'])


def downgrade() -> None:
    # Drop transcript table
    _drop_index_if_exists('transcript', 'ix_transcript_run_id')
    _drop_index_if_exists('transcript', 'ix_transcript_scope_seq')
    _drop_index_if_exists('transcript', 'ix_transcript_conversation_created')
    _drop_index_if_exists('transcript', 'ix_transcript_conversation_seq')
    _drop_index_if_exists('transcript', 'ix_transcript_conversation_id')
    _drop_index_if_exists('transcript', 'ix_transcript_bot_id')
    _drop_index_if_exists('transcript', 'ix_transcript_event_id')
    _drop_index_if_exists('transcript', 'ix_transcript_transcript_id')

    if _table_exists('transcript'):
        op.drop_table('transcript')

    # Drop event_log table
    _drop_index_if_exists('event_log', 'ix_event_log_run_id')
    _drop_index_if_exists('event_log', 'ix_event_log_conversation_id')
    _drop_index_if_exists('event_log', 'ix_event_log_bot_id')
    _drop_index_if_exists('event_log', 'ix_event_log_event_type')
    _drop_index_if_exists('event_log', 'ix_event_log_event_id')

    if _table_exists('event_log'):
        op.drop_table('event_log')
