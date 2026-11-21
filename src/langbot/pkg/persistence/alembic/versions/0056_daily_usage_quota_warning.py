"""Record when the daily message quota warning email was sent."""

import sqlalchemy as sa
from alembic import op

revision = '0056_daily_usage_quota_warning'
down_revision = '0055_pgvector_dimension_2048'
branch_labels = None
depends_on = None

TABLE = 'workspace_message_usage_daily'
COLUMN = 'quota_warning_at'


def _columns(conn) -> set[str] | None:
    inspector = sa.inspect(conn)
    if TABLE not in inspector.get_table_names():
        return None
    return {column['name'] for column in inspector.get_columns(TABLE)}


def upgrade():
    columns = _columns(op.get_bind())
    if columns is not None and COLUMN not in columns:
        op.add_column(TABLE, sa.Column(COLUMN, sa.DateTime(), nullable=True))


def downgrade():
    columns = _columns(op.get_bind())
    if columns is not None and COLUMN in columns:
        with op.batch_alter_table(TABLE) as batch:
            batch.drop_column(COLUMN)
