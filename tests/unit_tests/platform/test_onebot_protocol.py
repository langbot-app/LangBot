"""Wire-level conformance tests against an independent OneBot v11 peer."""

import asyncio
from contextlib import asynccontextmanager

import pytest
from quart import Quart
from websockets.asyncio.server import serve
from aiocqhttp.exceptions import ActionFailed
from langbot_plugin.api.entities.builtin.platform import events, message

from langbot.pkg.api.http.controller.groups.webhooks import WebhookRouterGroup
from tests.unit_tests.platform.onebot_mock import OneBotMock
from tests.unit_tests.platform.test_aiocqhttp_eba_adapter import make_adapter
from tests.unit_tests.platform.test_onebot_transport import bind


@asynccontextmanager
async def session(mode):
    adapter, peer = make_adapter(), OneBotMock()
    _, ap = bind(adapter)
    tasks = []
    try:
        if mode == 'forward_ws':

            async def endpoint(ws):
                assert ws.request.headers['Authorization'] == 'Bearer secret'
                task = asyncio.create_task(peer.run(ws.send, ws.recv))
                tasks.append(task)
                await asyncio.gather(task, return_exceptions=True)

            async with serve(endpoint, '127.0.0.1', 0) as server:
                adapter.config.update(
                    connection_mode=mode, ws_url=f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}'
                )
                tasks.append(asyncio.create_task(adapter.run_async()))
                await asyncio.wait_for(peer.ready.wait(), 3)
                # Establish account metadata and synchronize through a real API.
                await peer.emit({'post_type': 'meta_event', 'meta_event_type': 'lifecycle', 'sub_type': 'connect'})
                for _ in range(300):
                    if adapter.bot.connection:
                        break
                    await asyncio.sleep(0.01)
                yield adapter, peer
                await adapter.kill()
        else:
            app = Quart(__name__)
            await WebhookRouterGroup(ap, app).initialize()
            headers = {'Authorization': 'Bearer secret', 'X-Self-ID': '42', 'X-Client-Role': 'Universal'}
            async with app.test_client().websocket('/bots/bot-a/onebot/v11/ws', headers=headers) as ws:
                tasks.append(asyncio.create_task(peer.run(ws.send, ws.receive)))
                await asyncio.wait_for(peer.ready.wait(), 3)
                for _ in range(300):
                    if adapter.bot.connection:
                        break
                    await asyncio.sleep(0.01)
                yield adapter, peer
    finally:
        await adapter.kill()
        for task in tasks:
            task.cancel()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, AssertionError):
                raise result


@pytest.fixture(params=['forward_ws', 'reverse_ws'])
async def wire(request):
    async with session(request.param) as connected:
        async with asyncio.timeout(15):
            yield connected


@pytest.mark.parametrize(
    'kind,subtype',
    [
        ('private', 'friend'),
        ('private', 'group'),
        ('private', 'other'),
        ('group', 'normal'),
        ('group', 'anonymous'),
        ('group', 'notice'),
    ],
)
@pytest.mark.parametrize('encoding', ['array', 'cq'])
async def test_messages_and_quoted_reply(wire, kind, subtype, encoding):
    adapter, peer = wire
    received = asyncio.Queue()

    async def callback(event, source):
        await source.reply_message(event, message.MessageChain([message.Plain(text='reply')]), quote_origin=True)
        await received.put(event)

    adapter.register_listener(events.MessageReceivedEvent, callback)
    body = (
        'hi &amp; &#91;x&#93;[CQ:at,qq=42]'
        if encoding == 'cq'
        else [
            {'type': 'text', 'data': {'text': 'hi & [x]'}},
            {'type': 'at', 'data': {'qq': '42'}},
        ]
    )
    await peer.emit(peer.message(kind, subtype, body))
    event = await asyncio.wait_for(received.get(), 3)
    assert str(event.chat_id) == ('20001' if kind == 'group' else '10001')
    assert event.message_chain.get_first(message.Plain).text == 'hi & [x]'
    assert str(event.message_chain.get_first(message.At).target) == '42'
    request = peer.requests[-1]
    assert request['action'] == 'send_msg'
    assert request['params']['message_type'] == kind
    assert request['params']['message'][0] == {'type': 'reply', 'data': {'id': '9'}}


NOTICES = [
    ({'notice_type': 'group_upload', 'file': {'id': 'f', 'name': 'a.txt', 'size': 1, 'busid': 0}}, 'platform.specific'),
    ({'notice_type': 'group_admin', 'sub_type': 'set'}, 'platform.specific'),
    ({'notice_type': 'group_admin', 'sub_type': 'unset'}, 'platform.specific'),
    ({'notice_type': 'group_increase', 'sub_type': 'approve'}, 'group.member_joined'),
    ({'notice_type': 'group_increase', 'sub_type': 'invite'}, 'group.member_joined'),
    ({'notice_type': 'group_increase', 'sub_type': 'invite', 'user_id': 42}, 'bot.invited_to_group'),
    ({'notice_type': 'group_decrease', 'sub_type': 'leave'}, 'group.member_left'),
    ({'notice_type': 'group_decrease', 'sub_type': 'kick'}, 'group.member_left'),
    ({'notice_type': 'group_decrease', 'sub_type': 'kick_me', 'user_id': 42}, 'bot.removed_from_group'),
    ({'notice_type': 'group_ban', 'sub_type': 'ban', 'duration': 60}, 'group.member_banned'),
    ({'notice_type': 'group_ban', 'sub_type': 'lift_ban', 'duration': 0}, 'platform.specific'),
    ({'notice_type': 'group_ban', 'sub_type': 'ban', 'duration': 60, 'user_id': 42}, 'bot.muted'),
    ({'notice_type': 'group_ban', 'sub_type': 'lift_ban', 'duration': 0, 'user_id': 42}, 'bot.unmuted'),
    ({'notice_type': 'friend_add'}, 'friend.added'),
    ({'notice_type': 'group_recall', 'message_id': 9}, 'message.deleted'),
    ({'notice_type': 'friend_recall', 'message_id': 9}, 'message.deleted'),
    ({'notice_type': 'notify', 'sub_type': 'poke', 'target_id': 42}, 'platform.specific'),
    ({'notice_type': 'notify', 'sub_type': 'lucky_king', 'target_id': 42}, 'platform.specific'),
    ({'notice_type': 'notify', 'sub_type': 'honor', 'honor_type': 'talkative'}, 'platform.specific'),
]


@pytest.mark.parametrize('payload,expected', NOTICES)
async def test_notices(wire, payload, expected):
    adapter, peer = wire
    received = asyncio.Queue()

    async def callback(event, source):
        await received.put(event)

    adapter.register_listener(events.EBAEvent, callback)
    base = {'post_type': 'notice', 'user_id': 10001}
    if payload['notice_type'].startswith('group_') or payload['notice_type'] == 'notify':
        base.update(group_id=20001, operator_id=10002)
    await peer.emit(base | payload)
    event = await asyncio.wait_for(received.get(), 3)
    assert event.type == expected
    assert event.timestamp == 1700000000
    if payload['notice_type'] == 'friend_recall':
        assert str(event.operator.id) == '10001'
        assert str(event.chat_id) == '10001'
    if expected == 'platform.specific':
        assert event.data['notice_type'] == payload['notice_type']


@pytest.mark.parametrize(
    'kind,subtype,expected',
    [
        ('friend', None, 'friend.request_received'),
        ('group', 'invite', 'bot.invited_to_group'),
        ('group', 'add', 'platform.specific'),
    ],
)
async def test_requests(wire, kind, subtype, expected):
    adapter, peer = wire
    received = asyncio.Queue()

    async def callback(event, source):
        if kind == 'friend':
            await source.approve_friend_request(event.request_id, False, 'no')
        elif subtype == 'invite':
            await source.approve_group_invite(event.request_id, False)
        await received.put(event)

    adapter.register_listener(events.EBAEvent, callback)
    payload = {
        'post_type': 'request',
        'request_type': kind,
        'user_id': 10001,
        'comment': 'please',
        'flag': 'opaque-flag',
    }
    if subtype:
        payload.update(sub_type=subtype, group_id=20001)
    await peer.emit(payload)
    event = await asyncio.wait_for(received.get(), 3)
    assert event.type == expected
    if expected != 'platform.specific':
        assert peer.requests[-1]['params']['flag'] == 'opaque-flag'
        assert peer.requests[-1]['params']['approve'] is False


async def test_api_surface(wire):
    adapter, peer = wire
    chain = message.MessageChain([message.Plain(text='test')])
    for target in ('person', 'private', 'group'):
        assert str((await adapter.send_message(target, '10001', chain)).message_id) == '123'
    await adapter.delete_message('person', 10001, 9)
    assert str((await adapter.get_message('person', 10001, 9)).message_id) == '9'
    for target in ('person', 'private', 'group'):
        assert str((await adapter.forward_message('person', 10001, 9, target, 10001)).message_id) == '123'
    assert (await adapter.get_group_info('20001')).name == 'Mock group'
    assert len(await adapter.get_group_list()) == 1
    assert len(await adapter.get_group_member_list('20001')) == 1
    assert (await adapter.get_group_member_info('20001', '10001')).display_name == 'Card'
    assert (await adapter.get_user_info('10001')).nickname == 'Alice'
    assert len(await adapter.get_friend_list()) == 1
    await adapter.set_group_name('20001', 'new')
    await adapter.mute_member('20001', '10001', 60)
    assert peer.requests[-1]['params']['duration'] == 60
    await adapter.unmute_member('20001', '10001')
    assert peer.requests[-1]['params']['duration'] == 0
    await adapter.kick_member('20001', '10001')
    await adapter.leave_group('20001')
    await adapter.approve_friend_request('flag', True, 'remark')
    await adapter.approve_group_invite('flag')
    for action, params in [
        ('get_login_info', {}),
        ('get_status', {}),
        ('get_version_info', {}),
        ('get_group_honor_info', {'group_id': 20001, 'type': 'all'}),
        ('set_group_card', {'group_id': 20001, 'user_id': 10001, 'card': 'card'}),
        ('set_group_special_title', {'group_id': 20001, 'user_id': 10001, 'special_title': 't'}),
        ('set_group_admin', {'group_id': 20001, 'user_id': 10001, 'enable': True}),
        ('set_group_whole_ban', {'group_id': 20001, 'enable': True}),
        ('get_forward_msg', {'id': 'f'}),
        ('get_record', {'file': 'f', 'out_format': 'mp3'}),
        ('get_image', {'file': 'f'}),
        ('can_send_image', {}),
        ('can_send_record', {}),
    ]:
        result = await adapter.call_platform_api(action, params)
        assert isinstance(result, dict)
        assert peer.requests[-1]['action'] == action
        assert peer.requests[-1]['params'] == params


async def test_metadata_self_messages_and_recovery(wire):
    adapter, peer = wire
    received = asyncio.Queue()

    async def callback(event, source):
        await received.put(event)

    adapter.register_listener(events.EBAEvent, callback)
    for subtype in ('connect', 'enable', 'disable'):
        await peer.emit({'post_type': 'meta_event', 'meta_event_type': 'lifecycle', 'sub_type': subtype})
    await peer.emit(
        {
            'post_type': 'meta_event',
            'meta_event_type': 'heartbeat',
            'status': {'online': True, 'good': True},
            'interval': 5000,
        }
    )
    await peer.emit(peer.message('private', 'friend') | {'user_id': 42})
    # An invalid business event must not tear down the transport or block later events.
    await peer.emit(peer.message('private', 'friend', [{'type': 'face', 'data': {'id': 'invalid'}}]))
    await peer.emit(peer.message('private', 'friend'))
    event = await asyncio.wait_for(received.get(), 3)
    assert event.type == 'message.received'
    assert received.empty()
    assert adapter.bot_account_id == '42'
    results = await asyncio.gather(*(adapter.bot.get_login_info() for _ in range(32)))
    assert all(item['user_id'] == 42 for item in results)
    assert len({item['echo'] for item in peer.requests}) == len(peer.requests)
    assert not adapter.bot.connection.pending


@pytest.mark.parametrize(
    'status,code,valid',
    [
        ('ok', 0, True),
        ('async', 1, True),
        ('failed', 100, False),
        ('failed', 1400, False),
        ('failed', 1404, False),
        ('ok', 1, False),
        ('async', 0, False),
    ],
)
async def test_response_contract(wire, status, code, valid):
    adapter, peer = wire
    peer.response = {'status': status, 'retcode': code, 'data': None}
    if valid:
        assert await adapter.bot.call_action('delete_msg', message_id=9) is None
    else:
        with pytest.raises(ActionFailed):
            await adapter.bot.call_action('delete_msg', message_id=9)
