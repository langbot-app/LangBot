"""add immutable plugin installation identity

Revision ID: 0012_plugin_identity
Revises: 0011_postgres_tenant_rls
Create Date: 2026-07-19

The migration gives every legacy row a random, stable installation UUID.  A
legacy artifact digest is only a valid SHA-256-shaped recovery marker; Core
replaces it with the package digest and increments ``runtime_revision`` before
the next package apply.
"""

from __future__ import annotations

import hashlib
import uuid

import sqlalchemy as sa
from alembic import op


revision = '0012_plugin_identity'
down_revision = '0011_postgres_tenant_rls'
branch_labels = None
depends_on = None


_TABLE = 'plugin_settings'
_INSTALLATION_INDEX = 'ix_plugin_settings_workspace_installation'
_INSTALLATION_UNIQUE = 'uq_plugin_settings_installation_uuid'
_REVISION_CHECK = 'ck_plugin_settings_runtime_revision_positive'
_DIGEST_CHECK = 'ck_plugin_settings_artifact_digest_length'


def _column_names(conn: sa.Connection) -> set[str]:
    inspector = sa.inspect(conn)
    if _TABLE not in inspector.get_table_names():
        return set()
    return {column['name'] for column in inspector.get_columns(_TABLE)}


def _legacy_digest(installation_uuid: str) -> str:
    return hashlib.sha256(f'legacy-installation:{installation_uuid}'.encode()).hexdigest()


def _suspend_postgres_rls(conn: sa.Connection) -> tuple[bool, bool]:
    """Let the release migration backfill every tenant row after revision 0011."""

    if conn.dialect.name != 'postgresql':
        return False, False
    row = conn.execute(
        sa.text('SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = to_regclass(:table_name)'),
        {'table_name': _TABLE},
    ).one()
    rls_enabled, rls_forced = bool(row.relrowsecurity), bool(row.relforcerowsecurity)
    if rls_forced:
        op.execute(sa.text(f'ALTER TABLE {_TABLE} NO FORCE ROW LEVEL SECURITY'))
    if rls_enabled:
        op.execute(sa.text(f'ALTER TABLE {_TABLE} DISABLE ROW LEVEL SECURITY'))
    return rls_enabled, rls_forced


def _restore_postgres_rls(conn: sa.Connection, state: tuple[bool, bool]) -> None:
    if conn.dialect.name != 'postgresql':
        return
    rls_enabled, rls_forced = state
    if rls_enabled:
        op.execute(sa.text(f'ALTER TABLE {_TABLE} ENABLE ROW LEVEL SECURITY'))
    if rls_forced:
        op.execute(sa.text(f'ALTER TABLE {_TABLE} FORCE ROW LEVEL SECURITY'))


def _backfill(conn: sa.Connection) -> None:
    table = sa.table(
        _TABLE,
        sa.column('workspace_uuid', sa.String(36)),
        sa.column('plugin_author', sa.String(255)),
        sa.column('plugin_name', sa.String(255)),
        sa.column('installation_uuid', sa.String(36)),
        sa.column('artifact_digest', sa.String(64)),
        sa.column('runtime_revision', sa.Integer()),
    )
    rows = conn.execute(
        sa.select(
            table.c.workspace_uuid,
            table.c.plugin_author,
            table.c.plugin_name,
            table.c.installation_uuid,
            table.c.artifact_digest,
            table.c.runtime_revision,
        )
    ).all()
    for row in rows:
        installation_uuid = str(row.installation_uuid or uuid.uuid4())
        values: dict[str, object] = {}
        if not row.installation_uuid:
            values['installation_uuid'] = installation_uuid
        if not row.artifact_digest or len(str(row.artifact_digest)) != 64:
            values['artifact_digest'] = _legacy_digest(installation_uuid)
        if row.runtime_revision is None or row.runtime_revision < 1:
            values['runtime_revision'] = 1
        if values:
            conn.execute(
                table.update()
                .where(table.c.workspace_uuid == row.workspace_uuid)
                .where(table.c.plugin_author == row.plugin_author)
                .where(table.c.plugin_name == row.plugin_name)
                .values(**values)
            )


def _constraint_names(conn: sa.Connection, kind: str) -> set[str]:
    inspector = sa.inspect(conn)
    getter = inspector.get_unique_constraints if kind == 'unique' else inspector.get_check_constraints
    return {str(item.get('name')) for item in getter(_TABLE) if item.get('name')}


def upgrade() -> None:
    conn = op.get_bind()
    columns = _column_names(conn)
    if not columns:
        return

    if 'installation_uuid' not in columns:
        op.add_column(_TABLE, sa.Column('installation_uuid', sa.String(36), nullable=True))
    if 'artifact_digest' not in columns:
        op.add_column(_TABLE, sa.Column('artifact_digest', sa.String(64), nullable=True))
    if 'runtime_revision' not in columns:
        op.add_column(_TABLE, sa.Column('runtime_revision', sa.Integer(), nullable=True))

    rls_state = _suspend_postgres_rls(conn)
    try:
        _backfill(conn)
    finally:
        _restore_postgres_rls(conn, rls_state)

    # Fresh databases are created from current metadata before Alembic runs;
    # guards make the revision safe for that path and for interrupted upgrades.
    indexes = {index['name'] for index in sa.inspect(conn).get_indexes(_TABLE)}
    unique_constraints = _constraint_names(conn, 'unique')
    check_constraints = _constraint_names(conn, 'check')
    with op.batch_alter_table(_TABLE) as batch:
        batch.alter_column('installation_uuid', existing_type=sa.String(36), nullable=False)
        batch.alter_column('artifact_digest', existing_type=sa.String(64), nullable=False)
        batch.alter_column('runtime_revision', existing_type=sa.Integer(), nullable=False)
        if _REVISION_CHECK not in check_constraints:
            batch.create_check_constraint(_REVISION_CHECK, 'runtime_revision >= 1')
        if _DIGEST_CHECK not in check_constraints:
            batch.create_check_constraint(_DIGEST_CHECK, 'length(artifact_digest) = 64')
        if _INSTALLATION_UNIQUE not in unique_constraints:
            batch.create_unique_constraint(_INSTALLATION_UNIQUE, ['installation_uuid'])
        if _INSTALLATION_INDEX not in indexes and _INSTALLATION_INDEX not in unique_constraints:
            batch.create_index(
                _INSTALLATION_INDEX,
                ['workspace_uuid', 'installation_uuid'],
                unique=True,
            )


def downgrade() -> None:
    conn = op.get_bind()
    columns = _column_names(conn)
    if not columns:
        return
    indexes = {index['name'] for index in sa.inspect(conn).get_indexes(_TABLE)}
    checks = _constraint_names(conn, 'check')
    uniques = _constraint_names(conn, 'unique')
    with op.batch_alter_table(_TABLE) as batch:
        if _INSTALLATION_INDEX in indexes:
            batch.drop_index(_INSTALLATION_INDEX)
        if _DIGEST_CHECK in checks:
            batch.drop_constraint(_DIGEST_CHECK, type_='check')
        if _REVISION_CHECK in checks:
            batch.drop_constraint(_REVISION_CHECK, type_='check')
        if _INSTALLATION_UNIQUE in uniques:
            batch.drop_constraint(_INSTALLATION_UNIQUE, type_='unique')
        for column_name in ('runtime_revision', 'artifact_digest', 'installation_uuid'):
            if column_name in columns:
                batch.drop_column(column_name)
