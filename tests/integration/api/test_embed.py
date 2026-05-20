"""
API integration tests for embed widget endpoints.

Tests real HTTP API behavior for embed widget functionality.

Run: uv run pytest tests/integration/api/test_embed.py -q
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
        'langbot.pkg.api.http.controller.groups.pipelines',
        'langbot.pkg.api.http.controller.groups.pipelines.embed',
        'langbot.pkg.api.http.controller.main',
    ]

    with isolated_sys_modules(
        mocks={
            'langbot.pkg.core.app': mock_app,
            'langbot.pkg.core.entities': mock_entities,
        },
        clear=clear,
    ):
        import langbot.pkg.api.http.controller.groups.pipelines.embed as _embed  # noqa: E402, F401
        yield


@pytest.fixture(scope='module')
def fake_embed_app():
    """Create FakeApp with embed widget services (module scope)."""
    app = FakeApp()

    app.instance_config.data.update({
        'api': {'port': 5300},
        'system': {'allow_modify_login_info': True, 'limitation': {}},
    })

    # Create mock web_page_bot with valid UUID format
    mock_bot_entity = Mock()
    mock_bot_entity.uuid = 'a1b2c3d4-5678-90ab-cdef-123456789abc'
    mock_bot_entity.adapter = 'web_page_bot'
    mock_bot_entity.enable = True
    mock_bot_entity.use_pipeline_uuid = 'test-pipeline-uuid'
    mock_bot_entity.name = 'Test Web Bot'
    mock_bot_entity.adapter_config = {
        'turnstile_secret_key': '',
        'turnstile_site_key': '',
        'language': 'en_US',
        'bubble_icon': 'logo',
    }

    mock_runtime_bot = Mock()
    mock_runtime_bot.bot_entity = mock_bot_entity

    # Platform manager with bots
    app.platform_mgr = Mock()
    app.platform_mgr.bots = [mock_runtime_bot]

    # WebSocket proxy bot with adapter
    mock_websocket_adapter = Mock()
    mock_websocket_adapter.get_websocket_messages = Mock(return_value=[
        {'id': 'msg-1', 'content': 'test message'}
    ])
    mock_websocket_adapter.reset_session = Mock()
    mock_websocket_adapter.handle_websocket_message = AsyncMock()

    mock_ws_proxy_bot = Mock()
    mock_ws_proxy_bot.adapter = mock_websocket_adapter
    app.platform_mgr.websocket_proxy_bot = mock_ws_proxy_bot

    # Monitoring service for feedback
    app.monitoring_service = Mock()
    app.monitoring_service.record_feedback = AsyncMock()

    return app


@pytest.fixture(scope='module')
async def quart_test_client(fake_embed_app, http_controller_cls):
    """Create Quart test client (module scope)."""
    controller = http_controller_cls(fake_embed_app)
    await controller.initialize()

    client = controller.quart_app.test_client()
    yield client


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestEmbedWidgetEndpoint:
    """Tests for widget.js endpoint."""

    @pytest.mark.asyncio
    async def test_get_widget_js_success(self, quart_test_client):
        """GET /api/v1/embed/{bot_uuid}/widget.js returns JS."""
        response = await quart_test_client.get(
            '/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/widget.js'
        )

        assert response.status_code == 200
        assert 'javascript' in response.content_type

    @pytest.mark.asyncio
    async def test_get_widget_js_invalid_uuid(self, quart_test_client):
        """GET widget.js with invalid UUID returns 400."""
        response = await quart_test_client.get(
            '/api/v1/embed/invalid-uuid/widget.js'
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_widget_js_bot_not_found(self, quart_test_client):
        """GET widget.js for non-existent bot returns 404."""
        response = await quart_test_client.get(
            '/api/v1/embed/00000000-0000-0000-0000-000000000000/widget.js'
        )

        assert response.status_code == 404


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestEmbedLogoEndpoint:
    """Tests for logo endpoint."""

    @pytest.mark.asyncio
    async def test_get_logo_success(self, quart_test_client):
        """GET /api/v1/embed/logo returns image."""
        response = await quart_test_client.get('/api/v1/embed/logo')

        assert response.status_code == 200
        assert 'image/webp' in response.content_type


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestEmbedTurnstileVerifyEndpoint:
    """Tests for Turnstile verification endpoint."""

    @pytest.mark.asyncio
    async def test_turnstile_verify_no_secret(self, quart_test_client):
        """POST turnstile verify without secret returns dummy token."""
        response = await quart_test_client.post(
            '/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/turnstile/verify',
            json={'token': 'test-token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'token' in data['data']

    @pytest.mark.asyncio
    async def test_turnstile_verify_invalid_uuid(self, quart_test_client):
        """POST turnstile verify with invalid UUID returns 400."""
        response = await quart_test_client.post(
            '/api/v1/embed/invalid-uuid/turnstile/verify',
            json={'token': 'test-token'}
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_turnstile_verify_missing_token(self, quart_test_client):
        """POST turnstile verify without token returns 400."""
        response = await quart_test_client.post(
            '/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/turnstile/verify',
            json={}
        )

        assert response.status_code == 400


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestEmbedMessagesEndpoint:
    """Tests for messages endpoint."""

    @pytest.mark.asyncio
    async def test_get_messages_person_success(self, quart_test_client):
        """GET messages/person returns messages."""
        response = await quart_test_client.get(
            '/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/messages/person',
            headers={'Authorization': 'Bearer 1234567890.dummy'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'messages' in data['data']

    @pytest.mark.asyncio
    async def test_get_messages_group_success(self, quart_test_client):
        """GET messages/group returns messages."""
        response = await quart_test_client.get(
            '/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/messages/group',
            headers={'Authorization': 'Bearer 1234567890.dummy'}
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_messages_invalid_session_type(self, quart_test_client):
        """GET messages with invalid session_type returns 400."""
        response = await quart_test_client.get(
            '/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/messages/invalid',
            headers={'Authorization': 'Bearer 1234567890.dummy'}
        )

        assert response.status_code == 400


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestEmbedResetEndpoint:
    """Tests for session reset endpoint."""

    @pytest.mark.asyncio
    async def test_reset_session_person_success(self, quart_test_client):
        """POST reset/person resets session."""
        response = await quart_test_client.post(
            '/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/reset/person',
            headers={'Authorization': 'Bearer 1234567890.dummy'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0

    @pytest.mark.asyncio
    async def test_reset_session_invalid_uuid(self, quart_test_client):
        """POST reset with invalid UUID returns 400."""
        response = await quart_test_client.post(
            '/api/v1/embed/invalid-uuid/reset/person',
            headers={'Authorization': 'Bearer 1234567890.dummy'}
        )

        assert response.status_code == 400


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestEmbedFeedbackEndpoint:
    """Tests for feedback submission endpoint."""

    @pytest.mark.asyncio
    async def test_submit_feedback_like(self, quart_test_client):
        """POST feedback with type=1 (like) succeeds."""
        response = await quart_test_client.post(
            '/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/feedback',
            headers={'Authorization': 'Bearer 1234567890.dummy'},
            json={'message_id': 'msg-123', 'feedback_type': 1}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'feedback_id' in data['data']

    @pytest.mark.asyncio
    async def test_submit_feedback_dislike(self, quart_test_client):
        """POST feedback with type=2 (dislike) succeeds."""
        response = await quart_test_client.post(
            '/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/feedback',
            headers={'Authorization': 'Bearer 1234567890.dummy'},
            json={'message_id': 'msg-123', 'feedback_type': 2}
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_submit_feedback_invalid_type(self, quart_test_client):
        """POST feedback with invalid type returns 400."""
        response = await quart_test_client.post(
            '/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/feedback',
            headers={'Authorization': 'Bearer 1234567890.dummy'},
            json={'message_id': 'msg-123', 'feedback_type': 99}
        )

        assert response.status_code == 400
