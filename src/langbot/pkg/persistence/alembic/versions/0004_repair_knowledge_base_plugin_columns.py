"""repair knowledge base plugin architecture columns

Revision ID: 0004_repair_knowledge_base_plugin_columns
Revises: 0003_add_rerank_models
Create Date: 2026-04-23
"""

import sqlalchemy as sa
from alembic import op

revision = '0004_repair_knowledge_base_plugin_columns'
down_revision = '0003_add_rerank_models'
branch_labels = None
depends_on = None

NEW_COLUMNS = {
    'knowledge_engine_plugin_id': sa.String(),
    'collection_id': sa.String(),
    'creation_settings': sa.JSON(),
    'retrieval_settings': sa.JSON(),
}


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _get_columns(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column['name'] for column in inspector.get_columns(table_name)}


def _table_has_rows(conn: sa.Connection, table_name: str) -> bool:
    result = conn.execute(sa.text(f'SELECT COUNT(*) FROM {table_name}'))
    return bool(result.scalar())


def _ensure_metadata_flag(conn: sa.Connection, value: str) -> None:
    result = conn.execute(sa.text("SELECT value FROM metadata WHERE key = 'rag_plugin_migration_needed'"))
    if result.first() is None:
        conn.execute(
            sa.text("INSERT INTO metadata (key, value) VALUES ('rag_plugin_migration_needed', :value)"),
            {'value': value},
        )
    else:
        conn.execute(
            sa.text("UPDATE metadata SET value = :value WHERE key = 'rag_plugin_migration_needed'"),
            {'value': value},
        )


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not _table_exists(inspector, 'knowledge_bases'):
        return

    columns = _get_columns(inspector, 'knowledge_bases')
    missing_columns = {name: column_type for name, column_type in NEW_COLUMNS.items() if name not in columns}
    had_legacy_rows = _table_has_rows(conn, 'knowledge_bases')
    has_external_rows = _table_exists(inspector, 'external_knowledge_bases') and _table_has_rows(
        conn, 'external_knowledge_bases'
    )
    has_backup = _table_exists(inspector, 'knowledge_bases_backup')

    if missing_columns and had_legacy_rows and not has_backup:
        conn.execute(sa.text('CREATE TABLE knowledge_bases_backup AS SELECT * FROM knowledge_bases'))
        has_backup = True

    with op.batch_alter_table('knowledge_bases') as batch_op:
        for column_name, column_type in missing_columns.items():
            batch_op.add_column(sa.Column(column_name, column_type, nullable=True))

    if missing_columns and had_legacy_rows:
        conn.execute(sa.text('DELETE FROM knowledge_bases'))

    if has_backup or has_external_rows:
        _ensure_metadata_flag(conn, 'true')


def downgrade() -> None:
    pass
