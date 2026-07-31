"""enforce PostgreSQL tenant isolation with exact discovery contracts

Revision ID: 0011_postgres_tenant_rls
Revises: 0010_scope_resources
Create Date: 2026-07-19

The table and policy lists are deliberately duplicated from the runtime
contract. Alembic revisions must remain self-contained after application code
evolves. Discovery policies are SELECT-only and reveal the minimum rows needed
to turn an authenticated credential into one Workspace transaction.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0011_postgres_tenant_rls'
down_revision = '0010_scope_resources'
branch_labels = None
depends_on = None


_POLICY_NAME = 'langbot_workspace_isolation'
_ACCOUNT_POLICY_NAME = 'langbot_account_discovery'
_API_KEY_POLICY_NAME = 'langbot_api_key_discovery'
_INVITATION_POLICY_NAME = 'langbot_invitation_discovery'
_INSTANCE_POLICY_NAME = 'langbot_instance_discovery'

_TENANT_SETTING = 'langbot.workspace_uuid'
_ACCOUNT_SETTING = 'langbot.account_uuid'
_API_KEY_HASH_SETTING = 'langbot.api_key_hash'
_INVITATION_HASH_SETTING = 'langbot.invitation_hash'
_INSTANCE_SETTING = 'langbot.instance_uuid'
_OSS_WORKSPACE_METADATA_KEY = 'oss_workspace_uuid'

_TENANT_TABLE_COLUMNS: dict[str, str] = {
    'workspaces': 'uuid',
    'workspace_memberships': 'workspace_uuid',
    'workspace_invitations': 'workspace_uuid',
    'workspace_execution_states': 'workspace_uuid',
    'workspace_metadata': 'workspace_uuid',
    'api_keys': 'workspace_uuid',
    'bots': 'workspace_uuid',
    'bot_admins': 'workspace_uuid',
    'binary_storages': 'workspace_uuid',
    'mcp_servers': 'workspace_uuid',
    'model_providers': 'workspace_uuid',
    'llm_models': 'workspace_uuid',
    'embedding_models': 'workspace_uuid',
    'rerank_models': 'workspace_uuid',
    'legacy_pipelines': 'workspace_uuid',
    'pipeline_run_records': 'workspace_uuid',
    'plugin_settings': 'workspace_uuid',
    'knowledge_bases': 'workspace_uuid',
    'knowledge_base_files': 'workspace_uuid',
    'knowledge_base_chunks': 'workspace_uuid',
    'webhooks': 'workspace_uuid',
    'monitoring_messages': 'workspace_uuid',
    'monitoring_llm_calls': 'workspace_uuid',
    'monitoring_tool_calls': 'workspace_uuid',
    'monitoring_sessions': 'workspace_uuid',
    'monitoring_errors': 'workspace_uuid',
    'monitoring_embedding_calls': 'workspace_uuid',
    'monitoring_feedback': 'workspace_uuid',
}


def _setting(name: str) -> str:
    return f"NULLIF(current_setting('{name}', true), '')"


def _tenant_expression(column: str) -> str:
    return f'{column}::text = {_setting(_TENANT_SETTING)}'


_DISCOVERY_POLICIES: dict[str, dict[str, str]] = {
    'workspace_memberships': {
        _ACCOUNT_POLICY_NAME: (f"account_uuid::text = {_setting(_ACCOUNT_SETTING)} AND status = 'active'"),
    },
    'workspace_execution_states': {
        _INSTANCE_POLICY_NAME: (
            f"instance_uuid = {_setting(_INSTANCE_SETTING)} AND state = 'active' AND write_fenced = false"
        ),
    },
    'api_keys': {
        _API_KEY_POLICY_NAME: (
            f"key_hash = {_setting(_API_KEY_HASH_SETTING)} AND status = 'active' "
            'AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)'
        ),
    },
    'workspace_invitations': {
        _INVITATION_POLICY_NAME: f'token_hash = {_setting(_INVITATION_HASH_SETTING)}',
    },
}


def _quote_identifier(conn: sa.Connection, identifier: str) -> str:
    return conn.dialect.identifier_preparer.quote(identifier)


def _record_oss_workspace_scope(conn: sa.Connection) -> None:
    """Keep PostgreSQL OSS usable after FORCE RLS is enabled."""

    local_workspaces = (
        conn.execute(sa.text("SELECT uuid FROM workspaces WHERE source = 'local' ORDER BY uuid")).scalars().all()
    )
    if len(local_workspaces) != 1:
        return

    existing = conn.execute(
        sa.text('SELECT value FROM metadata WHERE key = :key'),
        {'key': _OSS_WORKSPACE_METADATA_KEY},
    ).scalar_one_or_none()
    if existing is None:
        conn.execute(
            sa.text('INSERT INTO metadata (key, value) VALUES (:key, :value)'),
            {'key': _OSS_WORKSPACE_METADATA_KEY, 'value': local_workspaces[0]},
        )
    elif existing != local_workspaces[0]:
        raise RuntimeError('Stored OSS Workspace scope does not match the local Workspace')


def _drop_all_policies(conn: sa.Connection, table_name: str) -> None:
    policy_names = conn.execute(
        sa.text(
            """
            SELECT p.polname
            FROM pg_policy p
            JOIN pg_class c ON c.oid = p.polrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = current_schema() AND c.relname = :table_name
            """
        ),
        {'table_name': table_name},
    ).scalars()
    table = _quote_identifier(conn, table_name)
    for policy in policy_names:
        op.execute(sa.text(f'DROP POLICY {_quote_identifier(conn, policy)} ON {table}'))


def _create_policy(
    conn: sa.Connection,
    table_name: str,
    policy_name: str,
    expression: str,
    *,
    command: str,
) -> None:
    table = _quote_identifier(conn, table_name)
    policy = _quote_identifier(conn, policy_name)
    if command == 'ALL':
        sql = f'CREATE POLICY {policy} ON {table} AS PERMISSIVE FOR ALL TO PUBLIC USING ({expression}) WITH CHECK ({expression})'
    elif command == 'SELECT':
        sql = f'CREATE POLICY {policy} ON {table} AS PERMISSIVE FOR SELECT TO PUBLIC USING ({expression})'
    else:  # pragma: no cover - migration-local invariant
        raise AssertionError(f'Unsupported RLS command: {command}')
    op.execute(sa.text(sql))


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != 'postgresql':
        return

    existing_tables = set(sa.inspect(conn).get_table_names())
    missing_tables = set(_TENANT_TABLE_COLUMNS) - existing_tables
    if missing_tables:
        raise RuntimeError(f'Cannot enable tenant RLS before all tenant-owned tables exist: {sorted(missing_tables)!r}')

    _record_oss_workspace_scope(conn)

    for table_name, tenant_column in _TENANT_TABLE_COLUMNS.items():
        table = _quote_identifier(conn, table_name)
        _drop_all_policies(conn, table_name)
        op.execute(sa.text(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY'))
        _create_policy(
            conn,
            table_name,
            _POLICY_NAME,
            _tenant_expression(_quote_identifier(conn, tenant_column)),
            command='ALL',
        )
        for policy_name, expression in _DISCOVERY_POLICIES.get(table_name, {}).items():
            _create_policy(conn, table_name, policy_name, expression, command='SELECT')


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != 'postgresql':
        return

    existing_tables = set(sa.inspect(conn).get_table_names())
    for table_name in _TENANT_TABLE_COLUMNS:
        if table_name not in existing_tables:
            continue
        table = _quote_identifier(conn, table_name)
        _drop_all_policies(conn, table_name)
        op.execute(sa.text(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY'))
