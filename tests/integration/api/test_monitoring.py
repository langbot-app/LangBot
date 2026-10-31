"""
API integration tests for monitoring endpoints.

Tests real HTTP API behavior for monitoring data retrieval.

Run: uv run pytest tests/integration/api/test_monitoring.py -q
"""

from __future__ import annotations

import csv
import io

import pytest
from unittest.mock import MagicMock, AsyncMock, Mock, patch
from types import SimpleNamespace

from tests.factories import FakeApp


pytestmark = pytest.mark.integration


@pytest.fixture(scope='module')
def mock_circular_import_chain():
    """Break circular import chain for API controller."""
    from tests.utils.import_isolation import isolated_sys_modules, MockLifecycleControlScope

    class FakeMinimalApplication:
        pass

    mock_app = MagicMock()
    mock_app.Application = FakeMinimalApplication

    mock_entities = MagicMock()
    mock_entities.LifecycleControlScope = MockLifecycleControlScope

    clear = [
        'langbot.pkg.api.http.controller.group',
        'langbot.pkg.api.http.controller.groups',
        'langbot.pkg.api.http.controller.groups.monitoring',
        'langbot.pkg.api.http.controller.main',
    ]

    with isolated_sys_modules(
        mocks={
            'langbot.pkg.core.app': mock_app,
            'langbot.pkg.core.entities': mock_entities,
        },
        clear=clear,
    ):
        import langbot.pkg.api.http.controller.groups.monitoring as _monitoring  # noqa: E402, F401

        yield


@pytest.fixture(scope='module')
def fake_monitoring_app():
    """Create FakeApp with monitoring services (module scope)."""
    app = FakeApp()

    app.instance_config.data.update(
        {
            'api': {'port': 5300},
            'system': {'allow_modify_login_info': True, 'limitation': {}},
        }
    )

    # Auth services - USER_TOKEN auth requires jwt verification AND get_user_by_email
    app.user_service = Mock()
    app.user_service.is_initialized = AsyncMock(return_value=True)
    app.user_service.verify_jwt_token = AsyncMock(return_value='test@example.com')
    app.user_service.get_user_by_email = AsyncMock(
        return_value=SimpleNamespace(
            uuid='account-uuid',
            user='test@example.com',
            email='test@example.com',
        )
    )
    app.workspace_collaboration_service = SimpleNamespace(
        resolve_account_workspace=AsyncMock(
            return_value=SimpleNamespace(
                execution=SimpleNamespace(instance_uuid='instance', placement_generation=1),
                workspace=SimpleNamespace(uuid='00000000-0000-0000-0000-00000000000a'),
                membership=SimpleNamespace(
                    uuid='membership-uuid',
                    role='owner',
                    projection_revision=1,
                ),
            )
        )
    )

    # Monitoring service
    app.monitoring_service = Mock()
    from langbot.pkg.api.http.service.monitoring import MonitoringService

    app.monitoring_service.normalize_page_window = MonitoringService(app).normalize_page_window
    app.monitoring_service.get_overview_metrics = AsyncMock(
        return_value={
            'total_messages': 100,
            'total_llm_calls': 50,
            'total_sessions': 20,
            'active_sessions': 5,
            'total_errors': 2,
        }
    )
    app.monitoring_service.get_messages = AsyncMock(return_value=([{'id': 'msg-1', 'content': 'test'}], 100))
    app.monitoring_service.get_llm_calls = AsyncMock(return_value=([{'id': 'llm-1'}], 50))
    app.monitoring_service.get_tool_calls = AsyncMock(return_value=([{'id': 'tool-1'}], 5))
    app.monitoring_service.get_embedding_calls = AsyncMock(return_value=([{'id': 'emb-1'}], 10))
    app.monitoring_service.get_sessions = AsyncMock(return_value=([{'session_id': 'sess-1'}], 20))
    app.monitoring_service.get_errors = AsyncMock(return_value=([{'id': 'err-1'}], 2))
    app.monitoring_service.get_session_analysis = AsyncMock(
        return_value={
            'found': True,
            'session_id': 'sess-1',
        }
    )
    app.monitoring_service.get_message_details = AsyncMock(
        return_value={
            'found': True,
            'message_id': 'msg-1',
        }
    )
    app.monitoring_service.get_feedback_stats = AsyncMock(return_value={'like_count': 10})
    app.monitoring_service.get_feedback_list = AsyncMock(return_value=([{'feedback_id': 'fb-1'}], 12))
    app.monitoring_service.export_messages = AsyncMock(
        return_value=[{'id': 'msg-1', 'message_content': 'hello, "quoted"'}]
    )
    app.monitoring_service.export_llm_calls = AsyncMock(return_value=[{'id': 'llm-1'}])
    app.monitoring_service.export_errors = AsyncMock(return_value=[{'id': 'err-1'}])
    app.monitoring_service.export_sessions = AsyncMock(return_value=[{'session_id': 'sess-1'}])
    app.monitoring_service.export_feedback = AsyncMock(return_value=[{'id': 'fb-1'}])
    app.monitoring_service.export_embedding_calls = AsyncMock(return_value=[{'id': 'emb-1'}])
    app.monitoring_service._escape_csv_field = MonitoringService(app)._escape_csv_field

    return app


@pytest.fixture(autouse=True)
def reset_monitoring_calls(fake_monitoring_app):
    fake_monitoring_app.monitoring_service.reset_mock()


@pytest.fixture(scope='module')
async def quart_test_client(fake_monitoring_app, http_controller_cls):
    """Create Quart test client (module scope)."""
    controller = http_controller_cls(fake_monitoring_app)
    await controller.initialize()

    client = controller.quart_app.test_client()
    yield client


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestMonitoringOverviewEndpoint:
    """Tests for /api/v1/monitoring/overview endpoint."""

    @pytest.mark.asyncio
    async def test_get_overview_success(self, quart_test_client):
        """GET /api/v1/monitoring/overview returns metrics."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/overview', headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0

        assert data['data'] == {
            'total_messages': 100,
            'total_llm_calls': 50,
            'total_sessions': 20,
            'active_sessions': 5,
            'total_errors': 2,
        }

    @pytest.mark.asyncio
    async def test_viewer_can_read_monitoring_but_cannot_export(
        self,
        quart_test_client,
        fake_monitoring_app,
    ):
        """Ordinary monitoring is resource.view; export remains data.export."""
        membership = (
            fake_monitoring_app.workspace_collaboration_service.resolve_account_workspace.return_value.membership
        )
        original_role = membership.role
        membership.role = 'viewer'
        try:
            response = await quart_test_client.get(
                '/api/v1/monitoring/overview',
                headers={'Authorization': 'Bearer test_token'},
            )
            assert response.status_code == 200

            export_response = await quart_test_client.get(
                '/api/v1/monitoring/export?type=messages',
                headers={'Authorization': 'Bearer test_token'},
            )
            assert export_response.status_code == 403
            assert (await export_response.get_json())['code'] == 'permission_denied'
        finally:
            membership.role = original_role


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestMonitoringMessagesEndpoint:
    """Tests for /api/v1/monitoring/messages endpoint."""

    @pytest.mark.asyncio
    async def test_get_messages_success(self, quart_test_client):
        """GET /api/v1/monitoring/messages returns message list."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/messages', headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'messages' in data['data']

        data = await response.get_json()
        assert data['code'] == 0
        assert data['data'] == {
            'messages': [{'id': 'msg-1', 'content': 'test'}],
            'total': 100,
            'limit': 100,
            'offset': 0,
        }


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestMonitoringLLMCallsEndpoint:
    """Tests for /api/v1/monitoring/llm-calls endpoint."""

    @pytest.mark.asyncio
    async def test_get_llm_calls_success(self, quart_test_client):
        """GET /api/v1/monitoring/llm-calls."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/llm-calls', headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200

        data = await response.get_json()
        assert data['code'] == 0
        assert data['data'] == {'llm_calls': [{'id': 'llm-1'}], 'total': 50, 'limit': 100, 'offset': 0}


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestMonitoringEmbeddingCallsEndpoint:
    """Tests for /api/v1/monitoring/embedding-calls endpoint."""

    @pytest.mark.asyncio
    async def test_get_embedding_calls_success(self, quart_test_client):
        """GET /api/v1/monitoring/embedding-calls."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/embedding-calls', headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200

        data = await response.get_json()
        assert data['code'] == 0
        assert data['data'] == {'embedding_calls': [{'id': 'emb-1'}], 'total': 10, 'limit': 100, 'offset': 0}


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestMonitoringSessionsEndpoint:
    """Tests for /api/v1/monitoring/sessions endpoint."""

    @pytest.mark.asyncio
    async def test_get_sessions_success(self, quart_test_client):
        """GET /api/v1/monitoring/sessions."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/sessions', headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200

        data = await response.get_json()
        assert data['code'] == 0
        assert data['data'] == {'sessions': [{'session_id': 'sess-1'}], 'total': 20, 'limit': 100, 'offset': 0}

    @pytest.mark.asyncio
    async def test_get_sessions_forwards_user_search_and_page_window(self, quart_test_client, fake_monitoring_app):
        fake_monitoring_app.monitoring_service.get_sessions.reset_mock()

        response = await quart_test_client.get(
            '/api/v1/monitoring/sessions?botId=bot-1&userQuery=alice&limit=20&offset=40',
            headers={'Authorization': 'Bearer test_token'},
        )

        assert response.status_code == 200
        kwargs = fake_monitoring_app.monitoring_service.get_sessions.await_args.kwargs
        assert kwargs['bot_ids'] == ['bot-1']
        assert kwargs['user_query'] == 'alice'
        assert kwargs['limit'] == 20
        assert kwargs['offset'] == 40

    @pytest.mark.asyncio
    @pytest.mark.session_summary
    @pytest.mark.parametrize('query', ['mode=real', 'mode=debug', 'status=failed'])
    async def test_session_list_rejects_execution_filters(self, quart_test_client, fake_monitoring_app, query):
        response = await quart_test_client.get(
            '/api/v1/monitoring/sessions?' + query,
            headers={'Authorization': 'Bearer test_token'},
        )
        assert response.status_code == 400
        fake_monitoring_app.monitoring_service.get_sessions.assert_not_awaited()


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestMonitoringErrorsEndpoint:
    """Tests for /api/v1/monitoring/errors endpoint."""

    @pytest.mark.asyncio
    async def test_get_errors_success(self, quart_test_client):
        """GET /api/v1/monitoring/errors."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/errors', headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200

        data = await response.get_json()
        assert data['code'] == 0
        assert data['data'] == {'errors': [{'id': 'err-1'}], 'total': 2, 'limit': 100, 'offset': 0}


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestMonitoringAllDataEndpoint:
    """Tests for /api/v1/monitoring/data endpoint."""

    @pytest.mark.asyncio
    async def test_get_all_data_success(self, quart_test_client):
        """GET /api/v1/monitoring/data returns all data."""
        traffic = {'series': [], 'truncated': False}
        with patch(
            'langbot.pkg.api.http.controller.groups.monitoring.get_traffic_series',
            new=AsyncMock(return_value=traffic),
        ) as get_traffic:
            response = await quart_test_client.get(
                '/api/v1/monitoring/data', headers={'Authorization': 'Bearer test_token'}
            )
        get_traffic.assert_awaited_once()

        assert response.status_code == 200
        data = await response.get_json()
        assert 'overview' in data['data']
        assert data['data']['traffic'] == traffic

        assert data['code'] == 0
        assert data['data']['overview'] == {
            'total_messages': 100,
            'total_llm_calls': 50,
            'total_sessions': 20,
            'active_sessions': 5,
            'total_errors': 2,
        }
        assert data['data']['messages'] == [{'id': 'msg-1', 'content': 'test'}]
        assert data['data']['llmCalls'] == [{'id': 'llm-1'}]
        assert data['data']['toolCalls'] == [{'id': 'tool-1'}]
        assert data['data']['embeddingCalls'] == [{'id': 'emb-1'}]
        assert data['data']['sessions'] == [{'session_id': 'sess-1'}]
        assert data['data']['errors'] == [{'id': 'err-1'}]
        assert data['data']['totalCount'] == {
            'messages': 100,
            'llmCalls': 50,
            'toolCalls': 5,
            'embeddingCalls': 10,
            'sessions': 20,
            'errors': 2,
        }

    @pytest.mark.asyncio
    @pytest.mark.session_summary
    @pytest.mark.contract('reader_http')
    @pytest.mark.parametrize(
        'query,mode,statuses',
        [
            ('/data?mode=all', 'all', None),
            ('/data?mode=real&status=failed', 'real', ['failed']),
            ('/data?mode=debug&status=running', 'debug', ['running']),
            ('/data?status=completed&status=failed', 'all', ['completed', 'failed']),
            ('/sessions?mode=all&userQuery=Alice', None, None),
        ],
    )
    async def test_http_session_queries_only_read_summaries(
        self,
        quart_test_client,
        fake_monitoring_app,
        monkeypatch,
        query,
        mode,
        statuses,
    ):
        """Other /data records may read history; its session query may not."""
        import datetime
        import sqlite3
        from contextlib import asynccontextmanager
        import sqlalchemy as sa
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from langbot.pkg.api.http.service.monitoring import MonitoringService
        from langbot.pkg.entity.persistence.monitoring import MonitoringSession
        from langbot.pkg.persistence.session_summary_reader import SqlSessionSummaryReader

        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        try:
            async with engine.begin() as connection:
                await connection.run_sync(MonitoringSession.__table__.create)
                await connection.execute(
                    sa.insert(MonitoringSession).values(
                        workspace_uuid='00000000-0000-0000-0000-00000000000a',
                        bot_id='bot-a',
                        session_id='summary',
                        bot_name='Bot',
                        pipeline_id='pipeline-a',
                        pipeline_name='Pipeline',
                        message_count=7,
                        start_time=datetime.datetime(2026, 1, 2),
                        last_activity=datetime.datetime(2026, 1, 2),
                        user_name='Alice',
                    )
                )

            @asynccontextmanager
            async def scope(workspace):
                assert workspace == '00000000-0000-0000-0000-00000000000a'
                async with AsyncSession(engine) as session:
                    yield session

            service = MonitoringService(fake_monitoring_app)
            service._session_list = SqlSessionSummaryReader(scope)
            monkeypatch.setattr(fake_monitoring_app.monitoring_service, 'get_sessions', service.get_sessions)

            def authorize(action, table, column, database, trigger):
                if action == sqlite3.SQLITE_READ and table != 'monitoring_sessions':
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK

            async with engine.connect() as connection:
                await connection.run_sync(
                    lambda sync: sync.connection.dbapi_connection.run_async(
                        lambda raw: raw._execute(raw._conn.set_authorizer, authorize)
                    )
                )
            with patch(
                'langbot.pkg.api.http.controller.groups.monitoring.get_traffic_series',
                new=AsyncMock(return_value={}),
            ):
                response = await quart_test_client.get(
                    '/api/v1/monitoring' + query + '&botId=bot-a&pipelineId=pipeline-a'
                    '&startTime=2026-01-01T00:00:00&endTime=2026-01-03T00:00:00',
                    headers={'Authorization': 'Bearer test_token'},
                )
            assert response.status_code == 200
            result = (await response.get_json())['data']
            assert [row['session_id'] for row in result['sessions']] == ['summary']
            assert result['sessions'][0]['message_count'] == 7
            assert (result['totalCount']['sessions'] if mode is not None else result['total']) == 1
            if mode is not None:
                kwargs = fake_monitoring_app.monitoring_service.get_messages.await_args.kwargs
                assert kwargs['mode'] == mode and kwargs['execution_statuses'] == statuses
        finally:
            await engine.dispose()


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestMonitoringDetailsEndpoints:
    """Tests for detail endpoints."""

    @pytest.mark.asyncio
    async def test_get_session_analysis(self, quart_test_client, fake_monitoring_app):
        """GET /api/v1/monitoring/sessions/{id}/analysis."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/sessions/sess-1/analysis'
            '?startTime=2026-08-31T16%3A00%3A00.000Z'
            '&endTime=2026-09-01T15%3A59%3A59.999Z',
            headers={'Authorization': 'Bearer test_token'},
        )

        assert response.status_code == 200
        kwargs = fake_monitoring_app.monitoring_service.get_session_analysis.await_args.kwargs
        assert kwargs['start_time'].isoformat() == '2026-08-31T16:00:00'
        assert kwargs['end_time'].isoformat() == '2026-09-01T15:59:59.999000'

    @pytest.mark.asyncio
    async def test_get_message_details(self, quart_test_client):
        """GET /api/v1/monitoring/messages/{id}/details."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/messages/msg-1/details', headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200

        data = await response.get_json()
        assert data['code'] == 0
        assert data['data'] == {'found': True, 'message_id': 'msg-1'}


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestMonitoringFeedbackEndpoints:
    """Tests for feedback endpoints."""

    @pytest.mark.asyncio
    async def test_get_feedback_stats(self, quart_test_client):
        """GET /api/v1/monitoring/feedback/stats."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/feedback/stats', headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200

        data = await response.get_json()
        assert data['code'] == 0
        assert data['data'] == {'like_count': 10}

    @pytest.mark.asyncio
    async def test_get_feedback_list(self, quart_test_client):
        """GET /api/v1/monitoring/feedback."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/feedback', headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200

        data = await response.get_json()
        assert data['code'] == 0
        assert data['data'] == {'feedback': [{'feedback_id': 'fb-1'}], 'total': 12, 'limit': 100, 'offset': 0}


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestMonitoringExportEndpoint:
    """Tests for /api/v1/monitoring/export endpoint."""

    @pytest.mark.asyncio
    async def test_export_messages(self, quart_test_client, fake_monitoring_app):
        """GET export?type=messages returns CSV."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/export?type=messages', headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        assert 'text/csv' in response.content_type

        assert 'text/csv' in response.content_type
        assert 'monitoring-messages-' in response.headers['Content-Disposition']
        body = (await response.get_data()).decode('utf-8-sig')
        records = list(csv.DictReader(io.StringIO(body)))
        assert len(records) == 1
        assert records[0]['id'] == 'msg-1'
        called = fake_monitoring_app.monitoring_service.export_messages
        assert called.await_count == 1
        assert called.await_args.args[0].workspace_uuid == '00000000-0000-0000-0000-00000000000a'
        assert called.await_args.kwargs['limit'] == 100000
        assert records[0]['message_content'] == 'hello, "quoted"'

    @pytest.mark.asyncio
    async def test_export_llm_calls(self, quart_test_client, fake_monitoring_app):
        """GET export?type=llm-calls returns CSV."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/export?type=llm-calls', headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200

        assert 'text/csv' in response.content_type
        assert 'monitoring-llm-calls-' in response.headers['Content-Disposition']
        body = (await response.get_data()).decode('utf-8-sig')
        records = list(csv.DictReader(io.StringIO(body)))
        assert len(records) == 1
        assert records[0]['id'] == 'llm-1'
        called = fake_monitoring_app.monitoring_service.export_llm_calls
        assert called.await_count == 1
        assert called.await_args.args[0].workspace_uuid == '00000000-0000-0000-0000-00000000000a'
        assert called.await_args.kwargs['limit'] == 100000

    @pytest.mark.asyncio
    async def test_export_sessions(self, quart_test_client, fake_monitoring_app):
        """GET export?type=sessions returns CSV."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/export?type=sessions', headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200

        assert 'text/csv' in response.content_type
        assert 'monitoring-sessions-' in response.headers['Content-Disposition']
        body = (await response.get_data()).decode('utf-8-sig')
        records = list(csv.DictReader(io.StringIO(body)))
        assert len(records) == 1
        assert records[0]['session_id'] == 'sess-1'
        called = fake_monitoring_app.monitoring_service.export_sessions
        assert called.await_count == 1
        assert called.await_args.args[0].workspace_uuid == '00000000-0000-0000-0000-00000000000a'
        assert called.await_args.kwargs['limit'] == 100000

    @pytest.mark.asyncio
    async def test_export_feedback(self, quart_test_client, fake_monitoring_app):
        """GET export?type=feedback returns CSV."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/export?type=feedback', headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200

        assert 'text/csv' in response.content_type
        assert 'monitoring-feedback-' in response.headers['Content-Disposition']
        body = (await response.get_data()).decode('utf-8-sig')
        records = list(csv.DictReader(io.StringIO(body)))
        assert len(records) == 1
        assert records[0]['id'] == 'fb-1'
        called = fake_monitoring_app.monitoring_service.export_feedback
        assert called.await_count == 1
        assert called.await_args.args[0].workspace_uuid == '00000000-0000-0000-0000-00000000000a'
        assert called.await_args.kwargs['limit'] == 100000
