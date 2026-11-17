"""Knowledge source migrations preserve legacy rows and reject unsafe downgrade."""

import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
import sqlalchemy as sa

migration = importlib.import_module('langbot.pkg.persistence.alembic.versions.0053_knowledge_artifact_sources')


@pytest.mark.parametrize('partial', [False, True])
def test_upgrade_downgrade_and_live_source_guard(partial):
    engine = sa.create_engine('sqlite://')
    with engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
        conn.execute(sa.text('CREATE TABLE knowledge_bases (uuid TEXT PRIMARY KEY)'))
        conn.execute(sa.text('CREATE TABLE knowledge_base_files (uuid TEXT PRIMARY KEY, workspace_uuid TEXT)'))
        if not partial:
            conn.execute(
                sa.text('CREATE TABLE artifacts (id TEXT PRIMARY KEY, workspace_uuid TEXT, UNIQUE(workspace_uuid,id))')
            )
        migration.upgrade()
        migration.upgrade()
        conn.execute(sa.text("INSERT INTO knowledge_bases VALUES ('kb', false)"))
        conn.execute(sa.text("INSERT INTO knowledge_base_files VALUES ('f', 'w', 'art_source')"))
        with pytest.raises(RuntimeError, match='Artifact-backed'):
            migration.downgrade()
        assert 'deleting' in {c['name'] for c in sa.inspect(conn).get_columns('knowledge_bases')}
        conn.execute(sa.text('UPDATE knowledge_base_files SET artifact_id=NULL'))
        conn.execute(sa.text('UPDATE knowledge_bases SET deleting=true'))
        with pytest.raises(RuntimeError, match='pending'):
            migration.downgrade()
        conn.execute(sa.text('UPDATE knowledge_bases SET deleting=false'))
        migration.downgrade()
        migration.downgrade()
        assert 'artifact_id' not in {c['name'] for c in sa.inspect(conn).get_columns('knowledge_base_files')}
        assert conn.execute(sa.text('SELECT uuid FROM knowledge_base_files')).scalar_one() == 'f'
    engine.dispose()


def test_empty_schema_is_supported():
    engine = sa.create_engine('sqlite://')
    with engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
        migration.upgrade()
        migration.downgrade()
        assert not sa.inspect(conn).get_table_names()
    engine.dispose()


@pytest.mark.asyncio
async def test_full_model_schema_with_legacy_children_and_foreign_keys(tmp_path):
    from sqlalchemy.ext.asyncio import create_async_engine
    from langbot.pkg.entity import persistence
    from langbot.pkg.entity.persistence.base import Base
    from langbot.pkg.utils import importutil
    from langbot.pkg.persistence.alembic_runner import run_alembic_downgrade, run_alembic_upgrade, run_alembic_stamp
    from langbot.pkg.entity.persistence.workspace import Workspace
    from langbot.pkg.entity.persistence.rag import KnowledgeBase, File, Chunk

    importutil.import_modules_in_pkg(persistence)
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "full.db"}')

    @sa.event.listens_for(engine.sync_engine, 'connect')
    def foreign_keys(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(sa.insert(Workspace).values(uuid='ws', instance_uuid='instance', name='ws', slug='ws'))
            await conn.execute(sa.insert(KnowledgeBase).values(uuid='kb', workspace_uuid='ws', name='kb'))
            await conn.execute(sa.insert(File).values(uuid='file', workspace_uuid='ws', kb_id='kb', status='completed'))
            await conn.execute(
                sa.insert(Chunk).values(uuid='chunk', workspace_uuid='ws', file_id='file', text='retain me')
            )
        await run_alembic_stamp(engine, '0053_knowledge_artifact_sources')
        await run_alembic_downgrade(engine, '0052_artifact_skill_sources')
        await run_alembic_upgrade(engine, '0053_knowledge_artifact_sources')
        async with engine.connect() as conn:
            assert (await conn.execute(sa.select(Chunk.text))).scalar_one() == 'retain me'
            assert (await conn.exec_driver_sql('PRAGMA foreign_keys')).scalar_one() == 1
            assert not (await conn.exec_driver_sql('PRAGMA foreign_key_check')).first()
    finally:
        await engine.dispose()
