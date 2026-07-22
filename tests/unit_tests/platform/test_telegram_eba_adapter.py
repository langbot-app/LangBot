from __future__ import annotations

import base64
import datetime
import pathlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import yaml
import telegram
from telegram.ext import CallbackQueryHandler, ChatMemberHandler, MessageHandler, MessageReactionHandler

from langbot.pkg.platform.adapters.telegram.event_converter import TelegramEventConverter
from langbot.pkg.platform.adapters.telegram.platform_api import PLATFORM_API_MAP
from langbot.pkg.platform.adapters.telegram.adapter import TelegramAdapter
from langbot.pkg.platform.adapters.telegram.interaction import (
    interaction_event_from_update,
    parse_interaction_callback,
)
from langbot.pkg.platform.botmgr import RuntimeBot
from langbot_plugin.api.definition.abstract.platform.event_logger import AbstractEventLogger
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities import events as plugin_events


@pytest.fixture(autouse=True)
def clear_proxy_env(monkeypatch):
    for key in ('ALL_PROXY', 'HTTPS_PROXY', 'HTTP_PROXY', 'all_proxy', 'https_proxy', 'http_proxy'):
        monkeypatch.delenv(key, raising=False)


class DummyLogger(AbstractEventLogger):
    async def info(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def debug(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def warning(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def error(self, text, images=None, message_session_id=None, no_throw=True):
        pass


def make_adapter() -> TelegramAdapter:
    return TelegramAdapter(
        {
            'token': '123456:ABCDEF_fake_token_for_object_parsing',
            'markdown_card': False,
            'enable-stream-reply': False,
        },
        DummyLogger(),
    )


def make_update(data: dict) -> telegram.Update:
    payload = {'update_id': 1000, **data}
    return telegram.Update.de_json(payload, make_adapter().bot)


def base_message_payload(**overrides):
    payload = {
        'message_id': 10,
        'date': int(datetime.datetime.now(datetime.UTC).timestamp()),
        'chat': {'id': 123, 'type': 'private', 'first_name': 'Chat User'},
        'from': {'id': 456, 'is_bot': False, 'first_name': 'Sender', 'username': 'sender'},
        'text': 'hello',
    }
    payload.update(overrides)
    return payload


def test_telegram_adapter_registers_all_declared_update_handlers():
    adapter = make_adapter()

    handlers = adapter.application.handlers[0]

    assert sum(isinstance(handler, MessageHandler) for handler in handlers) == 2
    assert sum(isinstance(handler, ChatMemberHandler) for handler in handlers) == 2
    assert any(isinstance(handler, CallbackQueryHandler) for handler in handlers)
    assert any(isinstance(handler, MessageReactionHandler) for handler in handlers)


@pytest.mark.asyncio
async def test_telegram_adapter_dispatches_only_most_specific_eba_listener():
    adapter = make_adapter()
    calls: list[str] = []

    async def wildcard_listener(event, adapter):
        calls.append('event')

    async def eba_listener(event, adapter):
        calls.append('eba')

    async def message_listener(event, adapter):
        calls.append('message.received')

    adapter.register_listener(platform_events.Event, wildcard_listener)
    adapter.register_listener(platform_events.EBAEvent, eba_listener)
    adapter.register_listener(platform_events.MessageReceivedEvent, message_listener)

    event = platform_events.MessageReceivedEvent(
        message_id=1,
        message_chain=platform_message.MessageChain([platform_message.Plain(text='hello')]),
        sender=platform_entities.User(id=1),
        chat_id=1,
    )

    await adapter._dispatch_eba_event(event)

    assert calls == ['message.received']


@pytest.mark.asyncio
async def test_telegram_adapter_dispatch_falls_back_to_eba_then_event_listener():
    adapter = make_adapter()
    calls: list[str] = []

    async def wildcard_listener(event, adapter):
        calls.append('event')

    async def eba_listener(event, adapter):
        calls.append('eba')

    adapter.register_listener(platform_events.Event, wildcard_listener)
    adapter.register_listener(platform_events.EBAEvent, eba_listener)

    event = platform_events.MessageEditedEvent(
        message_id=1,
        new_content=platform_message.MessageChain([platform_message.Plain(text='edited')]),
        editor=platform_entities.User(id=1),
        chat_id=1,
    )

    await adapter._dispatch_eba_event(event)
    assert calls == ['eba']

    adapter.unregister_listener(platform_events.EBAEvent, eba_listener)
    await adapter._dispatch_eba_event(event)
    assert calls == ['eba', 'event']


def test_telegram_supported_events_match_manifest():
    adapter_events = make_adapter().get_supported_events()
    manifest_path = (
        pathlib.Path(__file__).parents[3]
        / 'src'
        / 'langbot'
        / 'pkg'
        / 'platform'
        / 'adapters'
        / 'telegram'
        / 'manifest.yaml'
    )
    manifest_events = yaml.safe_load(manifest_path.read_text(encoding='utf-8'))['spec']['supported_events']

    assert adapter_events == manifest_events
    assert 'message.deleted' not in adapter_events
    assert 'group.info_updated' not in adapter_events


def test_telegram_interaction_callback_parser_uses_compact_indexes():
    assert parse_interaction_callback('lbi:token:a:2') == {
        'callback_token': 'token',
        'action_ref': 2,
    }
    assert parse_interaction_callback('lbi:token:f:1:3') == {
        'callback_token': 'token',
        'field_ref': 1,
        'option_ref': 3,
    }
    assert parse_interaction_callback('ordinary-button') is None
    with pytest.raises(ValueError, match='invalid Telegram interaction callback'):
        parse_interaction_callback('lbi:token:a:not-an-index')


@pytest.mark.asyncio
async def test_telegram_interaction_request_renders_action_buttons_and_thread_target():
    adapter = make_adapter()
    sent = SimpleNamespace(message_id=321)
    bot = SimpleNamespace(send_message=AsyncMock(return_value=sent))
    object.__setattr__(adapter, 'bot', bot)

    result = await adapter.call_platform_api(
        'interaction.request',
        {
            'callback_token': 'callback-token',
            'reply_target': {'target_type': 'group', 'target_id': '-1001#7'},
            'request': {
                'interaction_id': 'form-1',
                'kind': 'choice',
                'title': 'Approve?',
                'actions': [
                    {'id': 'approve', 'label': 'Approve', 'style': 'primary'},
                    {'id': 'reject', 'label': 'Reject', 'style': 'danger'},
                ],
                'fallback_text': 'Reply approve or reject.',
            },
        },
    )

    assert result == {'ok': True, 'message_id': 321, 'rich': True}
    kwargs = bot.send_message.await_args.kwargs
    assert kwargs['chat_id'] == -1001
    assert kwargs['message_thread_id'] == 7
    buttons = kwargs['reply_markup'].inline_keyboard
    assert buttons[0][0].callback_data == 'lbi:callback-token:a:0'
    assert buttons[1][0].callback_data == 'lbi:callback-token:a:1'


@pytest.mark.asyncio
async def test_telegram_interaction_request_renders_select_or_falls_back():
    adapter = make_adapter()
    bot = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(message_id=1)))
    object.__setattr__(adapter, 'bot', bot)
    base_params = {
        'callback_token': 'callback-token',
        'reply_target': {'target_type': 'person', 'target_id': '123'},
        'request': {
            'interaction_id': 'form-1',
            'title': 'Choose priority',
            'fields': [
                {
                    'id': 'priority',
                    'label': 'Priority',
                    'type': 'select',
                    'options': [{'value': 'urgent', 'label': 'Urgent'}],
                }
            ],
            'fallback_text': 'Reply with a priority.',
        },
    }

    result = await adapter.call_platform_api('interaction.request', base_params)
    assert result['rich'] is True
    button = bot.send_message.await_args.kwargs['reply_markup'].inline_keyboard[0][0]
    assert button.callback_data == 'lbi:callback-token:f:0:0'

    base_params['request']['fields'][0]['type'] = 'text'
    result = await adapter.call_platform_api('interaction.request', base_params)
    assert result['rich'] is False
    kwargs = bot.send_message.await_args.kwargs
    assert 'reply_markup' not in kwargs
    assert 'Reply with a priority.' in kwargs['text']


def test_telegram_interaction_callback_builds_scoped_host_event():
    update = SimpleNamespace(
        callback_query=SimpleNamespace(
            message=SimpleNamespace(
                chat=SimpleNamespace(id=-1001, type='supergroup'),
                message_thread_id=7,
            ),
            from_user=SimpleNamespace(id=456),
        )
    )

    event = interaction_event_from_update(
        update,
        {'callback_token': 'callback-token', 'action_ref': 1},
    )

    assert event.action == 'interaction.submitted'
    assert event.data['callback_token'] == 'callback-token'
    assert event.data['action_ref'] == 1
    assert event.data['actor_id'] == '456'
    assert event.data['target_type'] == 'group'
    assert event.data['target_id'] == '-1001#7'


@pytest.mark.asyncio
async def test_telegram_interaction_callback_answers_and_dispatches_once():
    adapter = make_adapter()
    listener = AsyncMock()
    adapter.register_listener(platform_events.EBAEvent, listener)
    query = SimpleNamespace(
        data='lbi:callback-token:a:0',
        answer=AsyncMock(),
        edit_message_reply_markup=AsyncMock(),
        message=SimpleNamespace(
            chat=SimpleNamespace(id=123, type='private'),
            message_thread_id=None,
        ),
        from_user=SimpleNamespace(id=456),
    )
    update = SimpleNamespace(
        message=None,
        edited_message=None,
        chat_member=None,
        my_chat_member=None,
        callback_query=query,
        message_reaction=None,
    )
    callback_handler = next(
        handler for handler in adapter.application.handlers[0] if isinstance(handler, CallbackQueryHandler)
    )

    await callback_handler.callback(update, None)

    query.answer.assert_awaited_once_with()
    query.edit_message_reply_markup.assert_awaited_once_with(reply_markup=None)
    listener.assert_awaited_once()
    event = listener.await_args.args[0]
    assert event.action == 'interaction.submitted'
    assert event.data['action_ref'] == 0


@pytest.mark.asyncio
async def test_telegram_converter_maps_message_and_edited_message_events():
    update = make_update({'message': base_message_payload(text='hello @test_bot')})
    event = await TelegramEventConverter.target2yiri(update, make_adapter().bot, 'test_bot')

    assert isinstance(event, platform_events.MessageReceivedEvent)
    assert event.type == 'message.received'
    assert event.chat_type == platform_entities.ChatType.PRIVATE
    assert event.chat_id == 123
    assert event.sender.id == 456
    assert platform_message.At in event.message_chain
    assert isinstance(event.message_chain[0], platform_message.At)
    assert isinstance(event.message_chain[1], platform_message.Plain)
    assert event.message_chain[1].text == 'hello '

    group_chat = {'id': -100123, 'type': 'supergroup', 'title': 'Test Group'}
    edited_payload = base_message_payload(chat=group_chat, text='edited')
    edited_payload['edit_date'] = edited_payload['date'] + 1
    edited = make_update({'edited_message': edited_payload})
    edited_event = await TelegramEventConverter.target2yiri(edited, make_adapter().bot, 'test_bot')

    assert isinstance(edited_event, platform_events.MessageEditedEvent)
    assert edited_event.type == 'message.edited'
    assert edited_event.chat_type == platform_entities.ChatType.GROUP
    assert edited_event.group.name == 'Test Group'
    assert str(edited_event.new_content) == 'edited'


@pytest.mark.asyncio
async def test_telegram_legacy_group_converter_preserves_actor_identity():
    adapter = make_adapter()
    group_chat = {'id': -100123, 'type': 'supergroup', 'title': 'Test Group'}
    update = make_update({'message': base_message_payload(chat=group_chat)})

    event = await adapter.legacy_event_converter.target2yiri(update, adapter.bot, 'test_bot')

    assert isinstance(event, platform_events.GroupMessage)
    assert event.sender.id == 456
    assert event.sender.group.id == -100123


@pytest.mark.asyncio
async def test_telegram_converter_maps_non_message_updates():
    chat_member = make_update(
        {
            'chat_member': {
                'chat': {'id': -1001, 'type': 'supergroup', 'title': 'Group'},
                'from': {'id': 1, 'is_bot': False, 'first_name': 'Admin'},
                'date': int(datetime.datetime.now(datetime.UTC).timestamp()),
                'old_chat_member': {
                    'user': {'id': 2, 'is_bot': False, 'first_name': 'Member'},
                    'status': 'left',
                },
                'new_chat_member': {
                    'user': {'id': 2, 'is_bot': False, 'first_name': 'Member'},
                    'status': 'member',
                },
            }
        }
    )
    joined = await TelegramEventConverter.target2yiri(chat_member, make_adapter().bot, 'test_bot')
    assert isinstance(joined, platform_events.MemberJoinedEvent)
    assert joined.type == 'group.member_joined'

    callback = make_update(
        {
            'callback_query': {
                'id': 'cb-1',
                'from': {'id': 3, 'is_bot': False, 'first_name': 'Clicker'},
                'chat_instance': 'ci',
                'data': 'button-data',
                'message': base_message_payload(message_id=77),
            }
        }
    )
    callback_event = await TelegramEventConverter.target2yiri(callback, make_adapter().bot, 'test_bot')
    assert isinstance(callback_event, platform_events.PlatformSpecificEvent)
    assert callback_event.action == 'callback_query'
    assert callback_event.data['callback_query_id'] == 'cb-1'
    assert callback_event.data['data'] == 'button-data'

    reaction = make_update(
        {
            'message_reaction': {
                'chat': {'id': -1001, 'type': 'supergroup', 'title': 'Group'},
                'message_id': 77,
                'date': int(datetime.datetime.now(datetime.UTC).timestamp()),
                'user': {'id': 3, 'is_bot': False, 'first_name': 'Reactor'},
                'old_reaction': [],
                'new_reaction': [{'type': 'emoji', 'emoji': '👍'}],
            }
        }
    )
    reaction_event = await TelegramEventConverter.target2yiri(reaction, make_adapter().bot, 'test_bot')
    assert isinstance(reaction_event, platform_events.MessageReactionEvent)
    assert reaction_event.reaction == '👍'
    assert reaction_event.is_add is True


@pytest.mark.asyncio
async def test_telegram_converter_maps_bot_status_events():
    base_member = {
        'chat': {'id': -1001, 'type': 'supergroup', 'title': 'Group'},
        'from': {'id': 1, 'is_bot': False, 'first_name': 'Admin'},
        'date': int(datetime.datetime.now(datetime.UTC).timestamp()),
    }
    restricted_member = {
        'user': {'id': 999, 'is_bot': True, 'first_name': 'Bot'},
        'status': 'restricted',
        'is_member': True,
        'can_send_messages': False,
        'can_send_audios': False,
        'can_send_documents': False,
        'can_send_photos': False,
        'can_send_videos': False,
        'can_send_video_notes': False,
        'can_send_voice_notes': False,
        'can_send_polls': False,
        'can_send_other_messages': False,
        'can_add_web_page_previews': False,
        'can_change_info': False,
        'can_invite_users': False,
        'can_pin_messages': False,
        'can_manage_topics': False,
        'can_edit_tag': False,
        'can_react_to_messages': False,
        'until_date': 0,
    }
    invited = make_update(
        {
            'my_chat_member': {
                **base_member,
                'old_chat_member': {
                    'user': {'id': 999, 'is_bot': True, 'first_name': 'Bot'},
                    'status': 'left',
                },
                'new_chat_member': {
                    'user': {'id': 999, 'is_bot': True, 'first_name': 'Bot'},
                    'status': 'member',
                },
            }
        }
    )
    invited_event = await TelegramEventConverter.target2yiri(invited, make_adapter().bot, 'test_bot')
    assert isinstance(invited_event, platform_events.BotInvitedToGroupEvent)

    muted = make_update(
        {
            'my_chat_member': {
                **base_member,
                'old_chat_member': {
                    'user': {'id': 999, 'is_bot': True, 'first_name': 'Bot'},
                    'status': 'member',
                },
                'new_chat_member': {
                    **restricted_member,
                },
            }
        }
    )
    muted_event = await TelegramEventConverter.target2yiri(muted, make_adapter().bot, 'test_bot')
    assert isinstance(muted_event, platform_events.BotMutedEvent)

    unmuted = make_update(
        {
            'my_chat_member': {
                **base_member,
                'old_chat_member': {
                    **restricted_member,
                },
                'new_chat_member': {
                    'user': {'id': 999, 'is_bot': True, 'first_name': 'Bot'},
                    'status': 'member',
                },
            }
        }
    )
    unmuted_event = await TelegramEventConverter.target2yiri(unmuted, make_adapter().bot, 'test_bot')
    assert isinstance(unmuted_event, platform_events.BotUnmutedEvent)


@pytest.mark.asyncio
async def test_telegram_reply_message_sends_text_image_and_file_components():
    adapter = make_adapter()
    bot = SimpleNamespace(
        send_message=AsyncMock(),
        send_photo=AsyncMock(),
        send_document=AsyncMock(),
    )
    object.__setattr__(adapter, 'bot', bot)
    update = make_update({'message': base_message_payload(message_id=88)})

    message_source = platform_events.MessageReceivedEvent(
        message_id=88,
        source_platform_object=update,
    )
    await adapter.reply_message(
        message_source,
        platform_message.MessageChain(
            [
                platform_message.Plain(text='reply text'),
                platform_message.Image(
                    base64='data:image/png;base64,' + base64.b64encode(b'image-bytes').decode('utf-8')
                ),
                platform_message.File(
                    name='test.txt',
                    size=4,
                    base64='data:text/plain;base64,' + base64.b64encode(b'test').decode('utf-8'),
                ),
            ]
        ),
        quote_origin=True,
    )

    bot.send_message.assert_awaited_once()
    bot.send_photo.assert_awaited_once()
    bot.send_document.assert_awaited_once()
    assert bot.send_message.await_args.kwargs['reply_to_message_id'] == 88
    assert bot.send_photo.await_args.kwargs['reply_to_message_id'] == 88
    assert bot.send_photo.await_args.kwargs['photo'].input_file_content == b'image-bytes'
    assert bot.send_document.await_args.kwargs['document'].filename == 'test.txt'
    assert bot.send_document.await_args.kwargs['document'].input_file_content == b'test'


@pytest.mark.asyncio
async def test_telegram_platform_apis_call_underlying_bot_methods():
    bot = SimpleNamespace(
        pin_chat_message=AsyncMock(),
        unpin_chat_message=AsyncMock(),
        unpin_all_chat_messages=AsyncMock(),
        get_chat_administrators=AsyncMock(
            return_value=[
                SimpleNamespace(
                    user=SimpleNamespace(id=1, username='admin', first_name='Admin'),
                    status='administrator',
                    custom_title='Boss',
                )
            ]
        ),
        set_chat_title=AsyncMock(),
        set_chat_description=AsyncMock(),
        get_chat_member_count=AsyncMock(return_value=3),
        send_chat_action=AsyncMock(),
        create_chat_invite_link=AsyncMock(
            return_value=SimpleNamespace(
                invite_link='https://t.me/+abc',
                name='invite',
                is_primary=False,
                is_revoked=False,
            )
        ),
        answer_callback_query=AsyncMock(),
    )

    assert await PLATFORM_API_MAP['pin_message'](bot, {'chat_id': 1, 'message_id': 2}) == {'ok': True}
    assert await PLATFORM_API_MAP['unpin_message'](bot, {'chat_id': 1, 'message_id': 2}) == {'ok': True}
    assert await PLATFORM_API_MAP['unpin_all_messages'](bot, {'chat_id': 1}) == {'ok': True}
    admins = await PLATFORM_API_MAP['get_chat_administrators'](bot, {'chat_id': 1})
    assert admins['administrators'][0]['user_id'] == 1
    assert await PLATFORM_API_MAP['set_chat_title'](bot, {'chat_id': 1, 'title': 'New'}) == {'ok': True}
    assert await PLATFORM_API_MAP['set_chat_description'](bot, {'chat_id': 1, 'description': 'Desc'}) == {'ok': True}
    assert await PLATFORM_API_MAP['get_chat_member_count'](bot, {'chat_id': 1}) == {'count': 3}
    assert await PLATFORM_API_MAP['send_chat_action'](bot, {'chat_id': 1, 'action': 'typing'}) == {'ok': True}
    invite = await PLATFORM_API_MAP['create_chat_invite_link'](bot, {'chat_id': 1, 'name': 'invite'})
    assert invite['invite_link'] == 'https://t.me/+abc'
    assert await PLATFORM_API_MAP['answer_callback_query'](bot, {'callback_query_id': 'cb'}) == {'ok': True}


@pytest.mark.asyncio
async def test_telegram_unmute_member_uses_current_chat_permissions_fields():
    adapter = make_adapter()
    bot = SimpleNamespace(restrict_chat_member=AsyncMock())
    object.__setattr__(adapter, 'bot', bot)

    await adapter.unmute_member(group_id=-1001, user_id=123)

    permissions = bot.restrict_chat_member.await_args.kwargs['permissions']
    assert permissions.can_send_messages is True
    assert permissions.can_send_photos is True
    assert permissions.can_send_documents is True


def test_runtime_bot_maps_telegram_eba_events_to_plugin_events():
    group = platform_entities.UserGroup(id='group-1', name='Group')
    user = platform_entities.User(id='user-1', nickname='User')

    cases = [
        (
            platform_events.MessageReceivedEvent(
                message_id='msg',
                message_chain=platform_message.MessageChain([platform_message.Plain(text='hi')]),
                sender=user,
                chat_id='user-1',
            ),
            plugin_events.MessageReceived,
        ),
        (
            platform_events.MessageReactionEvent(message_id='msg', user=user, reaction='👍'),
            plugin_events.MessageReactionReceived,
        ),
        (
            platform_events.MemberJoinedEvent(group=group, member=user),
            plugin_events.GroupMemberJoined,
        ),
        (
            platform_events.BotUnmutedEvent(group=group, operator=user),
            plugin_events.BotUnmuted,
        ),
        (
            platform_events.PlatformSpecificEvent(adapter_name='telegram', action='callback_query', data={'data': 'x'}),
            plugin_events.PlatformSpecificEventReceived,
        ),
    ]

    for platform_event, plugin_event_type in cases:
        plugin_event = RuntimeBot._eba_event_to_plugin_event(platform_event)
        assert isinstance(plugin_event, plugin_event_type)
        assert plugin_event.model_dump()['event_name'] == plugin_event_type.__name__
