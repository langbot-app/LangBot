"""Tests for Telegram message conversion and Dify form callback helpers."""

import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import ForceReply, Message

import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message

from langbot.pkg.platform.sources.telegram import (
    TelegramAdapter,
    TelegramMessageConverter,
    _decode_telegram_base64_limited,
    _telegram_form_action_from_callback,
    _telegram_select_field_options,
)


def test_telegram_base64_decode_is_bounded(monkeypatch):
    import langbot.pkg.platform.sources.telegram as telegram_module

    monkeypatch.setattr(telegram_module, '_MAX_TELEGRAM_MEDIA_BYTES', 4)

    with pytest.raises(ValueError, match='exceeds'):
        _decode_telegram_base64_limited('A' * 12)


TELEGRAM_BOT_TOKEN = '123456789:AAExampleBotTokenThatMustNotLeak'
TELEGRAM_FILE_URL = f'https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/photos/file_0.jpg'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('text', 'entities', 'expected_text', 'mentioned'),
    [
        ('hello', [], 'hello', False),
        ('hello @test_bot', [('mention', 6, 9)], 'hello ', True),
        ('😀 @TEST_BOT!', [('mention', 3, 9)], '😀 !', True),
        ('/help@TeSt_BoT', [('bot_command', 0, 14)], '/help', True),
        ('@test_bot_extra hello', [('mention', 0, 15)], '@test_bot_extra hello', False),
        ('@test_bot', [('code', 0, 9)], '@test_bot', False),
        ('@test_bot', [('pre', 0, 9)], '@test_bot', False),
        ('https://example.com/@test_bot', [('url', 0, 29)], 'https://example.com/@test_bot', False),
        ('/help@test_bot', [('bot_command', 0, 14)], '/help', True),
        ('/help@test_bot_extra', [('bot_command', 0, 20)], '/help@test_bot_extra', False),
        ('😀 @test_bot!', [('mention', 3, 9)], '😀 !', True),
        (
            '@test_bot @test_bot',
            [('mention', 0, 9), ('code', 10, 9)],
            ' @test_bot',
            True,
        ),
        (
            '@test_bot 😀 @test_bot',
            [('mention', 0, 9), ('mention', 13, 9)],
            ' 😀 ',
            True,
        ),
    ],
)
async def test_telegram_mentions_use_entity_boundaries(text, entities, expected_text, mentioned):
    message = Message.de_json(
        {
            'message_id': 10,
            'date': 1700000000,
            'chat': {'id': 123, 'type': 'private'},
            'text': text,
            'entities': [{'type': kind, 'offset': offset, 'length': length} for kind, offset, length in entities],
        },
        None,
    )

    chain = await TelegramMessageConverter.target2yiri(message, None, 'test_bot')

    expected = [platform_message.Plain(text=expected_text)]
    if mentioned:
        expected.insert(0, platform_message.At(target='test_bot'))
    assert list(chain) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize('media_type', ['photo', 'voice', 'document'])
@pytest.mark.parametrize(
    ('caption', 'caption_entities', 'expected_text', 'mentioned'),
    [
        ('😀 @test_bot', [('mention', 3, 9)], '😀 ', True),
        ('😀 @TEST_BOT', [('mention', 3, 9)], '😀 ', True),
        ('😀 @test_bot', [('code', 3, 9)], '😀 @test_bot', False),
        ('😀 @test_bot', [('pre', 3, 9)], '😀 @test_bot', False),
        ('https://example.com/@test_bot', [('url', 0, 29)], 'https://example.com/@test_bot', False),
        ('@test_bot_extra', [('mention', 0, 15)], '@test_bot_extra', False),
        ('ordinary caption', [], 'ordinary caption', False),
        ('😀 @TEST_BOT @test_bot', [('mention', 3, 9), ('mention', 13, 9)], '😀  ', True),
        ('😀 @TEST_BOT @test_bot', [('mention', 3, 9), ('code', 13, 9)], '😀  @test_bot', True),
    ],
)
async def test_telegram_caption_mentions_preserve_media(
    monkeypatch, media_type, caption, caption_entities, expected_text, mentioned
):
    media = {'file_id': 'file-1', 'file_unique_id': 'unique-1'}
    if media_type == 'photo':
        media = [{**media, 'width': 1, 'height': 1}]
    elif media_type == 'voice':
        media = {**media, 'duration': 1}
    else:
        media = {**media, 'file_name': 'report.txt', 'file_size': 5}
    message = Message.de_json(
        {
            'message_id': 10,
            'date': 1700000000,
            'chat': {'id': 123, 'type': 'private'},
            'caption': caption,
            'caption_entities': [
                {'type': kind, 'offset': offset, 'length': length} for kind, offset, length in caption_entities
            ],
            media_type: media,
        },
        SimpleNamespace(get_file=AsyncMock(return_value=SimpleNamespace(file_path=TELEGRAM_FILE_URL))),
    )

    response = MagicMock(headers={})

    async def iter_chunked(_chunk_size):
        yield b'media'

    response.content.iter_chunked = iter_chunked

    @asynccontextmanager
    async def fake_get(url):
        assert url == TELEGRAM_FILE_URL
        yield response

    monkeypatch.setattr(
        'langbot.pkg.platform.sources.telegram.httpclient.get_session',
        lambda **kwargs: MagicMock(get=fake_get),
    )

    chain = list(await TelegramMessageConverter.target2yiri(message, None, 'test_bot'))

    if mentioned:
        assert chain.pop(0) == platform_message.At(target='test_bot')
    assert chain.pop(0) == platform_message.Plain(text=expected_text)
    assert len(chain) == 1
    expected_type = {
        'photo': platform_message.Image,
        'voice': platform_message.Voice,
        'document': platform_message.File,
    }
    assert isinstance(chain[0], expected_type[media_type])
    assert chain[0].base64.endswith('bWVkaWE=')


@pytest.mark.asyncio
async def test_telegram_photo_does_not_expose_bot_token_in_image_url():
    """Regression test for the Telegram bot-token leak.

    telegram.Bot builds file.file_path as
    https://api.telegram.org/file/bot<TOKEN>/<path>, embedding the bot token.
    The converter must not copy that URL into Image.url, or the token leaks to
    the monitoring DB, dashboard and every installed plugin via the message
    chain. Only base64 (which carries no token) may be stored.
    """
    tg_file = MagicMock()
    tg_file.file_path = TELEGRAM_FILE_URL

    photo_size = MagicMock()
    photo_size.get_file = AsyncMock(return_value=tg_file)

    message = MagicMock()
    message.text = None
    message.caption = None
    message.photo = [photo_size]
    message.voice = None
    message.document = None

    response = MagicMock()
    response.headers = {}

    async def iter_chunked(_chunk_size):
        yield b'\xff\xd8\xff\xe0jpeg-bytes'

    response.content.iter_chunked = iter_chunked

    @asynccontextmanager
    async def fake_get(url):
        yield response

    fake_session = MagicMock()
    fake_session.get = fake_get

    with patch(
        'langbot.pkg.platform.sources.telegram.httpclient.get_session',
        return_value=fake_session,
    ):
        chain = await TelegramMessageConverter.target2yiri(message, MagicMock(), 'bot-account')

    images = [c for c in chain if isinstance(c, platform_message.Image)]
    assert len(images) == 1
    image = images[0]

    # The token-bearing URL must not be retained anywhere on the component.
    assert not image.url
    assert image.base64 is not None
    assert image.base64.startswith('data:image/jpeg;base64,')

    # Belt-and-suspenders: the token must not appear in the serialized chain
    # (this is what gets persisted to the monitoring DB and sent to plugins).
    serialized = json.dumps(chain.model_dump(), ensure_ascii=False)
    assert TELEGRAM_BOT_TOKEN not in serialized
    assert 'api.telegram.org/file/bot' not in serialized


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
        'inputs': {'select': {'index': 1}},
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


def test_telegram_form_callback_cache_consumes_the_whole_form_group():
    adapter = TelegramAdapter.model_construct()
    adapter._form_action_titles = {}
    adapter._cache_form_action_titles({'callback-a': 'A', 'callback-b': 'B'}, now=100.0)

    assert adapter._take_form_action_title('callback-a', now=101.0) == 'A'
    assert adapter._take_form_action_title('callback-a', now=101.0) is None
    assert adapter._take_form_action_title('callback-b', now=101.0) is None
    assert adapter._form_action_titles == {}


def test_telegram_form_callback_cache_prunes_expired_entries():
    adapter = TelegramAdapter.model_construct()
    adapter._form_action_titles = {}
    adapter._cache_form_action_titles({'callback-a': 'A'}, now=100.0)

    assert adapter._take_form_action_title('callback-a', now=100.0 + adapter._FORM_ACTION_CACHE_TTL) is None
    assert adapter._form_action_titles == {}


def test_telegram_form_callback_cache_preserves_pipeline_uuid():
    adapter = TelegramAdapter.model_construct()
    adapter._form_action_titles = {}
    adapter._cache_form_action_titles(
        {'callback-a': 'Approve'},
        pipeline_uuid='pipeline-routed',
        now=100.0,
    )

    assert adapter._take_form_action_context('callback-a', now=101.0) == (
        'Approve',
        'pipeline-routed',
    )


def test_telegram_form_callback_cache_is_bounded():
    adapter = TelegramAdapter.model_construct()
    adapter._form_action_titles = {}

    adapter._cache_form_action_titles(
        {f'callback-{index}': str(index) for index in range(5000)},
        now=100.0,
    )

    assert len(adapter._form_action_titles) == adapter._MAX_FORM_ACTION_TITLES


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
