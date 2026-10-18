"""Index incremental expiry of historical inline images."""

from alembic import op
import sqlalchemy as sa

revision = '0041_inline_media_ttl_indexes'
down_revision = '0040_conversation_page_index'
branch_labels = None
depends_on = None

INDEXES = (
    ('monitoring_messages', ['workspace_uuid', 'timestamp', 'id']),
    ('event_log', ['workspace_id', 'created_at', 'id']),
    ('agent_run', ['workspace_id', 'created_at', 'id']),
    ('agent_run_event', ['created_at', 'id', 'run_id']),
    ('transcript', ['workspace_id', 'created_at', 'id']),
)


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for table, columns in INDEXES:
        if not inspector.has_table(table):
            continue
        name = f'ix_{table}_media_ttl'
        if name not in {index['name'] for index in inspector.get_indexes(table)}:
            op.create_index(name, table, columns)


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for table, _ in reversed(INDEXES):
        if not inspector.has_table(table):
            continue
        name = f'ix_{table}_media_ttl'
        if name in {index['name'] for index in inspector.get_indexes(table)}:
            op.drop_index(name, table_name=table)
