"""WeCom template-card rendering and callbacks for structured interactions."""

from __future__ import annotations

import time
import typing
import uuid

from langbot.libs.wecom_ai_bot_api.wecombotevent import WecomBotEvent
from langbot_plugin.api.entities.builtin.platform import events as platform_events


def interaction_delivery_capabilities() -> dict[str, typing.Any]:
    return {
        'field_types': ['select'],
        'action_styles': ['default', 'primary', 'danger'],
        'supports_updates': True,
        'max_fields': 1,
    }


def _button_style(style: str) -> int:
    if style == 'primary':
        return 1
    if style == 'danger':
        return 2
    return 0


def build_interaction_card(request: dict[str, typing.Any], callback_token: str) -> dict[str, typing.Any] | None:
    fields = request.get('fields') if isinstance(request.get('fields'), list) else []
    actions = request.get('actions') if isinstance(request.get('actions'), list) else []
    buttons: list[dict[str, typing.Any]] = []
    if actions and not fields:
        buttons = [
            {
                'text': str(action.get('label') or action.get('id') or index + 1),
                'style': _button_style(str(action.get('style') or 'default')),
                'key': f'lbi:{callback_token}:a:{index}',
            }
            for index, action in enumerate(actions[:6])
            if isinstance(action, dict)
        ]
    elif len(fields) == 1 and not actions and isinstance(fields[0], dict):
        field = fields[0]
        if field.get('type') != 'select':
            return None
        options = field.get('options') if isinstance(field.get('options'), list) else []
        buttons = [
            {
                'text': str(option.get('label') or option.get('value') or index + 1),
                'style': 0,
                'key': f'lbi:{callback_token}:f:0:{index}',
            }
            for index, option in enumerate(options[:6])
            if isinstance(option, dict)
        ]
    if not buttons:
        return None
    description = str(request.get('description') or '').strip()
    if len(fields) == 1 and isinstance(fields[0], dict):
        label = str(fields[0].get('label') or '').strip()
        description = '\n\n'.join(part for part in (description, label) if part)
    return {
        'msgtype': 'template_card',
        'template_card': {
            'card_type': 'button_interaction',
            'main_title': {'title': str(request.get('title') or '')},
            'sub_title_text': description,
            'button_list': buttons,
            'task_id': f'lbi-{uuid.uuid4().hex}',
        },
    }


async def send_interaction(adapter: typing.Any, params: dict[str, typing.Any]) -> dict[str, typing.Any]:
    request = params.get('request')
    reply_target = params.get('reply_target')
    callback_token = str(params.get('callback_token') or '')
    if not isinstance(request, dict) or not isinstance(reply_target, dict) or not callback_token:
        raise ValueError('interaction.request requires request, reply_target, and callback_token')
    target_type = str(reply_target.get('target_type') or '')
    target_id = str(reply_target.get('target_id') or '')
    card = build_interaction_card(request, callback_token)
    if card is None:
        fallback = '\n\n'.join(
            part
            for part in (
                str(request.get('title') or '').strip(),
                str(request.get('description') or '').strip(),
                str(request.get('fallback_text') or '').strip(),
            )
            if part
        )
        result = await adapter.send_message(target_type, target_id, adapter._plain_message(fallback))
        return {'ok': True, 'message_id': result.message_id, 'rich': False}
    raw = await adapter.bot.send_template_card(target_id, card)
    return {'ok': True, 'message_id': None, 'rich': True, 'raw': raw}


def _template_card_event(event: WecomBotEvent) -> dict[str, typing.Any]:
    wrapper = event.get('event') or {}
    if not isinstance(wrapper, dict):
        return {}
    for key in ('template_card_event', 'templateCardEvent', 'TemplateCardEvent'):
        value = wrapper.get(key)
        if isinstance(value, dict):
            return value
    return wrapper


def _callback_key(payload: dict[str, typing.Any]) -> str:
    value = payload.get('EventKey') or payload.get('event_key') or payload.get('eventKey') or payload.get('key') or ''
    if value:
        return str(value)
    for button_name in ('button', 'Button', 'selected_button', 'selectedButton'):
        button = payload.get(button_name)
        if not isinstance(button, dict):
            continue
        value = button.get('key') or button.get('Key') or button.get('event_key') or button.get('EventKey') or ''
        if value:
            return str(value)
    return ''


def parse_callback_key(value: str) -> dict[str, typing.Any]:
    parts = value.split(':')
    if len(parts) == 4 and parts[0] == 'lbi' and parts[1] and parts[2] == 'a' and parts[3].isdigit():
        return {'callback_token': parts[1], 'action_ref': int(parts[3])}
    if (
        len(parts) == 5
        and parts[0] == 'lbi'
        and parts[1]
        and parts[2] == 'f'
        and parts[3].isdigit()
        and parts[4].isdigit()
    ):
        return {
            'callback_token': parts[1],
            'field_ref': int(parts[3]),
            'option_ref': int(parts[4]),
        }
    raise ValueError('invalid WeCom interaction callback key')


def interaction_event_from_native(
    event: WecomBotEvent,
) -> platform_events.PlatformSpecificEvent | None:
    callback_key = _callback_key(_template_card_event(event))
    if not callback_key.startswith('lbi:'):
        return None
    parsed = parse_callback_key(callback_key)
    target_type = 'group' if event.type == 'group' or event.chatid else 'person'
    target_id = str(event.chatid or event.userid or '')
    return platform_events.PlatformSpecificEvent(
        type='platform.specific',
        adapter_name='wecombot-eba',
        action='interaction.submitted',
        data={
            **parsed,
            'actor_id': str(event.userid or ''),
            'target_type': target_type,
            'target_id': target_id,
            'display_text': 'submitted',
        },
        timestamp=time.time(),
        source_platform_object=event,
    )
