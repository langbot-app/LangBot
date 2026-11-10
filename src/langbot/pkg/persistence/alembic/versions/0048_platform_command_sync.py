"""Store platform command synchronization state."""

from alembic import op
import sqlalchemy as sa

revision = '0048_platform_command_sync'
down_revision = '0047_bot_command_settings'
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('bots'):
        return
    if 'platform_command_sync' in {column['name'] for column in inspector.get_columns('bots')}:
        return
    with op.batch_alter_table('bots') as batch:
        batch.add_column(sa.Column('platform_command_sync', sa.JSON(), nullable=False, server_default='{}'))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('bots'):
        return
    if 'platform_command_sync' not in {column['name'] for column in inspector.get_columns('bots')}:
        return
    with op.batch_alter_table('bots') as batch:
        batch.drop_column('platform_command_sync')
