"""Unit tests for monitoring trace HTTP routes."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, Mock

import pytest
import quart

from tests.factories import FakeApp
from tests.utils.import_isolation import MockLifecycleControlScope, isolated_sys_modules


pytestmark = pytest.mark.asyncio


@pytest.fixture
async def monitoring_client():
    mock_app = Mock()
    mock_app.Application = type('FakeMinimalApplication', (), {})
    mock_entities = Mock()
    mock_entities.LifecycleControlScope = MockLifecycleControlScope

    clear = [
        'langbot.pkg.api.http.controller.group',
        'langbot.pkg.api.http.controller.groups',
        'langbot.pkg.api.http.controller.groups.monitoring',
        'langbot.pkg.api.http.controller.main',
    ]

    app = FakeApp()
    app.user_service = Mock()
    app.user_service.verify_jwt_token = AsyncMock(return_value='test@example.com')
    app.user_service.get_user_by_email = AsyncMock(return_value=Mock(email='test@example.com'))

    app.monitoring_service = Mock()
    app.monitoring_service.get_traces = AsyncMock(return_value=([{'trace_id': 'trace-1'}], 1))
    app.monitoring_service.get_trace_details = AsyncMock(
        side_effect=lambda trace_id: {
            'found': trace_id == 'trace-1',
            'trace_id': trace_id,
            'trace': {'trace_id': trace_id} if trace_id == 'trace-1' else None,
            'spans': [] if trace_id == 'trace-1' else None,
        }
    )

    with isolated_sys_modules(
        mocks={
            'langbot.pkg.core.app': mock_app,
            'langbot.pkg.core.entities': mock_entities,
        },
        clear=clear,
    ):
        from langbot.pkg.api.http.controller.groups.monitoring import MonitoringRouterGroup

        quart_app = quart.Quart(__name__)
        group = MonitoringRouterGroup(app, quart_app)
        await group.initialize()

        yield app, quart_app.test_client()


async def test_get_traces_route_forwards_filters(monitoring_client):
    app, client = monitoring_client

    response = await client.get(
        '/api/v1/monitoring/traces'
        '?botId=bot-1'
        '&pipelineId=pipeline-1'
        '&sessionId=session-1'
        '&status=success'
        '&startTime=2026-01-01T00:00:00Z'
        '&endTime=2026-01-02T00:00:00Z'
        '&limit=25'
        '&offset=5',
        headers={'Authorization': 'Bearer test_token'},
    )

    assert response.status_code == 200
    data = await response.get_json()
    assert data['data'] == {
        'traces': [{'trace_id': 'trace-1'}],
        'total': 1,
        'limit': 25,
        'offset': 5,
    }
    app.monitoring_service.get_traces.assert_awaited_once_with(
        bot_ids=['bot-1'],
        pipeline_ids=['pipeline-1'],
        session_ids=['session-1'],
        statuses=['success'],
        start_time=datetime.datetime(2026, 1, 1, 0, 0),
        end_time=datetime.datetime(2026, 1, 2, 0, 0),
        limit=25,
        offset=5,
    )


async def test_get_trace_details_route_returns_404_for_missing_trace(monitoring_client):
    _app, client = monitoring_client

    response = await client.get(
        '/api/v1/monitoring/traces/trace-missing',
        headers={'Authorization': 'Bearer test_token'},
    )

    assert response.status_code == 404
    data = await response.get_json()
    assert data['code'] == -1
    assert data['msg'] == 'Trace trace-missing not found'
