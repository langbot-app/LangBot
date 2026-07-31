"""align the OSS Workspace UUID with the persisted instance identity

Revision ID: 0017_oss_workspace_identity
Revises: 0016_support_admin_sessions
Create Date: 2026-07-31
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op


revision = '0017_oss_workspace_identity'
down_revision = '0016_support_admin_sessions'
branch_labels = None
depends_on = None

_WORKSPACE_IDENTITY_NAMESPACE = uuid.UUID('8ea04f29-8528-4cc3-bb28-30a838c89d76')
_OSS_WORKSPACE_METADATA_KEY = 'oss_workspace_uuid'


def _workspace_uuid_from_instance_id(instance_id: str) -> str:
    value = instance_id.strip()
    candidate = value[len('instance_') :] if value.startswith('instance_') else value
    try:
        return str(uuid.UUID(candidate))
    except ValueError:
        return str(uuid.uuid5(_WORKSPACE_IDENTITY_NAMESPACE, value))


def _quote(conn: sa.Connection, identifier: str) -> str:
    return conn.dialect.identifier_preparer.quote(identifier)


def _defer_foreign_keys(conn: sa.Connection, inspector: sa.Inspector, table_names: list[str]) -> None:
    """Allow the transaction to re-key a connected tenant graph atomically."""

    if conn.dialect.name == 'sqlite':
        conn.execute(sa.text('PRAGMA defer_foreign_keys = ON'))
        return
    if conn.dialect.name != 'postgresql':
        raise RuntimeError(f'Unsupported Workspace identity migration dialect: {conn.dialect.name}')

    for table_name in table_names:
        for foreign_key in inspector.get_foreign_keys(table_name):
            constraint_name = foreign_key.get('name')
            if not constraint_name:
                continue
            conn.execute(
                sa.text(
                    f'ALTER TABLE {_quote(conn, table_name)} '
                    f'ALTER CONSTRAINT {_quote(conn, constraint_name)} DEFERRABLE INITIALLY DEFERRED'
                )
            )


def _suspend_postgres_rls(
    conn: sa.Connection,
    table_names: list[str],
) -> dict[str, tuple[bool, bool]]:
    if conn.dialect.name != 'postgresql':
        return {}

    states: dict[str, tuple[bool, bool]] = {}
    for table_name in table_names:
        row = conn.execute(
            sa.text(
                'SELECT relrowsecurity, relforcerowsecurity '
                'FROM pg_class WHERE oid = to_regclass(:table_name)'
            ),
            {'table_name': table_name},
        ).one()
        enabled, forced = bool(row.relrowsecurity), bool(row.relforcerowsecurity)
        states[table_name] = (enabled, forced)
        table = _quote(conn, table_name)
        if forced:
            conn.execute(sa.text(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY'))
        if enabled:
            conn.execute(sa.text(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY'))
    return states


def _restore_postgres_rls(conn: sa.Connection, states: dict[str, tuple[bool, bool]]) -> None:
    for table_name, (enabled, forced) in states.items():
        table = _quote(conn, table_name)
        if enabled:
            conn.execute(sa.text(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY'))
        if forced:
            conn.execute(sa.text(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY'))


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    table_names = inspector.get_table_names()
    if 'workspaces' not in table_names:
        return

    metadata = sa.MetaData()
    workspaces = sa.Table('workspaces', metadata, autoload_with=conn)
    local_rows = conn.execute(sa.select(workspaces).where(workspaces.c.source == 'local')).mappings().all()
    if not local_rows:
        return
    if len(local_rows) != 1:
        raise RuntimeError('Cannot align OSS Workspace identity: expected exactly one local Workspace')

    old_row = dict(local_rows[0])
    old_uuid = old_row['uuid']
    canonical_uuid = _workspace_uuid_from_instance_id(old_row['instance_uuid'])
    if old_uuid == canonical_uuid:
        return
    if conn.execute(sa.select(workspaces.c.uuid).where(workspaces.c.uuid == canonical_uuid)).scalar_one_or_none():
        raise RuntimeError(f'Cannot align OSS Workspace identity: target {canonical_uuid!r} already exists')

    tenant_tables = [
        table_name
        for table_name in table_names
        if table_name == 'workspaces'
        or 'workspace_uuid' in {column['name'] for column in inspector.get_columns(table_name)}
    ]
    rls_states = _suspend_postgres_rls(conn, tenant_tables)
    try:
        _defer_foreign_keys(conn, inspector, table_names)

        # Release local source/slug uniqueness while the canonical parent exists
        # alongside the old parent for the duration of this transaction.
        temporary_slug = f'__workspace_rekey__{old_uuid}'
        conn.execute(
            workspaces.update()
            .where(workspaces.c.uuid == old_uuid)
            .values(source='cloud_projection', slug=temporary_slug)
        )
        new_row = dict(old_row)
        new_row['uuid'] = canonical_uuid
        conn.execute(workspaces.insert().values(**new_row))

        for table_name in tenant_tables:
            if table_name == 'workspaces':
                continue
            table = sa.Table(table_name, metadata, autoload_with=conn, extend_existing=True)
            conn.execute(
                table.update()
                .where(table.c.workspace_uuid == old_uuid)
                .values(workspace_uuid=canonical_uuid)
            )

        if 'metadata' in table_names:
            conn.execute(
                sa.text(
                    'UPDATE metadata SET value = :canonical_uuid '
                    'WHERE key = :key AND value = :old_uuid'
                ),
                {
                    'canonical_uuid': canonical_uuid,
                    'key': _OSS_WORKSPACE_METADATA_KEY,
                    'old_uuid': old_uuid,
                },
            )
        conn.execute(workspaces.delete().where(workspaces.c.uuid == old_uuid))
        if conn.dialect.name == 'postgresql':
            # Fire deferred FK triggers before ALTER TABLE restores RLS; PostgreSQL
            # rejects ALTER TABLE while a relation has pending trigger events.
            conn.execute(sa.text('SET CONSTRAINTS ALL IMMEDIATE'))
    except Exception:
        # Alembic owns the transaction. Rollback restores the transactional RLS DDL.
        raise
    else:
        _restore_postgres_rls(conn, rls_states)


def downgrade() -> None:
    # The previous random UUID is intentionally not recoverable. Keeping the
    # canonical identity preserves every FK and is safe for older application code.
    pass
