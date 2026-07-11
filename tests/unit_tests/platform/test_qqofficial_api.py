"""Tests for QQ Official keyboard payload helpers."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import langbot_plugin.api.entities.builtin.platform.message as platform_message

from langbot.libs.qq_official_api.api import (
    QQ_SELECT_ACTION_PREFIX,
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
    adapter.ap = None
    adapter._stream_ctx = {}
    adapter._stream_ctx_ts = {}
    adapter._fallback_text = {}
    adapter._fallback_text_ts = {}
    return adapter


@pytest.mark.asyncio
async def test_qq_stream_uses_cumulative_chunks_as_snapshots():
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
        ' two',
    ]


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
