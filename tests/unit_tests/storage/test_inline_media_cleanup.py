"""Historical image TTL preserves records and makes bounded, durable progress."""

import datetime as dt
import importlib
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.api.http.service.maintenance import MaintenanceService
from langbot.pkg.entity.persistence.agent_run import AgentRun, AgentRunEvent
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.event_log import EventLog
from langbot.pkg.entity.persistence.metadata import WorkspaceMetadata
from langbot.pkg.entity.persistence.monitoring import MonitoringMessage
from langbot.pkg.entity.persistence.transcript import Transcript
from langbot.pkg.entity.persistence.workspace import Workspace
from langbot.pkg.persistence.mgr import PersistenceManager
from langbot.pkg.storage import inline_media_cleanup as cleanup
from langbot.pkg.storage.media import MediaCache


WORKSPACE_A = '00000000-0000-0000-0000-00000000000a'
WORKSPACE_B = '00000000-0000-0000-0000-00000000000b'
CONTEXT = ExecutionContext(instance_uuid='instance', workspace_uuid=WORKSPACE_A, placement_generation=1)
NOW = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
OLD = NOW - dt.timedelta(days=40)
PAYLOAD = json.dumps(
    {
        'content': [
            {'type': 'Plain', 'text': 'Keep the message'},
            {'type': 'Image', 'base64': 'eA==', 'url': 'https://upstream/image'},
            {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,eA=='}},
            {'type': 'image_base64', 'image_base64': 'eA=='},
            {'type': 'Image', 'url': '/api/v1/files/media/already-externalized.png'},
        ],
        'custom': {'count': 0, 'enabled': False},
    }
)
SOURCES = [MonitoringMessage, EventLog, AgentRun, AgentRunEvent, Transcript]


@pytest.fixture
async def application(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "inline-media.db"}')
    ap = SimpleNamespace(logger=logging.getLogger(__name__), instance_config=SimpleNamespace(data={}))
    ap.persistence_mgr = PersistenceManager(ap)
    ap.persistence_mgr.db = SimpleNamespace(get_engine=lambda: engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            sa.insert(Workspace),
            [
                {
                    'uuid': workspace,
                    'instance_uuid': 'instance',
                    'name': workspace,
                    'slug': workspace,
                    'source': 'cloud_projection',
                }
                for workspace in (WORKSPACE_A, WORKSPACE_B)
            ],
        )
    yield ap
    await engine.dispose()


async def insert_record(ap, model, number, workspace=WORKSPACE_A, timestamp=OLD, payload=PAYLOAD):
    if model is MonitoringMessage:
        values = dict(
            id=str(number),
            workspace_uuid=workspace,
            timestamp=timestamp,
            message_content=payload,
            bot_id='bot',
            bot_name='Bot',
            pipeline_id='pipeline',
            pipeline_name='Pipeline',
            session_id='session',
            status='success',
            level='info',
        )
        field = 'message_content'
    elif model is AgentRunEvent:
        run_id = f'parent-{number}'
        await ap.persistence_mgr.execute_async(
            sa.insert(AgentRun).values(
                run_id=run_id, runner_id='runner', workspace_id=workspace, status='completed', created_at=timestamp
            )
        )
        values = dict(
            id=number, run_id=run_id, sequence=1, type='message.completed', created_at=timestamp, data_json=payload
        )
        field = 'data_json'
    else:
        values = dict(id=number, workspace_id=workspace, created_at=timestamp)
        if model is EventLog:
            values.update(
                event_id=f'event-{number}', event_type='message.received', source='platform', input_json=payload
            )
            field = 'input_json'
        elif model is AgentRun:
            values.update(
                run_id=f'run-{number}',
                runner_id='runner',
                status='completed',
                metadata_json=payload,
                updated_at=timestamp,
            )
            field = 'metadata_json'
        else:
            values.update(
                transcript_id=f'transcript-{number}',
                event_id=f'event-{number}',
                conversation_id='conversation',
                role='user',
                item_type='message',
                seq=number,
                content_json=payload,
            )
            field = 'content_json'
    # Seed the pre-contract database format without applying today's write policy.
    values[field] = sa.bindparam('historical_payload', payload, type_=sa.Text())
    await ap.persistence_mgr.execute_async(sa.insert(model).values(**values))
    return field


async def read_record(ap, model, number, field):
    return (
        await ap.persistence_mgr.execute_async(sa.select(getattr(model, field)).where(model.id == number))
    ).scalar_one()


@pytest.mark.asyncio
@pytest.mark.parametrize('model', SOURCES, ids=lambda model: model.__tablename__)
async def test_ttl_expires_only_old_images_in_the_current_workspace(application, model):
    field = await insert_record(application, model, 1)
    await insert_record(application, model, 2, timestamp=NOW)
    await insert_record(application, model, 3, workspace=WORKSPACE_B)
    assert await cleanup.cleanup_inline_media(application, CONTEXT, 30) == 1
    saved = json.loads(await read_record(application, model, 1, field))
    assert not MediaCache.has_inline_images(saved)
    assert saved['content'][0]['text'] == 'Keep the message'
    assert saved['content'][1]['url'] == 'https://upstream/image'
    assert saved['content'][-1]['url'].startswith('/api/v1/files/media/')
    assert saved['custom'] == {'count': 0, 'enabled': False}
    assert await read_record(application, model, 2, field) == PAYLOAD
    assert await read_record(application, model, 3, field) == PAYLOAD
    if model is AgentRun:
        assert await read_record(application, model, 1, 'updated_at') == OLD


@pytest.mark.asyncio
async def test_row_budget_resumes_persisted_progress_and_later_expiry(application, monkeypatch):
    monkeypatch.setattr(cleanup, 'ROWS_PER_TABLE', 1)
    for number in (1, 2):
        await insert_record(application, MonitoringMessage, number)
    await insert_record(application, MonitoringMessage, 3, timestamp=NOW - dt.timedelta(days=5))
    for number in (1, 2):
        assert await cleanup.cleanup_inline_media(application, CONTEXT, 30) == 1
        assert not MediaCache.has_inline_images(
            json.loads(await read_record(application, MonitoringMessage, number, 'message_content'))
        )
    assert await cleanup.cleanup_inline_media(application, CONTEXT, 30) == 0
    assert await cleanup.cleanup_inline_media(application, CONTEXT, 1) == 1
    assert (await application.persistence_mgr.execute_async(sa.select(WorkspaceMetadata.value))).first()


@pytest.mark.asyncio
async def test_event_scan_budget_advances_past_foreign_events_without_reading_payloads(application, monkeypatch):
    monkeypatch.setattr(cleanup, 'ROWS_PER_TABLE', 2)
    for number in range(1, 5):
        await insert_record(application, AgentRunEvent, number, workspace=WORKSPACE_B)
    await application.persistence_mgr.execute_async(sa.delete(AgentRun).where(AgentRun.run_id == 'parent-3'))
    await insert_record(application, AgentRunEvent, 5)
    await insert_record(application, AgentRunEvent, 6, timestamp=NOW)
    engine = application.persistence_mgr.get_db_engine()
    statements = []

    def capture_statement(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith('SELECT ') and 'FROM agent_run_event' in statement:
            columns = tuple(context.compiled.statement.selected_columns.keys())
            statements.append((statement, parameters, columns))

    sa.event.listen(engine.sync_engine, 'before_cursor_execute', capture_statement)
    try:
        for expected_id in (2, 4):
            assert await cleanup.cleanup_inline_media(application, CONTEXT, 30) == 0
            cursor = (
                await application.persistence_mgr.execute_async(
                    sa.select(WorkspaceMetadata.value).where(
                        WorkspaceMetadata.workspace_uuid == WORKSPACE_A,
                        WorkspaceMetadata.key == cleanup.CURSOR_PREFIX + 'agent_run_event',
                    )
                )
            ).scalar_one()
            assert json.loads(cursor) == [OLD.isoformat(), expected_id]
        assert await cleanup.cleanup_inline_media(application, CONTEXT, 30) == 1
        assert await cleanup.cleanup_inline_media(application, CONTEXT, 30) == 0
    finally:
        sa.event.remove(engine.sync_engine, 'before_cursor_execute', capture_statement)

    assert not MediaCache.has_inline_images(json.loads(await read_record(application, AgentRunEvent, 5, 'data_json')))
    for number in (1, 2, 3, 4, 6):
        assert await read_record(application, AgentRunEvent, number, 'data_json') == PAYLOAD
    assert {columns for _, _, columns in statements} == {('id', 'created_at'), ('data_json', 'metadata_json')}
    async with engine.connect() as connection:
        for statement, parameters, columns in statements:
            plan = ' '.join(
                row[3] for row in await connection.exec_driver_sql('EXPLAIN QUERY PLAN ' + statement, parameters)
            )
            # Classify by projection; SQLite versions describe EXISTS plans differently.
            if columns == ('id', 'created_at'):
                assert 'COVERING INDEX ix_agent_run_event_media_ttl' in plan, plan
            else:
                assert 'SEARCH agent_run_event USING INTEGER PRIMARY KEY' in plan, plan
            assert 'TEMP B-TREE' not in plan, plan


@pytest.mark.asyncio
async def test_payload_budget_processes_one_oversized_row_then_yields(application, monkeypatch):
    monkeypatch.setattr(cleanup, 'CHARACTERS_PER_TABLE', 1)
    await insert_record(application, MonitoringMessage, 1)
    await insert_record(application, MonitoringMessage, 2)
    assert await cleanup.cleanup_inline_media(application, CONTEXT, 30) == 1
    assert await read_record(application, MonitoringMessage, 2, 'message_content') == PAYLOAD
    assert await cleanup.cleanup_inline_media(application, CONTEXT, 30) == 1


@pytest.mark.asyncio
async def test_payload_update_and_cursor_roll_back_together(application, monkeypatch):
    await insert_record(application, MonitoringMessage, 1)
    execute = application.persistence_mgr.execute_async

    async def fail_checkpoint(statement, *args, **kwargs):
        if isinstance(statement, sa.sql.dml.Insert) and statement.table.name == 'workspace_metadata':
            raise RuntimeError('Checkpoint failed')
        return await execute(statement, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(application.persistence_mgr, 'execute_async', fail_checkpoint)
        with pytest.raises(RuntimeError, match='Checkpoint failed'):
            await cleanup.cleanup_inline_media(application, CONTEXT, 30)
    assert await read_record(application, MonitoringMessage, 1, 'message_content') == PAYLOAD
    assert await cleanup.cleanup_inline_media(application, CONTEXT, 30) == 1


@pytest.mark.asyncio
async def test_unchanged_or_invalid_records_are_not_rewritten_or_revisited(application):
    values = [
        'plain text',
        '{invalid base64 JSON',
        '{"count": 0, "enabled": false}',
        json.dumps({'type': 'Image', 'url': '/api/v1/files/media/existing.png'}),
    ]
    for number, payload in enumerate(values, 1):
        await insert_record(application, MonitoringMessage, number, payload=payload)
    assert await cleanup.cleanup_inline_media(application, CONTEXT, 30) == 0
    for number, payload in enumerate(values, 1):
        assert await read_record(application, MonitoringMessage, number, 'message_content') == payload
    before = (await application.persistence_mgr.execute_async(sa.select(WorkspaceMetadata.value))).scalars().all()
    assert await cleanup.cleanup_inline_media(application, CONTEXT, 30) == 0
    after = (await application.persistence_mgr.execute_async(sa.select(WorkspaceMetadata.value))).scalars().all()
    assert before == after


@pytest.mark.asyncio
@pytest.mark.parametrize('model', [MonitoringMessage, AgentRunEvent])
async def test_concurrent_payload_change_does_not_advance_cursor(application, monkeypatch, model):
    field = await insert_record(application, model, 1)
    execute = application.persistence_mgr.execute_async

    async def lose_update(statement, *args, **kwargs):
        if isinstance(statement, sa.sql.dml.Update) and statement.table.name == model.__tablename__:
            return SimpleNamespace(rowcount=0)
        return await execute(statement, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(application.persistence_mgr, 'execute_async', lose_update)
        assert await cleanup.cleanup_inline_media(application, CONTEXT, 30) == 0
    assert (
        await execute(
            sa.select(WorkspaceMetadata.value).where(
                WorkspaceMetadata.workspace_uuid == WORKSPACE_A,
                WorkspaceMetadata.key == cleanup.CURSOR_PREFIX + model.__tablename__,
            )
        )
    ).first() is None
    assert await read_record(application, model, 1, field) == PAYLOAD
    assert await cleanup.cleanup_inline_media(application, CONTEXT, 30) == 1


@pytest.mark.asyncio
async def test_storage_maintenance_uses_media_ttl_for_inline_records(application):
    await insert_record(application, MonitoringMessage, 1, timestamp=NOW - dt.timedelta(days=5))
    application.instance_config.data = {'storage': {'media_cache': {'retention_days': 2}}}
    cache = SimpleNamespace(cleanup=AsyncMock(return_value={}))
    application.storage_mgr = SimpleNamespace(media_cache=cache)
    service = MaintenanceService(application)
    service._is_oss_singleton = AsyncMock(return_value=False)
    service._cleanup_expired_uploaded_files = AsyncMock(return_value=0)
    assert (await service.cleanup_expired_files(CONTEXT))['inline_media_records'] == 1
    cache.cleanup.assert_not_awaited()


def test_ttl_indexes_migrate_idempotently_and_support_cursor_queries():
    migration = importlib.import_module('langbot.pkg.persistence.alembic.versions.0039_execution_lease_indexes')
    engine = sa.create_engine('sqlite:///:memory:')
    try:
        with engine.begin() as connection:
            Base.metadata.create_all(connection)
            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
                migration.upgrade()
                migration.upgrade()
                for table, name, columns in migration.INDEXES:
                    indexes = {
                        index['name']: index['column_names'] for index in sa.inspect(connection).get_indexes(table)
                    }
                    assert indexes[name] == columns
                    orm_index = next(index for index in Base.metadata.tables[table].indexes if index.name == name)
                    assert [column.name for column in orm_index.columns] == columns
                query = (
                    sa.select(MonitoringMessage.id, MonitoringMessage.message_content)
                    .where(
                        MonitoringMessage.workspace_uuid == WORKSPACE_A,
                        MonitoringMessage.timestamp < NOW,
                        sa.tuple_(MonitoringMessage.timestamp, MonitoringMessage.id) > sa.tuple_(OLD, '0'),
                    )
                    .order_by(MonitoringMessage.timestamp, MonitoringMessage.id)
                    .limit(1)
                )
                sql = str(query.compile(dialect=engine.dialect, compile_kwargs={'literal_binds': True}))
                plan = ' '.join(str(row) for row in connection.exec_driver_sql('EXPLAIN QUERY PLAN ' + sql))
                assert 'ix_monitoring_messages_media_ttl' in plan
                assert 'TEMP B-TREE' not in plan
                migration.downgrade()
    finally:
        engine.dispose()


def test_index_migration_allows_historical_schemas_without_monitoring_tables():
    migration = importlib.import_module('langbot.pkg.persistence.alembic.versions.0039_execution_lease_indexes')
    engine = sa.create_engine('sqlite:///:memory:')
    try:
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                migration.downgrade()
                assert not sa.inspect(connection).get_table_names()
    finally:
        engine.dispose()
