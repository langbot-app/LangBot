"""Retain shared Artifact references for knowledge file consumers."""

from contextlib import contextmanager

import sqlalchemy as sa
from alembic import op

revision = '0053_knowledge_artifact_sources'
down_revision = '0052_artifact_skill_sources'
branch_labels = None
depends_on = None


@contextmanager
def _preserve_sqlite_children(conn):
    """Batch recreation must not cascade-delete existing Chunk children."""
    enabled = conn.dialect.name == 'sqlite' and conn.exec_driver_sql('PRAGMA foreign_keys').scalar()
    if enabled:
        if conn.exec_driver_sql('PRAGMA foreign_key_check').first():
            raise RuntimeError('Repair existing foreign-key violations before knowledge migration')
        with op.get_context().autocommit_block():
            conn.exec_driver_sql('PRAGMA foreign_keys=OFF')
    try:
        yield
        if enabled and conn.exec_driver_sql('PRAGMA foreign_key_check').first():
            raise RuntimeError('Knowledge migration failed foreign-key validation')
    finally:
        if enabled:
            with op.get_context().autocommit_block():
                conn.exec_driver_sql('PRAGMA foreign_keys=ON')


def upgrade():
    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())
    if 'knowledge_bases' in tables and 'deleting' not in {
        c['name'] for c in sa.inspect(conn).get_columns('knowledge_bases')
    }:
        op.add_column('knowledge_bases', sa.Column('deleting', sa.Boolean(), nullable=False, server_default=sa.false()))
    if 'knowledge_base_files' not in tables:
        return
    columns = {c['name'] for c in sa.inspect(conn).get_columns('knowledge_base_files')}
    foreign_keys = {c['name'] for c in sa.inspect(conn).get_foreign_keys('knowledge_base_files')}
    with _preserve_sqlite_children(conn), op.batch_alter_table('knowledge_base_files') as batch:
        if 'artifact_id' not in columns:
            batch.add_column(sa.Column('artifact_id', sa.String(40), nullable=True))
        if 'artifacts' in tables and 'fk_knowledge_file_artifact' not in foreign_keys:
            batch.create_foreign_key(
                'fk_knowledge_file_artifact',
                'artifacts',
                ['workspace_uuid', 'artifact_id'],
                ['workspace_uuid', 'id'],
                ondelete='RESTRICT',
            )


def downgrade():
    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())
    kb_columns = (
        {c['name'] for c in sa.inspect(conn).get_columns('knowledge_bases')} if 'knowledge_bases' in tables else set()
    )
    file_columns = (
        {c['name'] for c in sa.inspect(conn).get_columns('knowledge_base_files')}
        if 'knowledge_base_files' in tables
        else set()
    )
    # Validate both safety gates before mutating either table, including partial schemas.
    if (
        'deleting' in kb_columns
        and conn.execute(sa.text('SELECT 1 FROM knowledge_bases WHERE deleting = true LIMIT 1')).first()
    ):
        raise RuntimeError('Complete pending knowledge base deletion before downgrade')
    if (
        'artifact_id' in file_columns
        and conn.execute(sa.text('SELECT 1 FROM knowledge_base_files WHERE artifact_id IS NOT NULL LIMIT 1')).first()
    ):
        raise RuntimeError('Delete Artifact-backed knowledge files before downgrade')
    if 'artifact_id' in file_columns:
        foreign_keys = {c['name'] for c in sa.inspect(conn).get_foreign_keys('knowledge_base_files')}
        with _preserve_sqlite_children(conn), op.batch_alter_table('knowledge_base_files') as batch:
            if 'fk_knowledge_file_artifact' in foreign_keys:
                batch.drop_constraint('fk_knowledge_file_artifact', type_='foreignkey')
            batch.drop_column('artifact_id')
    if 'deleting' in kb_columns:
        with _preserve_sqlite_children(conn), op.batch_alter_table('knowledge_bases') as batch:
            batch.drop_column('deleting')
