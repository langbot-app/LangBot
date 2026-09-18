"""Add private management-assistant conversations."""

import sqlalchemy as sa
from alembic import op

revision = '0025_assistant_conversations'
down_revision = '0024_passkey_credentials'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if 'assistant_conversations' not in sa.inspect(conn).get_table_names():
        op.create_table(
            'assistant_conversations',
            sa.Column('uuid', sa.String(36), primary_key=True),
            sa.Column(
                'workspace_uuid', sa.String(36), sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'), nullable=False
            ),
            sa.Column('account_uuid', sa.String(36), sa.ForeignKey('users.uuid', ondelete='CASCADE'), nullable=False),
            sa.Column('revision', sa.Integer, nullable=False, server_default='0'),
            sa.Column('status', sa.String(20), nullable=False, server_default='ready'),
            sa.Column('messages', sa.JSON, nullable=False),
            sa.Column('error', sa.Text),
            sa.Column('model_name', sa.String(255)),
            sa.Column('model_uuid', sa.String(36)),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        )
    if conn.dialect.name == 'postgresql':
        op.execute('ALTER TABLE assistant_conversations ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE assistant_conversations FORCE ROW LEVEL SECURITY')
        op.execute('DROP POLICY IF EXISTS langbot_workspace_isolation ON assistant_conversations')
        op.execute("""CREATE POLICY langbot_workspace_isolation ON assistant_conversations
            USING (workspace_uuid::text = NULLIF(current_setting('langbot.workspace_uuid', true), ''))
            WITH CHECK (workspace_uuid::text = NULLIF(current_setting('langbot.workspace_uuid', true), ''))""")


def downgrade() -> None:
    op.drop_table('assistant_conversations')
