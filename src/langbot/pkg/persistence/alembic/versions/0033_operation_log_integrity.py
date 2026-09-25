"""add tamper-evidence columns to workspace operation logs

Revision ID: 0033_operation_log_integrity
Revises: 0032_workspace_operation_logs
Create Date: 2026-09-25

Adds the append-only hash chain (``record_hash`` / ``prev_hash``) and the
``dedupe_key`` used to collapse repeated read observations. Fresh databases
already receive these columns from SQLAlchemy ``create_all``; this revision
upgrades existing databases and is guarded so neither path fails.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0033_operation_log_integrity'
down_revision = '0032_workspace_operation_logs'
branch_labels = None
depends_on = None


_TABLE_NAME = 'workspace_operation_logs'
_NEW_COLUMNS = (
    sa.Column('record_hash', sa.String(64), nullable=True),
    sa.Column('prev_hash', sa.String(64), nullable=True),
    sa.Column('dedupe_key', sa.String(64), nullable=True),
)
_DEDUPE_INDEX = 'ix_workspace_operation_logs_workspace_dedupe'


def upgrade() -> None:
    conn = op.get_bind()
    if _TABLE_NAME not in set(sa.inspect(conn).get_table_names()):
        return

    existing = {column['name'] for column in sa.inspect(conn).get_columns(_TABLE_NAME)}
    missing = [column for column in _NEW_COLUMNS if column.name not in existing]
    if missing:
        with op.batch_alter_table(_TABLE_NAME, recreate='auto') as batch:
            for column in missing:
                batch.add_column(column)

    index_names = {index['name'] for index in sa.inspect(conn).get_indexes(_TABLE_NAME)}
    if _DEDUPE_INDEX not in index_names:
        op.create_index(
            _DEDUPE_INDEX,
            _TABLE_NAME,
            ['workspace_uuid', 'dedupe_key', 'created_at'],
            unique=False,
        )


def downgrade() -> None:
    conn = op.get_bind()
    if _TABLE_NAME not in set(sa.inspect(conn).get_table_names()):
        return

    index_names = {index['name'] for index in sa.inspect(conn).get_indexes(_TABLE_NAME)}
    if _DEDUPE_INDEX in index_names:
        op.drop_index(_DEDUPE_INDEX, table_name=_TABLE_NAME)

    existing = {column['name'] for column in sa.inspect(conn).get_columns(_TABLE_NAME)}
    removable = [column.name for column in _NEW_COLUMNS if column.name in existing]
    if removable:
        with op.batch_alter_table(_TABLE_NAME, recreate='auto') as batch:
            for name in removable:
                batch.drop_column(name)
