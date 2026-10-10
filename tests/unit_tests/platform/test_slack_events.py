import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import urlencode

import pytest
from slack_sdk.signature import SignatureVerifier

from langbot.libs.slack_api.api import SlackClient
from langbot.libs.slack_api.slackevent import SlackEvent
from langbot.pkg.platform.adapters.slack.event_converter import SlackEventConverter
from langbot.pkg.api.http.service.slack_setup import manifest
from langbot.libs.slack_api.media import send_chain
from langbot_plugin.api.entities.builtin.platform import message as pm


def client():
    return SlackClient('test', 'secret', SimpleNamespace(error=AsyncMock(), warning=AsyncMock()), True)


async def test_thread_text_and_file_use_the_same_channel_and_thread():
    bot = client()
    bot.client = SimpleNamespace(
        chat_postMessage=AsyncMock(return_value={'ok': True, 'ts': '2.1'}),
        files_upload_v2=AsyncMock(return_value={'ok': True, 'files': [{'id': 'F1'}]}),
    )
    await send_chain(
        bot,
        'channel',
        'D1',
        pm.MessageChain(
            [
                pm.Plain(text='reply'),
                pm.File(name='test.txt', base64='dGVzdA=='),
            ]
        ),
        thread_ts='1.1',
    )
    bot.client.chat_postMessage.assert_awaited_once_with(channel='D1', text='reply', thread_ts='1.1')
    assert bot.client.files_upload_v2.call_args.kwargs['thread_ts'] == '1.1'
    assert bot.client.files_upload_v2.call_args.kwargs['channel'] == 'D1'


async def test_http_backpressure_does_not_mark_event_seen():
    bot = client()
    for index in range(100):
        assert bot._enqueue({'index': index}, str(index))
    assert not bot._enqueue({'event_id': 'overflow'}, 'overflow')
    assert 'overflow' not in bot.socket_seen
    await bot.close_socket()


@pytest.mark.parametrize(
    ('raw', 'expected'),
    [
        (
            {'type': 'message', 'subtype': 'message_changed', 'message': {'ts': '1.1', 'text': 'new', 'user': 'U1'}},
            'message.edited',
        ),
        ({'type': 'message', 'subtype': 'message_deleted', 'deleted_ts': '1.1'}, 'message.deleted'),
        (
            {'type': 'reaction_added', 'user': 'U1', 'reaction': 'thumbsup', 'item': {'type': 'message', 'ts': '1.1'}},
            'message.reaction',
        ),
        (
            {
                'type': 'reaction_removed',
                'user': 'U1',
                'reaction': 'thumbsup',
                'item': {'type': 'message', 'ts': '1.1'},
            },
            'message.reaction',
        ),
        ({'type': 'member_joined_channel', 'user': 'U1'}, 'group.member_joined'),
        ({'type': 'member_left_channel', 'user': 'U1'}, 'group.member_left'),
        ({'type': 'member_joined_channel', 'user': 'UBOT', 'inviter': 'U1'}, 'bot.invited_to_group'),
        ({'type': 'member_left_channel', 'user': 'UBOT'}, 'bot.removed_from_group'),
        ({'type': 'channel_rename', 'channel': {'id': 'C1', 'name': 'new'}}, 'group.info_updated'),
        ({'type': 'group_archive'}, 'group.info_updated'),
        ({'type': 'message', 'subtype': 'channel_topic', 'topic': 'new'}, 'group.info_updated'),
        ({'type': 'app_home_opened', 'user': 'U1', 'tab': 'home'}, 'platform.specific'),
        ({'type': 'app_uninstalled'}, 'platform.specific'),
        ({'type': 'tokens_revoked', 'tokens': {'bot': ['UBOT']}}, 'platform.specific'),
    ],
)
async def test_standard_events(raw, expected):
    event = await SlackEventConverter(bot_user_id='UBOT').target2yiri(
        SlackEvent({'event_id': 'delivery', 'event': {'channel': 'C1', 'channel_type': 'channel', **raw}})
    )
    assert event.type == expected
    if expected.startswith('message.'):
        assert event.message_id == '1.1'
        assert event.chat_id == 'C1'
    if expected == 'message.reaction':
        assert event.is_add == (raw['type'] == 'reaction_added')
    if expected == 'message.deleted':
        assert event.operator is None
    if expected == 'message.edited':
        assert 'new' in str(event.new_content)
    if raw['type'] == 'channel_rename':
        assert event.group.name == 'new'
        assert event.changed_fields == ['name']


async def test_channel_messages_are_not_duplicate_mentions_or_new_messages_on_edit():
    bot = client()
    bot._handle_message = AsyncMock()
    await bot.handle_payload({'event': {'type': 'message', 'channel_type': 'channel', 'text': '<@BOT> hello'}})
    bot._handle_message.assert_not_awaited()
    await bot.handle_payload({'event': {'type': 'app_mention', 'channel': 'C1', 'text': '<@BOT> hello'}})
    assert bot._handle_message.await_count == 1
    await bot.handle_payload({'event': {'type': 'message', 'channel_type': 'im', 'subtype': 'message_changed'}})
    assert bot._handle_message.call_args.args[1] == 'event'


@pytest.mark.parametrize('kind', ['block_actions', 'view_submission', 'view_closed', 'shortcut', 'message_action'])
async def test_interactions_dispatched_and_sanitized(kind):
    bot = client()
    handler = AsyncMock()
    bot.on_message('event')(handler)
    payload = {'type': kind, 'token': 'secret', 'response_url': 'secret-url', 'user': {'id': 'U1'}}
    await bot.handle_payload(payload)
    event = await SlackEventConverter().target2yiri(handler.call_args.args[0])
    assert event.action == f'slack.{kind}'
    assert 'token' not in event.data and 'response_url' not in event.data


async def test_http_signature_fast_ack_form_and_retry_dedup():
    bot = client()
    gate = asyncio.Event()

    async def process(_):
        await gate.wait()

    bot.handle_payload = AsyncMock(side_effect=process)

    def request(body, mime):
        stamp = str(int(time.time()))
        return SimpleNamespace(
            get_data=AsyncMock(return_value=body),
            mimetype=mime,
            headers={
                'X-Slack-Request-Timestamp': stamp,
                'X-Slack-Signature': SignatureVerifier('secret').generate_signature(timestamp=stamp, body=body),
            },
        )

    body = urlencode({'payload': json.dumps({'type': 'block_actions'})}).encode()
    try:
        async with bot.app.app_context():
            assert await bot._handle_callback_internal(request(body, 'application/x-www-form-urlencoded')) == ('', 200)
            invalid = request(body, 'application/x-www-form-urlencoded')
            invalid.headers['X-Slack-Signature'] = 'invalid'
            assert (await bot._handle_callback_internal(invalid))[1] == 401
            event_body = json.dumps({'event_id': 'E1', 'event': {'type': 'app_home_opened'}}).encode()
            await bot._handle_callback_internal(request(event_body, 'application/json'))
            await bot._handle_callback_internal(request(event_body, 'application/json'))
            assert bot.socket_queue.qsize() == 2
    finally:
        gate.set()
        await bot.close_socket()


async def test_socket_interactivity_ack_and_delivery():
    bot = client()
    socket = SimpleNamespace(send_socket_mode_response=AsyncMock())
    payload = {'type': 'view_submission'}
    request = SimpleNamespace(type='interactive', envelope_id='E1', payload=payload)
    await bot._socket_request(socket, request)
    await bot._socket_request(socket, request)
    assert bot.socket_queue.qsize() == 1
    socket.send_socket_mode_response.assert_awaited()
    assert await bot.socket_queue.get() == payload


@pytest.mark.parametrize('socket', [True, False])
def test_setup_complete_manifest(socket):
    result = manifest(
        'LangBot', 'https://example.com/bots/1', 'https://example.com/callback', events=True, socket_mode=socket
    )
    settings = result['settings']
    assert {
        'message.channels',
        'message.groups',
        'message.mpim',
        'reaction_added',
        'reaction_removed',
        'member_joined_channel',
        'member_left_channel',
        'app_home_opened',
        'app_uninstalled',
        'tokens_revoked',
    } <= set(settings['event_subscriptions']['bot_events'])
    assert 'reactions:read' in result['oauth_config']['scopes']['bot']
    assert settings['interactivity']['is_enabled']
    assert ('request_url' in settings['interactivity']) is not socket
    assert ('request_url' in settings['event_subscriptions']) is not socket
    assert 'interactivity' not in manifest('LangBot', '', '', events=False, socket_mode=socket)['settings']
