"""Skill artifact schema upgrade and safe downgrade on complete and partial schemas."""

import importlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

pytestmark = pytest.mark.integration
migration = importlib.import_module('langbot.pkg.persistence.alembic.versions.0052_artifact_skill_sources')


@pytest.mark.parametrize('partial', [False, True])
def test_skill_source_upgrade_downgrade(partial):
    engine = sa.create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(sa.text('CREATE TABLE artifacts (id TEXT PRIMARY KEY)'))
        if not partial:
            conn.execute(sa.text('CREATE TABLE skill_versions (uuid VARCHAR(36) PRIMARY KEY)'))
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            migration.upgrade()
            assert {'source_version_id', 'source_revision', 'source_path'} <= {
                column['name'] for column in sa.inspect(conn).get_columns('artifacts')
            }
            if not partial:
                assert 'fk_artifact_skill_version' in {
                    key['name'] for key in sa.inspect(conn).get_foreign_keys('artifacts')
                }
            migration.downgrade()
            migration.downgrade()
            assert {column['name'] for column in sa.inspect(conn).get_columns('artifacts')} == {'id'}
    engine.dispose()


def test_skill_source_downgrade_refuses_package_as_file():
    engine = sa.create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(sa.text('CREATE TABLE artifacts (id TEXT PRIMARY KEY)'))
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            conn.execute(sa.text("INSERT INTO artifacts VALUES ('a', 'version', 'revision', 'file')"))
            with pytest.raises(RuntimeError, match='Release and collect'):
                migration.downgrade()
            assert conn.execute(sa.text('SELECT source_version_id FROM artifacts')).scalar_one() == 'version'
    engine.dispose()


def test_skill_source_migration_empty_schema():
    engine = sa.create_engine('sqlite://')
    with engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
        migration.upgrade()
        migration.downgrade()
        assert sa.inspect(conn).get_table_names() == []
    engine.dispose()


@pytest.mark.asyncio
async def test_skill_source_full_model_schema_roundtrip(tmp_path):
    from sqlalchemy.ext.asyncio import create_async_engine
    from langbot.pkg.entity import persistence
    from langbot.pkg.entity.persistence.base import Base
    from langbot.pkg.utils import importutil
    from langbot.pkg.persistence.alembic_runner import (
        run_alembic_downgrade,
        run_alembic_upgrade,
        run_alembic_stamp,
    )

    importutil.import_modules_in_pkg(persistence)
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "full.db"}')
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await run_alembic_stamp(engine, '0052_artifact_skill_sources')
        await run_alembic_downgrade(engine, '0051_artifact_publications')
        await run_alembic_upgrade(engine, '0052_artifact_skill_sources')
        async with engine.connect() as conn:
            keys = await conn.run_sync(lambda sync: sa.inspect(sync).get_foreign_keys('artifacts'))
            assert {'fk_artifact_skill_version', 'fk_artifacts_content_scope'} <= {key['name'] for key in keys}
            checks = await conn.run_sync(lambda sync: sa.inspect(sync).get_check_constraints('artifacts'))
            assert {'ck_artifact_skill_source', 'ck_artifacts_size'} <= {check['name'] for check in checks}
        await run_alembic_downgrade(engine, '0051_artifact_publications')
    finally:
        await engine.dispose()
