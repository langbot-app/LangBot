"""Full-group gateway messages retain group identity and passive replies."""

import base64
import json
import time
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from quart import Quart, request

import langbot.pkg.core.app  # noqa: F401 -- initialize legacy platform registration
from langbot.pkg.platform.adapters.qqofficial.adapter import QQOfficialAdapter
from langbot.pkg.platform.sources.qqofficial import QQOfficialAdapter as LegacyQQOfficialAdapter
from langbot_plugin.api.definition.abstract.platform.event_logger import AbstractEventLogger
from langbot_plugin.api.entities.builtin.platform import entities, events, message
from langbot.pkg.utils import httpclient


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.parametrize('adapter_class', [QQOfficialAdapter, LegacyQQOfficialAdapter]),
    pytest.mark.parametrize('transport', ['gateway', 'webhook']),
]
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')


def group_payload(content='hello'):
    return {
        'id': 'message-one',
        'group_openid': 'group-one',
        'timestamp': '2026-10-24T12:00:00+0800',
        'content': content,
        'author': {'member_openid': 'member-one'},
        'attachments': [],
    }


async def receive_message(monkeypatch, adapter_class, transport, event_type, payload, *, form_data=None):
    received, outbound = [], []
    adapter = adapter_class(
        {'appid': 'fixture-app', 'secret': 'fixture-secret', 'token': '', 'enable-webhook': transport == 'webhook'},
        Mock(spec=AbstractEventLogger),
    )
    adapter.bot.access_token = 'fixture-token'
    adapter.bot.access_token_expiry_time = time.time() + 3600

    async def gateway(on_event, on_ready, on_error):
        await on_event(event_type, payload)

    monkeypatch.setattr(adapter.bot, 'connect_gateway_loop', gateway)
    real_client = httpx.AsyncClient

    async def respond(request):
        outbound.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={'id': 'reply-one'}, request=request)

    def client(*args, **kwargs):
        return real_client(*args, **kwargs, transport=httpx.MockTransport(respond))

    monkeypatch.setattr(httpx, 'AsyncClient', client)

    async def listener(event, active_adapter):
        received.append(event)
        reply = message.MessageChain([message.Plain(text='fixture reply')])
        if form_data is None:
            await active_adapter.reply_message(event, reply)
        else:
            await active_adapter.reply_message_chunk(event, SimpleNamespace(_form_data=form_data), reply, is_final=True)

    listener_type = events.MessageReceivedEvent
    if adapter_class is LegacyQQOfficialAdapter:
        listener_type = events.FriendMessage if event_type == 'C2C_MESSAGE_CREATE' else events.GroupMessage
    adapter.register_listener(listener_type, listener)
    try:
        if transport == 'gateway':
            await adapter.run_async()
        else:
            app = Quart(__name__)

            @app.post('/qq')
            async def callback():
                return await adapter.handle_unified_webhook('fixture-bot', '', request)

            response = await app.test_client().post('/qq', json={'op': 0, 't': event_type, 'd': payload})
            assert response.status_code == 200
    finally:
        await adapter.kill()
    return received, outbound


async def test_unmentioned_full_group_message_retains_identity_and_passive_reply(monkeypatch, adapter_class, transport):
    received, outbound = await receive_message(
        monkeypatch, adapter_class, transport, 'GROUP_MESSAGE_CREATE', group_payload()
    )
    assert len(received) == 1
    event = received[0]
    assert event.sender.id == 'member-one'
    assert event.group.id == 'group-one'
    if isinstance(event, events.MessageReceivedEvent):
        assert event.chat_type == entities.ChatType.GROUP
        assert event.chat_id == 'group-one'
    assert event.source_platform_object.t == 'GROUP_MESSAGE_CREATE'
    assert not any(isinstance(component, message.At) for component in event.message_chain)
    assert [component.text for component in event.message_chain if isinstance(component, message.Plain)] == ['hello']
    assert len(outbound) == 1
    assert outbound[0][0] == '/v2/groups/group-one/messages'
    assert outbound[0][1]['msg_id'] == 'message-one'


@pytest.mark.parametrize(
    'key,content,expected',
    [
        ('id', '<@bot-one> /help', ' /help'),
        ('member_openid', '/help <@!bot-one>', '/help '),
        ('openid', '<@other-one> <@bot-one> help', '<@other-one>  help'),
    ],
)
async def test_native_self_mention_in_full_group_mode_still_marks_bot_and_strips_token(
    monkeypatch, adapter_class, transport, key, content, expected
):
    payload = group_payload(content)
    payload['mentions'] = [{key: 'bot-one', 'is_you': True}]
    received, outbound = await receive_message(monkeypatch, adapter_class, transport, 'GROUP_MESSAGE_CREATE', payload)
    assert len(received) == 1
    chain = received[0].message_chain
    expected_target = 'fixture-app' if adapter_class is QQOfficialAdapter else 'justbot'
    assert [component.target for component in chain if isinstance(component, message.At)] == [expected_target]
    assert [component.text for component in chain if isinstance(component, message.Plain)] == [expected]
    assert received[0].source_platform_object.t == 'GROUP_MESSAGE_CREATE'
    assert len(outbound) == 1


@pytest.mark.parametrize(
    'mentions',
    [
        None,
        {'id': 'bot-one', 'is_you': True},
        [None, 'bot-one'],
        [{'id': 'bot-one', 'bot': True}],
        [{'id': 'bot-one', 'is_you': False}],
        [{'id': 'bot-one', 'is_you': 1}],
        [{'id': 'bot-one', 'is_you': 'true'}],
        [{'id': 'other-one', 'is_you': True}],
        [{'id': '<@all>', 'is_you': True}],
        [{'id': 'x' * 129, 'is_you': True}],
    ],
)
async def test_other_or_unverified_mentions_do_not_authorize_bot_response(
    monkeypatch, adapter_class, transport, mentions
):
    content = '<@bot-one> @fixture-app /help'
    payload = group_payload(content)
    payload.update(mentions=mentions, is_at_bot=True, bot_account_id='untrusted')
    received, _ = await receive_message(monkeypatch, adapter_class, transport, 'GROUP_MESSAGE_CREATE', payload)
    assert len(received) == 1
    assert not any(isinstance(component, message.At) for component in received[0].message_chain)
    assert [component.text for component in received[0].message_chain if isinstance(component, message.Plain)] == [
        content
    ]


async def test_group_image_without_mention_remains_an_image_without_at(monkeypatch, adapter_class, transport):
    class Download:
        headers = {'Content-Length': str(len(PNG))}

        def raise_for_status(self):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def iter_chunked(self, size):
            yield PNG

        @property
        def content(self):
            return self

    downloads = []

    def get(url):
        downloads.append(url)
        return Download()

    monkeypatch.setattr(httpclient, 'get_session', lambda: SimpleNamespace(get=get))
    payload = group_payload('')
    payload['attachments'] = [{'url': 'https://images.example/image.png', 'content_type': 'image/png'}]
    received, outbound = await receive_message(monkeypatch, adapter_class, transport, 'GROUP_MESSAGE_CREATE', payload)
    assert len(received) == 1
    assert not any(isinstance(component, message.At) for component in received[0].message_chain)
    images = [component for component in received[0].message_chain if isinstance(component, message.Image)]
    assert len(images) == 1 and images[0].url == 'https://images.example/image.png'
    assert base64.b64decode(images[0].base64.split(',')[-1]) == PNG
    assert downloads == ['https://images.example/image.png']
    assert len(outbound) == 1 and outbound[0][1]['msg_id'] == 'message-one'


@pytest.mark.parametrize('author', [{'openid': 'old-member'}, {'member_openid': 'member-one', 'openid': 'old-member'}])
async def test_member_id_supports_legacy_alias_and_prefers_canonical_field(
    monkeypatch, adapter_class, transport, author
):
    payload = group_payload()
    payload['author'] = author
    received, _ = await receive_message(monkeypatch, adapter_class, transport, 'GROUP_MESSAGE_CREATE', payload)
    assert received[0].sender.id == author.get('member_openid', 'old-member')


async def test_existing_at_only_mode_still_marks_the_bot(monkeypatch, adapter_class, transport):
    received, outbound = await receive_message(
        monkeypatch, adapter_class, transport, 'GROUP_AT_MESSAGE_CREATE', group_payload('/help')
    )
    expected_target = 'fixture-app' if adapter_class is QQOfficialAdapter else 'justbot'
    assert [component.target for component in received[0].message_chain if isinstance(component, message.At)] == [
        expected_target
    ]
    assert len(outbound) == 1 and outbound[0][1]['msg_id'] == 'message-one'


async def test_private_message_still_uses_its_original_reply_target(monkeypatch, adapter_class, transport):
    payload = group_payload()
    payload['author'] = {'user_openid': 'private-one'}
    payload.pop('group_openid')
    received, outbound = await receive_message(monkeypatch, adapter_class, transport, 'C2C_MESSAGE_CREATE', payload)
    assert received[0].sender.id == 'private-one'
    assert not any(isinstance(component, message.At) for component in received[0].message_chain)
    assert outbound[0][0] == '/v2/users/private-one/messages'
    assert outbound[0][1]['msg_id'] == 'message-one'
