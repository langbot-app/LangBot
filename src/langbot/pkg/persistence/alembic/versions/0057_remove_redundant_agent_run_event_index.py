"""Remove the duplicate AgentRunEvent sequence index."""

import sqlalchemy as sa
from alembic import op


revision = '0057_remove_redundant_agent_run_event_index'
down_revision = '0056_daily_usage_quota_warning'
branch_labels = None
depends_on = None

TABLE = 'agent_run_event'
INDEX = 'ix_agent_run_event_run_sequence'


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table(TABLE) and INDEX in {item['name'] for item in inspector.get_indexes(TABLE)}:
        op.drop_index(INDEX, table_name=TABLE)


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table(TABLE) and INDEX not in {item['name'] for item in inspector.get_indexes(TABLE)}:
        op.create_index(INDEX, TABLE, ['run_id', 'sequence'])
