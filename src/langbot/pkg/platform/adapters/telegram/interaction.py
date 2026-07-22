"""Telegram rendering and callback conversion for structured interactions."""

from __future__ import annotations

import time
import typing

import telegram

import langbot_plugin.api.entities.builtin.platform.events as platform_events


INTERACTION_CALLBACK_PREFIX = 'lbi'


def parse_interaction_callback(data: str | None) -> dict[str, typing.Any] | None:
    """Parse a compact interaction callback without trusting platform values."""
    if not data or not data.startswith(f'{INTERACTION_CALLBACK_PREFIX}:'):
        return None
    parts = data.split(':')
    if len(parts) == 4 and parts[2] == 'a':
        token, action_ref = parts[1], parts[3]
        if token and action_ref.isdigit():
            return {'callback_token': token, 'action_ref': int(action_ref)}
    if len(parts) == 5 and parts[2] == 'f':
        token, field_ref, option_ref = parts[1], parts[3], parts[4]
        if token and field_ref.isdigit() and option_ref.isdigit():
            return {
                'callback_token': token,
                'field_ref': int(field_ref),
                'option_ref': int(option_ref),
            }
    raise ValueError('invalid Telegram interaction callback data')


def interaction_delivery_capabilities() -> dict[str, typing.Any]:
    """Return the structured interaction subset Telegram can render natively."""
    return {
        'field_types': ['select'],
        'action_styles': ['default', 'primary', 'danger'],
        'supports_updates': True,
        'max_fields': 1,
    }


def _callback_data(callback_token: str, *parts: str | int) -> str:
    value = ':'.join((INTERACTION_CALLBACK_PREFIX, callback_token, *(str(part) for part in parts)))
    if len(value.encode('utf-8')) > 64:
        raise ValueError('Telegram interaction callback exceeds 64 bytes')
    return value


def _build_keyboard(request: dict[str, typing.Any], callback_token: str) -> telegram.InlineKeyboardMarkup | None:
    fields = request.get('fields') if isinstance(request.get('fields'), list) else []
    actions = request.get('actions') if isinstance(request.get('actions'), list) else []

    if actions and not fields:
        rows = [
            [
                telegram.InlineKeyboardButton(
                    str(action.get('label') or action.get('id') or index + 1),
                    callback_data=_callback_data(callback_token, 'a', index),
                )
            ]
            for index, action in enumerate(actions)
            if isinstance(action, dict)
        ]
        return telegram.InlineKeyboardMarkup(rows) if rows else None

    if len(fields) == 1 and not actions:
        field = fields[0]
        if not isinstance(field, dict) or field.get('type') != 'select':
            return None
        options = field.get('options') if isinstance(field.get('options'), list) else []
        rows = [
            [
                telegram.InlineKeyboardButton(
                    str(option.get('label') or option.get('value') or option_index + 1),
                    callback_data=_callback_data(callback_token, 'f', 0, option_index),
                )
            ]
            for option_index, option in enumerate(options)
            if isinstance(option, dict)
        ]
        return telegram.InlineKeyboardMarkup(rows) if rows else None

    return None


def _message_text(request: dict[str, typing.Any], *, rich: bool) -> str:
    parts = [str(request.get('title') or '').strip()]
    description = str(request.get('description') or '').strip()
    if description:
        parts.append(description)
    fields = request.get('fields') if isinstance(request.get('fields'), list) else []
    if rich and len(fields) == 1 and isinstance(fields[0], dict):
        label = str(fields[0].get('label') or '').strip()
        if label:
            parts.append(label)
    if not rich:
        fallback = str(request.get('fallback_text') or '').strip()
        if fallback:
            parts.append(fallback)
    return '\n\n'.join(part for part in parts if part)


async def send_interaction(bot: telegram.Bot, params: dict[str, typing.Any]) -> dict[str, typing.Any]:
    """Render a supported interaction or its required plain-text fallback."""
    request = params.get('request')
    reply_target = params.get('reply_target')
    callback_token = str(params.get('callback_token') or '')
    if not isinstance(request, dict) or not isinstance(reply_target, dict) or not callback_token:
        raise ValueError('interaction.request requires request, reply_target, and callback_token')

    target_id = str(reply_target.get('target_id') or '')
    if not target_id:
        raise ValueError('interaction.request has no target_id')
    chat_id_text, _, thread_id_text = target_id.partition('#')
    chat_id: int | str = int(chat_id_text) if chat_id_text.lstrip('-').isdigit() else chat_id_text
    message_thread_id = int(thread_id_text) if thread_id_text.isdigit() else None
    keyboard = _build_keyboard(request, callback_token)
    send_args: dict[str, typing.Any] = {
        'chat_id': chat_id,
        'text': _message_text(request, rich=keyboard is not None),
    }
    if message_thread_id is not None:
        send_args['message_thread_id'] = message_thread_id
    if keyboard is not None:
        send_args['reply_markup'] = keyboard

    sent = await bot.send_message(**send_args)
    return {'ok': True, 'message_id': getattr(sent, 'message_id', None), 'rich': keyboard is not None}


def interaction_event_from_update(
    update: telegram.Update,
    parsed: dict[str, typing.Any],
) -> platform_events.PlatformSpecificEvent:
    """Convert a trusted callback shape into the Host interaction event."""
    query = update.callback_query
    if query is None or query.message is None or query.from_user is None:
        raise ValueError('Telegram interaction callback has no message or actor')
    message = query.message
    target_type = 'person' if message.chat.type == 'private' else 'group'
    target_id = str(message.chat.id)
    if message.message_thread_id:
        target_id = f'{target_id}#{message.message_thread_id}'

    data = {
        **parsed,
        'actor_id': str(query.from_user.id),
        'target_type': target_type,
        'target_id': target_id,
        'display_text': 'submitted',
    }
    return platform_events.PlatformSpecificEvent(
        type='platform.specific',
        timestamp=time.time(),
        adapter_name='telegram',
        action='interaction.submitted',
        data=data,
        source_platform_object=update,
    )
