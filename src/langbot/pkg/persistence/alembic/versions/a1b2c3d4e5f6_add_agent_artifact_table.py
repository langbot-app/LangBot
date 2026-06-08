"""add_agent_artifact_table

Revision ID: a1b2c3d4e5f6
Revises: 58846a8d7a81
Create Date: 2026-05-23 20:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'a1b2c3d4e5f6'
down_revision = '58846a8d7a81'
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    return index_name in {index['name'] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str], *, unique: bool = False) -> None:
    if not _table_exists(table_name) or _index_exists(table_name, index_name):
        return
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.create_index(index_name, columns, unique=unique)


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    if not _table_exists(table_name) or not _index_exists(table_name, index_name):
        return
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.drop_index(index_name)


def upgrade() -> None:
    # Create agent_artifact table
    if not _table_exists('agent_artifact'):
        op.create_table(
            'agent_artifact',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('artifact_id', sa.String(255), nullable=False, unique=True),
            sa.Column('artifact_type', sa.String(50), nullable=False),
            sa.Column('mime_type', sa.String(255), nullable=True),
            sa.Column('name', sa.String(255), nullable=True),
            sa.Column('size_bytes', sa.BigInteger(), nullable=True),
            sa.Column('sha256', sa.String(64), nullable=True),
            sa.Column('source', sa.String(50), nullable=False),
            sa.Column('storage_key', sa.String(255), nullable=True),
            sa.Column('storage_type', sa.String(50), nullable=False, server_default='binary_storage'),
            sa.Column('conversation_id', sa.String(255), nullable=True),
            sa.Column('run_id', sa.String(255), nullable=True),
            sa.Column('runner_id', sa.String(255), nullable=True),
            sa.Column('bot_id', sa.String(255), nullable=True),
            sa.Column('workspace_id', sa.String(255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.Column('metadata_json', sa.Text(), nullable=True),
        )

    # Create indexes for agent_artifact
    _create_index_if_missing('agent_artifact', 'ix_agent_artifact_artifact_id', ['artifact_id'], unique=True)
    _create_index_if_missing('agent_artifact', 'ix_agent_artifact_conversation_id', ['conversation_id'])
    _create_index_if_missing('agent_artifact', 'ix_agent_artifact_run_id', ['run_id'])


def downgrade() -> None:
    # Drop agent_artifact table
    _drop_index_if_exists('agent_artifact', 'ix_agent_artifact_run_id')
    _drop_index_if_exists('agent_artifact', 'ix_agent_artifact_conversation_id')
    _drop_index_if_exists('agent_artifact', 'ix_agent_artifact_artifact_id')

    if _table_exists('agent_artifact'):
        op.drop_table('agent_artifact')
