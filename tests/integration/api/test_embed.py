"""
API integration tests for embed widget endpoints.

Tests real HTTP API behavior for embed widget functionality.

Run: uv run pytest tests/integration/api/test_embed.py -q
"""

from __future__ import annotations

import json
import os
from pathlib import Path

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
    mock_runtime_bot.get_pipeline_target_for_event_type = Mock(return_value='test-pipeline-uuid')
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

        body = await response.get_data(as_text=True)
        assert 'a1b2c3d4-5678-90ab-cdef-123456789abc' in body
        assert 'baseUrl: "http://localhost"' in body
        assert '__LANGBOT_' not in body

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ('query', 'expected_base'),
        [('', 'https://public.example/bot'), ('?preview=wizard', 'http://localhost')],
    )
    async def test_widget_preview_uses_current_backend(
        self, quart_test_client, fake_embed_app, monkeypatch, query, expected_base
    ):
        monkeypatch.setitem(fake_embed_app.instance_config.data['api'], 'webhook_prefix', 'https://public.example/bot')
        response = await quart_test_client.get('/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/widget.js' + query)
        assert response.status_code == 200
        body = await response.get_data(as_text=True)
        assert f'baseUrl: "{expected_base}"' in body
        assert f'logoUrl: "{expected_base}"' in body

    def test_widget_template_cache_reloads_after_file_change(self, monkeypatch, tmp_path):
        """Development edits to widget.js take effect without restarting the backend."""
        import langbot.pkg.api.http.controller.groups.pipelines.embed as embed

        template_path = tmp_path / 'widget.js'
        template_path.write_text('first version', encoding='utf-8')
        monkeypatch.setattr(embed.paths, 'get_resource_path', lambda _: str(template_path))
        embed._widget_template_cache = None
        embed._widget_template_cache_mtime_ns = None

        assert embed._get_widget_template() == 'first version'

        previous_mtime_ns = template_path.stat().st_mtime_ns
        template_path.write_text('second version', encoding='utf-8')
        os.utime(template_path, ns=(previous_mtime_ns + 1_000_000, previous_mtime_ns + 1_000_000))

        assert embed._get_widget_template() == 'second version'

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

        body = await response.get_data()
        assert body == (Path(__file__).parents[3] / 'src/langbot/templates/embed/logo.webp').read_bytes()
        assert body[:4] == b'RIFF' and body[8:12] == b'WEBP'


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestEmbedTurnstileVerifyEndpoint:
    """Tests for Turnstile verification endpoint."""

    @pytest.mark.asyncio
    async def test_turnstile_verify_no_secret(self, quart_test_client, monkeypatch):
        """POST turnstile verify without secret returns dummy token."""
        import langbot.pkg.api.http.controller.groups.pipelines.embed as embed

        monkeypatch.setattr(embed.time, 'time', lambda: 1720000000.25)
        response = await quart_test_client.post(
            '/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/turnstile/verify', json={'token': 'test-token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'token' in data['data']

        assert data['data']['token'] == '1720000000.25.dummy'

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
    async def test_get_messages_group_success(self, quart_test_client, fake_embed_app):
        """GET messages/group returns messages."""
        response = await quart_test_client.get(
            f'/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/messages/group?session_id={SESSION_ID}',
            headers={'Authorization': 'Bearer 1234567890.dummy'},
        )

        assert response.status_code == 200

        data = await response.get_json()
        assert data['code'] == 0
        assert data['data']['messages'] == [{'id': 'msg-1', 'content': 'test message'}]
        adapter = fake_embed_app.platform_mgr.get_websocket_proxy_bot.return_value.adapter
        adapter.get_websocket_messages.assert_called_with('test-pipeline-uuid', 'group', SESSION_ID)

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
            f'/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/messages/invalid?session_id={SESSION_ID}',
            headers={'Authorization': 'Bearer 1234567890.dummy'},
        )

        assert response.status_code == 400

        assert (await response.get_json())['msg'] == 'session_type must be person or group'


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
    async def test_submit_feedback_like(self, quart_test_client, fake_embed_app, monkeypatch):
        """POST feedback with type=1 (like) succeeds."""
        import langbot.pkg.api.http.controller.groups.pipelines.embed as embed

        monkeypatch.setattr(embed.uuid, 'uuid4', lambda: SimpleNamespace(hex='123456789abcdef0123456789abcdef0'))
        fake_embed_app.monitoring_service.record_feedback.reset_mock()
        response = await quart_test_client.post(
            '/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/feedback',
            headers={'Authorization': 'Bearer 1234567890.dummy'},
            json={'message_id': 'msg-123', 'feedback_type': 1},
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'feedback_id' in data['data']

        data = await response.get_json()
        assert data['code'] == 0
        assert data['data']['feedback_id'] == 'embed_123456789abc'
        called = fake_embed_app.monitoring_service.record_feedback
        assert called.await_count == 1
        assert called.await_args.args[0].workspace_uuid == 'workspace-test'
        assert called.await_args.kwargs == {
            'feedback_id': 'embed_123456789abc',
            'feedback_type': 1,
            'bot_id': 'a1b2c3d4-5678-90ab-cdef-123456789abc',
            'bot_name': 'Test Web Bot',
            'pipeline_id': 'test-pipeline-uuid',
            'message_id': 'msg-123',
            'platform': 'web_page_bot',
        }

    @pytest.mark.asyncio
    async def test_submit_feedback_dislike(self, quart_test_client, fake_embed_app, monkeypatch):
        """POST feedback with type=2 (dislike) succeeds."""
        import langbot.pkg.api.http.controller.groups.pipelines.embed as embed

        monkeypatch.setattr(embed.uuid, 'uuid4', lambda: SimpleNamespace(hex='123456789abcdef0123456789abcdef0'))
        fake_embed_app.monitoring_service.record_feedback.reset_mock()
        response = await quart_test_client.post(
            '/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/feedback',
            headers={'Authorization': 'Bearer 1234567890.dummy'},
            json={'message_id': 'msg-123', 'feedback_type': 2},
        )

        assert response.status_code == 200

        data = await response.get_json()
        assert data['code'] == 0
        assert data['data']['feedback_id'] == 'embed_123456789abc'
        called = fake_embed_app.monitoring_service.record_feedback
        assert called.await_count == 1
        assert called.await_args.args[0].workspace_uuid == 'workspace-test'
        assert called.await_args.kwargs == {
            'feedback_id': 'embed_123456789abc',
            'feedback_type': 2,
            'bot_id': 'a1b2c3d4-5678-90ab-cdef-123456789abc',
            'bot_name': 'Test Web Bot',
            'pipeline_id': 'test-pipeline-uuid',
            'message_id': 'msg-123',
            'platform': 'web_page_bot',
        }

    @pytest.mark.asyncio
    async def test_submit_feedback_invalid_type(self, quart_test_client):
        """POST feedback with invalid type returns 400."""
        response = await quart_test_client.post(
            '/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/feedback',
            headers={'Authorization': 'Bearer 1234567890.dummy'},
            json={'message_id': 'msg-123', 'feedback_type': 99},
        )

        assert response.status_code == 400


@pytest.fixture
def embed_websocket_adapter(fake_embed_app, monkeypatch):
    """Serve reply lookups from a real WebSocket adapter's conversation history."""
    from langbot.pkg.platform.sources.websocket_adapter import WebSocketAdapter, WebSocketSession

    adapter = WebSocketAdapter.model_construct(
        websocket_person_session=WebSocketSession(id='person'),
        websocket_group_session=WebSocketSession(id='group'),
    )
    proxy_adapter = fake_embed_app.platform_mgr.get_websocket_proxy_bot.return_value.adapter
    monkeypatch.setattr(proxy_adapter, 'get_monitoring_message_id', adapter.get_monitoring_message_id)
    return adapter


@pytest.fixture
async def stored_feedback(tmp_path, fake_embed_app, monkeypatch, embed_websocket_adapter):
    """Route embed feedback into the real monitoring store on SQLite."""
    import sqlalchemy
    from sqlalchemy.ext.asyncio import create_async_engine

    from langbot.pkg.api.http.context import ExecutionContext
    from langbot.pkg.api.http.service.monitoring import MonitoringService
    from langbot.pkg.entity.persistence.base import Base
    from langbot.pkg.entity.persistence.monitoring import MonitoringFeedback
    from langbot.pkg.entity.persistence.workspace import Workspace

    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "monitoring.db"}')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(
            sqlalchemy.insert(Workspace).values(
                uuid='workspace-test',
                instance_uuid='instance-test',
                name='Test',
                slug='test',
                source='cloud_projection',
            )
        )

    async def execute_async(*args, **kwargs):
        async with engine.connect() as connection:
            result = await connection.execute(*args, **kwargs)
            await connection.commit()
            return result

    service = MonitoringService(
        SimpleNamespace(
            persistence_mgr=SimpleNamespace(execute_async=execute_async, get_db_engine=lambda: engine),
            instance_config=SimpleNamespace(data={'database': {'use': 'sqlite'}}),
        )
    )

    async def record_feedback(context, **kwargs):
        # RuntimeBot carries a real ExecutionContext; the module fixture does not.
        context = ExecutionContext(
            instance_uuid=context.instance_uuid,
            workspace_uuid=context.workspace_uuid,
            placement_generation=context.placement_generation,
        )
        return await service.record_feedback(context, **kwargs)

    monkeypatch.setattr(fake_embed_app.monitoring_service, 'record_feedback', record_feedback)

    async def rows():
        async with engine.connect() as connection:
            result = await connection.execute(
                sqlalchemy.select(
                    MonitoringFeedback.feedback_type,
                    MonitoringFeedback.session_id,
                    MonitoringFeedback.message_id,
                    MonitoringFeedback.stream_id,
                ).order_by(MonitoringFeedback.session_id)
            )
            return [tuple(row) for row in result]

    yield rows
    await engine.dispose()


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestEmbedFeedbackPerVisitor:
    """Each visitor's vote on each answer is one record that the visitor can change."""

    BOT_FEEDBACK_URL = '/api/v1/embed/a1b2c3d4-5678-90ab-cdef-123456789abc/feedback'
    OTHER_SESSION_ID = '9d3e8a41-2c7b-4f60-8e15-b4a7c2d9f031'

    async def _vote(self, client, session_id, message_id, feedback_type):
        response = await client.post(
            self.BOT_FEEDBACK_URL,
            headers={'Authorization': 'Bearer 1234567890.dummy'},
            json={
                'message_id': message_id,
                'feedback_type': feedback_type,
                'session_id': session_id,
                'session_type': 'person',
            },
        )
        assert response.status_code == 200
        return (await response.get_json())['data']['feedback_id']

    @pytest.mark.asyncio
    async def test_visitors_voting_on_the_same_bubble_id_stay_separate(self, quart_test_client, stored_feedback):
        # Bubble ids are per conversation, so both visitors' first answer is 2.
        first = await self._vote(quart_test_client, SESSION_ID, 2, 1)
        second = await self._vote(quart_test_client, self.OTHER_SESSION_ID, 2, 2)

        assert first != second
        assert await stored_feedback() == [
            (1, f'person_websocket_test-pipeline-uuid:{SESSION_ID}', '2', None),
            (2, f'person_websocket_test-pipeline-uuid:{self.OTHER_SESSION_ID}', '2', None),
        ]

    @pytest.mark.asyncio
    async def test_changing_and_cancelling_a_vote_updates_the_same_record(self, quart_test_client, stored_feedback):
        await self._vote(quart_test_client, self.OTHER_SESSION_ID, 2, 1)
        await self._vote(quart_test_client, SESSION_ID, 2, 1)
        await self._vote(quart_test_client, SESSION_ID, 2, 2)
        assert await stored_feedback() == [
            (2, f'person_websocket_test-pipeline-uuid:{SESSION_ID}', '2', None),
            (1, f'person_websocket_test-pipeline-uuid:{self.OTHER_SESSION_ID}', '2', None),
        ]

        # The widget sends 3 when a visitor clicks their active vote again.
        await self._vote(quart_test_client, SESSION_ID, 2, 3)
        assert await stored_feedback() == [
            (1, f'person_websocket_test-pipeline-uuid:{self.OTHER_SESSION_ID}', '2', None),
        ]

    @staticmethod
    def _show(adapter, session_id, message_id, role, monitoring_message_id=None):
        from langbot.pkg.platform.sources.websocket_adapter import WebSocketMessage

        adapter.websocket_person_session.append_message(
            adapter._conversation_key('test-pipeline-uuid', session_id),
            WebSocketMessage(
                id=message_id,
                role=role,
                content='text',
                message_chain=[],
                timestamp='2026-11-11T00:00:00',
                is_final=True,
                monitoring_message_id=monitoring_message_id,
            ),
        )

    @pytest.mark.asyncio
    async def test_vote_links_to_the_monitoring_record_of_the_rated_answer(
        self, quart_test_client, stored_feedback, embed_websocket_adapter
    ):
        self._show(embed_websocket_adapter, SESSION_ID, 1, 'user')
        self._show(embed_websocket_adapter, SESSION_ID, 2, 'assistant', 'monitoring-a')
        self._show(embed_websocket_adapter, self.OTHER_SESSION_ID, 2, 'assistant', 'monitoring-b')
        self._show(embed_websocket_adapter, self.OTHER_SESSION_ID, 3, 'assistant', 'monitoring-c')

        await self._vote(quart_test_client, SESSION_ID, 2, 1)
        await self._vote(quart_test_client, self.OTHER_SESSION_ID, 2, 2)
        # A bubble id that only exists in another visitor's conversation, and a
        # visitor's own question, link to nothing.
        await self._vote(quart_test_client, SESSION_ID, 3, 1)
        await self._vote(quart_test_client, SESSION_ID, 1, 1)

        rows = await stored_feedback()
        assert sorted(rows, key=lambda row: (row[1], row[2])) == [
            (1, f'person_websocket_test-pipeline-uuid:{SESSION_ID}', '1', None),
            (1, f'person_websocket_test-pipeline-uuid:{SESSION_ID}', '2', 'monitoring-a'),
            (1, f'person_websocket_test-pipeline-uuid:{SESSION_ID}', '3', None),
            (2, f'person_websocket_test-pipeline-uuid:{self.OTHER_SESSION_ID}', '2', 'monitoring-b'),
        ]

        # Changing the vote after the reply aged out of history keeps the link.
        embed_websocket_adapter.websocket_person_session.clear()
        await self._vote(quart_test_client, SESSION_ID, 2, 2)
        assert (2, f'person_websocket_test-pipeline-uuid:{SESSION_ID}', '2', 'monitoring-a') in await stored_feedback()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        'body',
        [
            {'session_id': 'visitor-1', 'message_id': 2},
            {'session_id': SESSION_ID, 'message_id': ''},
            {'session_id': SESSION_ID, 'message_id': 'x' * 65},
            {'session_id': SESSION_ID, 'message_id': 2, 'session_type': 'channel'},
        ],
        ids=['malformed-session', 'missing-message', 'oversized-message', 'unknown-session-type'],
    )
    async def test_conversation_vote_rejects_malformed_identity(self, quart_test_client, stored_feedback, body):
        response = await quart_test_client.post(
            self.BOT_FEEDBACK_URL,
            headers={'Authorization': 'Bearer 1234567890.dummy'},
            json={'feedback_type': 1, **body},
        )

        assert response.status_code == 400
        assert await stored_feedback() == []


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestEmbedWebSocketEndpoint:
    """The public socket authenticates before resolving shared runtime state."""

    @pytest.mark.asyncio
    async def test_authenticates_before_connecting(self, quart_test_client, fake_embed_app, monkeypatch):
        import langbot.pkg.api.http.controller.groups.pipelines.embed as embed

        authenticated = False
        original_authenticate = embed.EmbedRouterGroup._authenticate_websocket
        original_add = embed.ws_connection_manager.add_connection
        proxy = fake_embed_app.platform_mgr.get_websocket_proxy_bot

        async def authenticate(router, runtime_bot):
            nonlocal authenticated
            await original_authenticate(router, runtime_bot)
            authenticated = True

        async def get_proxy(*_args, **_kwargs):
            assert authenticated, 'Runtime lookup must follow successful authentication'
            return proxy.return_value

        async def add_connection(*args, **kwargs):
            assert authenticated, 'Connection registration must follow successful authentication'
            return await original_add(*args, **kwargs)

        monkeypatch.setattr(embed.EmbedRouterGroup, '_authenticate_websocket', authenticate)
        monkeypatch.setattr(proxy, 'side_effect', get_proxy)
        monkeypatch.setattr(embed.ws_connection_manager, 'add_connection', add_connection)
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
