"""Index execution leases, conversation paging, and historical inline image expiry."""

from alembic import op
import sqlalchemy as sa

revision = '0039_execution_lease_indexes'
down_revision = '0038_llm_call_details'
branch_labels = None
depends_on = None

INDEXES = (
    ('agent_run', 'ix_agent_run_workspace_status_lease', ['workspace_id', 'status', 'execution_lease_expires_at']),
    (
        'monitoring_messages',
        'ix_monitoring_messages_workspace_status_lease',
        ['workspace_uuid', 'status', 'execution_lease_expires_at'],
    ),
    (
        'monitoring_messages',
        'ix_monitoring_messages_conversation_page',
        ['workspace_uuid', 'bot_id', 'session_id', 'timestamp', 'id'],
    ),
    ('monitoring_messages', 'ix_monitoring_messages_media_ttl', ['workspace_uuid', 'timestamp', 'id']),
    ('event_log', 'ix_event_log_media_ttl', ['workspace_id', 'created_at', 'id']),
    ('agent_run', 'ix_agent_run_media_ttl', ['workspace_id', 'created_at', 'id']),
    ('agent_run_event', 'ix_agent_run_event_media_ttl', ['created_at', 'id', 'run_id']),
    ('transcript', 'ix_transcript_media_ttl', ['workspace_id', 'created_at', 'id']),
)


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for table, index, columns in INDEXES:
        if not inspector.has_table(table):
            continue
        if not set(columns) <= {column['name'] for column in inspector.get_columns(table)}:
            continue
        # Fresh installations create these indexes from ORM metadata before migrations.
        if index not in {item['name'] for item in inspector.get_indexes(table)}:
            op.create_index(index, table, columns)


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for table, index, _ in reversed(INDEXES):
        if not inspector.has_table(table):
            continue
        if index in {item['name'] for item in inspector.get_indexes(table)}:
            op.drop_index(index, table_name=table)
