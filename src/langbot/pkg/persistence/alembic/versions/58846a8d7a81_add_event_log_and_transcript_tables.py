"""add_event_log_and_transcript_tables

Revision ID: 58846a8d7a81
Revises: 0004_migrate_runner_config
Create Date: 2026-05-23 15:41:47.030841
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '58846a8d7a81'
down_revision = '0004_migrate_runner_config'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create event_log table
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
    with op.batch_alter_table('event_log', schema=None) as batch_op:
        batch_op.create_index('ix_event_log_event_id', ['event_id'], unique=True)
        batch_op.create_index('ix_event_log_event_type', ['event_type'], unique=False)
        batch_op.create_index('ix_event_log_bot_id', ['bot_id'], unique=False)
        batch_op.create_index('ix_event_log_conversation_id', ['conversation_id'], unique=False)
        batch_op.create_index('ix_event_log_run_id', ['run_id'], unique=False)

    # Create transcript table
    op.create_table(
        'transcript',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('transcript_id', sa.String(255), nullable=False, unique=True),
        sa.Column('event_id', sa.String(255), nullable=False),
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

    # Create indexes for transcript
    with op.batch_alter_table('transcript', schema=None) as batch_op:
        batch_op.create_index('ix_transcript_transcript_id', ['transcript_id'], unique=True)
        batch_op.create_index('ix_transcript_event_id', ['event_id'], unique=False)
        batch_op.create_index('ix_transcript_conversation_id', ['conversation_id'], unique=False)
        batch_op.create_index('ix_transcript_conversation_seq', ['conversation_id', 'seq'], unique=False)
        batch_op.create_index('ix_transcript_conversation_created', ['conversation_id', 'created_at'], unique=False)
        batch_op.create_index('ix_transcript_run_id', ['run_id'], unique=False)


def downgrade() -> None:
    # Drop transcript table
    with op.batch_alter_table('transcript', schema=None) as batch_op:
        batch_op.drop_index('ix_transcript_run_id')
        batch_op.drop_index('ix_transcript_conversation_created')
        batch_op.drop_index('ix_transcript_conversation_seq')
        batch_op.drop_index('ix_transcript_conversation_id')
        batch_op.drop_index('ix_transcript_event_id')
        batch_op.drop_index('ix_transcript_transcript_id')

    op.drop_table('transcript')

    # Drop event_log table
    with op.batch_alter_table('event_log', schema=None) as batch_op:
        batch_op.drop_index('ix_event_log_run_id')
        batch_op.drop_index('ix_event_log_conversation_id')
        batch_op.drop_index('ix_event_log_bot_id')
        batch_op.drop_index('ix_event_log_event_type')
        batch_op.drop_index('ix_event_log_event_id')

    op.drop_table('event_log')
