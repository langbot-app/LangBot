"""DingTalk card rendering and callbacks for structured interactions."""

from __future__ import annotations

import json
import time
import typing
import uuid

from langbot.libs.dingtalk_api.dingtalkevent import DingTalkEvent
from langbot_plugin.api.entities.builtin.platform import events as platform_events


def interaction_delivery_capabilities() -> dict[str, typing.Any]:
    return {
        'field_types': ['text', 'textarea', 'number', 'select'],
        'action_styles': ['default', 'primary', 'danger'],
        'supports_updates': True,
        'max_fields': 1,
    }


def _select_options(options: list[dict[str, typing.Any]]) -> list[dict[str, typing.Any]]:
    locales = ['zh_CN', 'zh_TW', 'en_US', 'ja_JP', 'vi_VN', 'th_TH', 'id_ID', 'ms_MY', 'ko_KR']
    result = []
    for option in options:
        value = str(option.get('value') or '')
        label = str(option.get('label') or value)
        if value:
            result.append({'value': value, 'text': {locale: label for locale in locales}})
    return result


def _field_card_params(field: dict[str, typing.Any]) -> dict[str, typing.Any] | None:
    field_type = str(field.get('type') or '')
    field_id = str(field.get('id') or '')
    if field_type not in {'text', 'textarea', 'number', 'select'} or not field_id:
        return None
    label = str(field.get('label') or field_id)
    placeholder = str(field.get('placeholder') or label)
    default = field.get('default')
    params: dict[str, typing.Any] = {
        'input_visible': '',
        'input_title': '',
        'input_placeholder': '',
        'input_value': '',
        'select_visible': '',
        'select_placeholder': '',
        'select_options': [],
        'index_o': [],
        'select_index': -1,
    }
    if field_type == 'select':
        raw_options = field.get('options') if isinstance(field.get('options'), list) else []
        options = [option for option in raw_options if isinstance(option, dict)]
        encoded_options = _select_options(options)
        if not encoded_options:
            return None
        selected_index = next(
            (index for index, option in enumerate(options) if str(option.get('value')) == str(default)),
            -1,
        )
        params.update(
            {
                'select_visible': 'true',
                'select_placeholder': placeholder,
                'select_options': [str(option.get('value') or '') for option in options],
                'index_o': encoded_options,
                'select_index': selected_index,
            }
        )
    else:
        params.update(
            {
                'input_visible': 'true',
                'input_title': label,
                'input_placeholder': placeholder,
                'input_value': '' if default is None else str(default),
            }
        )
    return params


def _prune_callback_contexts(adapter: typing.Any, now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    contexts = adapter.interaction_callback_contexts
    for key in [key for key, value in contexts.items() if float(value.get('expires_at') or 0) <= now]:
        contexts.pop(key, None)


def _buttons(request: dict[str, typing.Any], callback_token: str) -> list[dict[str, typing.Any]]:
    fields = request.get('fields') if isinstance(request.get('fields'), list) else []
    actions = request.get('actions') if isinstance(request.get('actions'), list) else []
    items: list[tuple[str, str, str]] = []
    if actions and not fields:
        items = [
            (
                str(action.get('label') or action.get('id') or index + 1),
                f'lbi:{callback_token}:a:{index}',
                str(action.get('style') or 'default'),
            )
            for index, action in enumerate(actions)
            if isinstance(action, dict)
        ]
    elif len(fields) == 1 and not actions and isinstance(fields[0], dict):
        field = fields[0]
        if field.get('type') != 'select':
            return []
        options = field.get('options') if isinstance(field.get('options'), list) else []
        items = [
            (
                str(option.get('label') or option.get('value') or index + 1),
                f'lbi:{callback_token}:f:0:{index}',
                'default',
            )
            for index, option in enumerate(options)
            if isinstance(option, dict)
        ]
    return [
        {
            'text': label,
            'color': 'blue' if style == 'primary' else 'red' if style == 'danger' else 'gray',
            'status': 'normal',
            'event': {
                'type': 'sendCardRequest',
                'params': {'actionId': callback_data, 'params': {'action_id': callback_data}},
            },
        }
        for label, callback_data, style in items
    ]


async def send_interaction(adapter: typing.Any, params: dict[str, typing.Any]) -> dict[str, typing.Any]:
    request = params.get('request')
    reply_target = params.get('reply_target')
    callback_token = str(params.get('callback_token') or '')
    if not isinstance(request, dict) or not isinstance(reply_target, dict) or not callback_token:
        raise ValueError('interaction.request requires request, reply_target, and callback_token')
    target_type = str(reply_target.get('target_type') or '')
    target_id = str(reply_target.get('target_id') or '')
    fields = request.get('fields') if isinstance(request.get('fields'), list) else []
    actions = request.get('actions') if isinstance(request.get('actions'), list) else []
    buttons = _buttons(request, callback_token)
    field_params = (
        _field_card_params(fields[0]) if len(fields) == 1 and not actions and isinstance(fields[0], dict) else None
    )
    if not buttons and field_params is None:
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
    if target_type not in {'group', 'person'} or not target_id:
        raise ValueError('interaction.request has an invalid DingTalk target')
    field_label = str(fields[0].get('label') or '').strip() if fields and isinstance(fields[0], dict) else ''
    content = '\n\n'.join(
        part
        for part in (
            f'## {str(request.get("title") or "").strip()}',
            str(request.get('description') or '').strip(),
            field_label,
        )
        if part
    )
    out_track_id = uuid.uuid4().hex
    card_param_map = {'content': content, 'btns': buttons}
    if field_params is not None:
        card_param_map.update(field_params)
    await adapter.bot.create_and_deliver_card(
        card_template_id=adapter.config['human_input_card_template_id'],
        out_track_id=out_track_id,
        open_space_id=(
            f'dtv1.card//IM_GROUP.{target_id}' if target_type == 'group' else f'dtv1.card//IM_ROBOT.{target_id}'
        ),
        is_group=target_type == 'group',
        card_param_map=card_param_map,
    )
    if field_params is not None:
        _prune_callback_contexts(adapter)
        field = fields[0]
        adapter.interaction_callback_contexts[out_track_id] = {
            'callback_token': callback_token,
            'field_id': str(field.get('id') or ''),
            'field_type': str(field.get('type') or ''),
            'options': [
                str(option.get('value') or '') for option in field.get('options') or [] if isinstance(option, dict)
            ],
            'expires_at': time.monotonic() + 30 * 60,
        }
    return {'ok': True, 'message_id': out_track_id, 'rich': True}


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
    raise ValueError('invalid DingTalk interaction callback data')


def _find_callback_data(value: typing.Any) -> str:
    if isinstance(value, str):
        return value if value.startswith('lbi:') else ''
    if isinstance(value, dict):
        for key in ('actionId', 'action_id', 'id'):
            found = _find_callback_data(value.get(key))
            if found:
                return found
        for child in value.values():
            found = _find_callback_data(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_callback_data(child)
            if found:
                return found
    return ''


def _find_named_value(value: typing.Any, names: set[str]) -> typing.Any:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in names and child not in (None, ''):
                return child
        for child in value.values():
            found = _find_named_value(child, names)
            if found not in (None, ''):
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_named_value(child, names)
            if found not in (None, ''):
                return found
    return None


def _callback_track_id(callback: dict[str, typing.Any]) -> str:
    value = _find_named_value(callback, {'outTrackId', 'out_track_id', 'outtrackid'})
    return str(value or '')


def _mapping(value: typing.Any) -> dict[str, typing.Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _native_field_value(callback: dict[str, typing.Any], context: dict[str, typing.Any]) -> typing.Any:
    field_type = str(context.get('field_type') or '')
    names = (
        {'select', 'selectResult', 'select_result', '__built_in_selectResult__'}
        if field_type == 'select'
        else {'input', 'inputResult', 'input_result', '__built_in_inputResult__'}
    )
    value = _find_named_value(callback, names)
    parsed = _mapping(value)
    if parsed:
        value = parsed.get('value', parsed.get('input', parsed.get('index')))
    if isinstance(value, dict):
        value = value.get('value') or value.get('input') or value.get('index')
    if field_type == 'select' and isinstance(value, int) and not isinstance(value, bool):
        options = context.get('options') if isinstance(context.get('options'), list) else []
        if 0 <= value < len(options):
            value = options[value]
    if field_type == 'number' and value not in (None, ''):
        text = str(value).strip()
        try:
            return int(text)
        except ValueError:
            try:
                return float(text)
            except ValueError:
                return value
    return value


def interaction_event_from_native(
    event: DingTalkEvent,
    callback_contexts: dict[str, dict[str, typing.Any]] | None = None,
) -> platform_events.PlatformSpecificEvent | None:
    callback = event.get('CardCallback') or {}
    callback_data = _find_callback_data(callback)
    if callback_data:
        parsed = parse_callback_data(callback_data)
    else:
        contexts = callback_contexts if callback_contexts is not None else {}
        track_id = _callback_track_id(callback)
        context = contexts.get(track_id)
        if context is None:
            return None
        value = _native_field_value(callback, context)
        if value in (None, ''):
            return None
        parsed = {
            'callback_token': str(context.get('callback_token') or ''),
            'values': {str(context.get('field_id') or ''): value},
        }
        contexts.pop(track_id, None)
    space_id = str(callback.get('space_id') or '')
    if 'IM_GROUP.' in space_id:
        target_type = 'group'
        target_id = space_id.split('IM_GROUP.', 1)[1]
    elif 'IM_ROBOT.' in space_id:
        target_type = 'person'
        target_id = space_id.split('IM_ROBOT.', 1)[1]
    else:
        raise ValueError('DingTalk interaction callback has no delivery space')
    return platform_events.PlatformSpecificEvent(
        type='platform.specific',
        adapter_name='dingtalk-eba',
        action='interaction.submitted',
        data={
            **parsed,
            'actor_id': str(callback.get('user_id') or ''),
            'target_type': target_type,
            'target_id': target_id,
            'display_text': 'submitted',
        },
        timestamp=time.time(),
        source_platform_object=event,
    )
