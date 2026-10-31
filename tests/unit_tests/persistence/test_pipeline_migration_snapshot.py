import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.pipeline import LegacyPipeline
from langbot.pkg.persistence.mgr import _ALEMBIC_TENANT_TABLES
from langbot.pkg.persistence.tenant_uow import TENANT_TABLE_COLUMNS


def test_snapshot_schema_registered_composite_fk_and_schema_only_migration(tmp_path):
    assert 'pipeline_migration_snapshots' in Base.metadata.tables, 'durable snapshot table missing'
    table = Base.metadata.tables['pipeline_migration_snapshots']
    assert isinstance(table.c.source_snapshot.type, sa.JSON)
    assert TENANT_TABLE_COLUMNS[table.name] == 'workspace_uuid'
    assert table.name in _ALEMBIC_TENANT_TABLES
    assert any(
        tuple(f.column.name for f in c.elements) == ('workspace_uuid', 'uuid') for c in table.foreign_key_constraints
    )
    assert any(
        isinstance(c, sa.UniqueConstraint)
        and [col.name for col in c.columns] == ['workspace_uuid', 'pipeline_uuid', 'source_fingerprint']
        for c in table.constraints
    )
    path = (
        Path(__file__).parents[3] / 'src/langbot/pkg/persistence/alembic/versions/0027_pipeline_migration_snapshots.py'
    )
    spec = importlib.util.spec_from_file_location('migration0027', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == '0026_merge_master_beta'
    assert len(migration.revision) <= 32, 'Alembic version_num is VARCHAR(32)'
    engine = sa.create_engine(f'sqlite:///{tmp_path / "schema.db"}')
    with engine.begin() as conn:
        # Upgrade an existing schema that has not yet created the journal.
        Base.metadata.create_all(conn, tables=[LegacyPipeline.__table__])
        statements = []
        sa.event.listen(conn, 'before_cursor_execute', lambda _c, _u, sql, *_a: statements.append(sql))
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            migration.upgrade()  # fresh-metadata boot and retry are idempotent
        assert table.name in sa.inspect(conn).get_table_names()
        assert not any(s.lstrip().upper().startswith(('UPDATE ', 'INSERT ', 'DELETE ')) for s in statements)
    engine.dispose()
