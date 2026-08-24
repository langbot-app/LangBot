"""Add Host-owned structured interaction records.

Revision ID: 0013_agent_interactions
Revises: 0012_monitoring_tool_calls
"""

from alembic import op
import sqlalchemy as sa


revision = '0013_agent_interactions'
down_revision = '0012_monitoring_tool_calls'
branch_labels = None
depends_on = None


_INDEXES = {
    'ix_agent_interaction_actor_id': (['actor_id'], False),
    'ix_agent_interaction_binding_id': (['binding_id'], False),
    'ix_agent_interaction_bot_id': (['bot_id'], False),
    'ix_agent_interaction_callback_token_hash': (['callback_token_hash'], True),
    'ix_agent_interaction_conversation_id': (['conversation_id'], False),
    'ix_agent_interaction_expires_at': (['expires_at'], False),
    'ix_agent_interaction_processor_id': (['processor_id'], False),
    'ix_agent_interaction_processor_status': (['processor_type', 'processor_id', 'status'], False),
    'ix_agent_interaction_processor_type': (['processor_type'], False),
    'ix_agent_interaction_run_id': (['run_id'], False),
    'ix_agent_interaction_runner_id': (['runner_id'], False),
    'ix_agent_interaction_scope_status': (['bot_id', 'conversation_id', 'actor_id', 'status'], False),
    'ix_agent_interaction_status': (['status'], False),
}


def _table_exists() -> bool:
    return 'agent_interaction' in sa.inspect(op.get_bind()).get_table_names()


def _index_names() -> set[str]:
    if not _table_exists():
        return set()
    return {index['name'] for index in sa.inspect(op.get_bind()).get_indexes('agent_interaction')}


def upgrade() -> None:
    if not _table_exists():
        op.create_table(
            'agent_interaction',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('interaction_id', sa.String(length=255), nullable=False),
            sa.Column('run_id', sa.String(length=255), nullable=False),
            sa.Column('binding_id', sa.String(length=255), nullable=False),
            sa.Column('runner_id', sa.String(length=255), nullable=False),
            sa.Column('processor_type', sa.String(length=50), nullable=False),
            sa.Column('processor_id', sa.String(length=255), nullable=False),
            sa.Column('bot_id', sa.String(length=255), nullable=True),
            sa.Column('workspace_id', sa.String(length=255), nullable=True),
            sa.Column('conversation_id', sa.String(length=255), nullable=True),
            sa.Column('thread_id', sa.String(length=255), nullable=True),
            sa.Column('actor_id', sa.String(length=255), nullable=True),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('request_json', sa.Text(), nullable=False),
            sa.Column('delivery_target_json', sa.Text(), nullable=True),
            sa.Column('callback_token_hash', sa.String(length=64), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.Column('submitted_at', sa.DateTime(), nullable=True),
            sa.Column('submission_json', sa.Text(), nullable=True),
            sa.Column('status_reason', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('callback_token_hash'),
            sa.UniqueConstraint('run_id', 'interaction_id', name='uq_agent_interaction_run_interaction'),
        )

    existing_indexes = _index_names()
    for index_name, (columns, unique) in _INDEXES.items():
        if index_name not in existing_indexes:
            op.create_index(index_name, 'agent_interaction', columns, unique=unique)


def downgrade() -> None:
    if _table_exists():
        op.drop_table('agent_interaction')
