"""Allow structured wizard progress in metadata values."""

from alembic import op
import sqlalchemy as sa

revision = '0037_metadata_text'
down_revision = '0036_execution_host_leases'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for table in ('metadata', 'workspace_metadata'):
        if inspector.has_table(table):
            with op.batch_alter_table(table) as batch:
                batch.alter_column('value', existing_type=sa.String(255), type_=sa.Text(), existing_nullable=True)


def downgrade():
    # Keep the widened type: narrowing would destroy valid saved progress.
    pass
