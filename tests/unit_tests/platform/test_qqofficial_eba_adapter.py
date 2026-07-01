from __future__ import annotations

import pathlib
import datetime
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from langbot.libs.qq_official_api.qqofficialevent import QQOfficialEvent
from langbot.pkg.platform.adapters.qqofficial.adapter import QQOfficialAdapter
from langbot.pkg.platform.adapters.qqofficial.errors import NotSupportedError
from langbot.pkg.platform.adapters.qqofficial.event_converter import QQOfficialEventConverter
from langbot.pkg.platform.adapters.qqofficial.message_converter import QQOfficialMessageConverter
from langbot.pkg.platform.adapters.qqofficial.platform_api import PLATFORM_API_MAP
from langbot_plugin.api.definition.abstract.platform.event_logger import AbstractEventLogger
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message


class DummyLogger(AbstractEventLogger):
    async def info(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def debug(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def warning(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def error(self, text, images=None, message_session_id=None, no_throw=True):
        pass


class DummyQQOfficialClient:
    MEDIA_TYPE_IMAGE = 1
    MEDIA_TYPE_VOICE = 3
    MEDIA_TYPE_FILE = 4

    def __init__(self, *args, **kwargs):
        self.app_id = kwargs['app_id']
        self.secret = kwargs['secret']
        self.token = kwargs['token']
        self.unified_mode = kwargs['unified_mode']
        self._message_handlers = {}
        self.sent = []
        self.access_token = ''
        self.access_token_expiry_time = None
        self.handle_unified_webhook = AsyncMock(return_value='success')
        self.connect_gateway_loop = AsyncMock()

    def on_message(self, msg_type: str):
        def decorator(func):
            self._message_handlers.setdefault(msg_type, []).append(func)
            return func

        return decorator

    async def check_access_token(self):
        return bool(self.access_token)

    async def get_access_token(self):
        self.access_token = 'token'
        self.access_token_expiry_time = 1710003600

    async def get_gateway_url(self):
        return 'wss://gateway.example.test'

    async def send_private_text_msg(self, user_openid, content, msg_id=None):
        self.sent.append(('private_text', user_openid, content, msg_id))
        return {'id': 'sent-private'}

    async def send_group_text_msg(self, group_openid, content, msg_id=None):
        self.sent.append(('group_text', group_openid, content, msg_id))
        return {'id': 'sent-group'}

    async def send_channle_group_text_msg(self, channel_id, content, msg_id=None):
        self.sent.append(('channel_text', channel_id, content, msg_id))
        return {'id': 'sent-channel'}

    async def send_channle_private_text_msg(self, guild_id, content, msg_id=None):
        self.sent.append(('dm_text', guild_id, content, msg_id))
        return {'id': 'sent-dm'}

    async def send_image_msg(self, target_type, target_id, file_url=None, file_data=None, msg_id=None, content=None):
        self.sent.append(('image', target_type, target_id, file_url, file_data, msg_id))
        return {'id': 'sent-image'}

    async def send_voice_msg(self, target_type, target_id, file_url=None, file_data=None, msg_id=None):
        self.sent.append(('voice', target_type, target_id, file_url, file_data, msg_id))
        return {'id': 'sent-voice'}

    async def send_file_msg(self, target_type, target_id, file_url=None, file_data=None, file_name=None, msg_id=None):
        self.sent.append(('file', target_type, target_id, file_url, file_data, file_name, msg_id))
        return {'id': 'sent-file'}

    async def send_stream_msg(self, **kwargs):
        self.sent.append(('stream', kwargs))
        return {'id': 'stream-1'}


def manifest() -> dict:
    manifest_path = (
        pathlib.Path(__file__).parents[3]
        / 'src'
        / 'langbot'
        / 'pkg'
        / 'platform'
        / 'adapters'
        / 'qqofficial'
        / 'manifest.yaml'
    )
    return yaml.safe_load(manifest_path.read_text())


def make_adapter(enable_webhook: bool = True) -> QQOfficialAdapter:
    config = {
        'appid': 'app-id',
        'secret': 'secret',
        'token': 'token',
        'enable-webhook': enable_webhook,
        'enable-stream-reply': True,
    }
    with patch('langbot.pkg.platform.adapters.qqofficial.adapter.QQOfficialClient', DummyQQOfficialClient):
        return QQOfficialAdapter(config, DummyLogger())


def qq_event(event_type: str = 'C2C_MESSAGE_CREATE', **overrides) -> QQOfficialEvent:
    payload = {
        't': event_type,
        'user_openid': overrides.get('user_openid', 'user-openid'),
        'timestamp': overrides.get('timestamp', '2026-06-01T10:00:00+0800'),
        'd_author_id': overrides.get('author_id', 'author-id'),
        'content': overrides.get('content', 'hello'),
        'd_id': overrides.get('message_id', 'msg-1'),
        'id': overrides.get('event_id', 'event-1'),
        'channel_id': overrides.get('channel_id', 'channel-1'),
        'username': overrides.get('username', 'alice'),
        'guild_id': overrides.get('guild_id', 'guild-1'),
        'member_openid': overrides.get('member_openid', 'member-openid'),
        'group_openid': overrides.get('group_openid', 'group-openid'),
        'image_attachments': overrides.get('image_attachments'),
        'content_type': overrides.get('content_type', 'image/png'),
    }
    payload.update(overrides.get('extra', {}))
    return QQOfficialEvent(payload)


def test_qqofficial_supported_events_match_manifest():
    assert make_adapter().get_supported_events() == manifest()['spec']['supported_events']


def test_qqofficial_supported_apis_match_manifest():
    supported_apis = make_adapter().get_supported_apis()
    manifest_apis = manifest()['spec']['supported_apis']

    assert supported_apis == manifest_apis['required'] + manifest_apis['optional']


def test_qqofficial_platform_api_map_matches_manifest():
    manifest_actions = {item['action'] for item in manifest()['spec']['platform_specific_apis']}

    assert set(PLATFORM_API_MAP) == manifest_actions


@pytest.mark.asyncio
async def test_qqofficial_message_converter_maps_common_components_to_send_payloads():
    payload = await QQOfficialMessageConverter.yiri2target(
        platform_message.MessageChain(
            [
                platform_message.Source(id='msg-0', time=datetime.datetime.now()),
                platform_message.Plain(text='hi'),
                platform_message.At(target='user-1', display='Alice'),
                platform_message.AtAll(),
                platform_message.Image(url='https://example.test/a.png'),
                platform_message.Voice(base64='data:audio/mpeg;base64,AAAA'),
                platform_message.File(name='a.txt', url='https://example.test/a.txt'),
                platform_message.Quote(origin=platform_message.MessageChain([platform_message.Plain(text='quoted')])),
            ]
        )
    )

    assert {'type': 'text', 'content': 'hi'} in payload
    assert {'type': 'text', 'content': '@Alice'} in payload
    assert {'type': 'text', 'content': '@all'} in payload
    assert any(item['type'] == 'image' and item['url'] == 'https://example.test/a.png' for item in payload)
    assert any(item['type'] == 'voice' and item['base64'].startswith('data:audio') for item in payload)
    assert any(item['type'] == 'file' and item['name'] == 'a.txt' for item in payload)
    assert {'type': 'text', 'content': 'quoted'} in payload


@pytest.mark.asyncio
async def test_qqofficial_event_converter_maps_private_group_and_platform_specific():
    private_event = await QQOfficialEventConverter().target2yiri(qq_event('C2C_MESSAGE_CREATE'))
    group_event = await QQOfficialEventConverter().target2yiri(qq_event('GROUP_AT_MESSAGE_CREATE'))
    channel_event = await QQOfficialEventConverter().target2yiri(qq_event('AT_MESSAGE_CREATE'))
    platform_event = await QQOfficialEventConverter().target2yiri(qq_event('UNKNOWN_EVENT'))

    assert isinstance(private_event, platform_events.MessageReceivedEvent)
    assert private_event.adapter_name == 'qqofficial-eba'
    assert private_event.chat_type == platform_entities.ChatType.PRIVATE
    assert private_event.chat_id == 'user-openid'
    assert str(private_event.message_chain) == 'hello'

    assert isinstance(group_event, platform_events.MessageReceivedEvent)
    assert group_event.chat_type == platform_entities.ChatType.GROUP
    assert group_event.chat_id == 'group-openid'
    assert isinstance(group_event.message_chain[1], platform_message.At)

    assert channel_event.chat_id == 'channel-1'
    assert isinstance(platform_event, platform_events.PlatformSpecificEvent)
    assert platform_event.action == 'qqofficial.UNKNOWN_EVENT'


@pytest.mark.asyncio
async def test_qqofficial_event_converter_maps_declared_lifecycle_events():
    converter = QQOfficialEventConverter()

    reaction_add = await converter.target2yiri(
        qq_event(
            'MESSAGE_REACTION_ADD',
            extra={
                'message_id': 'reacted-msg',
                'emoji': 'thumbs_up',
                'group_openid': 'group-openid',
                'openid': 'reactor-openid',
            },
        )
    )
    reaction_remove = await converter.target2yiri(
        qq_event('MESSAGE_REACTION_REMOVE', extra={'message_id': 'reacted-msg', 'emoji_id': '1'})
    )
    member_joined = await converter.target2yiri(
        qq_event('GROUP_MEMBER_ADD', extra={'openid': 'new-member', 'group_openid': 'group-openid'})
    )
    member_left = await converter.target2yiri(
        qq_event('GROUP_MEMBER_REMOVE', extra={'openid': 'old-member', 'operator_openid': 'operator-openid'})
    )
    bot_invited = await converter.target2yiri(
        qq_event('GROUP_ADD_ROBOT', extra={'group_openid': 'group-openid', 'op_user_id': 'inviter-openid'})
    )
    bot_removed = await converter.target2yiri(
        qq_event('GROUP_DEL_ROBOT', extra={'group_openid': 'group-openid', 'op_user_id': 'operator-openid'})
    )

    assert isinstance(reaction_add, platform_events.MessageReactionEvent)
    assert reaction_add.type == 'message.reaction'
    assert reaction_add.is_add is True
    assert reaction_add.message_id == 'reacted-msg'
    assert reaction_add.reaction == 'thumbs_up'
    assert reaction_add.chat_type == platform_entities.ChatType.GROUP

    assert isinstance(reaction_remove, platform_events.MessageReactionEvent)
    assert reaction_remove.is_add is False

    assert isinstance(member_joined, platform_events.MemberJoinedEvent)
    assert member_joined.type == 'group.member_joined'
    assert member_joined.group.id == 'group-openid'
    assert member_joined.member.id == 'new-member'

    assert isinstance(member_left, platform_events.MemberLeftEvent)
    assert member_left.type == 'group.member_left'
    assert member_left.member.id == 'old-member'
    assert member_left.operator.id == 'operator-openid'

    assert isinstance(bot_invited, platform_events.BotInvitedToGroupEvent)
    assert bot_invited.type == 'bot.invited_to_group'
    assert bot_invited.inviter.id == 'inviter-openid'

    assert isinstance(bot_removed, platform_events.BotRemovedFromGroupEvent)
    assert bot_removed.type == 'bot.removed_from_group'
    assert bot_removed.operator.id == 'operator-openid'


@pytest.mark.asyncio
async def test_qqofficial_adapter_dispatches_eba_and_legacy_and_caches_group_event():
    adapter = make_adapter()
    eba_calls: list[platform_events.Event] = []
    legacy_calls: list[platform_events.Event] = []

    async def eba_listener(event, adapter):
        eba_calls.append(event)

    async def legacy_listener(event, adapter):
        legacy_calls.append(event)

    adapter.register_listener(platform_events.MessageReceivedEvent, eba_listener)
    adapter.register_listener(platform_events.GroupMessage, legacy_listener)
    await adapter._handle_native_event(qq_event('GROUP_AT_MESSAGE_CREATE'))

    assert len(eba_calls) == 1
    assert len(legacy_calls) == 1
    received = eba_calls[0]
    assert await adapter.get_message('group', 'group-openid', 'msg-1') == received
    assert (await adapter.get_group_info('group-openid')).id == 'group-openid'
    assert (await adapter.get_group_member_info('group-openid', 'member-openid')).user.id == 'member-openid'


@pytest.mark.asyncio
async def test_qqofficial_adapter_dispatches_non_message_eba_events():
    adapter = make_adapter()
    calls: list[platform_events.Event] = []

    async def member_listener(event, adapter):
        calls.append(event)

    adapter.register_listener(platform_events.MemberJoinedEvent, member_listener)
    await adapter._handle_native_event(
        qq_event('GROUP_MEMBER_ADD', extra={'openid': 'new-member', 'group_openid': 'group-openid'})
    )

    assert len(calls) == 1
    assert isinstance(calls[0], platform_events.MemberJoinedEvent)
    assert calls[0].member.id == 'new-member'


@pytest.mark.asyncio
async def test_qqofficial_send_reply_stream_platform_api_and_unsupported():
    adapter = make_adapter()
    message = platform_message.MessageChain(
        [
            platform_message.Plain(text='reply'),
            platform_message.Image(url='https://example.test/a.png'),
        ]
    )
    source_event = await QQOfficialEventConverter().target2yiri(qq_event('C2C_MESSAGE_CREATE'))

    reply_result = await adapter.reply_message(source_event, message)
    assert reply_result.message_id == 'msg-1'
    assert ('private_text', 'user-openid', 'reply', 'msg-1') in adapter.bot.sent
    assert any(call[0] == 'image' and call[1] == 'c2c' for call in adapter.bot.sent)

    await adapter.send_message(
        'group', 'group-openid', platform_message.MessageChain([platform_message.Plain(text='hello group')])
    )
    assert ('group_text', 'group-openid', 'hello group', None) in adapter.bot.sent

    assert await adapter.call_platform_api('get_mode', {}) == {
        'webhook': True,
        'stream_reply': True,
        'bot_account_id': 'app-id',
    }
    await adapter.call_platform_api('refresh_access_token', {})
    assert adapter.bot.access_token == 'token'

    with pytest.raises(NotSupportedError):
        await adapter.call_platform_api('missing', {})


@pytest.mark.asyncio
async def test_qqofficial_client_next_reply_msg_seq_allocator():
    """msg_seq must increment per inbound msg_id to avoid 40054005 dedup (issue #2290)."""
    from langbot.libs.qq_official_api.api import QQOfficialClient

    client = QQOfficialClient(secret='s', token='t', app_id='a', logger=DummyLogger())

    # same msg_id -> strictly increasing 1, 2, 3
    assert [await client.next_reply_msg_seq('m1') for _ in range(3)] == [1, 2, 3]
    # a different msg_id is tracked independently
    assert await client.next_reply_msg_seq('m2') == 1
    # missing msg_id falls back to the global proactive counter, independent of per-id seqs
    assert [await client.next_reply_msg_seq(None) for _ in range(2)] == [1, 2]
    # concurrent allocations under the same msg_id are unique and gap-free
    import asyncio as _asyncio

    concurrent = await _asyncio.gather(*[client.next_reply_msg_seq('m3') for _ in range(50)])
    assert sorted(concurrent) == list(range(1, 51))


@pytest.mark.asyncio
async def test_qqofficial_text_send_carries_incrementing_msg_seq(monkeypatch):
    """Multiple text replies under one inbound msg_id get distinct msg_seq values."""
    from langbot.libs.qq_official_api.api import QQOfficialClient

    client = QQOfficialClient(secret='s', token='t', app_id='a', logger=DummyLogger())
    client.access_token = 'token'
    client.access_token_expiry_time = 9999999999

    captured = []

    class _Resp:
        status_code = 200

        def json(self):
            return {'id': 'ok'}

    class _DummyAsyncClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            captured.append(json)
            return _Resp()

    monkeypatch.setattr('langbot.libs.qq_official_api.api.httpx.AsyncClient', _DummyAsyncClient)

    await client.send_private_text_msg('user-1', 'first', 'inbound-1')
    await client.send_private_text_msg('user-1', 'second', 'inbound-1')
    await client.send_group_text_msg('group-1', 'third', 'inbound-1')

    seqs = [body['msg_seq'] for body in captured]
    assert seqs == [1, 2, 3]
    assert all(body['msg_id'] == 'inbound-1' for body in captured)


@pytest.mark.asyncio
async def test_qqofficial_stream_chunks_increment_msg_seq():
    """Each stream chunk must advance msg_seq so QQ does not dedup later chunks (issue #2290)."""
    adapter = make_adapter()
    source_event = await QQOfficialEventConverter().target2yiri(qq_event('C2C_MESSAGE_CREATE'))

    assert await adapter.create_message_card('msg-1', source_event) is True
    bot_message = {'resp_message_id': 'msg-1'}

    for idx, text in enumerate(['hello ', 'world ', 'done']):
        # reset the per-chunk rate limiter so each chunk actually sends
        adapter._stream_ctx['msg-1']['last_update_ts'] = 0
        await adapter.reply_message_chunk(
            source_event,
            bot_message,
            platform_message.MessageChain([platform_message.Plain(text=text)]),
            is_final=(idx == 2),
        )

    stream_calls = [call[1] for call in adapter.bot.sent if call[0] == 'stream']
    seqs = [kwargs['msg_seq'] for kwargs in stream_calls]
    # strictly increasing, no duplicates
    assert seqs == sorted(set(seqs))
    assert len(seqs) == len(set(seqs))
    assert seqs[0] == 1
