"""QQ Official keyboard rendering and interaction callback conversion."""

from __future__ import annotations

import time
import typing

from langbot_plugin.api.entities.builtin.platform import events as platform_events


def interaction_delivery_capabilities() -> dict[str, typing.Any]:
    return {
        'field_types': ['select'],
        'action_styles': ['default', 'primary', 'danger'],
        'supports_updates': True,
        'max_fields': 1,
    }


def _buttons(request: dict[str, typing.Any], callback_token: str) -> list[tuple[str, str, int]]:
    fields = request.get('fields') if isinstance(request.get('fields'), list) else []
    actions = request.get('actions') if isinstance(request.get('actions'), list) else []
    if actions and not fields:
        return [
            (
                str(action.get('label') or action.get('id') or index + 1),
                f'lbi:{callback_token}:a:{index}',
                1 if action.get('style') == 'primary' else 0,
            )
            for index, action in enumerate(actions[:25])
            if isinstance(action, dict)
        ]
    if len(fields) == 1 and not actions and isinstance(fields[0], dict):
        field = fields[0]
        if field.get('type') != 'select':
            return []
        options = field.get('options') if isinstance(field.get('options'), list) else []
        return [
            (
                str(option.get('label') or option.get('value') or index + 1),
                f'lbi:{callback_token}:f:0:{index}',
                0,
            )
            for index, option in enumerate(options[:25])
            if isinstance(option, dict)
        ]
    return []


def build_interaction_keyboard(request: dict[str, typing.Any], callback_token: str) -> dict[str, typing.Any] | None:
    buttons = _buttons(request, callback_token)
    if not buttons:
        return None
    rows = []
    for start in range(0, len(buttons), 2):
        rows.append(
            {
                'buttons': [
                    {
                        'id': str(start + offset + 1),
                        'render_data': {
                            'label': label,
                            'visited_label': f'✓ {label}',
                            'style': style,
                        },
                        'action': {
                            'type': 1,
                            'permission': {'type': 2},
                            'data': callback_data,
                            'unsupport_tips': 'Please update QQ to use this action.',
                        },
                    }
                    for offset, (label, callback_data, style) in enumerate(buttons[start : start + 2])
                ]
            }
        )
    return {'content': {'rows': rows}}


def _text(request: dict[str, typing.Any], rich: bool) -> str:
    parts = [str(request.get('title') or '').strip()]
    description = str(request.get('description') or '').strip()
    if description:
        parts.append(description)
    if not rich:
        fallback = str(request.get('fallback_text') or '').strip()
        if fallback:
            parts.append(fallback)
    return '\n\n'.join(part for part in parts if part)


async def send_interaction(adapter: typing.Any, params: dict[str, typing.Any]) -> dict[str, typing.Any]:
    request = params.get('request')
    reply_target = params.get('reply_target')
    callback_token = str(params.get('callback_token') or '')
    if not isinstance(request, dict) or not isinstance(reply_target, dict) or not callback_token:
        raise ValueError('interaction.request requires request, reply_target, and callback_token')
    target_type = str(reply_target.get('target_type') or '')
    target_id = str(reply_target.get('target_id') or '')
    keyboard = build_interaction_keyboard(request, callback_token)
    if keyboard is None or target_type not in {'person', 'group'}:
        result = await adapter.send_message(
            target_type,
            target_id,
            adapter._plain_message(_text(request, False)),
        )
        return {'ok': True, 'message_id': result.message_id, 'rich': False}
    raw = await adapter.bot.send_markdown_keyboard(
        target_type='c2c' if target_type == 'person' else 'group',
        target_id=target_id,
        markdown_content=_text(request, True),
        keyboard=keyboard,
        msg_id=reply_target.get('message_id'),
    )
    return {'ok': True, 'message_id': raw.get('id') if isinstance(raw, dict) else None, 'rich': True}


def parse_callback_data(value: str) -> dict[str, typing.Any]:
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
    raise ValueError('invalid QQ interaction callback data')


def interaction_event_from_payload(
    event_data: dict[str, typing.Any],
) -> platform_events.PlatformSpecificEvent | None:
    resolved = (event_data.get('data') or {}).get('resolved') or {}
    callback_data = str(resolved.get('button_data') or '')
    if not callback_data.startswith('lbi:'):
        return None
    parsed = parse_callback_data(callback_data)
    chat_type = event_data.get('chat_type')
    if chat_type == 2 or event_data.get('user_openid'):
        target_type = 'person'
        target_id = str(event_data.get('user_openid') or '')
    elif chat_type == 1 or event_data.get('group_openid'):
        target_type = 'group'
        target_id = str(event_data.get('group_openid') or '')
    elif chat_type == 0 or event_data.get('channel_id'):
        target_type = 'group'
        target_id = str(event_data.get('channel_id') or '')
    else:
        raise ValueError('QQ interaction callback has no target')
    actor_id = str(
        event_data.get('member_openid')
        or event_data.get('user_openid')
        or ((event_data.get('member') or {}).get('user') or {}).get('id')
        or ''
    )
    return platform_events.PlatformSpecificEvent(
        type='platform.specific',
        adapter_name='qqofficial-eba',
        action='interaction.submitted',
        data={
            **parsed,
            'actor_id': actor_id,
            'target_type': target_type,
            'target_id': target_id,
            'display_text': 'submitted',
        },
        timestamp=time.time(),
        source_platform_object=event_data,
    )
