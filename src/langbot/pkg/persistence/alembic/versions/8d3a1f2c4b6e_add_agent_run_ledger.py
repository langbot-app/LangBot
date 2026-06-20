"""add agent run ledger

Revision ID: 8d3a1f2c4b6e
Revises: 7b2c1d9e4f30
Create Date: 2026-06-15
"""

from alembic import op
import sqlalchemy as sa


revision = '8d3a1f2c4b6e'
down_revision = '7b2c1d9e4f30'
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    return index_name in {index['name'] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return column_name in {column['name'] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not _table_exists(table_name) or _column_exists(table_name, column.name):
        return
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.add_column(column)


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str], *, unique: bool = False) -> None:
    if not _table_exists(table_name) or _index_exists(table_name, index_name):
        return
    existing_columns = {column['name'] for column in sa.inspect(op.get_bind()).get_columns(table_name)}
    if not set(columns).issubset(existing_columns):
        return
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.create_index(index_name, columns, unique=unique)


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    if not _table_exists(table_name) or not _index_exists(table_name, index_name):
        return
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.drop_index(index_name)


def upgrade() -> None:
    if not _table_exists('agent_run'):
        op.create_table(
            'agent_run',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('run_id', sa.String(255), nullable=False, unique=True),
            sa.Column('event_id', sa.String(255), nullable=True),
            sa.Column('agent_id', sa.String(255), nullable=True),
            sa.Column('binding_id', sa.String(255), nullable=True),
            sa.Column('runner_id', sa.String(255), nullable=False),
            sa.Column('conversation_id', sa.String(255), nullable=True),
            sa.Column('thread_id', sa.String(255), nullable=True),
            sa.Column('workspace_id', sa.String(255), nullable=True),
            sa.Column('bot_id', sa.String(255), nullable=True),
            sa.Column('status', sa.String(50), nullable=False),
            sa.Column('status_reason', sa.Text(), nullable=True),
            sa.Column('queue_name', sa.String(255), nullable=True),
            sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('requested_runtime_id', sa.String(255), nullable=True),
            sa.Column('claimed_by_runtime_id', sa.String(255), nullable=True),
            sa.Column('claim_token', sa.String(255), nullable=True),
            sa.Column('claim_lease_expires_at', sa.DateTime(), nullable=True),
            sa.Column('dispatch_attempts', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('last_claimed_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('finished_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.Column('deadline_at', sa.DateTime(), nullable=True),
            sa.Column('cancel_requested_at', sa.DateTime(), nullable=True),
            sa.Column('usage_json', sa.Text(), nullable=True),
            sa.Column('cost_json', sa.Text(), nullable=True),
            sa.Column('authorization_json', sa.Text(), nullable=True),
            sa.Column('metadata_json', sa.Text(), nullable=True),
        )
    else:
        _add_column_if_missing('agent_run', sa.Column('queue_name', sa.String(255), nullable=True))
        _add_column_if_missing(
            'agent_run', sa.Column('priority', sa.Integer(), nullable=False, server_default='0')
        )
        _add_column_if_missing('agent_run', sa.Column('requested_runtime_id', sa.String(255), nullable=True))
        _add_column_if_missing('agent_run', sa.Column('claimed_by_runtime_id', sa.String(255), nullable=True))
        _add_column_if_missing('agent_run', sa.Column('claim_token', sa.String(255), nullable=True))
        _add_column_if_missing('agent_run', sa.Column('claim_lease_expires_at', sa.DateTime(), nullable=True))
        _add_column_if_missing(
            'agent_run', sa.Column('dispatch_attempts', sa.Integer(), nullable=False, server_default='0')
        )
        _add_column_if_missing('agent_run', sa.Column('last_claimed_at', sa.DateTime(), nullable=True))

    _create_index_if_missing('agent_run', 'ix_agent_run_run_id', ['run_id'], unique=True)
    _create_index_if_missing('agent_run', 'ix_agent_run_event_id', ['event_id'])
    _create_index_if_missing('agent_run', 'ix_agent_run_binding_id', ['binding_id'])
    _create_index_if_missing('agent_run', 'ix_agent_run_runner_id', ['runner_id'])
    _create_index_if_missing('agent_run', 'ix_agent_run_conversation_id', ['conversation_id'])
    _create_index_if_missing('agent_run', 'ix_agent_run_bot_id', ['bot_id'])
    _create_index_if_missing('agent_run', 'ix_agent_run_status', ['status'])
    _create_index_if_missing('agent_run', 'ix_agent_run_queue_name', ['queue_name'])
    _create_index_if_missing('agent_run', 'ix_agent_run_requested_runtime_id', ['requested_runtime_id'])
    _create_index_if_missing('agent_run', 'ix_agent_run_claimed_by_runtime_id', ['claimed_by_runtime_id'])
    _create_index_if_missing('agent_run', 'ix_agent_run_claim_token', ['claim_token'])
    _create_index_if_missing('agent_run', 'ix_agent_run_claim_lease_expires_at', ['claim_lease_expires_at'])
    _create_index_if_missing(
        'agent_run',
        'ix_agent_run_scope_status',
        ['bot_id', 'workspace_id', 'conversation_id', 'thread_id', 'status'],
    )
    _create_index_if_missing('agent_run', 'ix_agent_run_runner_status', ['runner_id', 'status'])
    _create_index_if_missing('agent_run', 'ix_agent_run_queue_claim', ['queue_name', 'status', 'priority', 'id'])

    if not _table_exists('agent_run_event'):
        op.create_table(
            'agent_run_event',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('run_id', sa.String(255), nullable=False),
            sa.Column('sequence', sa.Integer(), nullable=False),
            sa.Column('type', sa.String(100), nullable=False),
            sa.Column('data_json', sa.Text(), nullable=True),
            sa.Column('usage_json', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.Column('source', sa.String(50), nullable=True),
            sa.Column('metadata_json', sa.Text(), nullable=True),
            sa.UniqueConstraint('run_id', 'sequence', name='uq_agent_run_event_run_sequence'),
        )

    _create_index_if_missing('agent_run_event', 'ix_agent_run_event_run_id', ['run_id'])
    _create_index_if_missing('agent_run_event', 'ix_agent_run_event_type', ['type'])
    _create_index_if_missing(
        'agent_run_event',
        'ix_agent_run_event_run_sequence',
        ['run_id', 'sequence'],
    )

    if not _table_exists('agent_runtime'):
        op.create_table(
            'agent_runtime',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('runtime_id', sa.String(255), nullable=False, unique=True),
            sa.Column('status', sa.String(50), nullable=False),
            sa.Column('display_name', sa.String(255), nullable=True),
            sa.Column('endpoint', sa.String(1024), nullable=True),
            sa.Column('version', sa.String(255), nullable=True),
            sa.Column('capabilities_json', sa.Text(), nullable=True),
            sa.Column('labels_json', sa.Text(), nullable=True),
            sa.Column('metadata_json', sa.Text(), nullable=True),
            sa.Column('last_heartbeat_at', sa.DateTime(), nullable=True),
            sa.Column('heartbeat_deadline_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
        )

    _create_index_if_missing('agent_runtime', 'ix_agent_runtime_runtime_id', ['runtime_id'], unique=True)
    _create_index_if_missing('agent_runtime', 'ix_agent_runtime_status', ['status'])
    _create_index_if_missing('agent_runtime', 'ix_agent_runtime_last_heartbeat_at', ['last_heartbeat_at'])
    _create_index_if_missing('agent_runtime', 'ix_agent_runtime_heartbeat_deadline_at', ['heartbeat_deadline_at'])


def downgrade() -> None:
    _drop_index_if_exists('agent_runtime', 'ix_agent_runtime_heartbeat_deadline_at')
    _drop_index_if_exists('agent_runtime', 'ix_agent_runtime_last_heartbeat_at')
    _drop_index_if_exists('agent_runtime', 'ix_agent_runtime_status')
    _drop_index_if_exists('agent_runtime', 'ix_agent_runtime_runtime_id')
    if _table_exists('agent_runtime'):
        op.drop_table('agent_runtime')

    _drop_index_if_exists('agent_run_event', 'ix_agent_run_event_run_sequence')
    _drop_index_if_exists('agent_run_event', 'ix_agent_run_event_type')
    _drop_index_if_exists('agent_run_event', 'ix_agent_run_event_run_id')
    if _table_exists('agent_run_event'):
        op.drop_table('agent_run_event')

    _drop_index_if_exists('agent_run', 'ix_agent_run_queue_claim')
    _drop_index_if_exists('agent_run', 'ix_agent_run_claim_lease_expires_at')
    _drop_index_if_exists('agent_run', 'ix_agent_run_claim_token')
    _drop_index_if_exists('agent_run', 'ix_agent_run_claimed_by_runtime_id')
    _drop_index_if_exists('agent_run', 'ix_agent_run_requested_runtime_id')
    _drop_index_if_exists('agent_run', 'ix_agent_run_queue_name')
    _drop_index_if_exists('agent_run', 'ix_agent_run_runner_status')
    _drop_index_if_exists('agent_run', 'ix_agent_run_scope_status')
    _drop_index_if_exists('agent_run', 'ix_agent_run_status')
    _drop_index_if_exists('agent_run', 'ix_agent_run_bot_id')
    _drop_index_if_exists('agent_run', 'ix_agent_run_conversation_id')
    _drop_index_if_exists('agent_run', 'ix_agent_run_runner_id')
    _drop_index_if_exists('agent_run', 'ix_agent_run_binding_id')
    _drop_index_if_exists('agent_run', 'ix_agent_run_event_id')
    _drop_index_if_exists('agent_run', 'ix_agent_run_run_id')
    if _table_exists('agent_run'):
        op.drop_table('agent_run')
