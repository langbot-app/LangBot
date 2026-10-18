"""Page conversation identities without reading historical message payloads."""

from alembic import op
import sqlalchemy as sa

revision = '0040_conversation_page_index'
down_revision = '0039_execution_lease_indexes'
branch_labels = None
depends_on = None

TABLE = 'monitoring_messages'
INDEX = 'ix_monitoring_messages_conversation_page'


def upgrade():
    inspector = sa.inspect(op.get_bind())
    # Fresh databases already receive this index from ORM metadata.
    if inspector.has_table(TABLE) and INDEX not in {index['name'] for index in inspector.get_indexes(TABLE)}:
        op.create_index(INDEX, TABLE, ['workspace_uuid', 'bot_id', 'session_id', 'timestamp', 'id'])


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table(TABLE) and INDEX in {index['name'] for index in inspector.get_indexes(TABLE)}:
        op.drop_index(INDEX, table_name=TABLE)
