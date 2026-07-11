"""Tests for Telegram Dify form callback helpers."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import ForceReply

import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
from langbot.pkg.platform.sources.telegram import (
    TelegramAdapter,
    _telegram_form_action_from_callback,
    _telegram_select_field_options,
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


def test_telegram_select_field_options_are_extracted():
    assert _telegram_select_field_options(_select_form_data()) == ('choice', ['A', 'B', 'C'])


def test_telegram_select_callback_becomes_input_progress():
    assert _telegram_form_action_from_callback({'f': 1, 'x': 1}) == {
        'action_id': '',
        'inputs': {'select': '1'},
        '_input_progress': True,
    }


def test_telegram_action_callback_remains_final_action():
    assert _telegram_form_action_from_callback({'f': 1, 'a': 'approve'}) == {
        'action_id': 'approve',
        'inputs': {},
    }


def test_telegram_invalid_select_callback_is_rejected():
    assert _telegram_form_action_from_callback({'f': 1, 'x': -1}) is None
    assert _telegram_form_action_from_callback({'f': 1, 'x': 'invalid'}) is None


@pytest.mark.asyncio
async def test_telegram_select_field_sends_two_column_inline_keyboard():
    bot = MagicMock()
    bot.send_message = AsyncMock()
    adapter = TelegramAdapter.model_construct(bot=bot, config={}, msg_stream_id={}, seq=1, listeners={})
    adapter._form_action_titles = {}

    update = MagicMock()
    update.effective_chat.id = 123
    update.effective_message.message_thread_id = None
    event = platform_events.FriendMessage(
        sender=platform_entities.Friend(id='user-1', nickname='', remark=''),
        message_chain=platform_message.MessageChain([]),
        source_platform_object=update,
    )
    form_data = {
        **_select_form_data(),
        'node_title': 'Review',
        'form_content': 'Choose one',
        'workflow_run_id': 'workflow-run-12345678',
        'actions': [{'id': 'approve', 'title': 'Approve'}],
    }

    await adapter._send_form_action_buttons(event, form_data)

    args = bot.send_message.await_args.kwargs
    rows = args['reply_markup'].inline_keyboard
    assert [[button.text for button in row] for row in rows] == [['A', 'B'], ['C']]
    callback_data = rows[0][1].callback_data
    assert len(callback_data.encode('utf-8')) <= 64
    assert json.loads(callback_data)['x'] == 1
    assert callback_data in adapter._form_action_titles


@pytest.mark.asyncio
async def test_telegram_text_field_does_not_show_action_buttons():
    bot = MagicMock()
    bot.send_message = AsyncMock()
    adapter = TelegramAdapter.model_construct(bot=bot, config={}, msg_stream_id={}, seq=1, listeners={})
    adapter._form_action_titles = {}

    update = MagicMock()
    update.effective_chat.id = 123
    update.effective_message.message_thread_id = None
    event = platform_events.FriendMessage(
        sender=platform_entities.Friend(id='user-1', nickname='', remark=''),
        message_chain=platform_message.MessageChain([]),
        source_platform_object=update,
    )
    form_data = {
        '_current_input_field': 'us_input',
        'input_defs': [{'output_variable_name': 'us_input', 'type': 'paragraph'}],
        'node_title': '人工介入',
        'form_content': 'us_input (paragraph): reply "us_input: <value>"',
        'workflow_run_id': 'workflow-run-12345678',
        'actions': [{'id': 'yes', 'title': 'yes'}, {'id': 'no', 'title': 'no'}],
    }

    await adapter._send_form_action_buttons(event, form_data)

    args = bot.send_message.await_args.kwargs
    assert isinstance(args['reply_markup'], ForceReply)
    assert args['reply_markup'].selective is False
    assert args['reply_markup'].input_field_placeholder == 'us_input'
    assert 'Please reply' not in args['text']
    assert args['text'].startswith('[人工介入]')
    assert 'us_input (paragraph)' in args['text']
    assert adapter._form_action_titles == {}
