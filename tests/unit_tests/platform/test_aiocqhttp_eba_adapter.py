from __future__ import annotations

import pathlib
import datetime
from unittest.mock import AsyncMock

import aiocqhttp
import pytest
import yaml

from langbot.pkg.platform.adapters.aiocqhttp.adapter import AiocqhttpAdapter
from langbot.pkg.platform.adapters.aiocqhttp.event_converter import AiocqhttpEventConverter
from langbot.pkg.platform.adapters.aiocqhttp.message_converter import AiocqhttpMessageConverter
from langbot.pkg.platform.adapters.aiocqhttp.platform_api import PLATFORM_API_MAP
from langbot_plugin.api.definition.abstract.platform.event_logger import AbstractEventLogger
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.builtin.platform.errors import NotSupportedError


class DummyLogger(AbstractEventLogger):
    async def info(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def debug(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def warning(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def error(self, text, images=None, message_session_id=None, no_throw=True):
        pass


def make_adapter() -> AiocqhttpAdapter:
    return AiocqhttpAdapter({'host': '127.0.0.1', 'port': 2280, 'access-token': ''}, DummyLogger())


def manifest() -> dict:
    manifest_path = (
        pathlib.Path(__file__).parents[3]
        / 'src'
        / 'langbot'
        / 'pkg'
        / 'platform'
        / 'adapters'
        / 'aiocqhttp'
        / 'manifest.yaml'
    )
    return yaml.safe_load(manifest_path.read_text())


def onebot_event(payload: dict) -> aiocqhttp.Event:
    return aiocqhttp.Event.from_payload(payload)


def test_aiocqhttp_supported_events_match_manifest():
    assert make_adapter().get_supported_events() == manifest()['spec']['supported_events']


def test_aiocqhttp_supported_apis_match_manifest():
    supported_apis = make_adapter().get_supported_apis()
    manifest_apis = manifest()['spec']['supported_apis']

    assert supported_apis == manifest_apis['required'] + manifest_apis['optional']


def test_aiocqhttp_platform_api_map_matches_manifest():
    manifest_actions = {item['action'] for item in manifest()['spec']['platform_specific_apis']}

    assert set(PLATFORM_API_MAP) == manifest_actions


@pytest.mark.asyncio
async def test_aiocqhttp_adapter_dispatches_most_specific_eba_listener():
    adapter = make_adapter()
    calls: list[str] = []

    async def wildcard_listener(event, adapter):
        calls.append('event')

    async def eba_listener(event, adapter):
        calls.append('eba')

    async def message_listener(event, adapter):
        calls.append('message')

    adapter.register_listener(platform_events.Event, wildcard_listener)
    adapter.register_listener(platform_events.EBAEvent, eba_listener)
    adapter.register_listener(platform_events.MessageReceivedEvent, message_listener)

    event = platform_events.MessageReceivedEvent(
        message_id=1,
        message_chain=platform_message.MessageChain([platform_message.Plain(text='hello')]),
        sender={'id': 1},
        chat_id=1,
    )

    await adapter._dispatch_eba_event(event)

    assert calls == ['message']


@pytest.mark.asyncio
async def test_aiocqhttp_message_converter_maps_chain_to_onebot_segments():
    target, source_id, _ = await AiocqhttpMessageConverter.yiri2target(
        platform_message.MessageChain(
            [
                platform_message.Source(id=42, time=datetime.datetime.now()),
                platform_message.Plain(text='hi '),
                platform_message.At(target='10001'),
                platform_message.AtAll(),
                platform_message.Image(base64='data:image/png;base64,AAAA'),
                platform_message.Face(face_id=14, face_name='微笑'),
            ]
        )
    )

    assert source_id == 42
    assert [segment.type for segment in target] == ['text', 'at', 'at', 'image', 'face']
    assert target[3].data['file'] == 'base64://AAAA'


@pytest.mark.asyncio
async def test_aiocqhttp_message_converter_maps_media_file_quote_and_face_to_onebot_segments():
    target, _, _ = await AiocqhttpMessageConverter.yiri2target(
        platform_message.MessageChain(
            [
                platform_message.Quote(id=123, origin=platform_message.MessageChain([])),
                platform_message.Image(url='https://example.test/a.png'),
                platform_message.Voice(base64='data:audio/silk;base64,BBBB'),
                platform_message.File(name='doc.txt', url='https://example.test/doc.txt'),
                platform_message.Face(face_type='rps', face_id=1, face_name='猜拳'),
                platform_message.Face(face_type='dice', face_id=6, face_name='骰子'),
            ]
        )
    )

    assert [segment.type for segment in target] == ['reply', 'image', 'record', 'file', 'rps', 'dice']
    assert target[0].data['id'] == '123'
    assert target[1].data['file'] == 'https://example.test/a.png'
    assert target[2].data['file'] == 'base64://BBBB'
    assert target[3].data['name'] == 'doc.txt'


@pytest.mark.asyncio
async def test_aiocqhttp_message_converter_flattens_forward_nodes():
    target, _, _ = await AiocqhttpMessageConverter.yiri2target(
        platform_message.MessageChain(
            [
                platform_message.Forward(
                    node_list=[
                        platform_message.ForwardMessageNode(
                            sender_id='10001',
                            sender_name='Alice',
                            message_chain=platform_message.MessageChain([platform_message.Plain(text='node 1')]),
                        ),
                        platform_message.ForwardMessageNode(
                            sender_id='10002',
                            sender_name='Bob',
                            message_chain=platform_message.MessageChain([platform_message.At(target='999')]),
                        ),
                    ]
                )
            ]
        )
    )

    assert [segment.type for segment in target] == ['text', 'at']
    assert target[0].data['text'] == 'node 1'


@pytest.mark.asyncio
async def test_aiocqhttp_message_converter_maps_onebot_segments_to_chain():
    chain = await AiocqhttpMessageConverter.target2yiri(
        [
            {'type': 'text', 'data': {'text': 'hello '}},
            {'type': 'at', 'data': {'qq': 'all'}},
            {'type': 'at', 'data': {'qq': '10001'}},
            {'type': 'image', 'data': {'file': 'abc.image', 'url': 'https://example.test/a.png'}},
            {'type': 'image', 'data': {'emoji_package_id': '14', 'summary': '微笑'}},
            {'type': 'record', 'data': {'file': 'voice.silk', 'url': 'https://example.test/a.silk'}},
            {'type': 'file', 'data': {'file_id': 'file-1', 'name': 'doc.txt', 'size': '5'}},
            {'type': 'reply', 'data': {'id': '99'}},
            {'type': 'face', 'data': {'id': '14', 'raw': {'faceText': '/微笑'}}},
            {'type': 'rps', 'data': {'result': '2'}},
            {'type': 'dice', 'data': {'result': '6'}},
            {'type': 'json', 'data': {'data': '{}'}},
        ],
        message_id=123,
        timestamp=1710000000,
    )

    assert isinstance(chain[0], platform_message.Source)
    assert isinstance(chain[1], platform_message.Plain)
    assert isinstance(chain[2], platform_message.AtAll)
    assert isinstance(chain[3], platform_message.At)
    assert isinstance(chain[4], platform_message.Image)
    assert chain[4].url == 'https://example.test/a.png'
    assert isinstance(chain[5], platform_message.Face)
    assert isinstance(chain[6], platform_message.Voice)
    assert isinstance(chain[7], platform_message.File)
    assert isinstance(chain[8], platform_message.Quote)
    assert isinstance(chain[9], platform_message.Face)
    assert isinstance(chain[10], platform_message.Face)
    assert chain[10].face_type == 'rps'
    assert isinstance(chain[11], platform_message.Face)
    assert chain[11].face_type == 'dice'
    assert isinstance(chain[12], platform_message.Unknown)


@pytest.mark.asyncio
async def test_aiocqhttp_message_converter_fetches_reply_origin_when_bot_available():
    bot = AsyncMock()
    bot.get_msg.return_value = {
        'message_id': 99,
        'user_id': 10001,
        'group_id': 20001,
        'time': 1710000000,
        'message': [{'type': 'text', 'data': {'text': 'origin'}}],
    }

    chain = await AiocqhttpMessageConverter.target2yiri(
        [{'type': 'reply', 'data': {'id': '99'}}],
        message_id=123,
        bot=bot,
    )

    quote = chain[1]
    assert isinstance(quote, platform_message.Quote)
    assert quote.sender_id == 10001
    assert quote.group_id == 20001
    assert str(quote.origin) == 'origin'


@pytest.mark.asyncio
async def test_aiocqhttp_event_converter_maps_private_and_group_messages():
    private = onebot_event(
        {
            'post_type': 'message',
            'message_type': 'private',
            'sub_type': 'friend',
            'time': 1710000000,
            'self_id': 999,
            'message_id': 11,
            'user_id': 10001,
            'message': [{'type': 'text', 'data': {'text': 'hello'}}],
            'raw_message': 'hello',
            'sender': {'user_id': 10001, 'nickname': 'Alice'},
        }
    )
    private_event = await AiocqhttpEventConverter.target2yiri(private)

    assert isinstance(private_event, platform_events.MessageReceivedEvent)
    assert private_event.type == 'message.received'
    assert private_event.adapter_name == 'aiocqhttp'
    assert private_event.chat_type == platform_entities.ChatType.PRIVATE
    assert private_event.chat_id == 10001
    assert private_event.sender.nickname == 'Alice'

    group = onebot_event(
        {
            'post_type': 'message',
            'message_type': 'group',
            'sub_type': 'normal',
            'time': 1710000000,
            'self_id': 999,
            'message_id': 12,
            'group_id': 20001,
            'user_id': 10001,
            'message': [{'type': 'at', 'data': {'qq': '999'}}, {'type': 'text', 'data': {'text': ' ping'}}],
            'raw_message': '[CQ:at,qq=999] ping',
            'sender': {'user_id': 10001, 'nickname': 'Alice', 'card': 'Alice Card', 'role': 'member'},
        }
    )
    group_event = await AiocqhttpEventConverter.target2yiri(group)

    assert isinstance(group_event, platform_events.MessageReceivedEvent)
    assert group_event.chat_type == platform_entities.ChatType.GROUP
    assert group_event.chat_id == 20001
    assert group_event.group.id == 20001
    assert isinstance(group_event.message_chain[1], platform_message.At)


@pytest.mark.asyncio
async def test_aiocqhttp_event_converter_enriches_group_message_metadata():
    class Bot:
        group_info_calls = 0
        member_info_calls = 0

        async def get_group_info(self, group_id):
            self.group_info_calls += 1
            return {'group_id': group_id, 'group_name': 'Test Group'}

        async def get_group_member_info(self, group_id, user_id):
            self.member_info_calls += 1
            return {'group_id': group_id, 'user_id': user_id, 'card': 'Group Card', 'nickname': 'QQ Nickname'}

    group = onebot_event(
        {
            'post_type': 'message',
            'message_type': 'group',
            'sub_type': 'normal',
            'time': 1710000000,
            'self_id': 999,
            'message_id': 12,
            'group_id': 20002,
            'user_id': 10002,
            'message': [{'type': 'text', 'data': {'text': 'hello'}}],
            'raw_message': 'hello',
            'sender': {'user_id': 10002, 'nickname': '', 'card': '', 'role': 'member'},
        }
    )

    bot = Bot()
    first = await AiocqhttpEventConverter.target2yiri(group, bot)
    second = await AiocqhttpEventConverter.target2yiri(group, bot)

    assert first.group.name == 'Test Group'
    assert first.sender.nickname == 'Group Card'
    assert first.sender.remark == 'Group Card'
    assert second.group.name == 'Test Group'
    assert bot.group_info_calls == 1
    assert bot.member_info_calls == 1


@pytest.mark.asyncio
async def test_aiocqhttp_event_converter_maps_notice_and_request_events():
    deleted = await AiocqhttpEventConverter.notice_to_eba(
        onebot_event(
            {
                'post_type': 'notice',
                'notice_type': 'group_recall',
                'time': 1710000000,
                'self_id': 999,
                'group_id': 20001,
                'user_id': 10001,
                'operator_id': 10002,
                'message_id': 33,
            }
        )
    )
    assert isinstance(deleted, platform_events.MessageDeletedEvent)
    assert deleted.message_id == 33

    joined = await AiocqhttpEventConverter.notice_to_eba(
        onebot_event(
            {
                'post_type': 'notice',
                'notice_type': 'group_increase',
                'sub_type': 'invite',
                'time': 1710000000,
                'self_id': 999,
                'group_id': 20001,
                'operator_id': 10002,
                'user_id': 10003,
            }
        ),
        bot_user_id=999,
    )
    assert isinstance(joined, platform_events.MemberJoinedEvent)
    assert joined.join_type == 'invite'

    bot_muted = await AiocqhttpEventConverter.notice_to_eba(
        onebot_event(
            {
                'post_type': 'notice',
                'notice_type': 'group_ban',
                'sub_type': 'ban',
                'time': 1710000000,
                'self_id': 999,
                'group_id': 20001,
                'operator_id': 10002,
                'user_id': 999,
                'duration': 60,
            }
        ),
        bot_user_id=999,
    )
    assert isinstance(bot_muted, platform_events.BotMutedEvent)
    assert bot_muted.duration == 60

    friend_request = await AiocqhttpEventConverter.request_to_eba(
        onebot_event(
            {
                'post_type': 'request',
                'request_type': 'friend',
                'time': 1710000000,
                'self_id': 999,
                'user_id': 10004,
                'comment': 'please',
                'flag': 'flag-1',
            }
        )
    )
    assert isinstance(friend_request, platform_events.FriendRequestReceivedEvent)
    assert friend_request.request_id == 'flag-1'

    group_invite = await AiocqhttpEventConverter.request_to_eba(
        onebot_event(
            {
                'post_type': 'request',
                'request_type': 'group',
                'sub_type': 'invite',
                'time': 1710000000,
                'self_id': 999,
                'group_id': 20001,
                'user_id': 10004,
                'flag': 'group-flag',
            }
        )
    )
    assert isinstance(group_invite, platform_events.BotInvitedToGroupEvent)
    assert group_invite.request_id == 'group-flag'

    member_left = await AiocqhttpEventConverter.notice_to_eba(
        onebot_event(
            {
                'post_type': 'notice',
                'notice_type': 'group_decrease',
                'sub_type': 'kick',
                'time': 1710000000,
                'self_id': 999,
                'group_id': 20001,
                'operator_id': 10002,
                'user_id': 10003,
            }
        ),
        bot_user_id=999,
    )
    assert isinstance(member_left, platform_events.MemberLeftEvent)
    assert member_left.is_kicked is True

    friend_added = await AiocqhttpEventConverter.notice_to_eba(
        onebot_event(
            {
                'post_type': 'notice',
                'notice_type': 'friend_add',
                'time': 1710000000,
                'self_id': 999,
                'user_id': 10003,
            }
        )
    )
    assert isinstance(friend_added, platform_events.FriendAddedEvent)


@pytest.mark.asyncio
async def test_aiocqhttp_send_reply_and_common_api_call_shapes():
    adapter = make_adapter()
    bot = AsyncMock()
    bot.send_group_msg.return_value = {'message_id': 1}
    bot.send_private_msg.return_value = {'message_id': 3}
    bot.send.return_value = {'message_id': 2}
    bot.delete_msg.return_value = {}
    bot.get_msg.return_value = {
        'message_id': 77,
        'message_type': 'group',
        'time': 1710000000,
        'group_id': 20001,
        'sender': {'user_id': 10001, 'nickname': 'Alice'},
        'message': [{'type': 'text', 'data': {'text': 'fetched'}}],
    }
    bot.get_group_info.return_value = {'group_id': 20001, 'group_name': 'Group', 'member_count': 3}
    bot.get_group_list.return_value = [{'group_id': 20001, 'group_name': 'Group', 'member_count': 3}]
    bot.get_group_member_list.return_value = [
        {
            'group_id': 20001,
            'user_id': 10001,
            'nickname': 'Alice',
            'card': 'Alice Card',
            'role': 'admin',
            'join_time': 1710000000,
        }
    ]
    bot.get_group_member_info.return_value = {
        'group_id': 20001,
        'user_id': 10001,
        'nickname': 'Alice',
        'card': 'Alice Card',
        'role': 'admin',
        'join_time': 1710000000,
    }
    bot.get_stranger_info.return_value = {'user_id': 10001, 'nickname': 'Alice'}
    bot.get_friend_list.return_value = [{'user_id': 10001, 'nickname': 'Alice', 'remark': 'A'}]
    object.__setattr__(adapter, 'bot', bot)

    result = await adapter.send_message(
        'group',
        '20001',
        platform_message.MessageChain([platform_message.Plain(text='hello')]),
    )
    assert result.message_id == 1
    bot.send_group_msg.assert_awaited_once()
    assert bot.send_group_msg.await_args.kwargs['group_id'] == 20001

    source_event = onebot_event(
        {
            'post_type': 'message',
            'message_type': 'group',
            'sub_type': 'normal',
            'time': 1710000000,
            'self_id': 999,
            'message_id': 12,
            'group_id': 20001,
            'user_id': 10001,
            'message': [],
            'raw_message': '',
            'sender': {'user_id': 10001, 'nickname': 'Alice'},
        }
    )
    eba_source = await AiocqhttpEventConverter.message_to_eba(source_event)
    reply = await adapter.reply_message(
        eba_source,
        platform_message.MessageChain([platform_message.Plain(text='pong')]),
        quote_origin=True,
    )
    assert reply.message_id == 2
    assert bot.send.await_args.args[0] is source_event

    await adapter.delete_message('group', 20001, 12)
    bot.delete_msg.assert_awaited_once_with(message_id=12)

    group = await adapter.get_group_info(20001)
    assert group.name == 'Group'

    groups = await adapter.get_group_list()
    assert groups[0].id == 20001

    members = await adapter.get_group_member_list(20001)
    assert members[0].display_name == 'Alice Card'

    member = await adapter.get_group_member_info(20001, 10001)
    assert member.role == platform_entities.MemberRole.ADMIN

    user = await adapter.get_user_info(10001)
    assert user.nickname == 'Alice'

    friends = await adapter.get_friend_list()
    assert friends[0].remark == 'A'

    fetched = await adapter.get_message('group', 20001, 77)
    assert fetched.message_id == 77
    assert str(fetched.message_chain) == 'fetched'

    forwarded = await adapter.forward_message('group', 20001, 77, 'private', 10001)
    assert forwarded.message_id == 3
    bot.send_private_msg.assert_awaited_once()

    await adapter.set_group_name(20001, 'New Name')
    bot.set_group_name.assert_awaited_once_with(group_id=20001, group_name='New Name')

    await adapter.mute_member(20001, 10001, 60)
    bot.set_group_ban.assert_awaited_with(group_id=20001, user_id=10001, duration=60)

    await adapter.unmute_member(20001, 10001)
    bot.set_group_ban.assert_awaited_with(group_id=20001, user_id=10001, duration=0)

    await adapter.kick_member(20001, 10001)
    bot.set_group_kick.assert_awaited_once_with(group_id=20001, user_id=10001, reject_add_request=False)

    await adapter.leave_group(20001)
    bot.set_group_leave.assert_awaited_once_with(group_id=20001, is_dismiss=False)

    await adapter.approve_friend_request('flag-1', True, 'Alice')
    bot.set_friend_add_request.assert_awaited_once_with(flag='flag-1', approve=True, remark='Alice')

    await adapter.approve_group_invite('flag-2', False)
    bot.set_group_add_request.assert_awaited_once_with(flag='flag-2', sub_type='invite', approve=False, reason='')

    with pytest.raises(NotSupportedError):
        await adapter.upload_file(b'data', 'a.txt')

    with pytest.raises(NotSupportedError):
        await adapter.get_file_url('file-1')


@pytest.mark.asyncio
async def test_aiocqhttp_platform_specific_api_calls_all_declared_actions():
    adapter = make_adapter()
    bot = AsyncMock()
    bot.call_action.return_value = {'ok': True}
    object.__setattr__(adapter, 'bot', bot)

    for action in PLATFORM_API_MAP:
        result = await adapter.call_platform_api(action, {'x': 1})
        assert result == {'ok': True}

    called_actions = [call.args[0] for call in bot.call_action.await_args_list]
    assert called_actions == list(PLATFORM_API_MAP)

    with pytest.raises(NotSupportedError):
        await adapter.call_platform_api('missing_action', {})
