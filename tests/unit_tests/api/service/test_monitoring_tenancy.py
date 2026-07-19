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
from langbot.pkg.entity.persistence.workspace import Workspace


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
