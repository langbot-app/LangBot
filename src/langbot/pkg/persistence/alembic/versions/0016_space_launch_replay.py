"""add durable replay protection for signed Space launch assertions

Revision ID: 0016_space_launch_replay
Revises: 0015_cloud_core_collab
Create Date: 2026-07-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0016_space_launch_replay'
down_revision = '0015_cloud_core_collab'
branch_labels = None
depends_on = None

_TABLE = 'space_launch_assertion_consumptions'
_POLICY = 'langbot_directory_projection'
_SETTING = "NULLIF(current_setting('langbot.directory_instance_uuid', true), '')"


def upgrade() -> None:
    conn = op.get_bind()
    if _TABLE not in set(sa.inspect(conn).get_table_names()):
        op.create_table(
            _TABLE,
            sa.Column('instance_uuid', sa.String(255), nullable=False),
            sa.Column('jti', sa.String(255), nullable=False),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('consumed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint('instance_uuid', 'jti'),
        )
        op.create_index(
            'ix_space_launch_assertion_consumptions_expiry',
            _TABLE,
            ['instance_uuid', 'expires_at'],
            unique=False,
        )
    if conn.dialect.name == 'postgresql':
        table = conn.dialect.identifier_preparer.quote(_TABLE)
        policy = conn.dialect.identifier_preparer.quote(_POLICY)
        expression = f'instance_uuid::text = {_SETTING}'
        op.execute(sa.text(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'DROP POLICY IF EXISTS {policy} ON {table}'))
        op.execute(
            sa.text(
                f'CREATE POLICY {policy} ON {table} AS PERMISSIVE FOR ALL TO PUBLIC '
                f'USING ({expression}) WITH CHECK ({expression})'
            )
        )


def downgrade() -> None:
    if _TABLE in set(sa.inspect(op.get_bind()).get_table_names()):
        op.drop_table(_TABLE)
