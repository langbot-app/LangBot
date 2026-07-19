"""
API integration tests for embed widget endpoints.

Tests real HTTP API behavior for embed widget functionality.

Run: uv run pytest tests/integration/api/test_embed.py -q
"""

from __future__ import annotations

import json

import pytest
from unittest.mock import MagicMock, AsyncMock, Mock
from types import SimpleNamespace

from tests.factories import FakeApp


pytestmark = pytest.mark.integration
SESSION_ID = '31c0f2e9-b115-4ee6-8f15-3e624d6456b1'


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

    app.instance_config.data.update(
        {
            'api': {'port': 5300},
            'system': {'allow_modify_login_info': True, 'limitation': {}},
        }
    )

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
    mock_runtime_bot.execution_context = SimpleNamespace(
        instance_uuid='instance-test',
        workspace_uuid='workspace-test',
        placement_generation=1,
    )

    # Platform manager with bots
    app.platform_mgr = Mock()
    app.platform_mgr.bots = [mock_runtime_bot]
    app.platform_mgr.resolve_public_bot = AsyncMock(
        side_effect=lambda route_key: mock_runtime_bot if route_key == mock_bot_entity.uuid else None
    )

    # WebSocket proxy bot with adapter
    mock_websocket_adapter = Mock()
    mock_websocket_adapter.get_websocket_messages = Mock(return_value=[{'id': 'msg-1', 'content': 'test message'}])
    mock_websocket_adapter.reset_session = Mock()
    mock_websocket_adapter.handle_websocket_message = AsyncMock()

    mock_ws_proxy_bot = Mock()
    mock_ws_proxy_bot.adapter = mock_websocket_adapter
    app.platform_mgr.websocket_proxy_bot = mock_ws_proxy_bot
    app.platform_mgr.get_websocket_proxy_bot = AsyncMock(return_value=mock_ws_proxy_bot)
    app.workspace_service = SimpleNamespace(
        get_execution_binding=AsyncMock(
            return_value=SimpleNamespace(
                instance_uuid='instance-test',
                workspace_uuid='workspace-test',
                placement_generation=1,
            )
        )
    )

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
    async def test_get_widget_js_success(self, quart_test_client, fake_embed_app):
        """GET /api/v1/embed/{bot_uuid}/widget.js returns JS."""
        response = await quart_test_client.get('/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/widget.js')

        assert response.status_code == 200
        assert 'javascript' in response.content_type
        fake_embed_app.platform_mgr.resolve_public_bot.assert_any_await('a1b2c3d4-5678-90ab-cdef-123456789abc')

    @pytest.mark.asyncio
    async def test_get_widget_js_invalid_uuid(self, quart_test_client):
        """GET widget.js with invalid UUID returns 400."""
        response = await quart_test_client.get('/api/v1/embed/invalid-uuid/widget.js')

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_widget_js_bot_not_found(self, quart_test_client):
        """GET widget.js for non-existent bot returns 404."""
        response = await quart_test_client.get('/api/v1/embed/00000000-0000-0000-0000-000000000000/widget.js')

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
            '/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/turnstile/verify', json={'token': 'test-token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'token' in data['data']

    @pytest.mark.asyncio
    async def test_turnstile_verify_invalid_uuid(self, quart_test_client):
        """POST turnstile verify with invalid UUID returns 400."""
        response = await quart_test_client.post(
            '/api/v1/embed/invalid-uuid/turnstile/verify', json={'token': 'test-token'}
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_turnstile_verify_missing_token(self, quart_test_client):
        """POST turnstile verify without token returns 400."""
        response = await quart_test_client.post(
            '/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/turnstile/verify', json={}
        )

        assert response.status_code == 400


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestEmbedMessagesEndpoint:
    """Tests for messages endpoint."""

    @pytest.mark.asyncio
    async def test_get_messages_person_success(self, quart_test_client, fake_embed_app):
        """GET messages/person returns messages."""
        response = await quart_test_client.get(
            f'/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/messages/person?session_id={SESSION_ID}',
            headers={'Authorization': 'Bearer 1234567890.dummy'},
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'messages' in data['data']
        proxy_bot = fake_embed_app.platform_mgr.get_websocket_proxy_bot.return_value
        proxy_bot.adapter.get_websocket_messages.assert_called_with('test-pipeline-uuid', 'person', SESSION_ID)

    @pytest.mark.asyncio
    async def test_get_messages_group_success(self, quart_test_client):
        """GET messages/group returns messages."""
        response = await quart_test_client.get(
            f'/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/messages/group?session_id={SESSION_ID}',
            headers={'Authorization': 'Bearer 1234567890.dummy'},
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_messages_requires_session_id(self, quart_test_client):
        """GET messages without a client session identifier returns 400."""
        response = await quart_test_client.get(
            '/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/messages/person',
            headers={'Authorization': 'Bearer 1234567890.dummy'},
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_messages_invalid_session_type(self, quart_test_client):
        """GET messages with invalid session_type returns 400."""
        response = await quart_test_client.get(
            '/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/messages/invalid',
            headers={'Authorization': 'Bearer 1234567890.dummy'},
        )

        assert response.status_code == 400


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestEmbedResetEndpoint:
    """Tests for session reset endpoint."""

    @pytest.mark.asyncio
    async def test_reset_session_person_success(self, quart_test_client, fake_embed_app):
        """POST reset/person resets session."""
        response = await quart_test_client.post(
            f'/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/reset/person?session_id={SESSION_ID}',
            headers={'Authorization': 'Bearer 1234567890.dummy'},
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        proxy_bot = fake_embed_app.platform_mgr.get_websocket_proxy_bot.return_value
        proxy_bot.adapter.reset_session.assert_called_with('test-pipeline-uuid', 'person', SESSION_ID)

    @pytest.mark.asyncio
    async def test_reset_session_requires_session_id(self, quart_test_client):
        """POST reset without a client session identifier returns 400."""
        response = await quart_test_client.post(
            '/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/reset/person',
            headers={'Authorization': 'Bearer 1234567890.dummy'},
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_reset_session_invalid_uuid(self, quart_test_client):
        """POST reset with invalid UUID returns 400."""
        response = await quart_test_client.post(
            '/api/v1/embed/invalid-uuid/reset/person', headers={'Authorization': 'Bearer 1234567890.dummy'}
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
            json={'message_id': 'msg-123', 'feedback_type': 1},
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
            json={'message_id': 'msg-123', 'feedback_type': 2},
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_submit_feedback_invalid_type(self, quart_test_client):
        """POST feedback with invalid type returns 400."""
        response = await quart_test_client.post(
            '/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/feedback',
            headers={'Authorization': 'Bearer 1234567890.dummy'},
            json={'message_id': 'msg-123', 'feedback_type': 99},
        )

        assert response.status_code == 400


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestEmbedWebSocketEndpoint:
    """The public socket authenticates before resolving shared runtime state."""

    @pytest.mark.asyncio
    async def test_authenticates_before_connecting(self, quart_test_client, fake_embed_app):
        async with quart_test_client.websocket(
            f'/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/ws/connect'
            f'?session_type=person&session_id={SESSION_ID}',
            headers={'Origin': 'http://localhost'},
        ) as websocket:
            await websocket.send(json.dumps({'type': 'authenticate', 'token': ''}))
            connected = json.loads(await websocket.receive())
            assert connected['type'] == 'connected'
            assert connected['bot_uuid'] == 'a1b2c3d4-5678-90ab-cdef-123456789abc'
            await websocket.send(json.dumps({'type': 'disconnect'}))

        fake_embed_app.workspace_service.get_execution_binding.assert_awaited_with(
            'workspace-test',
            expected_generation=1,
        )

    @pytest.mark.asyncio
    async def test_rejects_non_auth_first_frame_before_runtime_lookup(self, quart_test_client, fake_embed_app):
        fake_embed_app.platform_mgr.get_websocket_proxy_bot.reset_mock()

        async with quart_test_client.websocket(
            f'/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/ws/connect'
            f'?session_type=person&session_id={SESSION_ID}',
            headers={'Origin': 'http://localhost'},
        ) as websocket:
            await websocket.send(json.dumps({'type': 'message', 'message': []}))
            response = json.loads(await websocket.receive())
            assert response == {'type': 'error', 'message': 'Unauthorized'}

        fake_embed_app.platform_mgr.get_websocket_proxy_bot.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_invalid_turnstile_session_before_runtime_lookup(self, quart_test_client, fake_embed_app):
        fake_embed_app.platform_mgr.get_websocket_proxy_bot.reset_mock()
        config = fake_embed_app.platform_mgr.resolve_public_bot.side_effect(
            'a1b2c3d4-5678-90ab-cdef-123456789abc'
        ).bot_entity.adapter_config
        config['turnstile_secret_key'] = 'test-secret'
        try:
            async with quart_test_client.websocket(
                f'/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/ws/connect'
                f'?session_type=person&session_id={SESSION_ID}',
                headers={'Origin': 'http://localhost'},
            ) as websocket:
                await websocket.send(json.dumps({'type': 'authenticate', 'token': 'invalid'}))
                response = json.loads(await websocket.receive())
                assert response == {'type': 'error', 'message': 'Unauthorized'}
        finally:
            config['turnstile_secret_key'] = ''

        fake_embed_app.platform_mgr.get_websocket_proxy_bot.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_message_when_bot_is_disabled_after_connect(self, quart_test_client, fake_embed_app):
        runtime_bot = fake_embed_app.platform_mgr.resolve_public_bot.side_effect('a1b2c3d4-5678-90ab-cdef-123456789abc')
        adapter = fake_embed_app.platform_mgr.get_websocket_proxy_bot.return_value.adapter
        adapter.handle_websocket_message.reset_mock()

        async with quart_test_client.websocket(
            f'/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/ws/connect'
            f'?session_type=person&session_id={SESSION_ID}',
            headers={'Origin': 'http://localhost'},
        ) as websocket:
            await websocket.send(json.dumps({'type': 'authenticate', 'token': ''}))
            assert json.loads(await websocket.receive())['type'] == 'connected'
            runtime_bot.bot_entity.enable = False
            try:
                await websocket.send(json.dumps({'type': 'message', 'message': [{'type': 'text', 'text': 'hi'}]}))
                response = json.loads(await websocket.receive())
                assert response == {'type': 'error', 'message': 'Bot is unavailable'}
            finally:
                runtime_bot.bot_entity.enable = True

        adapter.handle_websocket_message.assert_not_awaited()
