from __future__ import annotations

import datetime
from types import SimpleNamespace

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.monitoring import MonitoringLLMCall, MonitoringMessage
from langbot.pkg.entity.persistence.workspace import Workspace

pytestmark = pytest.mark.asyncio

A = '00000000-0000-0000-0000-00000000000a'
B = '00000000-0000-0000-0000-00000000000b'
START = datetime.datetime(2026, 1, 1)


@pytest.fixture
async def traffic_app():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(
            sqlalchemy.insert(Workspace),
            [
                {'uuid': wid, 'instance_uuid': 'instance', 'name': wid, 'slug': wid, 'source': 'cloud_projection'}
                for wid in (A, B)
            ],
        )
        for wid, bot, count in [(A, 'bot-a', 60), (A, 'bot-b', 7), (B, 'bot-a', 9)]:
            common = {
                'workspace_uuid': wid,
                'timestamp': START,
                'bot_id': bot,
                'bot_name': bot,
                'pipeline_id': 'pipeline',
                'pipeline_name': 'Pipeline',
                'session_id': 'person_42',
                'status': 'success',
            }
            await connection.execute(
                sqlalchemy.insert(MonitoringMessage),
                [
                    dict(common, id=f'{wid}-{bot}-{i}', message_content='test fixture', level='info', role='user')
                    for i in range(count)
                ],
            )
            await connection.execute(
                sqlalchemy.insert(MonitoringLLMCall),
                [
                    dict(
                        common,
                        id=f'{wid}-{bot}-{i}',
                        model_name='fixture-model',
                        input_tokens=1,
                        output_tokens=1,
                        total_tokens=2,
                        duration=1,
                    )
                    for i in range(count)
                ],
            )

    class Persistence:
        def get_db_engine(self):
            return engine

        async def execute_async(self, statement):
            async with engine.connect() as connection:
                return await connection.execute(statement)

    yield SimpleNamespace(persistence_mgr=Persistence())
    await engine.dispose()


async def test_traffic_counts_all_rows_not_just_latest_page(traffic_app):
    from langbot.pkg.api.http.service.monitoring_traffic import get_traffic_series

    context = ExecutionContext(instance_uuid='instance', workspace_uuid=A, placement_generation=1)
    result = await get_traffic_series(
        traffic_app, context, bot_ids=['bot-a'], start_time=START, end_time=START + datetime.timedelta(hours=2)
    )
    assert result['bucket'] == 'hour'
    assert result['truncated'] is False
    assert sum(point['messages'] for point in result['points']) == 60
    assert sum(point['llm_calls'] for point in result['points']) == 60
    assert len(result['points']) == 3
    assert result['points'][1]['messages'] == result['points'][1]['llm_calls'] == 0
    assert result['points'][0]['timestamp'] == '2026-01-01T00:00:00Z'


async def test_traffic_workspace_pipeline_and_empty_filters(traffic_app):
    from langbot.pkg.api.http.service.monitoring_traffic import get_traffic_series

    context = ExecutionContext(instance_uuid='instance', workspace_uuid=B, placement_generation=1)
    kwargs = dict(start_time=START, end_time=START + datetime.timedelta(hours=2))
    result = await get_traffic_series(traffic_app, context, **kwargs)
    assert sum(point['messages'] for point in result['points']) == 9
    empty = await get_traffic_series(traffic_app, context, pipeline_ids=['missing'], **kwargs)
    assert sum(point['messages'] for point in empty['points']) == 0
    assert sum(point['llm_calls'] for point in empty['points']) == 0


async def test_traffic_bounds_large_ranges_and_marks_truncation(traffic_app):
    from langbot.pkg.api.http.service.monitoring_traffic import get_traffic_series

    context = ExecutionContext(instance_uuid='instance', workspace_uuid=A, placement_generation=1)
    result = await get_traffic_series(
        traffic_app, context, start_time=START, end_time=START + datetime.timedelta(days=5000)
    )
    assert result['bucket'] == 'day'
    assert result['truncated'] is True
    assert len(result['points']) == 1000


async def test_traffic_fails_closed_without_workspace(traffic_app):
    from langbot.pkg.api.http.authz import WorkspaceRequiredError
    from langbot.pkg.api.http.service.monitoring_traffic import get_traffic_series

    with pytest.raises(WorkspaceRequiredError):
        await get_traffic_series(traffic_app, None)
