"""create tenant-scoped pgvector storage in the business database

Revision ID: 0013_tenant_pgvector
Revises: 0012_plugin_identity
Create Date: 2026-07-19

The Cloud application role never executes this DDL. A release migration role
installs pgvector once, creates an untyped vector column, and builds a bounded
set of expression/partial ANN indexes. Existing legacy rows are migrated only
when each row maps unambiguously to one knowledge base.
"""

from __future__ import annotations

import contextlib
import typing

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector


revision = '0013_tenant_pgvector'
down_revision = '0012_plugin_identity'
branch_labels = None
depends_on = None


_VECTOR_TABLE = 'langbot_vectors'
_LEGACY_TABLE = 'langbot_vectors_legacy_0013'
_TENANT_POLICY = 'langbot_workspace_isolation'
_TENANT_SETTING = 'langbot.workspace_uuid'
_KB_DIMENSION_CHECK = 'ck_knowledge_bases_embedding_dimension_positive'
_VECTOR_DIMENSION_CHECK = 'ck_langbot_vectors_embedding_dimension'
_VECTOR_ALLOWED_CHECK = 'ck_langbot_vectors_embedding_dimension_enabled'
_ALLOWED_DIMENSIONS = (384, 512, 768, 1024, 1536)
_LEGACY_SOURCE_TABLES = (
    'knowledge_bases',
    'knowledge_base_files',
    'knowledge_base_chunks',
)


def _quote(conn: sa.Connection, identifier: str) -> str:
    return conn.dialect.identifier_preparer.quote(identifier)


def _columns(conn: sa.Connection, table_name: str) -> set[str]:
    inspector = sa.inspect(conn)
    if table_name not in inspector.get_table_names():
        return set()
    return {column['name'] for column in inspector.get_columns(table_name)}


def _checks(conn: sa.Connection, table_name: str) -> set[str]:
    return {str(item['name']) for item in sa.inspect(conn).get_check_constraints(table_name) if item.get('name')}


def _ensure_knowledge_base_dimension(conn: sa.Connection) -> None:
    columns = _columns(conn, 'knowledge_bases')
    if 'embedding_dimension' not in columns:
        op.add_column('knowledge_bases', sa.Column('embedding_dimension', sa.Integer(), nullable=True))
    if _KB_DIMENSION_CHECK not in _checks(conn, 'knowledge_bases'):
        with op.batch_alter_table('knowledge_bases') as batch:
            batch.create_check_constraint(
                _KB_DIMENSION_CHECK,
                'embedding_dimension IS NULL OR embedding_dimension > 0',
            )


def _create_vector_table() -> None:
    enabled = ', '.join(str(item) for item in _ALLOWED_DIMENSIONS)
    op.create_table(
        _VECTOR_TABLE,
        sa.Column('workspace_uuid', sa.String(36), nullable=False),
        sa.Column('knowledge_base_uuid', sa.String(255), nullable=False),
        sa.Column('vector_id', sa.String(255), nullable=False),
        sa.Column('embedding_dimension', sa.Integer(), nullable=False),
        sa.Column('embedding', Vector(), nullable=False),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('file_id', sa.String(255), nullable=True),
        sa.Column('chunk_uuid', sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint(
            'workspace_uuid',
            'knowledge_base_uuid',
            'vector_id',
            name='pk_langbot_vectors',
        ),
        sa.ForeignKeyConstraint(
            ['workspace_uuid', 'knowledge_base_uuid'],
            ['knowledge_bases.workspace_uuid', 'knowledge_bases.uuid'],
            name='fk_langbot_vectors_workspace_kb',
            ondelete='CASCADE',
        ),
        sa.CheckConstraint(
            'vector_dims(embedding) = embedding_dimension',
            name=_VECTOR_DIMENSION_CHECK,
        ),
        sa.CheckConstraint(
            f'embedding_dimension IN ({enabled})',
            name=_VECTOR_ALLOWED_CHECK,
        ),
    )
    op.create_index(
        'ix_langbot_vectors_workspace_kb_file',
        _VECTOR_TABLE,
        ['workspace_uuid', 'knowledge_base_uuid', 'file_id'],
    )
    op.create_index(
        'ix_langbot_vectors_workspace_kb_chunk',
        _VECTOR_TABLE,
        ['workspace_uuid', 'knowledge_base_uuid', 'chunk_uuid'],
    )


def _legacy_mapping_predicate() -> str:
    return """
        kb.collection_id = legacy.collection
        OR EXISTS (
            SELECT 1
            FROM knowledge_base_files AS files
            LEFT JOIN knowledge_base_chunks AS chunks
              ON chunks.workspace_uuid = files.workspace_uuid
             AND chunks.file_id = files.uuid
            WHERE files.workspace_uuid = kb.workspace_uuid
              AND files.kb_id = kb.uuid
              AND (files.uuid = legacy.file_id OR chunks.uuid = legacy.chunk_uuid)
        )
    """


def _legacy_source_rls_states(conn: sa.Connection) -> dict[str, tuple[bool, bool]]:
    rows = (
        conn.execute(
            sa.text(
                """
                SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
                FROM pg_class AS c
                JOIN pg_namespace AS n ON n.oid = c.relnamespace
                WHERE n.nspname = current_schema()
                  AND c.relname IN :table_names
                  AND c.relkind IN ('r', 'p')
                """
            ).bindparams(sa.bindparam('table_names', expanding=True)),
            {'table_names': _LEGACY_SOURCE_TABLES},
        )
        .mappings()
        .all()
    )
    states = {str(row['relname']): (bool(row['relrowsecurity']), bool(row['relforcerowsecurity'])) for row in rows}
    missing = set(_LEGACY_SOURCE_TABLES) - set(states)
    if missing:
        raise RuntimeError(f'Legacy pgvector source tables are missing: {sorted(missing)!r}')
    return states


@contextlib.contextmanager
def _suspend_legacy_source_rls(conn: sa.Connection) -> typing.Iterator[None]:
    """Temporarily let the table-owning migrator map all legacy tenant rows.

    Revision 0011 enables and forces RLS on each source table. The release
    migrator intentionally has neither superuser nor BYPASSRLS, so even a table
    owner cannot read those rows until FORCE RLS is paused. Preserve both flags
    independently and restore them in ``finally`` so mixed pre-existing states
    survive successful, rejected, and interrupted legacy migrations.
    """

    states = _legacy_source_rls_states(conn)
    try:
        for table_name in _LEGACY_SOURCE_TABLES:
            table = _quote(conn, table_name)
            conn.execute(sa.text(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY'))
            conn.execute(sa.text(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY'))
        yield
    finally:
        for table_name in _LEGACY_SOURCE_TABLES:
            table = _quote(conn, table_name)
            rls_enabled, rls_forced = states[table_name]
            enabled_clause = 'ENABLE' if rls_enabled else 'DISABLE'
            forced_clause = 'FORCE' if rls_forced else 'NO FORCE'
            conn.execute(sa.text(f'ALTER TABLE {table} {enabled_clause} ROW LEVEL SECURITY'))
            conn.execute(sa.text(f'ALTER TABLE {table} {forced_clause} ROW LEVEL SECURITY'))


def _migrate_legacy_rows(conn: sa.Connection) -> None:
    predicate = _legacy_mapping_predicate()
    ambiguous = conn.execute(
        sa.text(
            f"""
            WITH candidates AS (
                SELECT legacy.id, kb.workspace_uuid, kb.uuid AS knowledge_base_uuid
                FROM {_LEGACY_TABLE} AS legacy
                JOIN knowledge_bases AS kb ON ({predicate})
            ), candidate_counts AS (
                SELECT id, COUNT(*) AS count
                FROM candidates
                GROUP BY id
            )
            SELECT legacy.id, COALESCE(candidate_counts.count, 0) AS candidate_count
            FROM {_LEGACY_TABLE} AS legacy
            LEFT JOIN candidate_counts ON candidate_counts.id = legacy.id
            WHERE COALESCE(candidate_counts.count, 0) <> 1
            LIMIT 1
            """
        )
    ).first()
    if ambiguous is not None:
        raise RuntimeError(
            'Legacy pgvector row cannot be mapped to exactly one Workspace/knowledge base: '
            f'{ambiguous.id!r} has {ambiguous.candidate_count} candidates'
        )

    conn.execute(
        sa.text(
            f"""
            INSERT INTO {_VECTOR_TABLE} (
                workspace_uuid,
                knowledge_base_uuid,
                vector_id,
                embedding_dimension,
                embedding,
                text,
                file_id,
                chunk_uuid
            )
            SELECT
                kb.workspace_uuid,
                kb.uuid,
                legacy.id,
                vector_dims(legacy.embedding),
                legacy.embedding,
                legacy.text,
                legacy.file_id,
                legacy.chunk_uuid
            FROM {_LEGACY_TABLE} AS legacy
            JOIN knowledge_bases AS kb ON ({predicate})
            """
        )
    )

    mixed_dimension = conn.execute(
        sa.text(
            f"""
            SELECT workspace_uuid, knowledge_base_uuid
            FROM {_VECTOR_TABLE}
            GROUP BY workspace_uuid, knowledge_base_uuid
            HAVING MIN(embedding_dimension) <> MAX(embedding_dimension)
            LIMIT 1
            """
        )
    ).first()
    if mixed_dimension is not None:
        raise RuntimeError('Legacy knowledge base contains mixed embedding dimensions')

    conn.execute(
        sa.text(
            f"""
            UPDATE knowledge_bases AS kb
            SET embedding_dimension = dimensions.embedding_dimension
            FROM (
                SELECT workspace_uuid, knowledge_base_uuid, MIN(embedding_dimension) AS embedding_dimension
                FROM {_VECTOR_TABLE}
                GROUP BY workspace_uuid, knowledge_base_uuid
            ) AS dimensions
            WHERE kb.workspace_uuid = dimensions.workspace_uuid
              AND kb.uuid = dimensions.knowledge_base_uuid
              AND kb.embedding_dimension IS NULL
            """
        )
    )


def _drop_all_policies(conn: sa.Connection) -> None:
    table = _quote(conn, _VECTOR_TABLE)
    policies = conn.execute(
        sa.text(
            """
            SELECT p.polname
            FROM pg_policy p
            JOIN pg_class c ON c.oid = p.polrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = current_schema() AND c.relname = :table_name
            """
        ),
        {'table_name': _VECTOR_TABLE},
    ).scalars()
    for policy_name in policies:
        op.execute(sa.text(f'DROP POLICY {_quote(conn, policy_name)} ON {table}'))


def _enable_rls(conn: sa.Connection) -> None:
    table = _quote(conn, _VECTOR_TABLE)
    policy = _quote(conn, _TENANT_POLICY)
    expression = f"workspace_uuid::text = NULLIF(current_setting('{_TENANT_SETTING}', true), '')"
    _drop_all_policies(conn)
    op.execute(sa.text(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY'))
    op.execute(
        sa.text(
            f'CREATE POLICY {policy} ON {table} AS PERMISSIVE FOR ALL TO PUBLIC '
            f'USING ({expression}) WITH CHECK ({expression})'
        )
    )


def _create_ann_indexes(conn: sa.Connection) -> None:
    table = _quote(conn, _VECTOR_TABLE)
    for dimension in _ALLOWED_DIMENSIONS:
        index = _quote(conn, f'ix_langbot_vectors_hnsw_cosine_{dimension}')
        op.execute(
            sa.text(
                f'CREATE INDEX {index} ON {table} USING hnsw '
                f'((embedding::vector({dimension})) vector_cosine_ops) '
                f'WHERE embedding_dimension = {dimension}'
            )
        )


def upgrade() -> None:
    conn = op.get_bind()
    if 'knowledge_bases' not in sa.inspect(conn).get_table_names():
        if conn.dialect.name == 'postgresql':
            # The supported PostgreSQL release path creates the business
            # tables before stamping 0010 and reaching this migration. Missing
            # knowledge_bases therefore means the operator bypassed the
            # release bootstrap or the schema is incomplete; stamping head in
            # that state would make Cloud runtime validation unrecoverable.
            raise RuntimeError('PostgreSQL release migration requires the knowledge_bases table')
        # A direct empty SQLite Alembic walk is still used by migration tooling;
        # Core creates the complete ORM schema on its following compatibility
        # pass, including the portable embedding_dimension field.
        return

    _ensure_knowledge_base_dimension(conn)

    # pgvector storage is PostgreSQL-only, but ``embedding_dimension`` is an
    # ORM field used by both deployment modes. Existing OSS SQLite databases
    # must receive the column before this revision becomes a no-op.
    if conn.dialect.name != 'postgresql':
        return

    op.execute(sa.text('CREATE EXTENSION IF NOT EXISTS vector'))
    columns = _columns(conn, _VECTOR_TABLE)
    if columns:
        scoped_columns = {
            'workspace_uuid',
            'knowledge_base_uuid',
            'vector_id',
            'embedding_dimension',
            'embedding',
        }
        if scoped_columns.issubset(columns):
            raise RuntimeError('Tenant pgvector table exists before its owning release migration')
        legacy_columns = {'id', 'collection', 'embedding'}
        if not legacy_columns.issubset(columns):
            raise RuntimeError('Existing pgvector table has an unsupported schema')
        if _LEGACY_TABLE in sa.inspect(conn).get_table_names():
            raise RuntimeError(f'Interrupted pgvector migration left {_LEGACY_TABLE!r} behind')
        op.rename_table(_VECTOR_TABLE, _LEGACY_TABLE)

    _create_vector_table()
    if _LEGACY_TABLE in sa.inspect(conn).get_table_names():
        with _suspend_legacy_source_rls(conn):
            _migrate_legacy_rows(conn)
        op.drop_table(_LEGACY_TABLE)
    _create_ann_indexes(conn)
    _enable_rls(conn)


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == 'postgresql' and _VECTOR_TABLE in sa.inspect(conn).get_table_names():
        _drop_all_policies(conn)
        op.drop_table(_VECTOR_TABLE)

    columns = _columns(conn, 'knowledge_bases')
    if 'embedding_dimension' in columns:
        checks = _checks(conn, 'knowledge_bases')
        with op.batch_alter_table('knowledge_bases') as batch:
            if _KB_DIMENSION_CHECK in checks:
                batch.drop_constraint(_KB_DIMENSION_CHECK, type_='check')
            batch.drop_column('embedding_dimension')
