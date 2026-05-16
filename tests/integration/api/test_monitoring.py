"""
API integration tests for monitoring endpoints.

Tests real HTTP API behavior for monitoring data retrieval.

Run: uv run pytest tests/integration/api/test_monitoring.py -q
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, Mock

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

    app.instance_config.data.update({
        'api': {'port': 5300},
        'system': {'allow_modify_login_info': True, 'limitation': {}},
    })

    # Auth services - USER_TOKEN auth requires jwt verification AND get_user_by_email
    app.user_service = Mock()
    app.user_service.is_initialized = AsyncMock(return_value=True)
    app.user_service.verify_jwt_token = AsyncMock(return_value='test@example.com')
    app.user_service.get_user_by_email = AsyncMock(return_value=Mock(email='test@example.com'))

    # Monitoring service
    app.monitoring_service = Mock()
    app.monitoring_service.get_overview_metrics = AsyncMock(return_value={
        'total_messages': 100,
        'total_llm_calls': 50,
        'total_sessions': 20,
        'active_sessions': 5,
        'total_errors': 2,
    })
    app.monitoring_service.get_messages = AsyncMock(return_value=(
        [{'id': 'msg-1', 'content': 'test'}], 100
    ))
    app.monitoring_service.get_llm_calls = AsyncMock(return_value=(
        [{'id': 'llm-1'}], 50
    ))
    app.monitoring_service.get_embedding_calls = AsyncMock(return_value=(
        [{'id': 'emb-1'}], 10
    ))
    app.monitoring_service.get_sessions = AsyncMock(return_value=(
        [{'session_id': 'sess-1'}], 20
    ))
    app.monitoring_service.get_errors = AsyncMock(return_value=(
        [{'id': 'err-1'}], 2
    ))
    app.monitoring_service.get_session_analysis = AsyncMock(return_value={
        'found': True,
        'session_id': 'sess-1',
    })
    app.monitoring_service.get_message_details = AsyncMock(return_value={
        'found': True,
        'message_id': 'msg-1',
    })
    app.monitoring_service.get_feedback_stats = AsyncMock(return_value={'like_count': 10})
    app.monitoring_service.get_feedback_list = AsyncMock(return_value=(
        [{'feedback_id': 'fb-1'}], 12
    ))
    app.monitoring_service.export_messages = AsyncMock(return_value=[{'id': 'msg-1'}])
    app.monitoring_service.export_llm_calls = AsyncMock(return_value=[{'id': 'llm-1'}])
    app.monitoring_service.export_errors = AsyncMock(return_value=[{'id': 'err-1'}])
    app.monitoring_service.export_sessions = AsyncMock(return_value=[{'session_id': 'sess-1'}])
    app.monitoring_service.export_feedback = AsyncMock(return_value=[{'id': 'fb-1'}])
    app.monitoring_service.export_embedding_calls = AsyncMock(return_value=[{'id': 'emb-1'}])
    app.monitoring_service._escape_csv_field = Mock(return_value='escaped')

    return app


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
            '/api/v1/monitoring/overview',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestMonitoringMessagesEndpoint:
    """Tests for /api/v1/monitoring/messages endpoint."""

    @pytest.mark.asyncio
    async def test_get_messages_success(self, quart_test_client):
        """GET /api/v1/monitoring/messages returns message list."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/messages',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'messages' in data['data']


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestMonitoringLLMCallsEndpoint:
    """Tests for /api/v1/monitoring/llm-calls endpoint."""

    @pytest.mark.asyncio
    async def test_get_llm_calls_success(self, quart_test_client):
        """GET /api/v1/monitoring/llm-calls."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/llm-calls',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestMonitoringEmbeddingCallsEndpoint:
    """Tests for /api/v1/monitoring/embedding-calls endpoint."""

    @pytest.mark.asyncio
    async def test_get_embedding_calls_success(self, quart_test_client):
        """GET /api/v1/monitoring/embedding-calls."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/embedding-calls',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestMonitoringSessionsEndpoint:
    """Tests for /api/v1/monitoring/sessions endpoint."""

    @pytest.mark.asyncio
    async def test_get_sessions_success(self, quart_test_client):
        """GET /api/v1/monitoring/sessions."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/sessions',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestMonitoringErrorsEndpoint:
    """Tests for /api/v1/monitoring/errors endpoint."""

    @pytest.mark.asyncio
    async def test_get_errors_success(self, quart_test_client):
        """GET /api/v1/monitoring/errors."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/errors',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestMonitoringAllDataEndpoint:
    """Tests for /api/v1/monitoring/data endpoint."""

    @pytest.mark.asyncio
    async def test_get_all_data_success(self, quart_test_client):
        """GET /api/v1/monitoring/data returns all data."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/data',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert 'overview' in data['data']


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestMonitoringDetailsEndpoints:
    """Tests for detail endpoints."""

    @pytest.mark.asyncio
    async def test_get_session_analysis(self, quart_test_client):
        """GET /api/v1/monitoring/sessions/{id}/analysis."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/sessions/sess-1/analysis',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_message_details(self, quart_test_client):
        """GET /api/v1/monitoring/messages/{id}/details."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/messages/msg-1/details',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestMonitoringFeedbackEndpoints:
    """Tests for feedback endpoints."""

    @pytest.mark.asyncio
    async def test_get_feedback_stats(self, quart_test_client):
        """GET /api/v1/monitoring/feedback/stats."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/feedback/stats',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_feedback_list(self, quart_test_client):
        """GET /api/v1/monitoring/feedback."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/feedback',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestMonitoringExportEndpoint:
    """Tests for /api/v1/monitoring/export endpoint."""

    @pytest.mark.asyncio
    async def test_export_messages(self, quart_test_client):
        """GET export?type=messages returns CSV."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/export?type=messages',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        assert 'text/csv' in response.content_type

    @pytest.mark.asyncio
    async def test_export_llm_calls(self, quart_test_client):
        """GET export?type=llm-calls returns CSV."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/export?type=llm-calls',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_export_sessions(self, quart_test_client):
        """GET export?type=sessions returns CSV."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/export?type=sessions',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_export_feedback(self, quart_test_client):
        """GET export?type=feedback returns CSV."""
        response = await quart_test_client.get(
            '/api/v1/monitoring/export?type=feedback',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
