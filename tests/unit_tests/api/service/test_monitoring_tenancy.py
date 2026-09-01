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
from langbot.pkg.entity.persistence.monitoring import MonitoringLLMCall, MonitoringMessage
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


async def test_session_search_matches_user_id_or_name_within_workspace(service):
    context_a = _context(WORKSPACE_A)
    context_b = _context(WORKSPACE_B)
    fixtures = [
        (context_a, 'session-id-match', 'customer-42', 'Alice'),
        (context_a, 'session-name-match', 'customer-99', 'Bob Alice Cooper'),
        (context_a, 'session-no-match', 'customer-7', 'Bob'),
        (context_b, 'session-other-workspace', 'customer-42', 'Alice'),
    ]
    for context, session_id, user_id, user_name in fixtures:
        await service.record_session_start(
            context,
            session_id=session_id,
            bot_id='same-bot',
            bot_name='Same Bot',
            pipeline_id='same-pipeline',
            pipeline_name='Same Pipeline',
            user_id=user_id,
            user_name=user_name,
        )

    by_id, id_total = await service.get_sessions(context_a, user_query='customer-42')
    by_name, name_total = await service.get_sessions(context_a, user_query='alice')

    assert id_total == 1
    assert [session['session_id'] for session in by_id] == ['session-id-match']
    assert name_total == 2
    assert {session['session_id'] for session in by_name} == {
        'session-id-match',
        'session-name-match',
    }


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


async def test_monitoring_queries_and_detail_views_are_strictly_bounded(service):
    context = _context(WORKSPACE_A)
    service.ap.instance_config.data['monitoring'] = {
        'query_limits': {
            'page_rows': 2,
            'export_rows': 2,
            'detail_rows': 2,
            'timeseries_buckets': 2,
            'max_offset': 10,
        }
    }
    await service.record_session_start(
        context,
        session_id='same-session',
        bot_id='same-bot',
        bot_name='Same Bot',
        pipeline_id='same-pipeline',
        pipeline_name='Same Pipeline',
    )
    message_ids = [await _record_message(service, context, f'message-{index}') for index in range(4)]
    for index in range(3):
        await service.record_llm_call(
            context,
            bot_id='same-bot',
            bot_name='Same Bot',
            pipeline_id='same-pipeline',
            pipeline_name='Same Pipeline',
            session_id='same-session',
            model_name='model',
            input_tokens=1,
            output_tokens=2,
            duration=10,
            message_id=message_ids[0],
        )
        await service.record_tool_call(
            context,
            tool_name=f'tool-{index}',
            tool_source='native',
            duration=5,
            session_id='same-session',
            message_id=message_ids[0],
        )
        await service.record_error(
            context,
            bot_id='same-bot',
            bot_name='Same Bot',
            pipeline_id='same-pipeline',
            pipeline_name='Same Pipeline',
            error_type='Failure',
            error_message=f'error-{index}',
            session_id='same-session',
            message_id=message_ids[0],
        )

    page, total = await service.get_messages(context, limit=100000, offset=-5)
    exported = await service.export_messages(context, limit=100000)
    session_detail = await service.get_session_analysis(context, 'same-session')
    message_detail = await service.get_message_details(context, message_ids[0])

    assert total == 4
    assert len(page) == 2
    assert len(exported) == 2
    assert session_detail['message_stats']['total'] == 4
    assert session_detail['llm_stats']['total_calls'] == 3
    assert session_detail['tool_stats']['total_calls'] == 3
    assert len(session_detail['tool_calls']) == 2
    assert len(session_detail['errors']) == 2
    assert session_detail['detail_truncated'] == {
        'tool_calls': True,
        'errors': True,
    }
    assert message_detail['llm_stats']['total_calls'] == 3
    assert len(message_detail['llm_calls']) == 2
    assert len(message_detail['errors']) == 2
    assert message_detail['detail_truncated'] == {
        'llm_calls': True,
        'errors': True,
    }

    service.ap.instance_config.data['monitoring']['query_limits'] = {
        'page_rows': 999999,
        'export_rows': 999999,
        'detail_rows': 999999,
        'timeseries_buckets': 999999,
        'max_offset': 99999999,
    }
    assert service.normalize_page_window(999999, 99999999) == (5000, 10000000)
    assert service.normalize_export_limit(999999) == 50000
    assert service._detail_limit() == 10000
    assert service._timeseries_bucket_limit() == 10000


async def test_token_statistics_aggregate_and_limit_groups_in_database(service):
    context = _context(WORKSPACE_A)
    service.ap.instance_config.data['monitoring'] = {
        'query_limits': {
            'page_rows': 1,
            'timeseries_buckets': 2,
        }
    }
    first_hour = datetime.datetime(2026, 7, 28, 10, 0)
    rows = [
        {
            'id': f'llm-{index}',
            'workspace_uuid': WORKSPACE_A,
            'timestamp': first_hour + datetime.timedelta(hours=hour, minutes=index),
            'model_name': model,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': input_tokens + output_tokens,
            'duration': 100,
            'cost': 0.01,
            'status': 'success',
            'bot_id': 'same-bot',
            'bot_name': 'Same Bot',
            'pipeline_id': 'same-pipeline',
            'pipeline_name': 'Same Pipeline',
            'session_id': 'same-session',
        }
        for index, (hour, model, input_tokens, output_tokens) in enumerate(
            [
                (0, 'small-model', 1, 2),
                (1, 'large-model', 3, 4),
                (2, 'large-model', 5, 6),
                (2, 'large-model', 7, 8),
            ]
        )
    ]
    await service.ap.persistence_mgr.execute_async(sqlalchemy.insert(MonitoringLLMCall), rows)

    stats = await service.get_token_statistics(context, bucket='hour')

    assert stats['summary']['total_calls'] == 4
    assert stats['summary']['total_tokens'] == 36
    assert stats['by_model_truncated'] is True
    assert [model['model_name'] for model in stats['by_model']] == ['large-model']
    assert stats['timeseries_truncated'] is True
    assert stats['timeseries'] == [
        {
            'bucket': '2026-07-28 11:00',
            'input_tokens': 3,
            'output_tokens': 4,
            'total_tokens': 7,
            'calls': 1,
        },
        {
            'bucket': '2026-07-28 12:00',
            'input_tokens': 12,
            'output_tokens': 14,
            'total_tokens': 26,
            'calls': 2,
        },
    ]


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
                sqlalchemy.insert(MonitoringMessage),
                [
                    {
                        'id': f'expired-message-{index}',
                        'workspace_uuid': WORKSPACE_A,
                        'timestamp': datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
                        - datetime.timedelta(days=30),
                        'bot_id': 'bot',
                        'bot_name': 'Bot',
                        'pipeline_id': 'pipeline',
                        'pipeline_name': 'Pipeline',
                        'message_content': 'expired',
                        'session_id': 'session',
                        'status': 'success',
                        'level': 'info',
                    }
                    for index in range(5)
                ],
            )

        deleted = await MonitoringService(application).cleanup_expired_records(
            _context(WORKSPACE_A),
            retention_days=1,
            batch_size=2,
            max_batches_per_table=1,
        )

        assert deleted['monitoring_messages'] == 2
        async with engine.connect() as connection:
            remaining = await connection.scalar(
                sqlalchemy.select(sqlalchemy.func.count()).select_from(MonitoringMessage)
            )
        assert remaining == 3
    finally:
        await engine.dispose()
