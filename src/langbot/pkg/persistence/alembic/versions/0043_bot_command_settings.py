"""Add command_settings to bots table.

Revision ID: 0043_bot_command_settings
Revises: 0042_sqlite_incremental_vacuum
Create Date: 2026-10-31
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '0043_bot_command_settings'
down_revision = '0042_sqlite_incremental_vacuum'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'bots' not in tables:
        return

    existing_columns = {column['name'] for column in inspector.get_columns('bots')}
    if 'command_settings' not in existing_columns:
        with op.batch_alter_table('bots') as batch_op:
            batch_op.add_column(
                sa.Column(
                    'command_settings',
                    sa.JSON(),
                    nullable=False,
                    server_default='{"enabled": true, "prefixes": ["/"], "processors": []}',
                )
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'bots' not in tables:
        return

    existing_columns = {column['name'] for column in inspector.get_columns('bots')}
    if 'command_settings' not in existing_columns:
        return

    with op.batch_alter_table('bots') as batch_op:
        batch_op.drop_column('command_settings')
