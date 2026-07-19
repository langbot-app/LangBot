"""enforce PostgreSQL tenant isolation with row-level security

Revision ID: 0011_postgres_tenant_rls
Revises: 0010_scope_resources
Create Date: 2026-07-19

The table list is deliberately duplicated from the runtime contract. Alembic
revisions must remain self-contained after application code evolves.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0011_postgres_tenant_rls'
down_revision = '0010_scope_resources'
branch_labels = None
depends_on = None


_POLICY_NAME = 'langbot_workspace_isolation'
_TENANT_SETTING = 'langbot.workspace_uuid'
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


def _quote_identifier(conn: sa.Connection, identifier: str) -> str:
    return conn.dialect.identifier_preparer.quote(identifier)


def _record_oss_workspace_scope(conn: sa.Connection) -> None:
    """Keep PostgreSQL OSS usable after FORCE RLS is enabled.

    The runtime reads this instance-level metadata and installs the singleton
    Workspace as a transaction-local default. Cloud databases have no local
    Workspace and therefore do not receive this compatibility value.
    """
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


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != 'postgresql':
        return

    existing_tables = set(sa.inspect(conn).get_table_names())
    missing_tables = set(_TENANT_TABLE_COLUMNS) - existing_tables
    if missing_tables:
        raise RuntimeError(f'Cannot enable tenant RLS before all tenant-owned tables exist: {sorted(missing_tables)!r}')

    _record_oss_workspace_scope(conn)

    policy_name = _quote_identifier(conn, _POLICY_NAME)
    for table_name, tenant_column in _TENANT_TABLE_COLUMNS.items():
        table = _quote_identifier(conn, table_name)
        column = _quote_identifier(conn, tenant_column)
        tenant_value = f"CAST(NULLIF(current_setting('{_TENANT_SETTING}', true), '') AS VARCHAR(36))"

        op.execute(sa.text(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'DROP POLICY IF EXISTS {policy_name} ON {table}'))
        op.execute(
            sa.text(
                f'CREATE POLICY {policy_name} ON {table} '
                f'USING ({column} = {tenant_value}) '
                f'WITH CHECK ({column} = {tenant_value})'
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != 'postgresql':
        return

    existing_tables = set(sa.inspect(conn).get_table_names())
    policy_name = _quote_identifier(conn, _POLICY_NAME)
    for table_name in _TENANT_TABLE_COLUMNS:
        if table_name not in existing_tables:
            continue
        table = _quote_identifier(conn, table_name)
        op.execute(sa.text(f'DROP POLICY IF EXISTS {policy_name} ON {table}'))
        op.execute(sa.text(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY'))
