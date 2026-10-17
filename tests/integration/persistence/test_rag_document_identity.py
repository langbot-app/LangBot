"""Real database regressions for Host/engine identity; no live plugin or customer data."""

import asyncio
import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.pipeline import LegacyPipeline
from langbot.pkg.entity.persistence.rag import File, KnowledgeBase
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.entity.persistence.workspace import Workspace
from langbot.pkg.persistence import alembic_runner
from langbot.pkg.persistence.alembic_runner import (
    get_alembic_current,
    run_alembic_downgrade,
    run_alembic_stamp,
    run_alembic_upgrade,
)
from langbot.pkg.persistence.mgr import PersistenceManager
from langbot.pkg.rag.knowledge.kbmgr import RuntimeKnowledgeBase
from langbot.pkg.workspace.errors import WorkspaceNotFoundError

OLD_HEAD = '0024_passkey_credentials'


def current_head() -> str:
    """Resolve the live Alembic head instead of pinning a revision number.

    Parallel migrations (the TOTP and RAG document identity branches) are joined
    by a merge revision, so the head moves whenever either branch gains a new
    migration. Resolving it here keeps this test from needing an edit each time.
    """

    cfg = AlembicConfig()
    cfg.set_main_option('script_location', str(alembic_runner._ALEMBIC_DIR))
    return ScriptDirectory.from_config(cfg).get_current_head()


# The document identity work lives on its own branch: upgrades that exercise it
# must name the revision explicitly, because upgrading to the head would now
# also traverse the unrelated TOTP branch that shares this merge point.
DOCUMENT_IDENTITY_REVISION = '0025_rag_document_identity'
CONTEXT = ExecutionContext(instance_uuid='instance-a', workspace_uuid='workspace-a', placement_generation=5)


@pytest_asyncio.fixture(params=['sqlite', pytest.param('postgres', marks=pytest.mark.postgres)])
async def database(request, tmp_path):
    admin = None
    schema = 'ke_identity_' + uuid.uuid4().hex
    if request.param == 'postgres':
        url = os.environ.get('TEST_POSTGRES_URL')
        if not url:
            pytest.skip('TEST_POSTGRES_URL is required for disposable PostgreSQL tests')
        admin = create_async_engine(url)
        async with admin.begin() as conn:
            await conn.execute(sa.text(f'CREATE SCHEMA {schema}'))
        engine = create_async_engine(url, connect_args={'server_settings': {'search_path': schema}})
    else:
        engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "identity.db"}')

        @sa.event.listens_for(engine.sync_engine, 'connect')
        def enable_foreign_keys(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')

    try:
        yield engine
    finally:
        await engine.dispose()
        if admin is not None:
            async with admin.begin() as conn:
                await conn.execute(sa.text(f'DROP SCHEMA {schema} CASCADE'))
            await admin.dispose()


async def create_schema(engine, *, legacy=False):
    # Only the fixture-owned dependency closure; never all imported application tables.
    # Full-head upgrades also create the manual migration journal, whose scoped
    # foreign key requires the historical legacy_pipelines table.
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync: Base.metadata.create_all(
                sync, tables=[User.__table__, Workspace.__table__, LegacyPipeline.__table__, KnowledgeBase.__table__]
            )
        )
        if legacy:
            # Exact pre-0025 File shape, NOT current metadata stamped with an old revision.
            await conn.execute(
                sa.text("""CREATE TABLE knowledge_base_files (
                uuid VARCHAR(255) PRIMARY KEY UNIQUE,
                workspace_uuid VARCHAR(36) NOT NULL REFERENCES workspaces(uuid) ON DELETE CASCADE,
                kb_id VARCHAR(255), file_name VARCHAR, extension VARCHAR, created_at TIMESTAMP, status VARCHAR,
                CONSTRAINT uq_knowledge_base_files_workspace_uuid UNIQUE (workspace_uuid, uuid),
                CONSTRAINT fk_knowledge_base_files_workspace_kb FOREIGN KEY (workspace_uuid, kb_id)
                    REFERENCES knowledge_bases(workspace_uuid, uuid) ON DELETE CASCADE
            )""")
            )
            await conn.execute(
                sa.text(
                    'CREATE INDEX ix_knowledge_base_files_workspace_kb ON knowledge_base_files (workspace_uuid, kb_id)'
                )
            )
        else:
            await conn.run_sync(lambda sync: File.__table__.create(sync))
        for workspace in ('workspace-a', 'workspace-b'):
            await conn.execute(
                sa.insert(Workspace).values(
                    uuid=workspace,
                    instance_uuid='instance-a',
                    name=workspace,
                    slug=workspace,
                    source='cloud_projection',
                )
            )
        for kb, workspace in [('kb-a', 'workspace-a'), ('kb-other', 'workspace-a'), ('kb-b', 'workspace-b')]:
            await conn.execute(
                sa.insert(KnowledgeBase).values(
                    uuid=kb,
                    workspace_uuid=workspace,
                    name=kb,
                    knowledge_engine_plugin_id='author/engine',
                    collection_id=kb,
                )
            )


@pytest_asyncio.fixture
async def runtime(database):
    await create_schema(database)
    ap = SimpleNamespace(
        logger=Mock(),
        workspace_service=SimpleNamespace(
            get_execution_binding=AsyncMock(
                return_value=SimpleNamespace(
                    instance_uuid='instance-a',
                    placement_generation=5,
                )
            )
        ),
        storage_mgr=SimpleNamespace(
            require_scoped_object_key=Mock(),
            size_scoped_object_key=AsyncMock(return_value=12),
            delete_scoped_object_key=AsyncMock(),
        ),
        plugin_connector=SimpleNamespace(
            require_workspace_context=AsyncMock(side_effect=lambda context: context),
            call_rag_ingest=AsyncMock(return_value={'document_id': 'upstream-id', 'status': 'processing'}),
            call_rag_delete_document=AsyncMock(return_value=True),
        ),
    )
    ap.persistence_mgr = PersistenceManager(ap)
    ap.persistence_mgr.db = SimpleNamespace(get_engine=lambda: database)
    kb = KnowledgeBase(uuid='kb-a', workspace_uuid='workspace-a', name='kb', knowledge_engine_plugin_id='author/engine')
    return RuntimeKnowledgeBase(ap, kb, CONTEXT)


async def seed(runtime, *, status='pending', file_id='host-id', workspace='workspace-a', kb='kb-a'):
    values = dict(
        uuid=file_id, workspace_uuid=workspace, kb_id=kb, file_name='upload.txt', extension='txt', status=status
    )
    await runtime.ap.persistence_mgr.execute_async(sa.insert(File).values(**values))
    return File(**values)


async def read_file_row(runtime, file_id='host-id'):
    # A fresh connection proves committed state rather than an identity-map/mock result.
    async with runtime.ap.persistence_mgr.get_db_engine().connect() as conn:
        row = (await conn.execute(sa.select(File).where(File.uuid == file_id))).first()
        return None if row is None else dict(row._mapping)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'engine_id', ['dify-upstream', 'fastgpt-collection', 'ragflow-upstream', 'host-id', ' opaque ID ']
)
@pytest.mark.contract('rag_identity')
async def test_ingest_persists_exact_engine_identity_and_restart_delete(runtime, engine_id):
    file = await seed(runtime)
    runtime.ap.plugin_connector.call_rag_ingest.return_value['document_id'] = engine_id
    await runtime._store_file_task(CONTEXT, file, Mock())
    row = await read_file_row(runtime)
    assert row['uuid'] == 'host-id'
    assert row.get('engine_document_id') == engine_id
    assert row['status'] == 'completed'
    restarted = RuntimeKnowledgeBase(runtime.ap, runtime.knowledge_base_entity, CONTEXT)
    await restarted.delete_file(CONTEXT, 'host-id')
    runtime.ap.plugin_connector.call_rag_delete_document.assert_awaited_once_with('author/engine', engine_id, 'kb-a')
    assert await read_file_row(runtime) is None


@pytest.mark.asyncio
@pytest.mark.parametrize('response', [False, None, 0, 1, 'true', {}])
async def test_delete_without_explicit_confirmation_preserves_row(runtime, response):
    await seed(runtime, status='completed')
    runtime.ap.plugin_connector.call_rag_delete_document.return_value = response
    with pytest.raises(RuntimeError, match='delet'):
        await runtime.delete_file(CONTEXT, 'host-id')
    assert await read_file_row(runtime) is not None


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['exception', 'missing_plugin'])
async def test_delete_unavailable_retains_row(runtime, failure):
    await seed(runtime, status='completed')
    if failure == 'exception':
        runtime.ap.plugin_connector.call_rag_delete_document.side_effect = RuntimeError('upstream offline')
    else:
        runtime.knowledge_base_entity.knowledge_engine_plugin_id = None
    with pytest.raises(RuntimeError, match='delet'):
        await runtime.delete_file(CONTEXT, 'host-id')
    assert await read_file_row(runtime) is not None


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['pending', 'processing'])
async def test_delete_rejects_inflight_ingestion(runtime, status):
    await seed(runtime, status=status)
    with pytest.raises(RuntimeError, match='ingest'):
        await runtime.delete_file(CONTEXT, 'host-id')
    runtime.ap.plugin_connector.call_rag_delete_document.assert_not_awaited()
    assert await read_file_row(runtime) is not None


@pytest.mark.asyncio
@pytest.mark.parametrize('document_id', [None, '', '   ', 123, [], {}])
async def test_invalid_response_identity_cannot_complete(runtime, document_id):
    file = await seed(runtime)
    runtime.ap.plugin_connector.call_rag_ingest.return_value = {'status': 'completed', 'document_id': document_id}
    with pytest.raises(ValueError, match='document_id'):
        await runtime._store_file_task(CONTEXT, file, Mock())
    assert (await read_file_row(runtime))['status'] == 'interrupted'


@pytest.mark.asyncio
async def test_missing_response_identity_cannot_complete(runtime):
    file = await seed(runtime)
    runtime.ap.plugin_connector.call_rag_ingest.return_value = {'status': 'completed'}
    with pytest.raises(ValueError, match='document_id'):
        await runtime._store_file_task(CONTEXT, file, Mock())
    assert (await read_file_row(runtime))['status'] == 'interrupted'


@pytest.mark.asyncio
async def test_failed_ingestion_retains_returned_identity_for_cleanup(runtime):
    file = await seed(runtime)
    runtime.ap.plugin_connector.call_rag_ingest.return_value = {
        'document_id': 'uploaded-before-parsing-failed',
        'status': 'failed',
        'error_message': 'parsing failed',
    }
    with pytest.raises(Exception, match='parsing failed'):
        await runtime._store_file_task(CONTEXT, file, Mock())
    row = await read_file_row(runtime)
    assert row['status'] == 'failed'
    assert row.get('engine_document_id') == 'uploaded-before-parsing-failed'
    await runtime.delete_file(CONTEXT, 'host-id')
    runtime.ap.plugin_connector.call_rag_delete_document.assert_awaited_once_with(
        'author/engine', 'uploaded-before-parsing-failed', 'kb-a'
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['completed', 'failed'])
async def test_legacy_rows_use_host_id_only_with_confirmed_delete(runtime, status):
    await seed(runtime, status=status)
    await runtime.delete_file(CONTEXT, 'host-id')
    runtime.ap.plugin_connector.call_rag_delete_document.assert_awaited_once_with('author/engine', 'host-id', 'kb-a')
    assert await read_file_row(runtime) is None


@pytest.mark.asyncio
@pytest.mark.parametrize('workspace,kb', [('workspace-a', 'kb-other'), ('workspace-b', 'kb-b')])
async def test_status_update_and_delete_do_not_touch_other_scope(runtime, workspace, kb):
    await seed(runtime, workspace=workspace, kb=kb)
    assert not await runtime._set_file_status(CONTEXT, 'host-id', 'processing')
    with pytest.raises(WorkspaceNotFoundError):
        await runtime.delete_file(CONTEXT, 'host-id')
    assert (await read_file_row(runtime))['status'] == 'pending'
    runtime.ap.plugin_connector.call_rag_delete_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_rechecks_generation_after_plugin_response(runtime):
    await seed(runtime, status='completed')

    async def delete(*_):
        runtime.ap.workspace_service.get_execution_binding.side_effect = WorkspaceNotFoundError('stale placement')
        return True

    runtime.ap.plugin_connector.call_rag_delete_document.side_effect = delete
    with pytest.raises(WorkspaceNotFoundError):
        await runtime.delete_file(CONTEXT, 'host-id')
    assert await read_file_row(runtime) is not None


@pytest.mark.asyncio
async def test_ingest_rechecks_generation_before_mapping_write(runtime):
    file = await seed(runtime)

    async def ingest(*_):
        runtime.ap.workspace_service.get_execution_binding.side_effect = WorkspaceNotFoundError('stale placement')
        return {'document_id': 'upstream-id', 'status': 'completed'}

    runtime.ap.plugin_connector.call_rag_ingest.side_effect = ingest
    with pytest.raises(WorkspaceNotFoundError):
        await runtime._store_file_task(CONTEXT, file, Mock())
    row = await read_file_row(runtime)
    assert row['status'] == 'processing'
    assert row.get('engine_document_id') is None
    runtime.ap.storage_mgr.delete_scoped_object_key.assert_not_awaited()


@pytest.mark.asyncio
async def test_concurrent_delete_cannot_remove_ingestion_tracking(runtime):
    file = await seed(runtime)
    entered, release = asyncio.Event(), asyncio.Event()

    async def ingest(*_):
        entered.set()
        await release.wait()
        return {'document_id': 'upstream-id', 'status': 'completed'}

    runtime.ap.plugin_connector.call_rag_ingest.side_effect = ingest
    task = asyncio.create_task(runtime._store_file_task(CONTEXT, file, Mock()))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        with pytest.raises(RuntimeError, match='ingest'):
            await runtime.delete_file(CONTEXT, 'host-id')
    finally:
        release.set()
        await task
    assert (await read_file_row(runtime)).get('engine_document_id') == 'upstream-id'


@pytest.mark.asyncio
async def test_identity_and_completion_are_one_atomic_write(runtime):
    file = await seed(runtime)
    engine = runtime.ap.persistence_mgr.get_db_engine()
    attempts = []

    def reject_completion(_conn, _cursor, statement, parameters, _context, _many):
        if statement.startswith('UPDATE knowledge_base_files') and 'completed' in parameters:
            attempts.append(statement)
            raise RuntimeError('fixture mapping write failure')

    sa.event.listen(engine.sync_engine, 'before_cursor_execute', reject_completion)
    try:
        with pytest.raises(RuntimeError, match='mapping write failure'):
            await runtime._store_file_task(CONTEXT, file, Mock())
    finally:
        sa.event.remove(engine.sync_engine, 'before_cursor_execute', reject_completion)
    assert len(attempts) == 1
    assert 'engine_document_id=' in attempts[0]
    row = await read_file_row(runtime)
    assert row['status'] != 'completed'
    assert row.get('engine_document_id') == 'upstream-id'


@pytest.mark.asyncio
async def test_populated_legacy_migration_roundtrip(database):
    await create_schema(database, legacy=True)
    async with database.begin() as conn:
        await conn.execute(
            sa.text("""INSERT INTO knowledge_base_files
            (uuid, workspace_uuid, kb_id, file_name, extension, status)
            VALUES ('legacy', 'workspace-a', 'kb-a', 'original.txt', 'txt', 'completed')""")
        )
        assert 'engine_document_id' not in await conn.run_sync(
            lambda sync: {col['name'] for col in sa.inspect(sync).get_columns('knowledge_base_files')}
        )
    await run_alembic_stamp(database, OLD_HEAD)
    await run_alembic_upgrade(database, DOCUMENT_IDENTITY_REVISION)
    async with database.connect() as conn:
        columns = await conn.run_sync(lambda sync: sa.inspect(sync).get_columns('knowledge_base_files'))
        assert 'engine_document_id' in {col['name'] for col in columns}
        assert next(col for col in columns if col['name'] == 'engine_document_id')['nullable']
        row = (await conn.execute(sa.text('SELECT * FROM knowledge_base_files'))).mappings().one()
        assert row['uuid'] == 'legacy' and row['status'] == 'completed'
        assert row['engine_document_id'] is None
    assert await get_alembic_current(database) == DOCUMENT_IDENTITY_REVISION
    await run_alembic_upgrade(database, DOCUMENT_IDENTITY_REVISION)
    await run_alembic_stamp(database, OLD_HEAD)
    await run_alembic_upgrade(database, DOCUMENT_IDENTITY_REVISION)
    await run_alembic_downgrade(database, OLD_HEAD)
    async with database.connect() as conn:
        assert 'engine_document_id' not in await conn.run_sync(
            lambda sync: {col['name'] for col in sa.inspect(sync).get_columns('knowledge_base_files')}
        )
        assert (await conn.execute(sa.text('SELECT uuid FROM knowledge_base_files'))).scalar_one() == 'legacy'
    await run_alembic_upgrade(database)


@pytest.mark.asyncio
async def test_published_document_identity_branch_converges_to_release_head(database):
    await create_schema(database, legacy=True)
    await run_alembic_stamp(database, OLD_HEAD)
    await run_alembic_upgrade(database, DOCUMENT_IDENTITY_REVISION)
    async with database.begin() as conn:
        await conn.execute(
            sa.text("""INSERT INTO knowledge_base_files
            (uuid, workspace_uuid, kb_id, file_name, extension, status, engine_document_id)
            VALUES ('host-stable', 'workspace-a', 'kb-a', 'original.txt', 'txt', 'completed', 'opaque-engine-id')""")
        )
    await run_alembic_upgrade(database)
    await run_alembic_upgrade(database)
    assert await get_alembic_current(database) == current_head()
    async with database.connect() as conn:
        row = (await conn.execute(sa.text('SELECT * FROM knowledge_base_files'))).mappings().one()
        assert row['uuid'] == 'host-stable'
        assert row['engine_document_id'] == 'opaque-engine-id'
        assert row['status'] == 'completed'
        tables = await conn.run_sync(lambda sync: sa.inspect(sync).get_table_names())
        assert 'pipeline_migration_snapshots' in tables


@pytest.mark.asyncio
async def test_fresh_metadata_then_migration_is_idempotent(database):
    await create_schema(database)
    await run_alembic_stamp(database, OLD_HEAD)
    await run_alembic_upgrade(database)
    assert await get_alembic_current(database) == current_head()
    async with database.connect() as conn:
        assert 'engine_document_id' in await conn.run_sync(
            lambda sync: {col['name'] for col in sa.inspect(sync).get_columns('knowledge_base_files')}
        )
