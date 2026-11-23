"""Unit coverage for the LINE Omni adapter (unified webhook mode)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import pathlib

import pytest
import yaml
from linebot.v3.messaging import PushMessageRequest, ReplyMessageRequest
from linebot.v3.webhook import WebhookParser

from langbot.pkg.platform.adapters.line.adapter import LineAdapter
from langbot.pkg.platform.adapters.line.errors import NotSupportedError
from langbot.pkg.platform.adapters.line.event_converter import LineEventConverter
from langbot.pkg.platform.adapters.line.message_converter import LineMessageConverter
from langbot_plugin.api.definition.abstract.platform.event_logger import AbstractEventLogger
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message

SECRET = 'test-channel-secret'
TOKEN = 'test-channel-access-token'
PLATFORM_ROOT = pathlib.Path(__file__).parents[3] / 'src/langbot/pkg/platform'


class DummyLogger(AbstractEventLogger):
    def __init__(self):
        self.lines: list[tuple[str, str]] = []

    async def info(self, text, images=None, message_session_id=None, no_throw=True):
        self.lines.append(('info', str(text)))

    async def debug(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def warning(self, text, images=None, message_session_id=None, no_throw=True):
        self.lines.append(('warning', str(text)))

    async def error(self, text, images=None, message_session_id=None, no_throw=True):
        self.lines.append(('error', str(text)))


class DummyMessagingApi:
    def __init__(self, fail_reply: bool = False):
        self.push_requests: list[PushMessageRequest] = []
        self.reply_requests: list[ReplyMessageRequest] = []
        self.fail_reply = fail_reply
        self.leaved_groups: list[str] = []

    def push_message(self, request):
        self.push_requests.append(request)
        return {'sent': len(request.messages)}

    def reply_message(self, request):
        if self.fail_reply:
            raise RuntimeError('reply token expired')
        self.reply_requests.append(request)
        return {'sent': len(request.messages)}

    def get_bot_info(self):
        return type(
            'BotInfo', (), {'user_id': 'Ubot', 'basic_id': '@bot', 'display_name': 'Bot', 'chat_mode': 'chat'}
        )()

    def get_profile(self, user_id):
        return type(
            'Profile',
            (),
            {'user_id': user_id, 'display_name': 'Alice', 'picture_url': 'https://img/1.png', 'status_message': None},
        )()

    def get_group_summary(self, group_id):
        return type('Summary', (), {'group_id': group_id, 'group_name': 'Team', 'picture_url': None})()

    def leave_group(self, group_id):
        self.leaved_groups.append(group_id)


class DummyBlobApi:
    def __init__(self, content: bytes = b'image-bytes'):
        self.content = content
        self.requested: list[str] = []

    def get_message_content(self, message_id):
        self.requested.append(message_id)
        return self.content


class DummyApiClient:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class DummyHeaders(dict):
    def get(self, key, default=None):
        return dict.get(self, key, default)


class DummyRequest:
    def __init__(self, body: str, signature: str | None):
        self.headers = DummyHeaders({} if signature is None else {'X-Line-Signature': signature})
        self._body = body

    async def get_data(self, as_text: bool = False):
        return self._body if as_text else self._body.encode()


def sign(body: str, secret: str = SECRET) -> str:
    return base64.b64encode(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()).decode()


def message_event(
    *,
    text: str = 'hello',
    source: dict | None = None,
    reply_token: str = 'reply-token-1',
    message: dict | None = None,
) -> dict:
    return {
        'type': 'message',
        'mode': 'active',
        'timestamp': 1730000000000,
        'webhookEventId': '01HWEBHOOKID',
        'deliveryContext': {'isRedelivery': False},
        'source': source or {'type': 'user', 'userId': 'U-user-1'},
        'replyToken': reply_token,
        'message': message or {'id': 'msg-1', 'type': 'text', 'text': text, 'quoteToken': 'quote-1'},
    }


def webhook_body(*events: dict) -> str:
    return json.dumps({'destination': 'Ubot', 'events': list(events)})


def build_adapter(logger: DummyLogger | None = None) -> LineAdapter:
    return LineAdapter(
        config={'channel_access_token': TOKEN, 'channel_secret': SECRET},
        logger=logger or DummyLogger(),
    )


class EventSink:
    def __init__(self):
        self.events: list[platform_events.Event] = []

    async def __call__(self, event, adapter):
        self.events.append(event)


async def dispatch(adapter: LineAdapter, body: str, signature: str | None = None):
    response = await adapter.handle_unified_webhook(
        bot_uuid='bot-uuid', path='', request=DummyRequest(body, sign(body) if signature is None else signature)
    )
    pending = list(adapter.background_tasks)
    if pending:
        await asyncio_gather(pending)
    return response


async def asyncio_gather(tasks):
    import asyncio

    await asyncio.gather(*tasks, return_exceptions=True)


def parse_events(body: str) -> list:
    return WebhookParser(SECRET).parse(body, sign(body))


def test_manifest_is_discoverable_and_keeps_legacy_config():
    manifest = yaml.safe_load((PLATFORM_ROOT / 'adapters/line/manifest.yaml').read_text(encoding='utf-8'))
    legacy = yaml.safe_load((PLATFORM_ROOT / 'sources/line.yaml').read_text(encoding='utf-8'))
    assert manifest['metadata']['name'] == 'line-omni'
    assert manifest['execution']['python'] == {'path': './adapter.py', 'attr': 'LineAdapter'}
    assert {field['name'] for field in legacy['spec']['config']} <= {
        field['name'] for field in manifest['spec']['config']
    }
    assert manifest['spec']['help_links'] == legacy['spec']['help_links']
    assert 'message.received' in manifest['spec']['supported_events']
    assert (PLATFORM_ROOT / 'adapters/line' / manifest['metadata']['icon']).is_file()


def test_adapter_requires_credentials():
    with pytest.raises(ValueError, match='channel_access_token'):
        LineAdapter(config={'channel_secret': SECRET}, logger=DummyLogger())


@pytest.mark.asyncio
async def test_webhook_rejects_missing_and_invalid_signature():
    adapter = build_adapter()
    body = webhook_body(message_event())
    assert (await adapter.handle_unified_webhook('bot', '', DummyRequest(body, None))).status_code == 400
    assert (await adapter.handle_unified_webhook('bot', '', DummyRequest(body, 'bogus'))).status_code == 400


@pytest.mark.asyncio
async def test_webhook_dispatches_message_received_event():
    adapter = build_adapter()
    sink = EventSink()
    adapter.register_listener(platform_events.MessageReceivedEvent, sink)

    response = await dispatch(adapter, webhook_body(message_event(text='hi there')))

    assert response.status_code == 200
    assert len(sink.events) == 1
    event = sink.events[0]
    assert isinstance(event, platform_events.MessageReceivedEvent)
    assert event.adapter_name == 'line-omni'
    assert event.chat_type == platform_entities.ChatType.PRIVATE
    assert event.chat_id == 'U-user-1'
    assert event.message_id == 'msg-1'
    assert [type(component) for component in event.message_chain] == [platform_message.Source, platform_message.Plain]
    assert event.message_chain[1].text == 'hi there'


@pytest.mark.asyncio
async def test_webhook_serves_legacy_listeners_and_ignores_self_messages():
    adapter = build_adapter()
    adapter.bot_account_id = 'Ubot'
    legacy_sink = EventSink()
    adapter.register_listener(platform_events.FriendMessage, legacy_sink)

    await dispatch(adapter, webhook_body(message_event(source={'type': 'user', 'userId': 'Ubot'})))
    assert legacy_sink.events == []

    await dispatch(adapter, webhook_body(message_event(source={'type': 'user', 'userId': 'U-user-9'})))
    assert len(legacy_sink.events) == 1
    assert isinstance(legacy_sink.events[0], platform_events.FriendMessage)
    assert legacy_sink.events[0].sender.id == 'U-user-9'


@pytest.mark.asyncio
async def test_group_message_uses_group_chat_identity():
    events = parse_events(
        webhook_body(message_event(source={'type': 'group', 'groupId': 'C-group', 'userId': 'U-user-2'}))
    )
    event = await LineEventConverter().target2yiri(events[0])

    assert event.chat_type == platform_entities.ChatType.GROUP
    assert event.chat_id == 'C-group'
    assert event.group.id == 'C-group'
    assert event.sender.id == 'U-user-2'


@pytest.mark.asyncio
async def test_unsend_becomes_message_deleted():
    body = webhook_body(
        {
            'type': 'unsend',
            'mode': 'active',
            'timestamp': 1730000000000,
            'webhookEventId': '01HUNSEND',
            'deliveryContext': {'isRedelivery': False},
            'source': {'type': 'user', 'userId': 'U-user-1'},
            'unsend': {'messageId': 'msg-9'},
        }
    )
    event = await LineEventConverter().target2yiri(parse_events(body)[0])

    assert isinstance(event, platform_events.MessageDeletedEvent)
    assert event.message_id == 'msg-9'
    assert event.chat_id == 'U-user-1'


@pytest.mark.asyncio
async def test_follow_and_postback_stay_platform_specific():
    follow = webhook_body(
        {
            'type': 'follow',
            'mode': 'active',
            'timestamp': 1730000000000,
            'webhookEventId': '01HFOLLOW',
            'deliveryContext': {'isRedelivery': False},
            'source': {'type': 'user', 'userId': 'U-user-3'},
            'replyToken': 'token',
            'follow': {'isUnblocked': True},
        }
    )
    follow_event = await LineEventConverter().target2yiri(parse_events(follow)[0])
    assert follow_event.type == 'platform.specific'
    assert follow_event.action == 'line.follow'

    postback = webhook_body(
        {
            'type': 'postback',
            'mode': 'active',
            'timestamp': 1730000000000,
            'webhookEventId': '01HPOSTBACK',
            'deliveryContext': {'isRedelivery': False},
            'source': {'type': 'group', 'groupId': 'C-group', 'userId': 'U-user-4'},
            'replyToken': 'token',
            'postback': {'data': 'action=buy'},
        }
    )
    postback_event = await LineEventConverter().target2yiri(parse_events(postback)[0])
    assert postback_event.action == 'line.postback'
    assert postback_event.data['data'] == 'action=buy'
    assert postback_event.data['chat_id'] == 'C-group'


@pytest.mark.asyncio
async def test_member_joined_maps_group_and_member():
    body = webhook_body(
        {
            'type': 'memberJoined',
            'mode': 'active',
            'timestamp': 1730000000000,
            'webhookEventId': '01HJOINED',
            'deliveryContext': {'isRedelivery': False},
            'source': {'type': 'group', 'groupId': 'C-group'},
            'replyToken': 'token',
            'joined': {'members': [{'type': 'user', 'userId': 'U-user-5'}]},
        }
    )
    event = await LineEventConverter().target2yiri(parse_events(body)[0])

    assert isinstance(event, platform_events.MemberJoinedEvent)
    assert event.group.id == 'C-group'
    assert event.member.id == 'U-user-5'


@pytest.mark.asyncio
async def test_text_mention_becomes_at_component_for_the_bot():
    body = webhook_body(
        message_event(
            text='@bot hello',
            message={
                'id': 'msg-2',
                'type': 'text',
                'quoteToken': 'quote-2',
                'text': '@bot hello',
                'mention': {
                    'mentionees': [
                        {'index': 0, 'length': 4, 'userId': 'Ubot', 'isSelf': True, 'type': 'user'},
                    ]
                },
            },
        )
    )
    event = await LineEventConverter(bot_account_id='Ubot').target2yiri(parse_events(body)[0])

    at_components = [component for component in event.message_chain if isinstance(component, platform_message.At)]
    assert len(at_components) == 1
    assert at_components[0].target == 'Ubot'
    assert at_components[0].display == 'bot'


@pytest.mark.asyncio
async def test_image_message_is_downloaded_through_the_blob_api():
    blob = DummyBlobApi(b'jpeg-bytes')
    body = webhook_body(
        message_event(
            message={
                'id': 'msg-3',
                'type': 'image',
                'quoteToken': 'quote-3',
                'contentProvider': {'type': 'line'},
            }
        )
    )
    event = await LineEventConverter(blob_api=blob).target2yiri(parse_events(body)[0])

    image = event.message_chain[1]
    assert isinstance(image, platform_message.Image)
    assert image.base64 == f'data:image/jpeg;base64,{base64.b64encode(b"jpeg-bytes").decode()}'
    assert blob.requested == ['msg-3']


@pytest.mark.asyncio
async def test_outgoing_chain_builds_line_messages():
    chain = platform_message.MessageChain(
        [
            platform_message.Source(id='msg-1', time=__import__('datetime').datetime.now()),
            platform_message.Plain(text='hello'),
            platform_message.At(target='U-user-1', display='Alice'),
        ]
    )
    messages = await LineMessageConverter.yiri2target(chain)

    assert [message.type for message in messages] == ['text', 'text']
    assert messages[0].text == 'hello'
    assert messages[1].text == '@Alice'


@pytest.mark.asyncio
async def test_outgoing_image_requires_a_public_url():
    chain = platform_message.MessageChain([platform_message.Image(base64='ZGly')])
    with pytest.raises(NotSupportedError):
        await LineMessageConverter.yiri2target(chain)


@pytest.mark.asyncio
async def test_send_message_batches_five_messages_per_request():
    adapter = build_adapter()
    adapter.bot = DummyMessagingApi()
    chain = platform_message.MessageChain([platform_message.Plain(text='x'), platform_message.Plain(text='y')] * 3)

    result = await adapter.send_message('person', 'U-user-1', chain)

    assert [len(request.messages) for request in adapter.bot.push_requests] == [5, 1]
    assert all(request.to == 'U-user-1' for request in adapter.bot.push_requests)
    assert result.raw == {'sent': 6, 'target_id': 'U-user-1'}


@pytest.mark.asyncio
async def test_reply_uses_reply_token_then_falls_back_to_push():
    adapter = build_adapter()
    event = await LineEventConverter().target2yiri(parse_events(webhook_body(message_event()))[0])
    chain = platform_message.MessageChain([platform_message.Plain(text='pong')])

    adapter.bot = DummyMessagingApi()
    await adapter.reply_message(event, chain)
    assert adapter.bot.reply_requests[0].reply_token == 'reply-token-1'
    assert adapter.bot.push_requests == []

    adapter.bot = DummyMessagingApi(fail_reply=True)
    await adapter.reply_message(event, chain)
    assert adapter.bot.push_requests[0].to == 'U-user-1'


@pytest.mark.asyncio
async def test_profile_and_group_apis_use_the_messaging_api():
    adapter = build_adapter()
    adapter.bot = DummyMessagingApi()

    user = await adapter.get_user_info('U-user-1')
    group = await adapter.get_group_info('C-group')
    await adapter.leave_group('C-group')

    assert user.id == 'U-user-1'
    assert user.nickname == 'Alice'
    assert group.name == 'Team'
    assert adapter.bot.leaved_groups == ['C-group']
    with pytest.raises(NotSupportedError):
        await adapter.get_group_member_list('C-group')


@pytest.mark.asyncio
async def test_call_platform_api_dispatches_and_rejects_unknown_actions():
    adapter = build_adapter()
    adapter.bot = DummyMessagingApi()

    info = await adapter.call_platform_api('get_bot_info', {})
    assert info['user_id'] == 'Ubot'
    with pytest.raises(NotSupportedError):
        await adapter.call_platform_api('not_a_line_action', {})


@pytest.mark.asyncio
async def test_kill_closes_the_api_client():
    adapter = build_adapter()
    api_client = DummyApiClient()
    adapter.api_client = api_client

    assert await adapter.kill() is True
    assert api_client.closed is True
    assert adapter.background_tasks == set()
