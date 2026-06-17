"""Unit tests for MonitoringService trace observability."""

from __future__ import annotations

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.service.monitoring import MonitoringService
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence import monitoring as persistence_monitoring


pytestmark = pytest.mark.asyncio


class _SQLitePersistence:
    def __init__(self, engine):
        self._engine = engine

    def get_db_engine(self):
        return self._engine

    async def execute_async(self, *args, **kwargs):
        async with self._engine.connect() as conn:
            result = await conn.execute(*args, **kwargs)
            await conn.commit()
            return result

    def serialize_model(self, model, data, masked_columns=None):
        masked_columns = masked_columns or []
        return {
            column.name: getattr(data, column.name).isoformat()
            if isinstance(getattr(data, column.name), datetime.datetime)
            else getattr(data, column.name)
            for column in model.__table__.columns
            if column.name not in masked_columns
        }


@pytest.fixture
async def monitoring_service(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "monitoring.db"}')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    ap = SimpleNamespace(
        persistence_mgr=_SQLitePersistence(engine),
        instance_config=SimpleNamespace(data={'database': {'use': 'sqlite'}}),
        logger=Mock(),
    )
    service = MonitoringService(ap)
    yield service
    await engine.dispose()


async def test_trace_lifecycle_records_spans_and_returns_details(monitoring_service):
    started_at = datetime.datetime(2026, 1, 1, 12, 0, 0)
    ended_at = started_at + datetime.timedelta(milliseconds=125)

    trace_id = await monitoring_service.start_trace(
        trace_id='trace-test',
        name='Pipeline query',
        bot_id='bot-1',
        bot_name='Bot',
        pipeline_id='pipeline-1',
        pipeline_name='Default',
        session_id='session-1',
        message_id='message-1',
        query_id=42,
        attributes={'source': 'unit-test'},
    )
    assert trace_id == 'trace-test'

    root_span_id = await monitoring_service.record_span(
        trace_id=trace_id,
        span_id='span-root',
        name='Pipeline',
        kind='pipeline',
        status='completed',
        started_at=started_at,
        ended_at=ended_at,
        message_id='message-1',
        session_id='session-1',
        bot_id='bot-1',
        pipeline_id='pipeline-1',
        attributes={'stage_count': 2},
    )
    await monitoring_service.record_span(
        trace_id=trace_id,
        span_id='span-rag',
        parent_span_id=root_span_id,
        name='RAG retrieval',
        kind='rag.retrieval',
        status='failed',
        started_at=started_at + datetime.timedelta(seconds=1),
        duration=12.7,
        attributes={'top_k': 5},
        error_message='vector store timeout',
    )
    await monitoring_service.finish_trace(
        trace_id,
        status='completed',
        duration=250,
        message_id='message-final',
        attributes={'result_type': 'reply'},
    )

    traces, total = await monitoring_service.get_traces(
        bot_ids=['bot-1'],
        pipeline_ids=['pipeline-1'],
        session_ids=['session-1'],
        statuses=['success'],
        limit=10,
        offset=0,
    )

    assert total == 1
    assert traces[0]['trace_id'] == trace_id
    assert traces[0]['status'] == 'success'
    assert traces[0]['message_id'] == 'message-final'
    assert traces[0]['query_id'] == '42'
    assert traces[0]['attributes'] == {'result_type': 'reply'}

    details = await monitoring_service.get_trace_details(trace_id)
    assert details['found'] is True
    assert details['trace']['trace_id'] == trace_id
    assert [span['span_id'] for span in details['spans']] == ['span-root', 'span-rag']
    assert details['spans'][0]['status'] == 'success'
    assert details['spans'][0]['duration'] == 125
    assert details['spans'][0]['attributes'] == {'stage_count': 2}
    assert details['spans'][1]['status'] == 'error'
    assert details['spans'][1]['duration'] == 13
    assert details['spans'][1]['parent_span_id'] == 'span-root'
    assert details['spans'][1]['error_message'] == 'vector store timeout'


async def test_get_trace_details_returns_not_found_for_missing_trace(monitoring_service):
    details = await monitoring_service.get_trace_details('trace-missing')

    assert details == {'trace_id': 'trace-missing', 'found': False}


async def test_cleanup_expired_records_includes_traces_and_spans(monitoring_service):
    old_time = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(days=30)
    recent_time = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

    await monitoring_service.ap.persistence_mgr.execute_async(
        sqlalchemy.insert(persistence_monitoring.MonitoringTrace),
        [
            {
                'trace_id': 'trace-old',
                'started_at': old_time,
                'ended_at': old_time,
                'duration': 10,
                'status': 'success',
                'name': 'Old trace',
            },
            {
                'trace_id': 'trace-recent',
                'started_at': recent_time,
                'ended_at': recent_time,
                'duration': 10,
                'status': 'success',
                'name': 'Recent trace',
            },
        ],
    )
    await monitoring_service.ap.persistence_mgr.execute_async(
        sqlalchemy.insert(persistence_monitoring.MonitoringSpan),
        [
            {
                'span_id': 'span-old',
                'trace_id': 'trace-old',
                'name': 'Old span',
                'kind': 'pipeline',
                'status': 'success',
                'started_at': old_time,
                'ended_at': old_time,
            },
            {
                'span_id': 'span-recent',
                'trace_id': 'trace-recent',
                'name': 'Recent span',
                'kind': 'pipeline',
                'status': 'success',
                'started_at': recent_time,
                'ended_at': recent_time,
            },
        ],
    )

    monitoring_service._release_sqlite_space = AsyncMock()

    deleted = await monitoring_service.cleanup_expired_records(retention_days=7, batch_size=1)

    assert deleted['monitoring_traces'] == 1
    assert deleted['monitoring_spans'] == 1
    monitoring_service._release_sqlite_space.assert_awaited_once()

    remaining = await monitoring_service.get_trace_details('trace-recent')
    assert remaining['found'] is True
    assert remaining['spans'][0]['span_id'] == 'span-recent'
