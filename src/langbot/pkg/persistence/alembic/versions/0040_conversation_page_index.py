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
    # Fresh databases already receive this index from ORM metadata.
    if INDEX not in {index['name'] for index in sa.inspect(op.get_bind()).get_indexes(TABLE)}:
        op.create_index(INDEX, TABLE, ['workspace_uuid', 'bot_id', 'session_id', 'timestamp', 'id'])


def downgrade():
    if INDEX in {index['name'] for index in sa.inspect(op.get_bind()).get_indexes(TABLE)}:
        op.drop_index(INDEX, table_name=TABLE)
