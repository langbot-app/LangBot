import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from quart import Quart
import quart_cors
from quart.testing.connections import WebsocketResponseError
from aiocqhttp.exceptions import ActionFailed, ApiNotAvailable
from websockets.asyncio.server import serve

from langbot.pkg.platform.adapters.aiocqhttp.transport import OneBotConnection
from langbot.pkg.api.http.controller.groups.webhooks import WebhookRouterGroup
from tests.unit_tests.platform.test_aiocqhttp_eba_adapter import make_adapter


def bind(adapter):
    runtime = SimpleNamespace(
        adapter=adapter, enable=True, workspace_uuid='workspace-a', bot_entity=SimpleNamespace(uuid='bot-a')
    )
    ap = SimpleNamespace(platform_mgr=SimpleNamespace(resolve_public_bot=AsyncMock(return_value=runtime)))
    runtime.ap = ap
    adapter.bind_runtime(runtime)
    adapter.config['access-token'] = 'secret'
    return runtime, ap


async def test_echo_out_of_order_and_event_api_does_not_deadlock():
    incoming, outgoing = asyncio.Queue(), asyncio.Queue()
    handled = asyncio.Event()

    async def event(data):
        assert await connection.call_action('get_group_info', group_id=1) == {'name': 'group'}
        handled.set()

    connection = OneBotConnection(outgoing.put, incoming.get, AsyncMock(), event, AsyncMock())
    task = asyncio.create_task(connection.run())
    first = asyncio.create_task(connection.call_action('first'))
    second = asyncio.create_task(connection.call_action('second'))
    a, b = json.loads(await outgoing.get()), json.loads(await outgoing.get())
    for request in (b, a):
        await incoming.put(
            json.dumps({'echo': request['echo'], 'status': 'ok', 'retcode': 0, 'data': request['action']})
        )
    assert await first == 'first'
    assert await second == 'second'
    await incoming.put(json.dumps({'post_type': 'message', 'self_id': 42}))
    request = json.loads(await outgoing.get())
    await incoming.put(json.dumps({'echo': request['echo'], 'status': 'ok', 'retcode': 0, 'data': {'name': 'group'}}))
    await asyncio.wait_for(handled.wait(), 1)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert not connection.pending


async def test_timeout_disconnect_and_failure():
    outgoing = asyncio.Queue()
    connection = OneBotConnection(outgoing.put, AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock(), timeout=0.01)
    with pytest.raises(TimeoutError):
        await connection.call_action('timeout')
    assert not connection.pending
    await outgoing.get()
    connection.timeout = 2
    action = asyncio.create_task(connection.call_action('failure'))
    request = json.loads(await outgoing.get())
    connection.pending[request['echo']].set_result({'status': 'failed', 'retcode': 100})
    with pytest.raises(ActionFailed):
        await action
    action = asyncio.create_task(connection.call_action('disconnect'))
    await outgoing.get()
    await connection.close()
    with pytest.raises(ApiNotAvailable):
        await action


@pytest.mark.parametrize('payload', ['[]', 'broken', '{"post_type":"message","self_id":99}'])
async def test_invalid_frames_and_account_mismatch(payload):
    incoming = asyncio.Queue()
    await incoming.put(payload)
    connection = OneBotConnection(AsyncMock(), incoming.get, AsyncMock(), AsyncMock(), AsyncMock(), self_id='42')
    with pytest.raises(ValueError):
        await connection.run()
    assert connection.closed


async def test_main_port_reverse_ws_auth_and_placement():
    adapter = make_adapter()
    runtime, ap = bind(adapter)
    app = Quart(__name__)
    quart_cors.cors(app, allow_origin='*')
    await WebhookRouterGroup(ap, app).initialize()
    client = app.test_client()
    headers = {'Authorization': 'Bearer secret', 'X-Self-ID': '42', 'X-Client-Role': 'Universal'}
    for changes, status in [({'Authorization': 'Bearer wrong'}, 401), ({'X-Client-Role': 'Event'}, 400)]:
        with pytest.raises(WebsocketResponseError) as error:
            async with client.websocket('/bots/bot-a/onebot/v11/ws', headers=headers | changes):
                await asyncio.sleep(0.01)
        assert error.value.response.status_code == status
    async with client.websocket('/bots/bot-a/onebot/v11/ws', headers=headers | {'X-Workspace-Id': 'attacker'}) as ws:
        await ws.send(json.dumps({'post_type': 'meta_event', 'meta_event_type': 'heartbeat', 'self_id': 42}))
        for _ in range(100):
            if adapter.bot.connection:
                break
            await asyncio.sleep(0.001)
        action = asyncio.create_task(adapter.bot.get_login_info())
        request = json.loads(await ws.receive())
        await ws.send(json.dumps({'echo': request['echo'], 'status': 'ok', 'retcode': 0, 'data': {'user_id': 42}}))
        assert await asyncio.wait_for(action, 1) == {'user_id': 42}
        ap.platform_mgr.resolve_public_bot.return_value = None
        with pytest.raises(RuntimeError, match='placement'):
            await adapter.bot.get_login_info()
    assert runtime.workspace_uuid == 'workspace-a'
    await adapter.kill()


async def test_forward_ws_round_trip_and_shutdown():
    connected = asyncio.Event()

    async def endpoint(socket):
        assert socket.request.headers['Authorization'] == 'Bearer secret'
        await socket.send(json.dumps({'post_type': 'meta_event', 'meta_event_type': 'heartbeat', 'self_id': 42}))
        connected.set()
        async for raw in socket:
            request = json.loads(raw)
            await socket.send(
                json.dumps({'echo': request['echo'], 'status': 'ok', 'retcode': 0, 'data': {'message_id': 7}})
            )

    async with serve(endpoint, '127.0.0.1', 0) as server:
        adapter = make_adapter()
        bind(adapter)
        adapter.config.update(
            connection_mode='forward_ws', ws_url=f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}'
        )
        task = asyncio.create_task(adapter.run_async())
        await asyncio.wait_for(connected.wait(), 2)
        for _ in range(100):
            if adapter.bot.connection:
                break
            await asyncio.sleep(0.001)
        assert await adapter.bot.send_private_msg(user_id=1, message='hello') == {'message_id': 7}
        await adapter.kill()
        await asyncio.gather(task, return_exceptions=True)
        assert adapter.bot.connection is None


async def test_idle_placement_revocation_closes_connection():
    adapter = make_adapter()
    _, ap = bind(adapter)
    closed = asyncio.Event()

    async def close():
        closed.set()

    incoming = asyncio.Queue()
    task = asyncio.create_task(adapter.serve_connection(AsyncMock(), incoming.get, close, '42'))
    for _ in range(100):
        if adapter.bot.connection:
            break
        await asyncio.sleep(0.001)
    with pytest.raises(RuntimeError, match='active connection'):
        await adapter.serve_connection(AsyncMock(), incoming.get, close, '42')
    ap.platform_mgr.resolve_public_bot.return_value = None
    await asyncio.wait_for(closed.wait(), 7)
    with pytest.raises(RuntimeError, match='placement'):
        await task
    assert adapter.bot.connection is None


async def test_forward_reconnects_after_endpoint_disconnect():
    count = 0
    reconnected = asyncio.Event()

    async def endpoint(socket):
        nonlocal count
        count += 1
        if count == 1:
            await socket.close()
        else:
            reconnected.set()
            await socket.wait_closed()

    async with serve(endpoint, '127.0.0.1', 0) as server:
        adapter = make_adapter()
        bind(adapter)
        adapter.config.update(
            connection_mode='forward_ws', ws_url=f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}'
        )
        task = asyncio.create_task(adapter.run_async())
        await asyncio.wait_for(reconnected.wait(), 4)
        await adapter.kill()
        await asyncio.gather(task, return_exceptions=True)
        assert count == 2


def test_legacy_manifest_keeps_independent_adapter():
    from langbot.pkg.discover.engine import ComponentDiscoveryEngine
    from langbot.pkg.platform.adapters.aiocqhttp.adapter import AiocqhttpAdapter as NewAdapter
    from langbot.pkg.platform.sources.aiocqhttp import AiocqhttpAdapter as LegacyAdapter

    engine = ComponentDiscoveryEngine(SimpleNamespace())
    legacy = engine.load_component_manifest('pkg/platform/sources/aiocqhttp.yaml')
    modern = engine.load_component_manifest('pkg/platform/adapters/aiocqhttp/manifest.yaml')
    assert legacy.get_python_component_class() is LegacyAdapter
    assert modern.get_python_component_class() is NewAdapter
    assert modern.metadata.name == 'onebot-v11'
    assert LegacyAdapter is not NewAdapter
    fields = {item['name']: item for item in legacy.spec['config']}
    assert fields['port']['default'] == 2280
    assert fields['access-token']['required'] is False
    assert 'connection_mode' not in fields


def test_configuration_rejects_invalid_credentials_and_url():
    from langbot.pkg.platform.adapters.aiocqhttp.adapter import AiocqhttpAdapter
    from tests.unit_tests.platform.test_aiocqhttp_eba_adapter import DummyLogger

    with pytest.raises(ValueError, match='token'):
        AiocqhttpAdapter({}, DummyLogger())
    for url in ('https://example.com', 'ws://user:password@example.com', ''):
        with pytest.raises(ValueError, match='ws_url'):
            AiocqhttpAdapter({'access-token': 'secret', 'connection_mode': 'forward_ws', 'ws_url': url}, DummyLogger())


@pytest.mark.parametrize('mode', ['reverse_ws', 'forward_ws', 'legacy'])
async def test_message_event_to_reply_roundtrip(mode):
    """Exercise real converters and callbacks against a simulated protocol peer."""
    from langbot.pkg.platform.sources.aiocqhttp import AiocqhttpAdapter as LegacyAdapter
    from langbot_plugin.api.entities.builtin.platform import events, message
    from tests.unit_tests.platform.test_aiocqhttp_eba_adapter import DummyLogger

    adapter = LegacyAdapter({'access-token': 'secret'}, DummyLogger()) if mode == 'legacy' else make_adapter()
    finished = asyncio.Event()
    received = []

    async def callback(event, source):
        received.append(str(event.message_chain))
        await source.send_message('person', '10001', message.MessageChain([message.Plain(text='roundtrip reply')]))
        finished.set()

    adapter.register_listener(events.FriendMessage, callback)

    async def protocol_peer(send, receive):
        await send(
            json.dumps(
                {
                    'time': 1700000000,
                    'self_id': 42,
                    'post_type': 'message',
                    'message_type': 'private',
                    'sub_type': 'friend',
                    'message_id': 9,
                    'user_id': 10001,
                    'message': [{'type': 'text', 'data': {'text': 'roundtrip incoming'}}],
                    'raw_message': 'roundtrip incoming',
                    'font': 0,
                    'sender': {'user_id': 10001, 'nickname': 'Protocol test'},
                }
            )
        )
        while not finished.is_set():
            request = json.loads(await asyncio.wait_for(receive(), 3))
            action = request['action']
            if action == 'send_private_msg':
                assert str(request['params']['user_id']) == '10001'
                assert 'roundtrip reply' in json.dumps(request['params']['message'])
                data = {'message_id': 10}
            elif action == 'get_stranger_info':
                data = {'user_id': 10001, 'nickname': 'Protocol test'}
            else:
                raise AssertionError(f'Unexpected action: {action}')
            await send(json.dumps({'echo': request['echo'], 'status': 'ok', 'retcode': 0, 'data': data}))
            if action == 'send_private_msg':
                await asyncio.wait_for(finished.wait(), 3)

    if mode == 'forward_ws':
        bind(adapter)

        async def endpoint(ws):
            assert ws.request.headers['Authorization'] == 'Bearer secret'
            await protocol_peer(ws.send, ws.recv)

        async with serve(endpoint, '127.0.0.1', 0) as server:
            adapter.config.update(connection_mode=mode, ws_url=f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}')
            task = asyncio.create_task(adapter.run_async())
            try:
                await asyncio.wait_for(finished.wait(), 5)
            finally:
                await adapter.kill()
                await asyncio.gather(task, return_exceptions=True)
    else:
        if mode == 'legacy':
            app, path = adapter.bot._server_app, '/ws/'
        else:
            _, ap = bind(adapter)
            app, path = Quart(__name__), '/bots/bot-a/onebot/v11/ws'
            await WebhookRouterGroup(ap, app).initialize()
        headers = {'Authorization': 'Bearer secret', 'X-Self-ID': '42', 'X-Client-Role': 'Universal'}
        async with app.test_client().websocket(path, headers=headers) as ws:
            await protocol_peer(ws.send, ws.receive)
        await adapter.kill()
    assert received == ['roundtrip incoming']


@pytest.mark.parametrize(
    'name,path',
    [
        ('aiocqhttp', 'pkg/platform/sources/aiocqhttp.yaml'),
        ('onebot-v11', 'pkg/platform/adapters/aiocqhttp/manifest.yaml'),
        ('aiocqhttp-omni', 'pkg/platform/adapters/aiocqhttp/manifest.yaml'),
        ('aiocqhttp-eba', 'pkg/platform/adapters/aiocqhttp/manifest.yaml'),
    ],
)
async def test_public_url_only_available_for_new_onebot_adapter(name, path):
    from langbot.pkg.discover.engine import ComponentDiscoveryEngine
    from langbot.pkg.api.http.service.bot import BotService

    ap = SimpleNamespace(
        instance_config=SimpleNamespace(data={'api': {'webhook_prefix': 'https://bot.example.com'}}),
        platform_mgr=SimpleNamespace(get_bot_by_uuid=AsyncMock(return_value=None)),
    )
    ap.discover = ComponentDiscoveryEngine(ap)
    ap.discover.load_component_manifest(path)
    service = BotService(ap)
    service.get_bot = AsyncMock(return_value={'uuid': 'bot-a', 'adapter': name, 'adapter_config': {}})
    result = await service.get_runtime_bot_info('workspace-a', 'bot-a')
    expected = 'https://bot.example.com/bots/bot-a' if name != 'aiocqhttp' else None
    assert result['adapter_runtime_values']['webhook_full_url'] == expected
