"""add workflow tables and bot binding fields

Revision ID: 0009_add_workflow_tables
Revises: 0008_mcp_resource_prefs
Create Date: 2026-07-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0009_add_workflow_tables'
down_revision = '0008_mcp_resource_prefs'
branch_labels = None
depends_on = None


def _table_exists(conn: sa.Connection, table_name: str) -> bool:
    return table_name in sa.inspect(conn).get_table_names()


def _has_column(conn: sa.Connection, table_name: str, column_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return column_name in {column['name'] for column in sa.inspect(conn).get_columns(table_name)}


def _has_index_for_columns(conn: sa.Connection, table_name: str, columns: tuple[str, ...]) -> bool:
    if not _table_exists(conn, table_name):
        return False
    for index in sa.inspect(conn).get_indexes(table_name):
        if tuple(index.get('column_names') or ()) == columns:
            return True
    return False


def _ensure_index(conn: sa.Connection, table_name: str, index_name: str, columns: list[str]) -> None:
    if _has_index_for_columns(conn, table_name, tuple(columns)):
        return
    op.create_index(index_name, table_name, columns)


def _create_workflow_tables(conn: sa.Connection) -> None:
    if not _table_exists(conn, 'workflows'):
        op.create_table(
            'workflows',
            sa.Column('uuid', sa.String(255), primary_key=True),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('emoji', sa.String(10), nullable=True),
            sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('definition', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column('global_config', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column(
                'extensions_preferences',
                sa.JSON(),
                nullable=False,
                server_default=sa.text(
                    '\'{"enable_all_plugins": true, "enable_all_mcp_servers": true, "plugins": [], "mcp_servers": []}\''
                ),
            ),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    if not _table_exists(conn, 'workflow_versions'):
        op.create_table(
            'workflow_versions',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('workflow_uuid', sa.String(255), nullable=False),
            sa.Column('version', sa.Integer(), nullable=False),
            sa.Column('definition', sa.JSON(), nullable=False),
            sa.Column('global_config', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('created_by', sa.String(255), nullable=True),
            sa.UniqueConstraint('workflow_uuid', 'version', name='uq_workflow_version'),
        )

    if not _table_exists(conn, 'workflow_triggers'):
        op.create_table(
            'workflow_triggers',
            sa.Column('uuid', sa.String(255), primary_key=True),
            sa.Column('workflow_uuid', sa.String(255), nullable=False),
            sa.Column('type', sa.String(50), nullable=False),
            sa.Column('config', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    if not _table_exists(conn, 'workflow_executions'):
        op.create_table(
            'workflow_executions',
            sa.Column('uuid', sa.String(255), primary_key=True),
            sa.Column('workflow_uuid', sa.String(255), nullable=False),
            sa.Column('workflow_version', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(20), nullable=False),
            sa.Column('trigger_type', sa.String(50), nullable=True),
            sa.Column('trigger_data', sa.JSON(), nullable=True),
            sa.Column('variables', sa.JSON(), nullable=True),
            sa.Column('start_time', sa.DateTime(), nullable=True),
            sa.Column('end_time', sa.DateTime(), nullable=True),
            sa.Column('error', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    if not _table_exists(conn, 'workflow_node_executions'):
        op.create_table(
            'workflow_node_executions',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('execution_uuid', sa.String(255), nullable=False),
            sa.Column('node_id', sa.String(100), nullable=False),
            sa.Column('node_type', sa.String(50), nullable=False),
            sa.Column('status', sa.String(20), nullable=False),
            sa.Column('inputs', sa.JSON(), nullable=True),
            sa.Column('outputs', sa.JSON(), nullable=True),
            sa.Column('start_time', sa.DateTime(), nullable=True),
            sa.Column('end_time', sa.DateTime(), nullable=True),
            sa.Column('error', sa.Text(), nullable=True),
            sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        )

    if not _table_exists(conn, 'workflow_scheduled_jobs'):
        op.create_table(
            'workflow_scheduled_jobs',
            sa.Column('uuid', sa.String(255), primary_key=True),
            sa.Column('trigger_uuid', sa.String(255), nullable=False),
            sa.Column('cron_expression', sa.String(100), nullable=True),
            sa.Column('next_run_time', sa.DateTime(), nullable=True),
            sa.Column('last_run_time', sa.DateTime(), nullable=True),
            sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        )

    _ensure_index(conn, 'workflow_versions', 'ix_workflow_versions_workflow_uuid', ['workflow_uuid'])
    _ensure_index(conn, 'workflow_triggers', 'ix_workflow_triggers_workflow_uuid', ['workflow_uuid'])
    _ensure_index(conn, 'workflow_executions', 'ix_workflow_executions_workflow_uuid', ['workflow_uuid'])
    _ensure_index(
        conn,
        'workflow_node_executions',
        'ix_workflow_node_executions_execution_uuid',
        ['execution_uuid'],
    )
    _ensure_index(conn, 'workflow_scheduled_jobs', 'ix_workflow_scheduled_jobs_trigger_uuid', ['trigger_uuid'])


def _add_bot_binding_fields(conn: sa.Connection) -> None:
    if not _table_exists(conn, 'bots'):
        return

    if not _has_column(conn, 'bots', 'binding_type'):
        op.add_column(
            'bots',
            sa.Column('binding_type', sa.String(32), nullable=False, server_default='pipeline'),
        )

    if not _has_column(conn, 'bots', 'binding_uuid'):
        op.add_column('bots', sa.Column('binding_uuid', sa.String(64), nullable=True))

    conn.execute(
        sa.text("""
        UPDATE bots
        SET binding_uuid = use_pipeline_uuid
        WHERE use_pipeline_uuid IS NOT NULL
          AND use_pipeline_uuid != ''
          AND (binding_uuid IS NULL OR binding_uuid = '')
        """)
    )
    conn.execute(
        sa.text("""
        UPDATE bots
        SET binding_type = 'pipeline'
        WHERE binding_uuid IS NOT NULL
          AND binding_uuid != ''
          AND (binding_type IS NULL OR binding_type = '')
        """)
    )


def upgrade() -> None:
    conn = op.get_bind()
    _create_workflow_tables(conn)
    _add_bot_binding_fields(conn)


def downgrade() -> None:
    conn = op.get_bind()

    if _has_column(conn, 'bots', 'binding_uuid'):
        with op.batch_alter_table('bots') as batch_op:
            batch_op.drop_column('binding_uuid')
    if _has_column(conn, 'bots', 'binding_type'):
        with op.batch_alter_table('bots') as batch_op:
            batch_op.drop_column('binding_type')

    for table_name in (
        'workflow_scheduled_jobs',
        'workflow_node_executions',
        'workflow_executions',
        'workflow_triggers',
        'workflow_versions',
        'workflows',
    ):
        if _table_exists(conn, table_name):
            op.drop_table(table_name)
