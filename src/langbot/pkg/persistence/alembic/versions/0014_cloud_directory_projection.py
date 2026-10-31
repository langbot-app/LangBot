"""add the Cloud directory projection persistence boundary

Revision ID: 0014_cloud_directory
Revises: 0013_tenant_pgvector
Create Date: 2026-07-24

The open Core projector receives already-verified control-plane data and is the
only runtime path allowed to mutate projected Workspace directory rows. Its
transaction-local instance setting is intentionally distinct from both normal
Workspace scope and the read-only instance discovery scope.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0014_cloud_directory'
down_revision = '0013_tenant_pgvector'
branch_labels = None
depends_on = None


_STATE_TABLE = 'directory_projection_states'
_INBOX_TABLE = 'directory_projection_inbox'
_DIRECTORY_POLICY_NAME = 'langbot_directory_projection'
_TENANT_POLICY_NAME = 'langbot_workspace_isolation'
_LOCAL_WRITE_POLICY_NAME = 'langbot_workspace_local_directory_write'
_DIRECTORY_SETTING = 'langbot.directory_instance_uuid'
_TENANT_SETTING = 'langbot.workspace_uuid'
_PROJECTED_TENANT_TABLES = (
    'workspaces',
    'workspace_memberships',
    'workspace_execution_states',
)


def _setting(name: str) -> str:
    return f"NULLIF(current_setting('{name}', true), '')"


def _quote(conn: sa.Connection, identifier: str) -> str:
    return conn.dialect.identifier_preparer.quote(identifier)


def _create_tables(conn: sa.Connection) -> None:
    existing_tables = set(sa.inspect(conn).get_table_names())
    if _STATE_TABLE not in existing_tables:
        op.create_table(
            _STATE_TABLE,
            sa.Column('instance_uuid', sa.String(255), nullable=False),
            sa.Column('cursor', sa.BigInteger(), server_default='0', nullable=False),
            sa.Column('snapshot_coverage_cursor', sa.BigInteger(), server_default='0', nullable=False),
            sa.Column('snapshot_fingerprint', sa.Text(), nullable=False),
            sa.Column('last_applied_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint(
                'cursor >= 0',
                name='ck_directory_projection_state_cursor',
            ),
            sa.CheckConstraint(
                'snapshot_coverage_cursor >= 0 AND snapshot_coverage_cursor <= cursor',
                name='ck_directory_projection_state_snapshot_coverage',
            ),
            sa.CheckConstraint(
                'length(snapshot_fingerprint) = 64',
                name='ck_directory_projection_state_fingerprint',
            ),
            sa.PrimaryKeyConstraint('instance_uuid'),
        )
    if _INBOX_TABLE not in existing_tables:
        op.create_table(
            _INBOX_TABLE,
            sa.Column('instance_uuid', sa.String(255), nullable=False),
            sa.Column('event_uuid', sa.String(36), nullable=False),
            sa.Column('cursor', sa.BigInteger(), nullable=False),
            sa.Column('event_type', sa.String(128), nullable=False),
            sa.Column('revision', sa.BigInteger(), nullable=False),
            sa.Column('fingerprint', sa.Text(), nullable=False),
            sa.Column(
                'received_at',
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint(
                'cursor > 0',
                name='ck_directory_projection_inbox_cursor',
            ),
            sa.CheckConstraint(
                'revision > 0',
                name='ck_directory_projection_inbox_revision',
            ),
            sa.CheckConstraint(
                'length(fingerprint) = 64',
                name='ck_directory_projection_inbox_fingerprint',
            ),
            sa.PrimaryKeyConstraint('instance_uuid', 'event_uuid'),
            sa.UniqueConstraint(
                'instance_uuid',
                'cursor',
                name='uq_directory_projection_inbox_cursor',
            ),
        )
        op.create_index(
            'ix_directory_projection_inbox_pending',
            _INBOX_TABLE,
            ['instance_uuid', 'applied_at', 'cursor'],
            unique=False,
        )


def _drop_policy(conn: sa.Connection, table_name: str, policy_name: str) -> None:
    table = _quote(conn, table_name)
    policy = _quote(conn, policy_name)
    op.execute(sa.text(f'DROP POLICY IF EXISTS {policy} ON {table}'))


def _create_policy(
    conn: sa.Connection,
    table_name: str,
    policy_name: str,
    expression: str,
    *,
    command: str = 'ALL',
) -> None:
    table = _quote(conn, table_name)
    policy = _quote(conn, policy_name)
    _drop_policy(conn, table_name, policy_name)
    op.execute(sa.text(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY'))
    if command == 'SELECT':
        sql = f'CREATE POLICY {policy} ON {table} AS PERMISSIVE FOR SELECT TO PUBLIC USING ({expression})'
    elif command == 'ALL':
        sql = (
            f'CREATE POLICY {policy} ON {table} AS PERMISSIVE FOR ALL TO PUBLIC '
            f'USING ({expression}) WITH CHECK ({expression})'
        )
    else:  # pragma: no cover - migration-local invariant.
        raise AssertionError(f'Unsupported RLS policy command: {command}')
    op.execute(sa.text(sql))


def _install_postgres_policies(conn: sa.Connection) -> None:
    existing_tables = set(sa.inspect(conn).get_table_names())
    required_tables = set(_PROJECTED_TENANT_TABLES) | {_STATE_TABLE, _INBOX_TABLE}
    missing_tables = required_tables - existing_tables
    if missing_tables:
        raise RuntimeError(
            f'Cannot enable Cloud directory projection RLS before all required tables exist: {sorted(missing_tables)!r}'
        )

    directory_setting = _setting(_DIRECTORY_SETTING)
    tenant_setting = _setting(_TENANT_SETTING)
    directory_expressions = {
        'workspaces': (f"instance_uuid::text = {directory_setting} AND source = 'cloud_projection'"),
        'workspace_memberships': (
            'EXISTS ('
            'SELECT 1 FROM workspaces AS directory_workspace '
            'WHERE directory_workspace.uuid = workspace_memberships.workspace_uuid '
            f'AND directory_workspace.instance_uuid::text = {directory_setting} '
            "AND directory_workspace.source = 'cloud_projection'"
            ')'
        ),
        'workspace_execution_states': (
            f"instance_uuid::text = {directory_setting} AND source = 'cloud' AND EXISTS ("
            'SELECT 1 FROM workspaces AS directory_workspace '
            'WHERE directory_workspace.uuid = workspace_execution_states.workspace_uuid '
            f'AND directory_workspace.instance_uuid::text = {directory_setting} '
            "AND directory_workspace.source = 'cloud_projection'"
            ')'
        ),
        _STATE_TABLE: f'instance_uuid::text = {directory_setting}',
        _INBOX_TABLE: f'instance_uuid::text = {directory_setting}',
    }
    tenant_expressions = {
        'workspaces': f'uuid::text = {tenant_setting}',
        'workspace_memberships': f'workspace_uuid::text = {tenant_setting}',
        'workspace_execution_states': f'workspace_uuid::text = {tenant_setting}',
    }
    local_write_expressions = {
        'workspaces': f"uuid::text = {tenant_setting} AND source = 'local'",
        'workspace_memberships': (
            f'workspace_uuid::text = {tenant_setting} AND EXISTS ('
            'SELECT 1 FROM workspaces AS local_workspace '
            'WHERE local_workspace.uuid = workspace_memberships.workspace_uuid '
            "AND local_workspace.source = 'local'"
            ')'
        ),
        'workspace_execution_states': (
            f'workspace_uuid::text = {tenant_setting} AND EXISTS ('
            'SELECT 1 FROM workspaces AS local_workspace '
            'WHERE local_workspace.uuid = workspace_execution_states.workspace_uuid '
            "AND local_workspace.source = 'local'"
            ')'
        ),
    }
    for table_name in _PROJECTED_TENANT_TABLES:
        _create_policy(
            conn,
            table_name,
            _TENANT_POLICY_NAME,
            tenant_expressions[table_name],
            command='SELECT',
        )
        _create_policy(
            conn,
            table_name,
            _LOCAL_WRITE_POLICY_NAME,
            local_write_expressions[table_name],
        )
        _create_policy(
            conn,
            table_name,
            _DIRECTORY_POLICY_NAME,
            directory_expressions[table_name],
        )
    for table_name in (_STATE_TABLE, _INBOX_TABLE):
        _create_policy(
            conn,
            table_name,
            _DIRECTORY_POLICY_NAME,
            directory_expressions[table_name],
        )


def upgrade() -> None:
    conn = op.get_bind()
    _create_tables(conn)
    if conn.dialect.name == 'postgresql':
        _install_postgres_policies(conn)


def downgrade() -> None:
    conn = op.get_bind()
    existing_tables = set(sa.inspect(conn).get_table_names())
    if conn.dialect.name == 'postgresql':
        tenant_setting = _setting(_TENANT_SETTING)
        tenant_columns = {
            'workspaces': 'uuid',
            'workspace_memberships': 'workspace_uuid',
            'workspace_execution_states': 'workspace_uuid',
        }
        for table_name in _PROJECTED_TENANT_TABLES:
            if table_name not in existing_tables:
                continue
            _drop_policy(conn, table_name, _DIRECTORY_POLICY_NAME)
            _drop_policy(conn, table_name, _LOCAL_WRITE_POLICY_NAME)
            _create_policy(
                conn,
                table_name,
                _TENANT_POLICY_NAME,
                f'{tenant_columns[table_name]}::text = {tenant_setting}',
            )
        for table_name in (_STATE_TABLE, _INBOX_TABLE):
            if table_name not in existing_tables:
                continue
            _drop_policy(conn, table_name, _DIRECTORY_POLICY_NAME)
            table = _quote(conn, table_name)
            op.execute(sa.text(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY'))

    if _INBOX_TABLE in existing_tables:
        op.drop_table(_INBOX_TABLE)
    if _STATE_TABLE in existing_tables:
        op.drop_table(_STATE_TABLE)
