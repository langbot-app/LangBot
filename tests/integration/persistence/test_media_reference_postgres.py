"""Media writes against real asyncpg and existing TEXT columns.

Run with TEST_POSTGRES_URL pointing to a disposable PostgreSQL database.
Each case creates and removes its own schema.
"""

import importlib
import json
import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from langbot.pkg.agent.runner.run_journal import AgentRunJournal
from langbot.pkg.agent.runner.run_ledger_store import RunLedgerStore
from langbot.pkg.entity.persistence.agent_run import AgentRun, AgentRunEvent
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.persistence.tenant_uow import _validate_scoped_statement_call
from langbot.pkg.storage.media import MediaCache

pytestmark = [pytest.mark.integration, pytest.mark.slow, pytest.mark.asyncio]


def _published_schema(connection):
    with Operations.context(MigrationContext.configure(connection)):
        for revision in (
            '58846a8d7a81_add_event_log_and_transcript_tables',
            '8d3a1f2c4b6e_add_agent_run_ledger',
            '0036_execution_host_leases',
        ):
            importlib.import_module(f'langbot.pkg.persistence.alembic.versions.{revision}').upgrade()


@pytest.fixture(params=['metadata', 'published_migrations'])
async def pg_engine(request):
    url = os.environ.get('TEST_POSTGRES_URL')
    if not url:
        pytest.skip('TEST_POSTGRES_URL is required (disposable PostgreSQL)')
    namespace = f'media_contract_{uuid.uuid4().hex}'
    admin = create_async_engine(url)
    engine = None
    try:
        async with admin.begin() as conn:
            await conn.execute(sa.text(f'CREATE SCHEMA {namespace}'))
        engine = create_async_engine(url, connect_args={'server_settings': {'search_path': namespace}})
        async with engine.begin() as conn:
            if request.param == 'metadata':
                await conn.run_sync(
                    lambda sync: Base.metadata.create_all(sync, tables=[AgentRun.__table__, AgentRunEvent.__table__])
                )
            else:
                await conn.run_sync(_published_schema)
        yield engine
    finally:
        if engine is not None:
            await engine.dispose()
        async with admin.begin() as conn:
            await conn.execute(sa.text(f'DROP SCHEMA IF EXISTS {namespace} CASCADE'))
        await admin.dispose()


@pytest.fixture
async def store(pg_engine):
    store = RunLedgerStore(pg_engine)
    await store.create_run(
        run_id='run', event_id='event', binding_id=None, runner_id='runner', workspace_id='ws', metadata={'attempt': 0}
    )
    return store


@pytest.mark.parametrize('writer', ['orm', 'insert', 'update'])
@pytest.mark.parametrize(
    'image',
    [
        {'type': 'Image', 'base64': 'eA=='},
        {'type': 'image_base64', 'image_base64': 'eA=='},
        {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,eA=='}},
    ],
)
async def test_unprocessed_images_roll_back(pg_engine, store, writer, image):
    content = json.dumps({'nested': [image]})
    with pytest.raises(sa.exc.StatementError, match='Inline images cannot be persisted'):
        if writer == 'orm':
            async with AsyncSession(pg_engine) as session:
                run = (await session.execute(sa.select(AgentRun).where(AgentRun.run_id == 'run'))).scalar_one()
                run.status = 'completed'
                run.metadata_json = content
                await session.commit()
        else:
            statement = (
                sa.insert(AgentRun).values(run_id='new', runner_id='runner', status='completed', metadata_json=content)
                if writer == 'insert'
                else sa.update(AgentRun)
                .where(AgentRun.run_id == 'run')
                .values(status='completed', metadata_json=content)
            )
            async with pg_engine.begin() as conn:
                await conn.execute(statement)
    run = await store.get_run('run')
    assert run['status'] == 'running'
    assert run['metadata'] == {'attempt': 0}
    assert await store.get_run('new') is None


@pytest.mark.parametrize('operation', ['pin', 'finalize', 'status_only'])
async def test_legacy_metadata_updates_preserve_the_write_contract(pg_engine, store, operation):
    legacy = {'image': {'type': 'Image', 'base64': 'eA=='}, 'attempt': 0}
    original = json.dumps(legacy)
    async with pg_engine.begin() as conn:
        # Seed the pre-contract format while keeping current model mappings.
        await conn.execute(
            sa.update(AgentRun)
            .where(AgentRun.run_id == 'run')
            .values(metadata_json=sa.bindparam('legacy', original, type_=sa.Text()))
        )
        assert (
            await conn.execute(sa.select(AgentRun.run_id).where(AgentRun.metadata_json == original))
        ).scalar_one() == 'run'

    with pytest.raises(sa.exc.StatementError, match='Inline images cannot be persisted'):
        await store.finalize_run(
            run_id='run', status='completed', metadata={'new': {'type': 'Image', 'base64': 'eQ=='}}
        )
    assert (await store.get_run('run'))['status'] == 'running'
    assert (await store.get_run('run'))['metadata'] == legacy

    if operation == 'pin':
        assert await store.pin_skill_revision('run', 'ws', 'demo', 'v1') == 'v1'
        assert (await store.get_run('run'))['metadata'] == {
            'image': {'type': 'Image', 'base64': None},
            'attempt': 0,
            'activated_skills': {'demo': 'v1'},
        }
    else:
        metadata = {'note': 'done'} if operation == 'finalize' else None
        run = await store.finalize_run(run_id='run', status='completed', metadata=metadata)
        assert run['status'] == 'completed'
        assert run['metadata'] == (
            {'image': {'type': 'Image', 'base64': None}, 'attempt': 0, 'note': 'done'}
            if metadata is not None
            else legacy
        )


async def test_journal_retains_references_and_redacts_metadata(pg_engine, store):
    provider = SimpleNamespace(exists=AsyncMock(return_value=False), save=AsyncMock())
    storage = SimpleNamespace(storage_provider=provider)
    app = SimpleNamespace(storage_mgr=storage, persistence_mgr=SimpleNamespace(get_db_engine=lambda: pg_engine))
    storage.media_cache = MediaCache(app, storage)
    image = {'type': 'Image', 'base64': 'eA=='}
    event = await AgentRunJournal(app).append_run_result(
        run_id='run',
        sequence=1,
        result_dict={'type': 'tool.call.completed', 'data': {'image': image}},
        metadata={'preview': image},
    )
    assert event['data']['image']['base64'] is None
    assert event['data']['image']['url'].startswith('/api/v1/files/media/')
    assert event['metadata'] == {'preview': {'type': 'Image', 'base64': None}}
    provider.save.assert_awaited_once()
    async with pg_engine.connect() as conn:
        row = (await conn.execute(sa.select(AgentRunEvent.data_json, AgentRunEvent.metadata_json))).one()
        assert json.loads(row.data_json) == event['data']
        assert json.loads(row.metadata_json) == event['metadata']


async def test_text_schema_and_monitoring_json_casts(pg_engine, store):
    statement = sa.select(sa.cast(AgentRun.metadata_json, sa.JSON)['attempt'].as_integer())
    _validate_scoped_statement_call((statement,), {})
    async with pg_engine.connect() as conn:
        assert (await conn.execute(statement)).scalar_one() == 0
        columns = (
            (
                await conn.execute(
                    sa.text(
                        'SELECT data_type FROM information_schema.columns WHERE table_schema = current_schema() '
                        "AND table_name IN ('agent_run', 'agent_run_event') AND column_name IN ('data_json', 'metadata_json')"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert columns == ['text'] * 3
