import pytest
import aiocqhttp

import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
from langbot.pkg.platform.sources.aiocqhttp import (
    AiocqhttpAdapter,
    AiocqhttpEventConverter,
    AiocqhttpMessageConverter,
)


async def _convert_single(component: platform_message.MessageComponent):
    chain = platform_message.MessageChain([component])
    message, _, _ = await AiocqhttpMessageConverter.yiri2target(chain)
    return message[0]


class _TestLogger:
    def __init__(self):
        self.messages = []

    async def info(self, message):
        self.messages.append(message)


def _make_adapter():
    logger = _TestLogger()
    adapter = AiocqhttpAdapter.model_construct(
        config={},
        logger=logger,
        bot=aiocqhttp.CQHttp(),
        on_websocket_connection_event_cache=[],
        _listener_wrappers={},
    )
    adapter.bot.on_websocket_connection(adapter._on_websocket_connection)
    return adapter, logger


def test_connection_listener_is_registered_once_for_multiple_message_listeners():
    adapter, _ = _make_adapter()

    async def callback(event, source_adapter):
        return None

    adapter.register_listener(platform_events.FriendMessage, callback)
    adapter.register_listener(platform_events.GroupMessage, callback)
    adapter.register_listener(platform_events.FeedbackEvent, callback)

    assert len(adapter.bot._bus._subscribers['meta_event.lifecycle.connect']) == 1


@pytest.mark.asyncio
async def test_connection_listener_only_suppresses_exact_duplicates():
    adapter, logger = _make_adapter()
    first = aiocqhttp.Event({'self_id': 1001, 'time': 10})
    duplicate = aiocqhttp.Event({'self_id': 1001, 'time': 10})
    second = aiocqhttp.Event({'self_id': 2002, 'time': 20})

    await adapter._on_websocket_connection(first)
    await adapter._on_websocket_connection(duplicate)
    await adapter._on_websocket_connection(second)

    assert adapter.on_websocket_connection_event_cache == [first, second]
    assert logger.messages == [
        'WebSocket connection established, bot id: 1001',
        'WebSocket connection established, bot id: 2002',
    ]


def test_unregister_listener_removes_registered_wrapper():
    adapter, _ = _make_adapter()

    async def callback(event, source_adapter):
        return None

    adapter.register_listener(platform_events.GroupMessage, callback)
    assert len(adapter.bot._bus._subscribers['message.group']) == 1

    adapter.unregister_listener(platform_events.GroupMessage, callback)

    assert not adapter.bot._bus._subscribers['message.group']


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('payload', 'expected'),
    [
        ('data:image/jpeg;base64,raw-image', 'base64://raw-image'),
        ('raw-image', 'base64://raw-image'),
        ('base64://raw-image', 'base64://raw-image'),
    ],
)
async def test_image_base64_payload_is_normalized(payload, expected):
    segment = await _convert_single(platform_message.Image(base64=payload))

    assert segment.type == 'image'
    assert segment.data['file'] == expected


@pytest.mark.asyncio
async def test_voice_data_uri_base64_payload_is_normalized():
    segment = await _convert_single(platform_message.Voice(base64='data:audio/wav;base64,raw-voice'))

    assert segment.type == 'record'
    assert segment.data['file'] == 'base64://raw-voice'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('component', 'expected'),
    [
        (
            platform_message.File(name='report.txt', base64='data:text/plain;base64,raw-file'),
            {'file': 'base64://raw-file', 'name': 'report.txt'},
        ),
        (
            platform_message.File(name='report.txt', base64='raw-file'),
            {'file': 'base64://raw-file', 'name': 'report.txt'},
        ),
        (
            platform_message.File(name='a.txt', url='http://example.com/a.txt'),
            {'file': 'http://example.com/a.txt', 'name': 'a.txt'},
        ),
        (
            platform_message.File(name='a.txt', path='/tmp/a.txt'),
            {'file': '/tmp/a.txt', 'name': 'a.txt'},
        ),
    ],
)
async def test_file_message_uses_available_file_source(component, expected):
    segment = await _convert_single(component)

    assert segment.type == 'file'
    assert segment.data == expected


@pytest.mark.asyncio
async def test_forward_image_base64_payload_is_normalized():
    forward = platform_message.Forward(
        node_list=[
            platform_message.ForwardMessageNode(
                sender_id='10001',
                sender_name='Tester',
                message_chain=platform_message.MessageChain(
                    [platform_message.Image(base64='data:image/png;base64,raw-forward-image')]
                ),
            )
        ]
    )
    messages = []

    class Logger:
        async def info(self, _message):
            return None

        async def error(self, _message):
            return None

    class Bot:
        async def call_action(self, action, **kwargs):
            assert action == 'send_forward_msg'
            messages.append(kwargs)

    platform = AiocqhttpAdapter.model_construct(
        bot_account_id='10000',
        config={},
        logger=Logger(),
        bot=Bot(),
    )

    await platform._send_forward_message(1000, forward)

    assert messages[0]['messages'][0]['data']['content'][0] == {
        'type': 'image',
        'data': {'file': 'base64://raw-forward-image'},
    }


@pytest.mark.asyncio
async def test_group_message_member_name_prefers_group_card():
    event = aiocqhttp.Event(
        {
            'post_type': 'message',
            'message_type': 'group',
            'message_id': 1000,
            'message': '',
            'time': 1776491725,
            'group_id': 2000,
            'sender': {
                'user_id': 3000,
                'nickname': 'QQ Nickname',
                'card': 'Group Card',
                'role': 'member',
                'title': 'Special Title',
            },
        }
    )

    class Bot:
        async def get_group_info(self, group_id):
            assert group_id == 2000
            return {'group_id': group_id, 'group_name': 'Test Group'}

    converted = await AiocqhttpEventConverter().target2yiri(event, Bot())

    assert converted.sender.member_name == 'Group Card'
    assert converted.sender.group.id == 2000
    assert converted.sender.group.name == 'Test Group'
    assert converted.sender.special_title == 'Special Title'


@pytest.mark.asyncio
async def test_group_message_member_name_falls_back_to_nickname():
    event = aiocqhttp.Event(
        {
            'post_type': 'message',
            'message_type': 'group',
            'message_id': 1000,
            'message': '',
            'time': 1776491725,
            'group_id': 2000,
            'sender': {
                'user_id': 3000,
                'nickname': 'QQ Nickname',
                'card': '',
                'role': 'member',
            },
        }
    )

    converted = await AiocqhttpEventConverter().target2yiri(event)

    assert converted.sender.member_name == 'QQ Nickname'


@pytest.mark.asyncio
async def test_group_message_special_title_uses_group_member_info_when_sender_title_is_empty():
    event = aiocqhttp.Event(
        {
            'post_type': 'message',
            'message_type': 'group',
            'message_id': 1000,
            'message': '',
            'time': 1776491725,
            'group_id': 2000,
            'sender': {
                'user_id': 3000,
                'nickname': 'QQ Nickname',
                'card': 'Group Card',
                'role': 'member',
                'title': '',
            },
        }
    )

    class Bot:
        async def get_group_info(self, group_id):
            return {'group_id': group_id, 'group_name': 'Test Group'}

        async def get_group_member_info(self, group_id, user_id):
            assert group_id == 2000
            assert user_id == 3000
            return {'group_id': group_id, 'user_id': user_id, 'title': 'Member Title'}

    converted = await AiocqhttpEventConverter().target2yiri(event, Bot())

    assert converted.sender.special_title == 'Member Title'


@pytest.mark.asyncio
async def test_group_message_special_title_does_not_lookup_when_sender_title_exists():
    event = aiocqhttp.Event(
        {
            'post_type': 'message',
            'message_type': 'group',
            'message_id': 1000,
            'message': '',
            'time': 1776491725,
            'group_id': 2000,
            'sender': {
                'user_id': 3000,
                'nickname': 'QQ Nickname',
                'card': 'Group Card',
                'role': 'member',
                'title': 'Event Title',
            },
        }
    )

    class Bot:
        async def get_group_info(self, group_id):
            return {'group_id': group_id, 'group_name': 'Test Group'}

        async def get_group_member_info(self, group_id, user_id):
            raise AssertionError('get_group_member_info should not be called')

    converted = await AiocqhttpEventConverter().target2yiri(event, Bot())

    assert converted.sender.special_title == 'Event Title'


@pytest.mark.asyncio
async def test_group_message_special_title_member_info_failure_is_cached(monkeypatch):
    event = aiocqhttp.Event(
        {
            'post_type': 'message',
            'message_type': 'group',
            'message_id': 1000,
            'message': '',
            'time': 1776491725,
            'group_id': 2000,
            'sender': {
                'user_id': 3000,
                'nickname': 'QQ Nickname',
                'card': 'Group Card',
                'role': 'member',
                'title': '',
            },
        }
    )
    now = 1000.0

    class Bot:
        member_info_calls = 0

        async def get_group_info(self, group_id):
            return {'group_id': group_id, 'group_name': 'Test Group'}

        async def get_group_member_info(self, group_id, user_id):
            self.member_info_calls += 1
            raise RuntimeError('api unavailable')

    monkeypatch.setattr('langbot.pkg.platform.sources.aiocqhttp.time.monotonic', lambda: now)

    bot = Bot()
    converter = AiocqhttpEventConverter()

    first = await converter.target2yiri(event, bot)
    second = await converter.target2yiri(event, bot)

    assert first.sender.special_title == ''
    assert second.sender.special_title == ''
    assert bot.member_info_calls == 1


@pytest.mark.asyncio
async def test_group_message_special_title_member_info_cache_expires(monkeypatch):
    event = aiocqhttp.Event(
        {
            'post_type': 'message',
            'message_type': 'group',
            'message_id': 1000,
            'message': '',
            'time': 1776491725,
            'group_id': 2000,
            'sender': {
                'user_id': 3000,
                'nickname': 'QQ Nickname',
                'card': 'Group Card',
                'role': 'member',
                'title': '',
            },
        }
    )
    now = 1000.0

    class Bot:
        member_info_calls = 0

        async def get_group_info(self, group_id):
            return {'group_id': group_id, 'group_name': 'Test Group'}

        async def get_group_member_info(self, group_id, user_id):
            self.member_info_calls += 1
            return {
                'group_id': group_id,
                'user_id': user_id,
                'title': f'Member Title {self.member_info_calls}',
            }

    monkeypatch.setattr('langbot.pkg.platform.sources.aiocqhttp.time.monotonic', lambda: now)

    bot = Bot()
    converter = AiocqhttpEventConverter()

    first = await converter.target2yiri(event, bot)
    now = 87401.0
    second = await converter.target2yiri(event, bot)

    assert first.sender.special_title == 'Member Title 1'
    assert second.sender.special_title == 'Member Title 2'
    assert bot.member_info_calls == 2


@pytest.mark.asyncio
async def test_group_message_special_title_retries_after_negative_cache_expires(monkeypatch):
    event = aiocqhttp.Event(
        {
            'post_type': 'message',
            'message_type': 'group',
            'message_id': 1000,
            'message': '',
            'time': 1776491725,
            'group_id': 2000,
            'sender': {
                'user_id': 3000,
                'nickname': 'QQ Nickname',
                'card': 'Group Card',
                'role': 'member',
                'title': '',
            },
        }
    )
    now = 1000.0

    class Bot:
        member_info_calls = 0

        async def get_group_info(self, group_id):
            return {'group_id': group_id, 'group_name': 'Test Group'}

        async def get_group_member_info(self, group_id, user_id):
            self.member_info_calls += 1
            if self.member_info_calls == 1:
                raise RuntimeError('api unavailable')
            return {'group_id': group_id, 'user_id': user_id, 'title': 'Recovered Title'}

    monkeypatch.setattr('langbot.pkg.platform.sources.aiocqhttp.time.monotonic', lambda: now)

    bot = Bot()
    converter = AiocqhttpEventConverter()

    failed = await converter.target2yiri(event, bot)
    now = 1601.0
    recovered = await converter.target2yiri(event, bot)

    assert failed.sender.special_title == ''
    assert recovered.sender.special_title == 'Recovered Title'
    assert bot.member_info_calls == 2


@pytest.mark.asyncio
async def test_group_message_group_name_is_cached(monkeypatch):
    event = aiocqhttp.Event(
        {
            'post_type': 'message',
            'message_type': 'group',
            'message_id': 1000,
            'message': '',
            'time': 1776491725,
            'group_id': 2000,
            'sender': {
                'user_id': 3000,
                'nickname': 'QQ Nickname',
                'card': 'Group Card',
                'role': 'member',
            },
        }
    )

    class Bot:
        calls = 0

        async def get_group_info(self, group_id):
            self.calls += 1
            assert group_id == 2000
            return {'group_id': group_id, 'group_name': 'Cached Group'}

    monotonic = 1000.0
    monkeypatch.setattr('langbot.pkg.platform.sources.aiocqhttp.time.monotonic', lambda: monotonic)

    bot = Bot()
    converter = AiocqhttpEventConverter()

    first = await converter.target2yiri(event, bot)
    second = await converter.target2yiri(event, bot)

    assert first.sender.group.name == 'Cached Group'
    assert second.sender.group.name == 'Cached Group'
    assert bot.calls == 1


@pytest.mark.asyncio
async def test_group_message_group_name_cache_expires(monkeypatch):
    event = aiocqhttp.Event(
        {
            'post_type': 'message',
            'message_type': 'group',
            'message_id': 1000,
            'message': '',
            'time': 1776491725,
            'group_id': 2000,
            'sender': {
                'user_id': 3000,
                'nickname': 'QQ Nickname',
                'card': 'Group Card',
                'role': 'member',
            },
        }
    )
    now = 1000.0

    class Bot:
        calls = 0

        async def get_group_info(self, group_id):
            self.calls += 1
            return {'group_id': group_id, 'group_name': f'Group Name {self.calls}'}

    monkeypatch.setattr('langbot.pkg.platform.sources.aiocqhttp.time.monotonic', lambda: now)

    bot = Bot()
    converter = AiocqhttpEventConverter()

    first = await converter.target2yiri(event, bot)
    now = 4601.0
    second = await converter.target2yiri(event, bot)

    assert first.sender.group.name == 'Group Name 1'
    assert second.sender.group.name == 'Group Name 2'
    assert bot.calls == 2


@pytest.mark.asyncio
async def test_group_message_group_name_uses_placeholder_when_lookup_fails(monkeypatch):
    event = aiocqhttp.Event(
        {
            'post_type': 'message',
            'message_type': 'group',
            'message_id': 1000,
            'message': '',
            'time': 1776491725,
            'group_id': 2000,
            'sender': {
                'user_id': 3000,
                'nickname': 'QQ Nickname',
                'card': 'Group Card',
                'role': 'member',
            },
        }
    )
    now = 1000.0

    class Bot:
        calls = 0

        async def get_group_info(self, group_id):
            self.calls += 1
            raise RuntimeError('api unavailable')

    monkeypatch.setattr('langbot.pkg.platform.sources.aiocqhttp.time.monotonic', lambda: now)

    bot = Bot()
    converter = AiocqhttpEventConverter()

    converted = await converter.target2yiri(event, bot)
    cached_failure = await converter.target2yiri(event, bot)

    assert converted.sender.group.name == 'Group 2000'
    assert cached_failure.sender.group.name == 'Group 2000'
    assert bot.calls == 1


@pytest.mark.asyncio
async def test_group_message_group_name_retries_after_negative_cache_expires(monkeypatch):
    event = aiocqhttp.Event(
        {
            'post_type': 'message',
            'message_type': 'group',
            'message_id': 1000,
            'message': '',
            'time': 1776491725,
            'group_id': 2000,
            'sender': {
                'user_id': 3000,
                'nickname': 'QQ Nickname',
                'card': 'Group Card',
                'role': 'member',
            },
        }
    )
    now = 1000.0

    class Bot:
        calls = 0

        async def get_group_info(self, group_id):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError('api unavailable')
            return {'group_id': group_id, 'group_name': 'Recovered Group'}

    monkeypatch.setattr('langbot.pkg.platform.sources.aiocqhttp.time.monotonic', lambda: now)

    bot = Bot()
    converter = AiocqhttpEventConverter()

    failed = await converter.target2yiri(event, bot)
    now = 1061.0
    recovered = await converter.target2yiri(event, bot)

    assert failed.sender.group.name == 'Group 2000'
    assert recovered.sender.group.name == 'Recovered Group'
    assert bot.calls == 2
