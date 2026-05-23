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


def upgrade() -> None:
    # Create agent_artifact table
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
    with op.batch_alter_table('agent_artifact', schema=None) as batch_op:
        batch_op.create_index('ix_agent_artifact_artifact_id', ['artifact_id'], unique=True)
        batch_op.create_index('ix_agent_artifact_conversation_id', ['conversation_id'], unique=False)
        batch_op.create_index('ix_agent_artifact_run_id', ['run_id'], unique=False)


def downgrade() -> None:
    # Drop agent_artifact table
    with op.batch_alter_table('agent_artifact', schema=None) as batch_op:
        batch_op.drop_index('ix_agent_artifact_run_id')
        batch_op.drop_index('ix_agent_artifact_conversation_id')
        batch_op.drop_index('ix_agent_artifact_artifact_id')

    op.drop_table('agent_artifact')
