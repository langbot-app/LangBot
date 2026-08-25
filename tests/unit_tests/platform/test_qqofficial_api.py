"""Tests for QQ Official message and keyboard payload helpers."""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import langbot_plugin.api.entities.builtin.platform.message as platform_message

from langbot.libs.qq_official_api.api import (
    QQ_SELECT_ACTION_PREFIX,
    QQOfficialClient,
    build_keyboard_from_select_field,
    get_select_field_options,
    resolve_select_button_action,
)


def _select_form_data() -> dict:
    return {
        '_current_input_field': 'choice',
        'input_defs': [
            {
                'output_variable_name': 'choice',
                'type': 'select',
                'option_source': {'type': 'constant', 'value': ['A', 'B', 'C']},
            }
        ],
    }


def test_qq_select_field_builds_callback_buttons():
    keyboard = build_keyboard_from_select_field(_select_form_data(), buttons_per_row=2)

    rows = keyboard['content']['rows']
    assert [[button['render_data']['label'] for button in row['buttons']] for row in rows] == [
        ['A', 'B'],
        ['C'],
    ]
    assert rows[0]['buttons'][0]['action']['data'] == f'{QQ_SELECT_ACTION_PREFIX}0'
    assert rows[0]['buttons'][1]['action']['data'] == f'{QQ_SELECT_ACTION_PREFIX}1'


def test_qq_select_button_resolves_field_and_value():
    form_data = _select_form_data()

    assert get_select_field_options(form_data) == ('choice', ['A', 'B', 'C'])
    assert resolve_select_button_action(form_data, f'{QQ_SELECT_ACTION_PREFIX}1') == ('choice', 'B')
    assert resolve_select_button_action(form_data, f'{QQ_SELECT_ACTION_PREFIX}99') is None


@pytest.mark.asyncio
async def test_qq_seed_rejects_empty_secret_without_spinning():
    client = QQOfficialClient('', 'token', 'app-id', AsyncMock())

    with pytest.raises(ValueError, match='must not be empty'):
        await asyncio.wait_for(client.repeat_seed(''), timeout=0.1)


def test_qq_auxiliary_tasks_are_bounded():
    import langbot.pkg.core.app  # noqa: F401
    from langbot.pkg.platform.sources.qqofficial import QQOfficialAdapter

    adapter = QQOfficialAdapter.model_construct()
    adapter._background_tasks = {MagicMock(done=MagicMock(return_value=False)) for _ in range(100)}

    async def callback():
        raise AssertionError('rejected callback must not run')

    assert adapter._start_background_task(callback()) is False
    assert len(adapter._background_tasks) == 100


def test_qq_select_keyboard_fits_twenty_five_options():
    form_data = _select_form_data()
    form_data['input_defs'][0]['option_source']['value'] = [f'Option {idx}' for idx in range(25)]

    rows = build_keyboard_from_select_field(form_data)['content']['rows']

    assert len(rows) == 5
    assert all(len(row['buttons']) == 5 for row in rows)


def test_qq_non_select_field_does_not_build_keyboard():
    form_data = {
        '_current_input_field': 'comment',
        'input_defs': [{'output_variable_name': 'comment', 'type': 'paragraph'}],
    }

    assert build_keyboard_from_select_field(form_data)['content']['rows'] == []


def _stream_test_adapter():
    from langbot.pkg.platform.sources.qqofficial import QQOfficialAdapter

    adapter = QQOfficialAdapter.model_construct()
    adapter.logger = AsyncMock()
    adapter.bot = MagicMock()
    adapter.bot.send_stream_msg = AsyncMock(return_value={'id': 'stream-1'})
    adapter.bot.send_markdown_keyboard = AsyncMock(return_value={'id': 'message-1'})
    adapter.bot.send_private_text_msg = AsyncMock()
    adapter.bot.send_group_text_msg = AsyncMock()
    adapter.bot.send_private_markdown_msg = AsyncMock()
    adapter.bot.send_group_markdown_msg = AsyncMock()
    adapter.bot.send_channle_group_text_msg = AsyncMock()
    adapter.bot.send_channle_private_text_msg = AsyncMock()
    adapter.ap = None
    adapter._stream_ctx = {}
    adapter._stream_ctx_ts = {}
    adapter._fallback_text = {}
    adapter._fallback_text_ts = {}
    return adapter


@pytest.mark.asyncio
async def test_qq_stream_replace_mode_sends_complete_snapshots():
    adapter = _stream_test_adapter()
    adapter._stream_ctx['message-1'] = {
        'user_openid': 'user-1',
        'msg_id': 'source-1',
        'stream_msg_id': None,
        'msg_seq': 1,
        'index': 0,
        'last_update_ts': 0,
        'accumulated_text': '',
        'sent_length': 0,
        'session_started': False,
    }
    adapter._stream_ctx_ts['message-1'] = time.time()
    source = MagicMock()

    await adapter.reply_message_chunk(
        source,
        {'resp_message_id': 'message-1'},
        platform_message.MessageChain([platform_message.Plain(text='<think>one')]),
    )
    await adapter.reply_message_chunk(
        source,
        {'resp_message_id': 'message-1'},
        platform_message.MessageChain([platform_message.Plain(text='<think>one two')]),
        is_final=True,
    )

    assert [call.kwargs['content'] for call in adapter.bot.send_stream_msg.await_args_list] == [
        '<think>one',
        '<think>one two',
    ]


@pytest.mark.asyncio
async def test_qq_markdown_messages_use_markdown_payloads():
    requests = []

    def capture_request(request: httpx.Request) -> httpx.Response:
        requests.append((str(request.url), json.loads(request.content)))
        return httpx.Response(200, json={})

    client = QQOfficialClient('secret', 'token', 'app-id', AsyncMock())
    client.access_token = 'access-token'
    client.access_token_expiry_time = time.time() + 3600
    client._http_clients[None] = httpx.AsyncClient(transport=httpx.MockTransport(capture_request))

    try:
        await client.send_private_markdown_msg('user-1', '# Hello', msg_id='message-1', msg_seq=2)
        await client.send_group_markdown_msg('group-1', '* Hello', event_id='event-1', msg_seq=3)
    finally:
        await client.close()

    assert requests == [
        (
            'https://api.sgroup.qq.com/v2/users/user-1/messages',
            {'msg_type': 2, 'markdown': {'content': '# Hello'}, 'msg_seq': 2, 'msg_id': 'message-1'},
        ),
        (
            'https://api.sgroup.qq.com/v2/groups/group-1/messages',
            {'msg_type': 2, 'markdown': {'content': '* Hello'}, 'msg_seq': 3, 'event_id': 'event-1'},
        ),
    ]


@pytest.mark.asyncio
async def test_qq_markdown_rendering_switches_c2c_and_group_text_replies():
    adapter = _stream_test_adapter()
    adapter.config = {'enable-markdown-rendering': True}

    await adapter._send_c2c_or_group_text_reply('c2c', 'user-1', '# Hello', msg_id='message-1')
    await adapter._send_c2c_or_group_text_reply('group', 'group-1', '* Hello', event_id='event-1')

    adapter.bot.send_private_markdown_msg.assert_awaited_once_with(
        user_openid='user-1',
        content='# Hello',
        msg_id='message-1',
        event_id=None,
        msg_seq=1,
    )
    adapter.bot.send_group_markdown_msg.assert_awaited_once_with(
        group_openid='group-1',
        content='* Hello',
        msg_id=None,
        event_id='event-1',
        msg_seq=1,
    )
    adapter.bot.send_private_text_msg.assert_not_awaited()
    adapter.bot.send_group_text_msg.assert_not_awaited()


@pytest.mark.asyncio
async def test_qq_markdown_rendering_defaults_to_plain_text_replies():
    adapter = _stream_test_adapter()
    adapter.config = {}

    await adapter._send_c2c_or_group_text_reply('c2c', 'user-1', 'Hello')
    await adapter._send_c2c_or_group_text_reply('group', 'group-1', 'Hello')

    adapter.bot.send_private_text_msg.assert_awaited_once()
    adapter.bot.send_group_text_msg.assert_awaited_once()
    adapter.bot.send_private_markdown_msg.assert_not_awaited()
    adapter.bot.send_group_markdown_msg.assert_not_awaited()


@pytest.mark.asyncio
async def test_qq_markdown_rendering_does_not_affect_channel_messages():
    adapter = _stream_test_adapter()
    adapter.config = {'enable-markdown-rendering': True}
    message = platform_message.MessageChain([platform_message.Plain(text='# Hello')])

    channel_source = MagicMock()
    channel_source.t = 'AT_MESSAGE_CREATE'
    channel_source.channel_id = 'channel-1'
    channel_source.d_id = 'message-1'
    channel_event = MagicMock()
    channel_event.source_platform_object = channel_source
    await adapter.reply_message(channel_event, message)

    dm_source = MagicMock()
    dm_source.t = 'DIRECT_MESSAGE_CREATE'
    dm_source.guild_id = 'guild-1'
    dm_source.d_id = 'message-2'
    dm_event = MagicMock()
    dm_event.source_platform_object = dm_source
    await adapter.reply_message(dm_event, message)

    adapter.bot.send_channle_group_text_msg.assert_awaited_once_with('channel-1', '# Hello', 'message-1')
    adapter.bot.send_channle_private_text_msg.assert_awaited_once_with('guild-1', '# Hello', 'message-2')
    adapter.bot.send_private_markdown_msg.assert_not_awaited()
    adapter.bot.send_group_markdown_msg.assert_not_awaited()


@pytest.mark.asyncio
async def test_qq_non_streaming_fallback_keeps_latest_snapshot_only():
    from langbot.pkg.platform.sources.qqofficial import QQOfficialAdapter

    adapter = _stream_test_adapter()
    source = MagicMock()

    with patch.object(QQOfficialAdapter, 'reply_message', new=AsyncMock()) as reply_message:
        await adapter.reply_message_chunk(
            source,
            {'resp_message_id': 'message-1'},
            platform_message.MessageChain([platform_message.Plain(text='Hel')]),
        )
        await adapter.reply_message_chunk(
            source,
            {'resp_message_id': 'message-1'},
            platform_message.MessageChain([platform_message.Plain(text='Hello')]),
            is_final=True,
        )

    sent_chain = reply_message.await_args.args[1]
    assert str(sent_chain) == 'Hello'


@pytest.mark.asyncio
async def test_qq_text_field_prompt_keeps_form_content():
    from langbot.pkg.platform.sources.qqofficial import QQOfficialAdapter

    adapter = _stream_test_adapter()
    adapter._pending_forms = {}
    adapter._session_event_ids = {}
    adapter._anchor_msg_seq = {}
    source = MagicMock()
    source.d_id = 'source-1'
    source.t = 'C2C_MESSAGE_CREATE'
    event = MagicMock()
    event.source_platform_object = source
    event.sender.id = 'user-1'
    form_data = {
        '_current_input_field': 'us_input',
        'node_title': 'Manual input',
        'form_content': '1234\nEnter your question',
        'input_defs': [{'output_variable_name': 'us_input', 'type': 'paragraph'}],
        'actions': [{'id': 'yes', 'title': 'yes'}],
    }

    with patch.object(QQOfficialAdapter, '_resolve_target_from_event', return_value=('c2c', 'user-1')):
        await adapter._handle_form_chunk(event, platform_message.MessageChain([]), form_data)

    send_call = adapter.bot.send_markdown_keyboard.await_args.kwargs
    assert send_call['markdown_content'] == '### Manual input\n\n1234\nEnter your question'
    assert send_call['keyboard'] is None


@pytest.mark.asyncio
async def test_qq_select_click_enqueues_input_progress_query():
    import langbot.pkg.core.app  # noqa: F401
    from langbot.pkg.platform.sources.qqofficial import QQOfficialAdapter

    adapter = QQOfficialAdapter.model_construct()
    adapter.logger = AsyncMock()
    adapter.bot = MagicMock()
    adapter.bot.ack_interaction = AsyncMock()
    adapter.ap = MagicMock()
    adapter.ap.platform_mgr.bots = []
    adapter.ap.query_pool.add_query = AsyncMock()
    adapter._pending_forms = {
        'group_group-1': {
            'form_data': {
                **_select_form_data(),
                'form_token': 'token-1',
                'workflow_run_id': 'run-1',
                'node_title': 'Review',
                'actions': [{'id': 'approve', 'title': 'Approve'}],
            },
            'sender_id': 'initiator-1',
            'posted_at': time.time(),
        }
    }
    adapter._session_event_ids = {}
    adapter._anchor_msg_seq = {}

    await adapter._handle_interaction_create(
        {
            'id': 'interaction-1',
            'chat_type': 1,
            'group_openid': 'group-1',
            'member_openid': 'reviewer-2',
            'data': {'resolved': {'button_data': f'{QQ_SELECT_ACTION_PREFIX}1'}},
        },
        ws_event_id='event-1',
    )
    await asyncio.sleep(0)

    call = adapter.ap.query_pool.add_query.await_args
    form_action = call.kwargs['variables']['_dify_form_action']
    assert call.kwargs['launcher_id'] == 'group-1'
    assert call.kwargs['sender_id'] == 'reviewer-2'
    assert form_action['action_id'] == ''
    assert form_action['inputs'] == {'select': 'B'}
    assert form_action['_current_input_field'] == 'choice'
    assert form_action['_input_progress'] is True
    adapter.bot.ack_interaction.assert_awaited_once_with('interaction-1', code=0)
