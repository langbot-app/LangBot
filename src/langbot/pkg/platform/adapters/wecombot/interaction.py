"""WeCom template-card rendering and callbacks for structured interactions."""

from __future__ import annotations

import json
import time
import typing
import uuid

from langbot.libs.wecom_ai_bot_api.api import extract_template_card_action, extract_template_card_event_payload
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
    select_field: dict[str, typing.Any] | None = None
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
        if len(options) > 10:
            raise ValueError('WeCom select cards support at most 10 options')
        if options and all(isinstance(option, dict) for option in options):
            select_field = field
    if not buttons and select_field is None:
        return None
    description = str(request.get('description') or '').strip()
    if select_field is not None:
        options = select_field['options']
        selected_id = 'opt_1'
        for index, option in enumerate(options):
            if option.get('value') == select_field.get('default'):
                selected_id = f'opt_{index + 1}'
                break
        return {
            'msgtype': 'template_card',
            'template_card': {
                'card_type': 'multiple_interaction',
                'main_title': {'title': str(request.get('title') or ''), 'desc': description},
                'select_list': [
                    {
                        'question_key': 'f0',
                        'title': str(select_field.get('label') or ''),
                        'selected_id': selected_id,
                        'option_list': [
                            {
                                'id': f'opt_{index + 1}',
                                'text': str(option.get('label') or option.get('value') or '')[:10],
                            }
                            for index, option in enumerate(options)
                        ],
                    }
                ],
                'submit_button': {'text': 'Submit', 'key': f'lbi:{callback_token}:s'},
                'task_id': f'lbi-{uuid.uuid4().hex}',
            },
        }
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
        raise ValueError('send_interaction requires request, reply_target, and callback_token')
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
    if not isinstance(raw, dict) or raw.get('errcode', 0) != 0:
        detail = raw.get('errmsg', raw.get('errcode')) if isinstance(raw, dict) else 'no acknowledgement'
        raise RuntimeError(f'WeCom template card delivery failed: {detail}')
    source_message_id = str(reply_target.get('message_id') or '')
    if source_message_id and hasattr(adapter.bot, 'finish_stream_for_interaction'):
        await adapter.bot.finish_stream_for_interaction(source_message_id)
    return {
        'ok': True,
        'message_id': None,
        'rich': True,
        'task_id': card['template_card']['task_id'],
        'raw': raw,
    }


async def acknowledge_interaction(adapter: typing.Any, params: dict[str, typing.Any]) -> dict[str, typing.Any]:
    request = params.get('request')
    submission = params.get('submission')
    target = params.get('update_target')
    callback = params.get('callback_context')
    if not all(isinstance(value, dict) for value in (request, submission, target, callback)):
        raise ValueError('update_interaction requires request, submission, update_target, and callback_context')
    state = params.get('state', 'submitted')
    task_id = str(callback.get('task_id') or target.get('task_id') or '')
    req_id = str(callback.get('req_id') or '')
    if not req_id or not task_id or task_id != target.get('task_id') or target.get('rich') is not True:
        raise ValueError('WeCom interaction callback does not match the delivered card')

    card = build_interaction_card(request, state)
    if card is None:
        raise ValueError('WeCom interaction has no card to update')
    updated = card['template_card']
    updated['task_id'] = task_id
    action_id = submission.get('action_id') if state == 'submitted' else None
    if updated['card_type'] == 'button_interaction':
        for index, action in enumerate((request.get('actions') or [])[:6]):
            updated['button_list'][index]['key'] = state
            if isinstance(action, dict) and action.get('id') == action_id:
                button = updated['button_list'][index]
                button['text'] = f'✓ {button["text"]}'
                button['replace_text'] = button['text']
                break
    else:
        field = request['fields'][0]
        selected = (submission.get('values') or {}).get(field['id'])
        for index, option in enumerate(field.get('options') or []):
            if option.get('value') == selected:
                updated['select_list'][0]['selected_id'] = f'opt_{index + 1}'
                break
        updated['select_list'][0]['disable'] = True
        updated['submit_button']['text'] = {'submitted': 'Submitted', 'expired': 'Expired', 'cancelled': 'Cancelled'}[
            state
        ]
        updated['submit_button']['key'] = state
    raw = await adapter.bot.update_template_card(req_id, updated)
    if not isinstance(raw, dict) or raw.get('errcode', 0) != 0:
        detail = raw.get('errmsg', raw.get('errcode')) if isinstance(raw, dict) else 'no acknowledgement'
        raise RuntimeError(f'WeCom template card update failed: {detail}')
    return {**target, 'updated': True, 'raw': raw}


def _template_card_event(event: WecomBotEvent) -> dict[str, typing.Any]:
    return extract_template_card_event_payload(event)


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
    if len(parts) == 3 and parts[0] == 'lbi' and parts[1] and parts[2] == 's':
        return {'callback_token': parts[1], 'select_submit': True}
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


def _selected_option_ref(payload: dict[str, typing.Any]) -> int:
    selected_id: typing.Any = None
    selected_items = payload.get('selected_items', payload.get('SelectedItems'))
    if isinstance(selected_items, dict):
        items = selected_items.get('selected_item', selected_items.get('SelectedItem'))
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict) or item.get('question_key', item.get('QuestionKey')) != 'f0':
                    continue
                option_ids = item.get('option_ids', item.get('OptionIds'))
                if isinstance(option_ids, dict):
                    option_ids = option_ids.get('option_id', option_ids.get('OptionId'))
                if isinstance(option_ids, list) and len(option_ids) == 1:
                    selected_id = option_ids[0]
                break
    if selected_id is None and selected_items is None:
        response: typing.Any = next(
            (payload[key] for key in ('ResponseData', 'response_data', 'responseData') if key in payload), None
        )
        if isinstance(response, str):
            try:
                response = json.loads(response)
            except json.JSONDecodeError as exc:
                raise ValueError('invalid WeCom select response data') from exc
        if isinstance(response, dict):
            selections = next(
                (response[key] for key in ('select_list', 'SelectList', 'selectList') if key in response), None
            )
            if isinstance(selections, list):
                for item in selections:
                    if not isinstance(item, dict) or item.get('question_key', item.get('QuestionKey')) != 'f0':
                        continue
                    selected_id = next(
                        (
                            item[key]
                            for key in ('option_id', 'OptionId', 'optionId', 'selected_id', 'SelectedId', 'selectedId')
                            if item.get(key)
                        ),
                        None,
                    )
                    break
            else:
                selected_id = response.get('f0')
    if not isinstance(selected_id, str) or not selected_id.startswith('opt_') or not selected_id[4:].isdigit():
        raise ValueError('WeCom select response has an invalid option')
    option_number = int(selected_id[4:])
    if option_number < 1:
        raise ValueError('WeCom select response has an invalid option')
    return option_number - 1


def interaction_event_from_native(
    event: WecomBotEvent,
) -> platform_events.InteractionCallbackEvent | None:
    callback_key = _callback_key(_template_card_event(event))
    if not callback_key.startswith('lbi:'):
        return None
    parsed = parse_callback_key(callback_key)
    task_id, _, _ = extract_template_card_action(_template_card_event(event))
    if parsed.pop('select_submit', False):
        parsed['field_ref'] = 0
        parsed['option_ref'] = _selected_option_ref(_template_card_event(event))
    target_type = 'group' if event.type == 'group' or event.chatid else 'person'
    target_id = str(event.chatid or event.userid or '')
    return platform_events.InteractionCallbackEvent(
        adapter_name='wecombot-omni',
        callback_token=str(parsed.get('callback_token') or ''),
        actor_id=str(event.userid or ''),
        target_type=target_type,
        target_id=target_id,
        callback_context={'req_id': str(event.get('req_id') or ''), 'task_id': task_id},
        raw_submission=parsed,
        timestamp=time.time(),
        source_platform_object=event,
    )
