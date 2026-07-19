from __future__ import annotations

import datetime
from types import SimpleNamespace

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.authz import WorkspaceRequiredError
from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.api.http.service.monitoring import MonitoringService
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.monitoring import MonitoringMessage
from langbot.pkg.entity.persistence.workspace import Workspace
from langbot.pkg.persistence.mgr import PersistenceManager


pytestmark = pytest.mark.asyncio

WORKSPACE_A = '00000000-0000-0000-0000-00000000000a'
WORKSPACE_B = '00000000-0000-0000-0000-00000000000b'


def _context(workspace_uuid: str) -> ExecutionContext:
    return ExecutionContext(
        instance_uuid='instance',
        workspace_uuid=workspace_uuid,
        placement_generation=3,
        bot_uuid='same-bot',
        pipeline_uuid='same-pipeline',
    )


class _PersistenceManager:
    def __init__(self, engine):
        self.engine = engine

    async def execute_async(self, *args, **kwargs):
        async with self.engine.connect() as connection:
            result = await connection.execute(*args, **kwargs)
            await connection.commit()
            return result

    def get_db_engine(self):
        return self.engine

    @staticmethod
    def serialize_model(model, data, masked_columns=None):
        return {
            column.name: (
                getattr(data, column.name).isoformat()
                if isinstance(getattr(data, column.name), datetime.datetime)
                else getattr(data, column.name)
            )
            for column in model.__table__.columns
            if column.name not in (masked_columns or [])
        }


@pytest.fixture
async def service(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "monitoring.db"}')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(
            sqlalchemy.insert(Workspace),
            [
                {
                    'uuid': WORKSPACE_A,
                    'instance_uuid': 'instance',
                    'name': 'A',
                    'slug': 'a',
                    'source': 'cloud_projection',
                },
                {
                    'uuid': WORKSPACE_B,
                    'instance_uuid': 'instance',
                    'name': 'B',
                    'slug': 'b',
                    'source': 'cloud_projection',
                },
            ],
        )
    application = SimpleNamespace(
        persistence_mgr=_PersistenceManager(engine),
        instance_config=SimpleNamespace(data={'database': {'use': 'sqlite'}}),
    )
    yield MonitoringService(application)
    await engine.dispose()


async def _record_message(service, context, content):
    return await service.record_message(
        context,
        bot_id='same-bot',
        bot_name='Same Bot',
        pipeline_id='same-pipeline',
        pipeline_name='Same Pipeline',
        message_content=content,
        session_id='same-session',
    )


async def test_monitoring_write_without_execution_context_fails_closed(service):
    with pytest.raises(WorkspaceRequiredError):
        await _record_message(service, None, 'unscoped')


async def test_same_session_and_resource_ids_do_not_collide(service):
    context_a = _context(WORKSPACE_A)
    context_b = _context(WORKSPACE_B)
    message_a = await _record_message(service, context_a, 'tenant-a')
    message_b = await _record_message(service, context_b, 'tenant-b')
    await service.record_session_start(
        context_a,
        session_id='same-session',
        bot_id='same-bot',
        bot_name='Same Bot',
        pipeline_id='same-pipeline',
        pipeline_name='Same Pipeline',
    )
    await service.record_session_start(
        context_b,
        session_id='same-session',
        bot_id='same-bot',
        bot_name='Same Bot',
        pipeline_id='same-pipeline',
        pipeline_name='Same Pipeline',
    )

    messages_a, total_a = await service.get_messages(context_a)
    messages_b, total_b = await service.get_messages(context_b)
    assert total_a == total_b == 1
    assert messages_a[0]['message_content'] == 'tenant-a'
    assert messages_b[0]['message_content'] == 'tenant-b'
    assert (await service.get_message_details(context_b, message_a))['found'] is False
    assert (await service.get_message_details(context_a, message_b))['found'] is False


async def test_tool_call_inherits_context_from_connection_message_row(service):
    context = _context(WORKSPACE_A)
    message_id = await _record_message(service, context, 'tool context')

    await service.record_tool_call(
        context,
        tool_name='search',
        tool_source='native',
        duration=12,
        message_id=message_id,
    )

    tool_calls, total = await service.get_tool_calls(context)
    assert total == 1
    assert tool_calls[0]['bot_id'] == 'same-bot'
    assert tool_calls[0]['pipeline_id'] == 'same-pipeline'
    assert tool_calls[0]['session_id'] == 'same-session'
    assert tool_calls[0]['message_id'] == message_id


async def test_feedback_upsert_and_cancel_are_workspace_scoped(service):
    context_a = _context(WORKSPACE_A)
    context_b = _context(WORKSPACE_B)
    await service.record_feedback(context_a, feedback_id='same-feedback', feedback_type=1)
    await service.record_feedback(context_b, feedback_id='same-feedback', feedback_type=2)

    stats_a = await service.get_feedback_stats(context_a)
    stats_b = await service.get_feedback_stats(context_b)
    assert stats_a['total_likes'] == 1
    assert stats_a['total_dislikes'] == 0
    assert stats_b['total_likes'] == 0
    assert stats_b['total_dislikes'] == 1

    await service.record_feedback(context_a, feedback_id='same-feedback', feedback_type=3)
    assert (await service.get_feedback_stats(context_a))['total_feedback'] == 0
    assert (await service.get_feedback_stats(context_b))['total_feedback'] == 1


async def test_cleanup_commits_sqlite_delete_before_vacuum(tmp_path):
    engine = create_async_engine(
        f'sqlite+aiosqlite:///{tmp_path / "monitoring-cleanup.db"}',
        connect_args={'timeout': 0.1},
    )
    application = SimpleNamespace(
        instance_config=SimpleNamespace(data={'database': {'use': 'sqlite'}}),
    )
    manager = PersistenceManager(application)
    manager.db = SimpleNamespace(get_engine=lambda: engine)
    application.persistence_mgr = manager
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.execute(
                sqlalchemy.insert(Workspace).values(
                    uuid=WORKSPACE_A,
                    instance_uuid='instance',
                    name='A',
                    slug='a',
                    source='cloud_projection',
                )
            )
            await connection.execute(
                sqlalchemy.insert(MonitoringMessage).values(
                    id='expired-message',
                    workspace_uuid=WORKSPACE_A,
                    timestamp=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
                    - datetime.timedelta(days=30),
                    bot_id='bot',
                    bot_name='Bot',
                    pipeline_id='pipeline',
                    pipeline_name='Pipeline',
                    message_content='expired',
                    session_id='session',
                    status='success',
                    level='info',
                )
            )

        deleted = await MonitoringService(application).cleanup_expired_records(
            _context(WORKSPACE_A),
            retention_days=1,
        )

        assert deleted['monitoring_messages'] == 1
        async with engine.connect() as connection:
            remaining = await connection.scalar(
                sqlalchemy.select(sqlalchemy.func.count()).select_from(MonitoringMessage)
            )
        assert remaining == 0
    finally:
        await engine.dispose()
