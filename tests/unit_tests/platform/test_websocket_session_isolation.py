"""Regression tests for isolated embed-widget conversations."""

import asyncio
import contextvars
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.message as provider_message
from langbot.pkg.platform.sources import websocket_adapter as websocket_adapter_module
from langbot.pkg.platform.sources.websocket_adapter import WebSocketAdapter, WebSocketMessage, WebSocketSession
from langbot.pkg.platform.sources.websocket_manager import (
    WebSocketConnectionManager,
    WebSocketScope,
    is_valid_session_id,
)


SCOPE_A = WebSocketScope('instance-a', 'workspace-a', 1)
SCOPE_B = WebSocketScope('instance-a', 'workspace-b', 1)


def _adapter_logger(scope: WebSocketScope = SCOPE_A):
    logger = AsyncMock()
    logger.execution_context = Mock(
        instance_uuid=scope.instance_uuid,
        workspace_uuid=scope.workspace_uuid,
        placement_generation=scope.placement_generation,
    )
    return logger


@pytest.mark.asyncio
async def test_broadcast_only_reaches_connections_in_same_browser_session():
    manager = WebSocketConnectionManager()
    first = await manager.add_connection(
        websocket=Mock(),
        scope=SCOPE_A,
        pipeline_uuid='pipeline-1',
        session_type='person',
        session_id='session-a',
    )
    second = await manager.add_connection(
        websocket=Mock(),
        scope=SCOPE_A,
        pipeline_uuid='pipeline-1',
        session_type='person',
        session_id='session-b',
    )
    dashboard = await manager.add_connection(
        websocket=Mock(),
        scope=SCOPE_A,
        pipeline_uuid='pipeline-1',
        session_type='person',
    )

    await manager.broadcast_to_pipeline(
        'pipeline-1',
        {'type': 'response'},
        scope=SCOPE_A,
        session_type='person',
        session_id='session-a',
    )

    assert await first.send_queue.get() == {'type': 'response'}
    assert second.send_queue.empty()
    assert dashboard.send_queue.empty()

    await manager.broadcast_to_pipeline(
        'pipeline-1',
        {'type': 'dashboard-response'},
        scope=SCOPE_A,
        session_type='person',
        session_id=None,
    )

    assert await dashboard.send_queue.get() == {'type': 'dashboard-response'}
    assert first.send_queue.empty()
    assert second.send_queue.empty()


@pytest.mark.asyncio
async def test_pipeline_indexes_and_broadcasts_are_workspace_scoped():
    manager = WebSocketConnectionManager()
    workspace_a = await manager.add_connection(
        websocket=Mock(),
        scope=SCOPE_A,
        pipeline_uuid='shared-pipeline',
        session_type='person',
    )
    workspace_b = await manager.add_connection(
        websocket=Mock(),
        scope=SCOPE_B,
        pipeline_uuid='shared-pipeline',
        session_type='person',
    )

    await manager.broadcast_to_pipeline(
        'shared-pipeline',
        {'type': 'workspace-a'},
        scope=SCOPE_A,
    )

    assert await workspace_a.send_queue.get() == {'type': 'workspace-a'}
    assert workspace_b.send_queue.empty()
    assert await manager.get_connection(workspace_b.connection_id, scope=SCOPE_A) is None
    assert await manager.get_connection(workspace_b.connection_id, scope=SCOPE_B) is workspace_b
    assert manager.get_stats(scope=SCOPE_A)['total_connections'] == 1


@pytest.mark.asyncio
async def test_connection_admission_is_bounded_globally_and_per_workspace():
    manager = WebSocketConnectionManager()
    await manager.add_connection(
        websocket=Mock(),
        scope=SCOPE_A,
        pipeline_uuid='pipeline-1',
        session_type='person',
        max_connections=2,
        max_connections_per_workspace=1,
    )

    with pytest.raises(RuntimeError, match='Workspace WebSocket'):
        await manager.add_connection(
            websocket=Mock(),
            scope=SCOPE_A,
            pipeline_uuid='pipeline-2',
            session_type='person',
            max_connections=2,
            max_connections_per_workspace=1,
        )

    await manager.add_connection(
        websocket=Mock(),
        scope=SCOPE_B,
        pipeline_uuid='pipeline-1',
        session_type='person',
        max_connections=2,
        max_connections_per_workspace=1,
    )
    with pytest.raises(RuntimeError, match='WebSocket connection capacity'):
        await manager.add_connection(
            websocket=Mock(),
            scope=WebSocketScope('instance-a', 'workspace-c', 1),
            pipeline_uuid='pipeline-1',
            session_type='person',
            max_connections=2,
            max_connections_per_workspace=1,
        )


@pytest.mark.asyncio
async def test_close_scope_closes_and_removes_only_matching_connections():
    manager = WebSocketConnectionManager()
    websocket_a = Mock(close=AsyncMock())
    connection_a = await manager.add_connection(
        websocket=websocket_a,
        scope=SCOPE_A,
        pipeline_uuid='pipeline-1',
        session_type='person',
    )
    connection_b = await manager.add_connection(
        websocket=Mock(close=AsyncMock()),
        scope=SCOPE_B,
        pipeline_uuid='pipeline-1',
        session_type='person',
    )

    await manager.close_scope(SCOPE_A)

    websocket_a.close.assert_awaited_once()
    assert await manager.get_connection(connection_a.connection_id, scope=SCOPE_A) is None
    assert await manager.get_connection(connection_b.connection_id, scope=SCOPE_B) is connection_b


@pytest.mark.asyncio
async def test_embed_event_uses_stable_session_launcher(monkeypatch):
    manager = WebSocketConnectionManager()
    session_id = '31c0f2e9-b115-4ee6-8f15-3e624d6456b1'
    connection = await manager.add_connection(
        websocket=Mock(),
        scope=SCOPE_A,
        pipeline_uuid='pipeline-1',
        session_type='person',
        session_id=session_id,
    )
    monkeypatch.setattr(websocket_adapter_module, 'ws_connection_manager', manager)

    adapter = WebSocketAdapter.model_construct(ap=Mock(), logger=_adapter_logger())
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
async def test_pipeline_override_survives_detached_listener_task(monkeypatch):
    manager = WebSocketConnectionManager()
    connection = await manager.add_connection(
        websocket=Mock(),
        scope=SCOPE_A,
        pipeline_uuid='pipeline-1',
        session_type='person',
    )
    monkeypatch.setattr(websocket_adapter_module, 'ws_connection_manager', manager)

    class DetachedTaskManager:
        def __init__(self):
            self.tasks = []

        def create_task(self, coro, **_kwargs):
            task = asyncio.create_task(coro, context=contextvars.Context())
            self.tasks.append(task)
            return Mock(task=task)

    task_manager = DetachedTaskManager()
    adapter = WebSocketAdapter.model_construct(
        ap=Mock(task_mgr=task_manager),
        logger=_adapter_logger(),
    )
    adapter.websocket_person_session = WebSocketSession(id='person')
    adapter.websocket_group_session = WebSocketSession(id='group')
    pipeline_overrides = []

    async def listener(_event, callback_adapter):
        pipeline_overrides.append(callback_adapter.get_pipeline_uuid_override())

    adapter.listeners = {platform_events.FriendMessage: listener}
    await adapter.handle_websocket_message(
        connection,
        {'message': [{'type': 'Plain', 'text': 'hello'}], 'stream': False},
    )
    await asyncio.gather(*task_manager.tasks)

    assert pipeline_overrides == ['pipeline-1']


@pytest.mark.asyncio
async def test_stream_choice_is_scoped_to_each_message_listener(monkeypatch):
    manager = WebSocketConnectionManager()
    visitor = await manager.add_connection(
        websocket=Mock(),
        scope=SCOPE_A,
        pipeline_uuid='pipeline-1',
        session_type='person',
        session_id='31c0f2e9-b115-4ee6-8f15-3e624d6456b1',
    )
    dashboard = await manager.add_connection(
        websocket=Mock(),
        scope=SCOPE_A,
        pipeline_uuid='pipeline-1',
        session_type='person',
    )
    monkeypatch.setattr(websocket_adapter_module, 'ws_connection_manager', manager)

    adapter = WebSocketAdapter.model_construct(ap=Mock(), logger=_adapter_logger(), stream_enabled=True)
    adapter.websocket_person_session = WebSocketSession(id='person')
    adapter.websocket_group_session = WebSocketSession(id='group')
    visitor_listening = asyncio.Event()
    dashboard_sent = asyncio.Event()
    observed = {}

    async def listener(event, callback_adapter):
        if event.sender.id.startswith('websocket_pipeline-1:'):
            visitor_listening.set()
            # Another browser's message arrives while this one is still queued.
            await dashboard_sent.wait()
            observed['visitor'] = await callback_adapter.is_stream_output_supported()
        else:
            observed['dashboard'] = await callback_adapter.is_stream_output_supported()

    adapter.listeners = {platform_events.FriendMessage: listener}
    await adapter.handle_websocket_message(visitor, {'message': [{'type': 'Plain', 'text': 'hi'}], 'stream': True})
    await visitor_listening.wait()
    await adapter.handle_websocket_message(dashboard, {'message': [{'type': 'Plain', 'text': 'hi'}], 'stream': False})
    dashboard_sent.set()
    await asyncio.gather(*adapter.inbound_listener_tasks)

    assert observed == {'visitor': True, 'dashboard': False}
    # Outside a message listener the shared adapter keeps its default.
    assert await adapter.is_stream_output_supported() is True


@pytest.mark.asyncio
async def test_embed_group_event_uses_stable_session_launcher(monkeypatch):
    manager = WebSocketConnectionManager()
    session_id = '31c0f2e9-b115-4ee6-8f15-3e624d6456b1'
    connection = await manager.add_connection(
        websocket=Mock(),
        scope=SCOPE_A,
        pipeline_uuid='pipeline-1',
        session_type='group',
        session_id=session_id,
    )
    monkeypatch.setattr(websocket_adapter_module, 'ws_connection_manager', manager)

    adapter = WebSocketAdapter.model_construct(ap=Mock(), logger=_adapter_logger())
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
        scope=SCOPE_A,
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
        scope=SCOPE_A,
        pipeline_uuid='pipeline-2',
        session_type='person',
        session_id=session_id,
    )
    connection = await manager.add_connection(
        websocket=Mock(),
        scope=SCOPE_A,
        pipeline_uuid='pipeline-1',
        session_type='person',
        session_id=session_id,
    )
    monkeypatch.setattr(websocket_adapter_module, 'ws_connection_manager', manager)

    adapter = WebSocketAdapter.model_construct(ap=Mock(), logger=_adapter_logger())
    message_source = Mock()
    message_source.sender.id = f'websocket_pipeline-1:{session_id}'

    assert await adapter._get_message_context(message_source) == ('pipeline-1', session_id)
    assert await adapter._get_connection_from_target(f'websocketgroup_pipeline-1:{session_id}') is connection
    assert (
        await manager.get_connection_by_session_id(
            session_id,
            scope=SCOPE_A,
            pipeline_uuid='pipeline-1',
        )
        is connection
    )

    await manager.remove_connection(connection.connection_id)

    assert await adapter._get_message_context(message_source) == ('pipeline-1', session_id)
    assert (
        await manager.get_connection_by_session_id(
            session_id,
            scope=SCOPE_A,
            pipeline_uuid='pipeline-1',
        )
        is None
    )


@pytest.mark.asyncio
async def test_dashboard_reply_survives_connection_replacement(monkeypatch):
    manager = WebSocketConnectionManager()
    original = await manager.add_connection(
        websocket=Mock(),
        scope=SCOPE_A,
        pipeline_uuid='pipeline-1',
        session_type='person',
    )
    monkeypatch.setattr(websocket_adapter_module, 'ws_connection_manager', manager)

    adapter = WebSocketAdapter.model_construct(ap=Mock(), logger=_adapter_logger())
    adapter.websocket_person_session = WebSocketSession(id='person')
    adapter.websocket_group_session = WebSocketSession(id='group')
    received = []

    async def listener(event, _callback_adapter):
        received.append(event)

    adapter.listeners = {platform_events.FriendMessage: listener}
    await adapter.handle_websocket_message(
        original,
        {'message': [{'type': 'Plain', 'text': 'hello'}], 'stream': False},
    )
    await asyncio.sleep(0)
    await manager.remove_connection(original.connection_id)
    replacement = await manager.add_connection(
        websocket=Mock(),
        scope=SCOPE_A,
        pipeline_uuid='pipeline-1',
        session_type='person',
    )

    await adapter.reply_message(
        received[0],
        platform_message.MessageChain([platform_message.Plain(text='done')]),
    )

    response = await replacement.send_queue.get()
    assert response['type'] == 'response'
    assert response['data']['content'] == 'done'


@pytest.mark.asyncio
async def test_late_final_events_update_one_stream_message(monkeypatch):
    manager = WebSocketConnectionManager()
    connection = await manager.add_connection(
        websocket=Mock(),
        scope=SCOPE_A,
        pipeline_uuid='pipeline-1',
        session_type='person',
    )
    monkeypatch.setattr(websocket_adapter_module, 'ws_connection_manager', manager)

    adapter = WebSocketAdapter.model_construct(ap=Mock(), logger=_adapter_logger())
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


@pytest.mark.asyncio
async def test_replies_keep_the_monitoring_record_of_their_message_server_side(monkeypatch):
    manager = WebSocketConnectionManager()
    session_id = '31c0f2e9-b115-4ee6-8f15-3e624d6456b1'
    connection = await manager.add_connection(
        websocket=Mock(),
        scope=SCOPE_A,
        pipeline_uuid='pipeline-1',
        session_type='person',
        session_id=session_id,
    )
    monkeypatch.setattr(websocket_adapter_module, 'ws_connection_manager', manager)
    monkeypatch.setattr(websocket_adapter_module, '_MAX_MONITORING_MESSAGE_IDS', 2)

    adapter = WebSocketAdapter.model_construct(ap=Mock(), logger=_adapter_logger())
    adapter.websocket_person_session = WebSocketSession(id='person')
    adapter.websocket_group_session = WebSocketSession(id='group')

    def inbound(source_id):
        return platform_events.FriendMessage(
            sender=platform_entities.Friend(id=f'websocket_pipeline-1:{session_id}', nickname='User', remark='User'),
            message_chain=platform_message.MessageChain(
                [platform_message.Source(id=source_id, time=1), platform_message.Plain(text='hi')]
            ),
            time=1,
        )

    for index in range(3):
        await adapter.on_monitoring_message_created(Mock(message_event=inbound(f'src-{index}')), f'record-{index}')
    # Only the newest entries are kept.
    assert adapter.monitoring_message_ids == {'src-1': 'record-1', 'src-2': 'record-2'}

    reply = platform_message.MessageChain([platform_message.Plain(text='answer')])
    sent = await adapter.reply_message(inbound('src-2'), reply)
    unknown = await adapter.reply_message(inbound('src-0'), reply)

    assert 'monitoring_message_id' not in sent
    assert 'monitoring_message_id' not in (await connection.send_queue.get())['data']
    assert adapter.get_monitoring_message_id('pipeline-1', 'person', session_id, str(sent['id'])) == 'record-2'
    assert adapter.get_monitoring_message_id('pipeline-1', 'person', session_id, str(unknown['id'])) is None
    assert adapter.get_monitoring_message_id('pipeline-1', 'person', 'other-session', str(sent['id'])) is None
    assert all(
        'monitoring_message_id' not in message
        for message in adapter.get_websocket_messages('pipeline-1', 'person', session_id)
    )


def test_session_ids_must_be_canonical_random_uuids():
    assert is_valid_session_id('31c0f2e9-b115-4ee6-8f15-3e624d6456b1')
    assert not is_valid_session_id('session-a')
    assert not is_valid_session_id('00000000-0000-0000-0000-000000000000')


def test_history_read_does_not_allocate_unknown_session():
    adapter = WebSocketAdapter.model_construct(ap=Mock(), logger=_adapter_logger())
    adapter.websocket_person_session = WebSocketSession(id='person')
    adapter.websocket_group_session = WebSocketSession(id='group')

    assert adapter.get_websocket_messages('pipeline-1', 'person', 'missing-session') == []
    assert adapter.websocket_person_session.message_lists == {}


@pytest.mark.asyncio
async def test_attachment_key_must_belong_to_connection_upload_scope():
    manager = WebSocketConnectionManager()
    connection = await manager.add_connection(
        websocket=Mock(),
        scope=SCOPE_A,
        pipeline_uuid='pipeline-1',
        session_type='person',
    )
    storage_mgr = Mock()
    storage_mgr.scoped_prefix.return_value = 'v1/current/upload_image/'
    storage_mgr.is_scoped_object_key.return_value = True
    storage_mgr.load_scoped_object_key = AsyncMock(return_value=b'image')
    storage_mgr.delete_scoped_object_key = AsyncMock()
    adapter = WebSocketAdapter.model_construct(
        ap=Mock(storage_mgr=storage_mgr),
        logger=_adapter_logger(),
    )
    message_chain = [{'type': 'Image', 'path': 'v1/current/upload_image/key.png'}]

    await adapter._process_image_components(connection, message_chain)

    assert message_chain[0]['base64'].startswith('data:image/png;base64,')
    assert message_chain[0]['path'] == 'v1/current/upload_image/key.png'
    storage_mgr.scoped_prefix.assert_called_once_with(
        connection.execution_context,
        owner_type='upload_image',
    )
    storage_mgr.is_scoped_object_key.assert_called_once_with(
        'v1/current/upload_image/key.png',
        expected_owner_type='upload_image',
    )
    storage_mgr.load_scoped_object_key.assert_awaited_once_with(
        connection.execution_context,
        'v1/current/upload_image/key.png',
        expected_owner_type='upload_image',
    )
    storage_mgr.delete_scoped_object_key.assert_not_awaited()

    with pytest.raises(ValueError, match='does not belong'):
        await adapter._process_image_components(
            connection,
            [{'type': 'File', 'path': 'v1/other/upload/key.txt'}],
        )


def test_history_and_reset_are_scoped_to_browser_session():
    matching_provider_session = Mock(
        instance_uuid=SCOPE_A.instance_uuid,
        workspace_uuid=SCOPE_A.workspace_uuid,
        placement_generation=SCOPE_A.placement_generation,
        launcher_type=Mock(value='person'),
        launcher_id='websocket_pipeline-1:session-a',
    )
    matching_group_provider_session = Mock(
        instance_uuid=SCOPE_A.instance_uuid,
        workspace_uuid=SCOPE_A.workspace_uuid,
        placement_generation=SCOPE_A.placement_generation,
        launcher_type=Mock(value='group'),
        launcher_id='websocketgroup_pipeline-1:session-a',
    )
    other_session = Mock(
        instance_uuid=SCOPE_A.instance_uuid,
        workspace_uuid=SCOPE_A.workspace_uuid,
        placement_generation=SCOPE_A.placement_generation,
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
        logger=_adapter_logger(),
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
    assert widget.count('encodeURIComponent(state.sessionId)') >= 2
    assert 'endpoint.searchParams.set("session_id", state.sessionId)' in widget
    # Feedback votes are scoped to the visitor's conversation.
    assert 'session_id: state.sessionId,' in widget
    assert 'loadHistory(true)' in widget
    assert 'messageVersion !== state.messageVersion' in widget
    assert 'scheduleHistoryReload();' in widget
