"""DingTalk card rendering and callbacks for structured interactions."""

from __future__ import annotations

import json
import time
import typing
import uuid

from langbot.libs.dingtalk_api.a2ui import brand_components, binding, create_surface_messages, update_surface_messages
from langbot.libs.dingtalk_api.dingtalkevent import DingTalkEvent
from langbot_plugin.api.entities.builtin.platform import events as platform_events


def interaction_delivery_capabilities() -> dict[str, typing.Any]:
    return {
        'field_types': ['text', 'textarea', 'number', 'select'],
        'action_styles': ['default', 'primary', 'danger'],
        'supports_updates': True,
        'max_fields': 8,
    }


def _json_pointer_segment(value: str) -> str:
    return value.replace('~', '~0').replace('/', '~1')


def _build_interaction_messages(
    surface_id: str,
    request: dict[str, typing.Any],
    callback_token: str,
) -> tuple[dict[str, typing.Any], list[dict[str, typing.Any]], dict[str, str]]:
    raw_fields = request.get('fields') if isinstance(request.get('fields'), list) else []
    raw_actions = request.get('actions') if isinstance(request.get('actions'), list) else []
    fields = [field for field in raw_fields if isinstance(field, dict)][:8]
    actions = [action for action in raw_actions if isinstance(action, dict)]

    form: dict[str, typing.Any] = {}
    field_types: dict[str, str] = {}
    required_fields: list[tuple[str, str]] = []
    components: list[dict[str, typing.Any]] = []
    children: list[str] = []

    title = str(request.get('title') or '').strip()
    description = str(request.get('description') or '').strip()
    if title:
        components.append({'id': 'title', 'component': 'Text', 'text': title})
        children.append('title')
    if description:
        components.append({'id': 'description', 'component': 'Markdown', 'content': description})
        children.append('description')

    for index, field in enumerate(fields):
        field_id = str(field.get('id') or f'field_{index}')
        field_type = str(field.get('type') or 'text')
        if field_type not in {'text', 'textarea', 'number', 'select'}:
            continue
        field_types[field_id] = field_type
        path = f'/form/{_json_pointer_segment(field_id)}'
        component_id = f'field-{index}'
        label = str(field.get('label') or field_id)
        placeholder = str(field.get('placeholder') or '')
        default = field.get('default')

        if field_type == 'select':
            options = [
                {
                    'label': str(option.get('label') or option.get('value') or ''),
                    'value': str(option.get('value') or ''),
                }
                for option in field.get('options') or []
                if isinstance(option, dict) and str(option.get('value') or '')
            ]
            if not options:
                continue
            selected = default if isinstance(default, list) else ([] if default in (None, '') else [str(default)])
            form[field_id] = [str(value) for value in selected]
            component = {
                'id': component_id,
                'component': 'ChoicePicker',
                'label': placeholder or label,
                'variant': 'mutuallyExclusive',
                'displayStyle': 'dropdown',
                'options': options,
                'value': binding(path),
            }
        elif field_type == 'number':
            numeric_default = default if isinstance(default, (int, float)) and not isinstance(default, bool) else 0
            form[field_id] = numeric_default
            component = {
                'id': component_id,
                'component': 'NumberInput',
                'label': label,
                'placeholder': placeholder,
                'value': binding(path),
            }
        else:
            form[field_id] = '' if default is None else str(default)
            component = {
                'id': component_id,
                'component': 'TextField',
                'label': label,
                'placeholder': placeholder,
                'variant': 'longText' if field_type == 'textarea' else 'shortText',
                'value': binding(path),
            }
        components.append(component)
        children.append(component_id)
        if field.get('required'):
            required_fields.append((path, label))

    rendered_actions = actions or ([{'label': 'Submit', 'style': 'primary'}] if field_types else [])
    for index, action in enumerate(rendered_actions):
        label_id = f'action-label-{index}'
        button_id = f'action-{index}'
        callback_data = f'lbi:{callback_token}:a:{index}' if actions else f'lbi:{callback_token}:f:0'
        style = str(action.get('style') or 'default')
        button: dict[str, typing.Any] = {
            'id': button_id,
            'component': 'Button',
            'child': label_id,
            'variant': 'primary' if style == 'primary' else 'default',
            'action': {
                'event': {
                    'name': 'langbot_interaction_submit',
                    'context': {
                        'actionId': callback_data,
                        'values': binding('/form'),
                    },
                }
            },
        }
        if required_fields:
            button['checks'] = [
                {
                    'condition': {'call': 'required', 'args': {'value': binding(path)}},
                    'message': f'{label} is required',
                }
                for path, label in required_fields
            ]
        components.extend(
            [
                button,
                {
                    'id': label_id,
                    'component': 'Text',
                    'text': str(action.get('label') or action.get('id') or 'Submit'),
                },
            ]
        )
        children.append(button_id)

    children.insert(0, 'langbot-brand')
    components.extend(brand_components())
    components.insert(0, {'id': 'root', 'component': 'Column', 'children': children, 'gap': 12})
    return {'form': form}, components, field_types


def _prune_callback_contexts(adapter: typing.Any, now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    contexts = adapter.interaction_callback_contexts
    for key in [key for key, value in contexts.items() if float(value.get('expires_at') or 0) <= now]:
        contexts.pop(key, None)


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
    if not fields and not actions:
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
    update_target = params.get('update_target')
    if isinstance(update_target, dict):
        if update_target.get('rich') is not True or not update_target.get('message_id'):
            raise ValueError('DingTalk interaction update target is not an A2UI card')
        out_track_id = str(update_target['message_id'])
    else:
        out_track_id = uuid.uuid4().hex
    surface_id = f'langbot-interaction-{out_track_id}'
    data, components, field_types = _build_interaction_messages(surface_id, request, callback_token)
    if isinstance(update_target, dict):
        await adapter.bot.update_ai_card(
            out_track_id=out_track_id,
            a2ui_messages=update_surface_messages(surface_id, data=data, components=components),
            flow_status='CONFIRMING',
        )
    else:
        await adapter.bot.create_and_deliver_ai_card(
            out_track_id=out_track_id,
            open_space_id=(
                f'dtv1.card//im_group.{target_id}' if target_type == 'group' else f'dtv1.card//im_robot.{target_id}'
            ),
            is_group=target_type == 'group',
            a2ui_messages=create_surface_messages(surface_id, data=data, components=components),
            flow_status='CONFIRMING',
            summary=str(request.get('title') or request.get('fallback_text') or 'Interaction required'),
            biz_context={'callbackToken': callback_token},
        )
    _prune_callback_contexts(adapter)
    adapter.interaction_callback_contexts[out_track_id] = {
        'callback_token': callback_token,
        'field_types': field_types,
        'target_type': target_type,
        'target_id': target_id,
        'expires_at': time.monotonic() + 30 * 60,
    }
    return {
        'ok': True,
        'message_id': out_track_id,
        'rich': True,
        'updated': isinstance(update_target, dict),
    }


def parse_callback_data(value: str) -> dict[str, typing.Any]:
    parts = value.split(':')
    if len(parts) == 4 and parts[0] == 'lbi' and parts[1] and parts[2] == 'a' and parts[3].isdigit():
        return {'callback_token': parts[1], 'action_ref': int(parts[3])}
    if len(parts) == 4 and parts[0] == 'lbi' and parts[1] and parts[2] == 'f' and parts[3].isdigit():
        return {'callback_token': parts[1], 'field_ref': int(parts[3])}
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
    value = _find_named_value(callback, {'outTrackId', 'out_track_id', 'outtrackid', 'card_instance_id'})
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
        raw_values = _mapping(_find_named_value(callback, {'values'}))
        if 'field_ref' in parsed and 'option_ref' not in parsed:
            # The A2UI form submit button uses f:0, but its values already
            # contain the selected option; option refs belong to native pickers.
            if not raw_values:
                return None
            parsed.pop('field_ref')
        context: dict[str, typing.Any] = {}
        if callback_contexts is not None:
            track_id = _callback_track_id(callback)
            context = callback_contexts.get(track_id)
            if context is None:
                return None
            if parsed.get('callback_token') != context.get('callback_token'):
                return None
        if raw_values:
            field_types = context.get('field_types') if isinstance(context.get('field_types'), dict) else {}
            values = {}
            for field_id, value in raw_values.items():
                if field_types.get(field_id) == 'select' and isinstance(value, list):
                    value = value[0] if value else ''
                values[str(field_id)] = value
            parsed['values'] = values
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
    space_id = str(callback.get('space_id') or '')
    normalized_space_id = space_id.lower()
    if context.get('target_type') in {'group', 'person'} and context.get('target_id'):
        target_type = str(context['target_type'])
        target_id = str(context['target_id'])
    elif 'im_group.' in normalized_space_id:
        target_type = 'group'
        target_id = space_id[normalized_space_id.index('im_group.') + len('im_group.') :]
    elif 'im_robot.' in normalized_space_id:
        target_type = 'person'
        target_id = space_id[normalized_space_id.index('im_robot.') + len('im_robot.') :]
    else:
        raise ValueError('DingTalk interaction callback has no delivery space')
    return platform_events.PlatformSpecificEvent(
        type='platform.specific',
        adapter_name='dingtalk-omni',
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
