"""Management MCP, WebSocket and debug execution boundaries."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import quart

from langbot.pkg.api.http.controller.groups.pipelines.websocket_chat import WebSocketChatRouterGroup
from langbot.pkg.api.http.controller.groups.pipelines.embed import EmbedRouterGroup
from langbot.pkg.api.mcp.server import LangBotMCPServer
from langbot.pkg.telemetry import diagnostics as d
from tests.unit_tests.api.test_diagnostics_management_http import Recorder


@pytest.mark.asyncio
async def test_mcp_real_registered_tool_has_source_and_never_content():
    recorder = Recorder()
    seen = []

    async def get_bot(*args, **kwargs):
        seen.append(d.current_span())
        return {'secret': 'private-result'}

    ap = SimpleNamespace(diagnostics=recorder, bot_service=SimpleNamespace(get_bot=get_bot))
    server = LangBotMCPServer(ap)
    with patch('langbot.pkg.api.mcp.server._authorized', return_value=object()):
        result = await server.mcp.call_tool('get_bot', {'bot_uuid': 'private-bot'})
    assert result
    assert [e['outcome'] for e in recorder.events] == ['started', 'succeeded']
    assert recorder.events[-1]['operation'] == 'mcp.get_bot'
    assert recorder.events[-1]['source'] == 'mcp'
    assert seen[0] is not None
    assert 'private-' not in json.dumps(recorder.events)
    assert d.current_span() is None


@pytest.mark.asyncio
async def test_mcp_tool_permission_rejection_is_observed():
    server = LangBotMCPServer(SimpleNamespace(diagnostics=Recorder()))
    with pytest.raises(Exception):
        await server.mcp.call_tool('list_bots', {})
    assert server.ap.diagnostics.events[-1]['outcome'] in {'rejected', 'failed'}
    assert server.ap.diagnostics.events[-1]['source'] == 'mcp'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'group_class,path',
    [
        (WebSocketChatRouterGroup, '/api/v1/pipelines/private-pipeline/ws/connect'),
        (EmbedRouterGroup, '/api/v1/embed/11111111-1111-4111-8111-111111111111/ws/connect?session_id=private-session'),
    ],
)
async def test_real_websocket_session_auth_rejection_is_content_free(group_class, path):
    app = quart.Quart(__name__)
    ap = SimpleNamespace(diagnostics=Recorder())
    group = group_class(ap, app)
    group._authenticate_websocket = AsyncMock(side_effect=ValueError('private-token'))
    if group_class is EmbedRouterGroup:
        group._resolve_bot = AsyncMock(return_value=(object(), 'private-pipeline'))
    await group.initialize()
    async with app.test_client().websocket(path) as socket:
        frame = json.loads(await socket.receive())
        assert frame['type'] == 'error'
    terminal = [e for e in ap.diagnostics.events if e['outcome'] != 'started']
    assert terminal
    assert terminal[-1]['outcome'] == 'rejected'
    assert terminal[-1]['source'] == 'websocket'
    assert 'private-' not in json.dumps(ap.diagnostics.events)


@pytest.mark.asyncio
@pytest.mark.parametrize('group_class', [WebSocketChatRouterGroup, EmbedRouterGroup])
async def test_websocket_received_message_boundaries_do_not_capture_frames(group_class):
    app = quart.Quart(__name__)
    ap = SimpleNamespace(diagnostics=Recorder())
    group = group_class(ap, app)
    connection = SimpleNamespace(is_active=True, connection_id='private-id', send_queue=asyncio.Queue())
    adapter = SimpleNamespace(handle_websocket_message=AsyncMock())
    if group_class is WebSocketChatRouterGroup:
        group._revalidate_websocket_authorization = AsyncMock(return_value=object())
        args = (connection, adapter, object(), 'private-token')
    else:
        group._resolve_connected_bot = AsyncMock(return_value=object())
        args = (connection, adapter, object(), 'private-pipeline')

    async def receive():
        connection.is_active = False
        return json.dumps({'type': 'message', 'text': 'private-prompt'})

    with (
        patch('quart.websocket', SimpleNamespace(receive=receive)),
        patch(
            'langbot.pkg.api.http.controller.groups.pipelines.websocket_chat.ws_connection_manager.update_activity',
            new=AsyncMock(),
        ),
    ):
        await group._handle_receive(*args)
    adapter.handle_websocket_message.assert_awaited_once()
    assert [e['outcome'] for e in ap.diagnostics.events] == ['started', 'succeeded']
    assert ap.diagnostics.events[-1]['operation'].endswith('.message')
    assert 'private-' not in json.dumps(ap.diagnostics.events)
    assert d.current_span() is None


@pytest.mark.asyncio
async def test_debug_service_marks_synthetic_source_before_validation():
    from langbot.pkg.api.http.service.agent import AgentService

    ap = SimpleNamespace(diagnostics=Recorder())
    service = AgentService(ap)
    seen = []

    async def get_agent(*args):
        seen.append(d.current_span())
        return None

    service.get_agent = get_agent
    with pytest.raises(ValueError):
        await service.debug_agent(object(), 'private-id', {'text': 'private-prompt'})
    assert seen[0].fields['source'] == 'webui_debug'
    assert ap.diagnostics.events[-1]['operation'] == 'http.agent.debug_agent'
    assert ap.diagnostics.events[-1]['source'] == 'webui_debug'
    assert 'private-' not in json.dumps(ap.diagnostics.events)


@pytest.mark.asyncio
@pytest.mark.parametrize('group_class', [WebSocketChatRouterGroup, EmbedRouterGroup])
@pytest.mark.parametrize(
    'frame,expected', [('private-invalid-json', 'rejected'), ('{"type":"private-unknown"}', 'skipped')]
)
async def test_websocket_invalid_frames_have_finite_outcomes(group_class, frame, expected):
    app = quart.Quart(__name__)
    ap = SimpleNamespace(diagnostics=Recorder())
    group = group_class(ap, app)
    connection = SimpleNamespace(is_active=True, connection_id='private-id', send_queue=asyncio.Queue())

    async def receive():
        connection.is_active = False
        return frame

    with (
        patch('quart.websocket', SimpleNamespace(receive=receive)),
        patch(
            'langbot.pkg.api.http.controller.groups.pipelines.websocket_chat.ws_connection_manager.update_activity',
            new=AsyncMock(),
        ),
    ):
        await group._handle_receive(connection, object(), object(), 'private-token')
    assert ap.diagnostics.events[-1]['outcome'] == expected
    assert 'private-' not in json.dumps(ap.diagnostics.events)


@pytest.mark.asyncio
@pytest.mark.parametrize('group_class', [WebSocketChatRouterGroup, EmbedRouterGroup])
async def test_websocket_send_boundary_preserves_payload_and_cancellation(group_class):
    app = quart.Quart(__name__)
    ap = SimpleNamespace(diagnostics=Recorder())
    group = group_class(ap, app)
    connection = SimpleNamespace(is_active=False, send_queue=asyncio.Queue())
    await connection.send_queue.put({'text': 'private-answer'})
    send = AsyncMock(side_effect=asyncio.CancelledError('private-error'))
    with patch('quart.websocket', SimpleNamespace(send=send)):
        with pytest.raises(asyncio.CancelledError):
            await group._handle_send(connection)
    assert json.loads(send.call_args.args[0]) == {'text': 'private-answer'}
    assert ap.diagnostics.events[-1]['outcome'] == 'cancelled'
    assert ap.diagnostics.events[-1]['operation'].endswith('.send')
    assert 'private-' not in json.dumps(ap.diagnostics.events)
    assert d.current_span() is None
