"""Regression tests for isolated embed-widget conversations."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.message as provider_message
from langbot.pkg.platform.sources import websocket_adapter as websocket_adapter_module
from langbot.pkg.platform.sources.websocket_adapter import WebSocketAdapter, WebSocketMessage, WebSocketSession
from langbot.pkg.platform.sources.websocket_manager import WebSocketConnectionManager, is_valid_session_id


@pytest.mark.asyncio
async def test_broadcast_only_reaches_connections_in_same_browser_session():
    manager = WebSocketConnectionManager()
    first = await manager.add_connection(
        websocket=Mock(),
        pipeline_uuid='pipeline-1',
        session_type='person',
        session_id='session-a',
    )
    second = await manager.add_connection(
        websocket=Mock(),
        pipeline_uuid='pipeline-1',
        session_type='person',
        session_id='session-b',
    )
    dashboard = await manager.add_connection(
        websocket=Mock(),
        pipeline_uuid='pipeline-1',
        session_type='person',
    )

    await manager.broadcast_to_pipeline(
        'pipeline-1',
        {'type': 'response'},
        session_type='person',
        session_id='session-a',
    )

    assert await first.send_queue.get() == {'type': 'response'}
    assert second.send_queue.empty()
    assert dashboard.send_queue.empty()

    await manager.broadcast_to_pipeline(
        'pipeline-1',
        {'type': 'dashboard-response'},
        session_type='person',
        session_id=None,
    )

    assert await dashboard.send_queue.get() == {'type': 'dashboard-response'}
    assert first.send_queue.empty()
    assert second.send_queue.empty()


@pytest.mark.asyncio
async def test_embed_event_uses_stable_session_launcher(monkeypatch):
    manager = WebSocketConnectionManager()
    session_id = '31c0f2e9-b115-4ee6-8f15-3e624d6456b1'
    connection = await manager.add_connection(
        websocket=Mock(),
        pipeline_uuid='pipeline-1',
        session_type='person',
        session_id=session_id,
    )
    monkeypatch.setattr(websocket_adapter_module, 'ws_connection_manager', manager)

    adapter = WebSocketAdapter.model_construct(ap=Mock(), logger=AsyncMock())
    adapter.websocket_person_session = WebSocketSession(id='person')
    adapter.websocket_group_session = WebSocketSession(id='group')
    received = []

    async def listener(event, _callback_adapter):
        received.append(event)

    adapter.listeners = {platform_events.FriendMessage: listener}
    await adapter.handle_websocket_message(
        connection,
        {'message': [{'type': 'Plain', 'text': 'hello'}], 'stream': False},
    )
    await asyncio.sleep(0)

    assert received[0].sender.id == f'websocket_pipeline-1:{session_id}'


@pytest.mark.asyncio
async def test_embed_group_event_uses_stable_session_launcher(monkeypatch):
    manager = WebSocketConnectionManager()
    session_id = '31c0f2e9-b115-4ee6-8f15-3e624d6456b1'
    connection = await manager.add_connection(
        websocket=Mock(),
        pipeline_uuid='pipeline-1',
        session_type='group',
        session_id=session_id,
    )
    monkeypatch.setattr(websocket_adapter_module, 'ws_connection_manager', manager)

    adapter = WebSocketAdapter.model_construct(ap=Mock(), logger=AsyncMock())
    adapter.websocket_person_session = WebSocketSession(id='person')
    adapter.websocket_group_session = WebSocketSession(id='group')
    received = []

    async def listener(event, _callback_adapter):
        received.append(event)

    adapter.listeners = {platform_events.GroupMessage: listener}
    await adapter.handle_websocket_message(
        connection,
        {'message': [{'type': 'Plain', 'text': 'hello'}], 'stream': False},
    )
    await asyncio.sleep(0)

    assert received[0].sender.id == f'websocket_pipeline-1:{session_id}'
    assert received[0].sender.group.id == f'websocketgroup_pipeline-1:{session_id}'

    dashboard = await manager.add_connection(
        websocket=Mock(),
        pipeline_uuid='pipeline-1',
        session_type='group',
    )
    await adapter.handle_websocket_message(
        dashboard,
        {'stream': False, 'message': [{'type': 'Plain', 'text': 'dashboard'}]},
        None,
    )
    await asyncio.sleep(0)

    assert received[1].sender.id == f'websocket_{dashboard.connection_id}'
    assert received[1].sender.group.id == 'websocketgroup'


@pytest.mark.asyncio
async def test_stable_session_launcher_resolves_to_active_connection(monkeypatch):
    manager = WebSocketConnectionManager()
    session_id = '31c0f2e9-b115-4ee6-8f15-3e624d6456b1'
    await manager.add_connection(
        websocket=Mock(),
        pipeline_uuid='pipeline-2',
        session_type='person',
        session_id=session_id,
    )
    connection = await manager.add_connection(
        websocket=Mock(),
        pipeline_uuid='pipeline-1',
        session_type='person',
        session_id=session_id,
    )
    monkeypatch.setattr(websocket_adapter_module, 'ws_connection_manager', manager)

    adapter = WebSocketAdapter.model_construct(ap=Mock(), logger=AsyncMock())
    message_source = Mock()
    message_source.sender.id = f'websocket_pipeline-1:{session_id}'

    assert await adapter._get_message_context(message_source) == ('pipeline-1', session_id)
    assert await adapter._get_connection_from_target(f'websocketgroup_pipeline-1:{session_id}') is connection
    assert await manager.get_connection_by_session_id(session_id, 'pipeline-1') is connection

    await manager.remove_connection(connection.connection_id)

    assert await adapter._get_message_context(message_source) == ('pipeline-1', session_id)
    assert await manager.get_connection_by_session_id(session_id, 'pipeline-1') is None


@pytest.mark.asyncio
async def test_dashboard_reply_uses_event_pipeline_after_connection_closes(monkeypatch):
    manager = WebSocketConnectionManager()
    connection = await manager.add_connection(
        websocket=Mock(),
        pipeline_uuid='pipeline-1',
        session_type='person',
    )
    monkeypatch.setattr(websocket_adapter_module, 'ws_connection_manager', manager)

    app = Mock()
    app.platform_mgr.websocket_proxy_bot.bot_entity = Mock(spec=[])
    adapter = WebSocketAdapter.model_construct(ap=app, logger=AsyncMock())
    message_source = platform_events.FriendMessage(
        sender=platform_entities.Friend(
            id=f'websocket_{connection.connection_id}',
            nickname='User',
            remark='User',
        ),
        message_chain=platform_message.MessageChain([platform_message.Plain(text='hello')]),
        time=1,
    )
    object.__setattr__(message_source, '_langbot_pipeline_uuid', 'pipeline-1')
    await manager.remove_connection(connection.connection_id)

    assert await adapter._get_message_context(message_source) == ('pipeline-1', None)


@pytest.mark.asyncio
async def test_late_final_events_update_one_stream_message(monkeypatch):
    manager = WebSocketConnectionManager()
    connection = await manager.add_connection(
        websocket=Mock(),
        pipeline_uuid='pipeline-1',
        session_type='person',
    )
    monkeypatch.setattr(websocket_adapter_module, 'ws_connection_manager', manager)

    adapter = WebSocketAdapter.model_construct(ap=Mock(), logger=AsyncMock())
    adapter.websocket_person_session = WebSocketSession(id='person')
    adapter.websocket_group_session = WebSocketSession(id='group')
    message_source = platform_events.FriendMessage(
        sender=platform_entities.Friend(
            id=f'websocket_{connection.connection_id}',
            nickname='User',
            remark='User',
        ),
        message_chain=platform_message.MessageChain([platform_message.Plain(text='hello')]),
        time=1,
    )
    first = provider_message.MessageChunk(
        role='assistant',
        content='first final',
        is_final=True,
        resp_message_id='response-1',
    )
    second = provider_message.MessageChunk(
        role='assistant',
        content='corrected final',
        is_final=True,
        resp_message_id='response-1',
    )

    await adapter.reply_message_chunk(
        message_source,
        first,
        platform_message.MessageChain([platform_message.Plain(text='first final')]),
        is_final=True,
    )
    await adapter.reply_message_chunk(
        message_source,
        second,
        platform_message.MessageChain([platform_message.Plain(text='corrected final')]),
        is_final=True,
    )

    messages = adapter.get_websocket_messages('pipeline-1', 'person')
    assert len(messages) == 1
    assert messages[0]['content'] == 'corrected final'
    assert messages[0]['is_final'] is True


def test_session_ids_must_be_canonical_random_uuids():
    assert is_valid_session_id('31c0f2e9-b115-4ee6-8f15-3e624d6456b1')
    assert not is_valid_session_id('session-a')
    assert not is_valid_session_id('00000000-0000-0000-0000-000000000000')


def test_history_read_does_not_allocate_unknown_session():
    adapter = WebSocketAdapter.model_construct(ap=Mock(), logger=AsyncMock())
    adapter.websocket_person_session = WebSocketSession(id='person')
    adapter.websocket_group_session = WebSocketSession(id='group')

    assert adapter.get_websocket_messages('pipeline-1', 'person', 'missing-session') == []
    assert adapter.websocket_person_session.message_lists == {}


def test_history_and_reset_are_scoped_to_browser_session():
    matching_provider_session = Mock(
        launcher_type=Mock(value='person'),
        launcher_id='websocket_pipeline-1:session-a',
    )
    matching_group_provider_session = Mock(
        launcher_type=Mock(value='group'),
        launcher_id='websocketgroup_pipeline-1:session-a',
    )
    other_session = Mock(
        launcher_type=Mock(value='person'),
        launcher_id='websocket_pipeline-1:session-b',
    )
    ap = Mock()
    ap.sess_mgr.session_list = [
        matching_provider_session,
        matching_group_provider_session,
        other_session,
    ]
    adapter = WebSocketAdapter.model_construct(
        ap=ap,
        logger=AsyncMock(),
    )
    adapter.websocket_person_session = Mock()
    adapter.websocket_group_session = Mock()

    session_a = [
        WebSocketMessage(
            id=1,
            role='user',
            content='private-a',
            message_chain=[],
            timestamp='2026-07-13T00:00:00',
        )
    ]
    session_b = [
        WebSocketMessage(
            id=1,
            role='user',
            content='private-b',
            message_chain=[],
            timestamp='2026-07-13T00:00:00',
        )
    ]
    histories = {
        'pipeline-1:session-a': session_a,
        'pipeline-1:session-b': session_b,
    }
    stream_indexes = {
        'pipeline-1:session-a': {'response-a': 0},
        'pipeline-1:session-b': {'response-b': 0},
    }
    adapter.websocket_person_session.get_message_list.side_effect = histories.__getitem__
    adapter.websocket_person_session.message_lists = histories
    adapter.websocket_person_session.stream_message_indexes = stream_indexes
    adapter.websocket_group_session.message_lists = {}
    adapter.websocket_group_session.stream_message_indexes = {}

    assert adapter.get_websocket_messages('pipeline-1', 'person', 'session-a')[0]['content'] == 'private-a'
    assert adapter.get_websocket_messages('pipeline-1', 'person', 'session-b')[0]['content'] == 'private-b'

    adapter.reset_session('pipeline-1', 'person', 'session-a')

    assert histories['pipeline-1:session-a'] == []
    assert stream_indexes['pipeline-1:session-a'] == {}
    assert histories['pipeline-1:session-b'] == session_b
    assert stream_indexes['pipeline-1:session-b'] == {'response-b': 0}
    assert ap.sess_mgr.session_list == [matching_group_provider_session, other_session]

    adapter.reset_session('pipeline-1', 'group', 'session-a')

    assert ap.sess_mgr.session_list == [other_session]


def test_widget_sends_stable_session_id_to_all_conversation_endpoints():
    widget_path = Path(__file__).parents[3] / 'src/langbot/templates/embed/widget.js'
    widget = widget_path.read_text(encoding='utf-8')

    assert 'langbot_embed_session_' in widget
    assert 'window.sessionStorage' in widget
    assert 'window.localStorage' not in widget
    assert 'session_id=' in widget
    assert widget.count('encodeURIComponent(state.sessionId)') >= 3
    assert 'loadHistory(true)' in widget
    assert 'messageVersion !== state.messageVersion' in widget
    assert 'scheduleHistoryReload();' in widget
