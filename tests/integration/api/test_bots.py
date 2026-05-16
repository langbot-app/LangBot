"""
API integration tests for bot endpoints.

Tests real HTTP API behavior for bot management.

Run: uv run pytest tests/integration/api/test_bots.py -q
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
        'langbot.pkg.api.http.controller.groups.platform',
        'langbot.pkg.api.http.controller.groups.platform.bots',
        'langbot.pkg.api.http.controller.groups.platform.adapters',
        'langbot.pkg.api.http.controller.main',
    ]

    with isolated_sys_modules(
        mocks={
            'langbot.pkg.core.app': mock_app,
            'langbot.pkg.core.entities': mock_entities,
        },
        clear=clear,
    ):
        import langbot.pkg.api.http.controller.groups.platform.bots as _bots  # noqa: E402, F401
        yield


@pytest.fixture(scope='module')
def fake_bot_app():
    """Create FakeApp with bot services (module scope for reuse)."""
    app = FakeApp()

    app.instance_config.data.update({
        'api': {'port': 5300},
        'system': {'allow_modify_login_info': True, 'limitation': {}},
    })

    # Auth services
    app.user_service = Mock()
    app.user_service.is_initialized = AsyncMock(return_value=True)
    app.user_service.verify_jwt_token = AsyncMock(return_value='test@example.com')
    app.user_service.get_user_by_email = AsyncMock(return_value=Mock(email='test@example.com'))
    app.apikey_service = Mock()
    app.apikey_service.verify_api_key = AsyncMock(return_value=True)

    # Bot service
    app.bot_service = Mock()
    app.bot_service.get_bots = AsyncMock(return_value=[
        {
            'uuid': 'test-bot-uuid',
            'name': 'Test Bot',
            'platform': 'telegram',
            'pipeline_uuid': 'test-pipeline-uuid',
        }
    ])
    app.bot_service.get_runtime_bot_info = AsyncMock(return_value={
        'uuid': 'test-bot-uuid',
        'name': 'Test Bot',
        'platform': 'telegram',
        'pipeline_uuid': 'test-pipeline-uuid',
        'webhook_url': 'https://example.com/webhook/test-bot-uuid',
    })
    app.bot_service.create_bot = AsyncMock(return_value={'uuid': 'new-bot-uuid'})
    app.bot_service.update_bot = AsyncMock(return_value={})
    app.bot_service.delete_bot = AsyncMock()
    app.bot_service.list_event_logs = AsyncMock(return_value=(
        [{'uuid': 'log-1', 'message': 'test log'}],
        1
    ))
    app.bot_service.send_message = AsyncMock()

    # Platform manager
    app.platform_mgr = Mock()

    return app


@pytest.fixture(scope='module')
async def quart_test_client(fake_bot_app, http_controller_cls):
    """Create Quart test client (module scope to avoid route re-registration)."""
    controller = http_controller_cls(fake_bot_app)
    await controller.initialize()

    client = controller.quart_app.test_client()
    yield client


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestBotEndpoints:
    """Tests for /api/v1/platform/bots endpoints."""

    @pytest.mark.asyncio
    async def test_get_bots_success(self, quart_test_client):
        """GET /api/v1/platform/bots returns bot list."""
        response = await quart_test_client.get(
            '/api/v1/platform/bots',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'data' in data
        assert 'bots' in data['data']

    @pytest.mark.asyncio
    async def test_create_bot_success(self, quart_test_client):
        """POST /api/v1/platform/bots creates new bot."""
        response = await quart_test_client.post(
            '/api/v1/platform/bots',
            headers={'Authorization': 'Bearer test_token'},
            json={'name': 'New Bot', 'platform': 'telegram', 'pipeline_uuid': 'test-pipeline'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'uuid' in data['data']

    @pytest.mark.asyncio
    async def test_get_single_bot_success(self, quart_test_client):
        """GET /api/v1/platform/bots/{uuid} returns bot with runtime info."""
        response = await quart_test_client.get(
            '/api/v1/platform/bots/test-bot-uuid',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'bot' in data['data']

    @pytest.mark.asyncio
    async def test_update_bot_success(self, quart_test_client):
        """PUT /api/v1/platform/bots/{uuid} updates bot."""
        response = await quart_test_client.put(
            '/api/v1/platform/bots/test-bot-uuid',
            headers={'Authorization': 'Bearer test_token'},
            json={'name': 'Updated Bot'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0

    @pytest.mark.asyncio
    async def test_delete_bot_success(self, quart_test_client):
        """DELETE /api/v1/platform/bots/{uuid} deletes bot."""
        response = await quart_test_client.delete(
            '/api/v1/platform/bots/test-bot-uuid',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestBotLogsEndpoint:
    """Tests for bot logs endpoint."""

    @pytest.mark.asyncio
    async def test_get_bot_logs_success(self, quart_test_client):
        """POST /api/v1/platform/bots/{uuid}/logs returns logs."""
        response = await quart_test_client.post(
            '/api/v1/platform/bots/test-bot-uuid/logs',
            headers={'Authorization': 'Bearer test_token'},
            json={'from_index': -1, 'max_count': 10}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'logs' in data['data']
        assert 'total_count' in data['data']


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestBotSendMessageEndpoint:
    """Tests for bot send message endpoint."""

    @pytest.mark.asyncio
    async def test_send_message_success(self, quart_test_client):
        """POST /api/v1/platform/bots/{uuid}/send_message sends message."""
        response = await quart_test_client.post(
            '/api/v1/platform/bots/test-bot-uuid/send_message',
            headers={'Authorization': 'Bearer test_api_key'},
            json={
                'target_type': 'person',
                'target_id': 'user123',
                'message_chain': [{'type': 'text', 'text': 'Hello'}]
            }
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert data['data']['sent'] is True

    @pytest.mark.asyncio
    async def test_send_message_missing_target_type(self, quart_test_client):
        """POST send_message without target_type returns 400."""
        response = await quart_test_client.post(
            '/api/v1/platform/bots/test-bot-uuid/send_message',
            headers={'Authorization': 'Bearer test_api_key'},
            json={'target_id': 'user123', 'message_chain': [{'type': 'text', 'text': 'Hello'}]}
        )

        assert response.status_code == 400
        data = await response.get_json()
        assert data['code'] == -1

    @pytest.mark.asyncio
    async def test_send_message_invalid_target_type(self, quart_test_client):
        """POST send_message with invalid target_type returns 400."""
        response = await quart_test_client.post(
            '/api/v1/platform/bots/test-bot-uuid/send_message',
            headers={'Authorization': 'Bearer test_api_key'},
            json={
                'target_type': 'invalid',
                'target_id': 'user123',
                'message_chain': [{'type': 'text', 'text': 'Hello'}]
            }
        )

        assert response.status_code == 400
        data = await response.get_json()
        assert data['code'] == -1
