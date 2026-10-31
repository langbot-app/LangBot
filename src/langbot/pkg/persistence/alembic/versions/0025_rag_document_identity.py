"""Persist engine document identity separately from the public Host file UUID."""

from alembic import op
import sqlalchemy as sa

revision = '0025_rag_document_identity'
down_revision = '0024_passkey_credentials'
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'knowledge_base_files' not in inspector.get_table_names():
        return
    columns = {column['name'] for column in inspector.get_columns('knowledge_base_files')}
    if 'engine_document_id' not in columns:
        # Legacy upstream IDs cannot be inferred from Host UUIDs or user config.
        op.add_column('knowledge_base_files', sa.Column('engine_document_id', sa.Text(), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'knowledge_base_files' not in inspector.get_table_names():
        return
    columns = {column['name'] for column in inspector.get_columns('knowledge_base_files')}
    if 'engine_document_id' in columns:
        op.drop_column('knowledge_base_files', 'engine_document_id')
