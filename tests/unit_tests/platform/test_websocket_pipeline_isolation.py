"""Regression tests for cross-pipeline Debug Chat isolation (#2286).

Debug Chat routing must stay request-local: concurrent messages for
different pipelines must not race on the mutable singleton
``websocket_proxy_bot.bot_entity.use_pipeline_uuid`` field.
"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

import langbot_plugin.api.entities.builtin.platform.events as platform_events
from langbot.pkg.platform.sources import websocket_adapter as websocket_adapter_module
from langbot.pkg.platform.sources.websocket_adapter import (
    MAX_REMEMBERED_CONNECTION_ROUTES,
    WebSocketAdapter,
    WebSocketSession,
)
from langbot.pkg.platform.sources.websocket_manager import WebSocketConnectionManager


def _make_adapter() -> WebSocketAdapter:
    adapter = WebSocketAdapter.model_construct(ap=Mock(), logger=AsyncMock())
    adapter.websocket_person_session = WebSocketSession(id='person')
    adapter.websocket_group_session = WebSocketSession(id='group')
    return adapter


@pytest.mark.asyncio
async def test_concurrent_dashboard_events_resolve_their_own_pipeline(monkeypatch):
    manager = WebSocketConnectionManager()
    connection_a = await manager.add_connection(
        websocket=Mock(),
        pipeline_uuid='pipeline-a',
        session_type='person',
    )
    connection_b = await manager.add_connection(
        websocket=Mock(),
        pipeline_uuid='pipeline-b',
        session_type='person',
    )
    monkeypatch.setattr(websocket_adapter_module, 'ws_connection_manager', manager)

    adapter = _make_adapter()
    received = []

    async def listener(event, _callback_adapter):
        received.append(event)

    adapter.listeners = {platform_events.FriendMessage: listener}

    # Interleave two messages before either listener task runs, mimicking the
    # concurrent WebSocket messages from the cross-pipeline isolation QA case.
    await adapter.handle_websocket_message(
        connection_a,
        {'message': [{'type': 'Plain', 'text': 'PIPEA-token'}], 'stream': False},
    )
    await adapter.handle_websocket_message(
        connection_b,
        {'message': [{'type': 'Plain', 'text': 'PIPEB-token'}], 'stream': False},
    )
    await asyncio.sleep(0)

    # The singleton field now holds pipeline-b, but each event must still
    # resolve to the pipeline of the connection it arrived on.
    assert adapter.ap.platform_mgr.websocket_proxy_bot.bot_entity.use_pipeline_uuid == 'pipeline-b'
    assert len(received) == 2
    assert adapter.get_event_pipeline_uuid(received[0]) == 'pipeline-a'
    assert adapter.get_event_pipeline_uuid(received[1]) == 'pipeline-b'


@pytest.mark.asyncio
async def test_group_dashboard_event_resolves_pipeline(monkeypatch):
    manager = WebSocketConnectionManager()
    connection = await manager.add_connection(
        websocket=Mock(),
        pipeline_uuid='pipeline-a',
        session_type='group',
    )
    monkeypatch.setattr(websocket_adapter_module, 'ws_connection_manager', manager)

    adapter = _make_adapter()
    received = []

    async def listener(event, _callback_adapter):
        received.append(event)

    adapter.listeners = {platform_events.GroupMessage: listener}
    await adapter.handle_websocket_message(
        connection,
        {'message': [{'type': 'Plain', 'text': 'hello'}], 'stream': False},
    )
    await asyncio.sleep(0)

    assert adapter.get_event_pipeline_uuid(received[0]) == 'pipeline-a'


def test_embed_event_resolves_pipeline_without_live_connection(monkeypatch):
    monkeypatch.setattr(websocket_adapter_module, 'ws_connection_manager', WebSocketConnectionManager())

    adapter = _make_adapter()
    event = Mock()
    event.sender.id = 'websocket_pipeline-1:31c0f2e9-b115-4ee6-8f15-3e624d6456b1'

    assert adapter.get_event_pipeline_uuid(event) == 'pipeline-1'


def test_non_websocket_event_returns_no_pipeline_hint(monkeypatch):
    monkeypatch.setattr(websocket_adapter_module, 'ws_connection_manager', WebSocketConnectionManager())

    adapter = _make_adapter()
    event = Mock()
    event.sender.id = '12345678'

    assert adapter.get_event_pipeline_uuid(event) is None


@pytest.mark.asyncio
async def test_reply_context_survives_connection_close(monkeypatch):
    manager = WebSocketConnectionManager()
    connection = await manager.add_connection(
        websocket=Mock(),
        pipeline_uuid='pipeline-a',
        session_type='person',
    )
    monkeypatch.setattr(websocket_adapter_module, 'ws_connection_manager', manager)

    adapter = _make_adapter()
    adapter.listeners = {}
    await adapter.handle_websocket_message(
        connection,
        {'message': [{'type': 'Plain', 'text': 'hello'}], 'stream': False},
    )

    # Simulate another pipeline's message overwriting the singleton field
    # while pipeline-a's reply is still in flight.
    adapter.ap.platform_mgr.websocket_proxy_bot.bot_entity.use_pipeline_uuid = 'pipeline-b'

    message_source = Mock()
    message_source.sender.id = f'websocket_{connection.connection_id}'

    # Live connection resolves directly.
    assert await adapter._get_message_context(message_source) == ('pipeline-a', None)

    # After the client disconnects the retained route must still win over
    # the singleton fallback, so a late reply cannot leak to pipeline-b.
    await manager.remove_connection(connection.connection_id)
    assert await adapter._get_message_context(message_source) == ('pipeline-a', None)


def test_connection_route_memory_is_bounded():
    adapter = _make_adapter()

    for index in range(MAX_REMEMBERED_CONNECTION_ROUTES + 10):
        adapter._remember_connection_route(Mock(connection_id=f'conn-{index}', pipeline_uuid=f'pipeline-{index}'))

    assert len(adapter._connection_pipeline_routes) == MAX_REMEMBERED_CONNECTION_ROUTES
    assert 'conn-0' not in adapter._connection_pipeline_routes
    assert adapter._connection_pipeline_routes[f'conn-{MAX_REMEMBERED_CONNECTION_ROUTES + 9}'] == (
        f'pipeline-{MAX_REMEMBERED_CONNECTION_ROUTES + 9}'
    )
