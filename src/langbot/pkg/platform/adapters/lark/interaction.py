"""Lark card rendering and callback conversion for structured interactions."""

from __future__ import annotations

import json
import time
import typing
import uuid

from lark_oapi.api.cardkit.v1 import (
    Card,
    CreateCardRequest,
    CreateCardRequestBody,
    CreateCardResponse,
    UpdateCardRequest,
    UpdateCardRequestBody,
    UpdateCardResponse,
)
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    CreateMessageResponse,
)

from langbot_plugin.api.entities.builtin.platform import events as platform_events


def interaction_delivery_capabilities() -> dict[str, typing.Any]:
    return {
        'field_types': ['text', 'textarea', 'number', 'select'],
        'action_styles': ['default', 'primary', 'danger'],
        'supports_updates': True,
        'max_fields': 1,
    }


def _callback_value(
    callback_token: str,
    reply_target: dict[str, typing.Any],
    **refs: typing.Any,
) -> dict[str, typing.Any]:
    return {
        'lbi': callback_token,
        't': str(reply_target.get('target_type') or ''),
        'ck': 1,
        **refs,
    }


def _field_form_elements(
    field: dict[str, typing.Any],
    callback_token: str,
    reply_target: dict[str, typing.Any],
) -> list[dict[str, typing.Any]] | None:
    field_type = str(field.get('type') or '')
    if field_type not in {'text', 'textarea', 'number', 'select'}:
        return None
    field_id = str(field.get('id') or '')
    if not field_id:
        return None
    component_name = 'lbi_field_0'
    label = str(field.get('label') or field_id)
    placeholder = str(
        field.get('placeholder')
        or ('Select an option / 请选择' if field_type == 'select' else 'Enter a value / 请输入')
    )
    required = bool(field.get('required'))
    if field_type == 'select':
        raw_options = field.get('options') if isinstance(field.get('options'), list) else []
        options = [
            {
                'text': {
                    'tag': 'plain_text',
                    'content': str(option.get('label') or option.get('value') or ''),
                },
                'value': str(option.get('value') or ''),
            }
            for option in raw_options
            if isinstance(option, dict) and option.get('value') not in (None, '')
        ]
        if not options:
            return None
        field_element: dict[str, typing.Any] = {
            'tag': 'select_static',
            'name': component_name,
            'label': {'tag': 'plain_text', 'content': label},
            'placeholder': {'tag': 'plain_text', 'content': placeholder},
            'options': options,
            'width': 'fill',
            'required': required,
        }
        default = field.get('default')
        if default not in (None, ''):
            field_element['initial_option'] = str(default)
    else:
        default = field.get('default')
        field_element = {
            'tag': 'input',
            'name': component_name,
            'label': {'tag': 'plain_text', 'content': label},
            'placeholder': {'tag': 'plain_text', 'content': placeholder},
            'default_value': '' if default is None else str(default),
            'width': 'fill',
            'required': required,
        }
        if field_type == 'textarea':
            field_element.update(
                {
                    'input_type': 'multiline_text',
                    'rows': 3,
                    'auto_resize': True,
                    'max_rows': 6,
                }
            )

    submit_value = _callback_value(
        callback_token,
        reply_target,
        fm={component_name: field_id},
        ft={field_id: field_type},
    )
    submit_button = {
        'tag': 'button',
        'name': 'lbi_submit',
        'text': {'tag': 'plain_text', 'content': 'Submit / 提交'},
        'type': 'primary',
        'width': 'fill',
        'form_action_type': 'submit',
        'behaviors': [{'type': 'callback', 'value': submit_value}],
    }
    form_elements: list[dict[str, typing.Any]] = [field_element, submit_button]
    if field_type == 'select':
        form_elements.insert(
            0,
            {
                'tag': 'markdown',
                'content': f'**{label}{"*" if required else ""}**',
            },
        )
    return [
        {
            'tag': 'form',
            'name': 'lbi_form',
            'direction': 'vertical',
            'vertical_spacing': '12px',
            'elements': form_elements,
        }
    ]


def _render_submitted_value(value: typing.Any) -> str:
    rendered = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    rendered = rendered.strip().replace('\n', '\n  ')
    return rendered if len(rendered) <= 2000 else rendered[:1997] + '...'


def _submission_display_values(
    request: dict[str, typing.Any],
    submission: dict[str, typing.Any],
) -> list[dict[str, str]]:
    display_values: list[dict[str, str]] = []
    values = submission.get('values') if isinstance(submission.get('values'), dict) else {}
    fields = request.get('fields') if isinstance(request.get('fields'), list) else []
    for field in fields:
        if not isinstance(field, dict):
            continue
        field_id = str(field.get('id') or '')
        if field_id and field_id in values:
            display_value = {
                'label': str(field.get('label') or field_id),
                'value': _render_submitted_value(values[field_id]),
            }
            description = str(request.get('description') or '').strip()
            if description:
                display_value['description'] = description
            display_values.append(display_value)

    action_id = submission.get('action_id')
    if action_id:
        actions = request.get('actions') if isinstance(request.get('actions'), list) else []
        action_label = next(
            (
                str(action.get('label') or action_id)
                for action in actions
                if isinstance(action, dict) and str(action.get('id') or '') == str(action_id)
            ),
            str(action_id),
        )
        display_values.append({'label': 'Action', 'value': action_label})
    return display_values


def _stored_submitted_values(value: typing.Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    stored_values = [
        {
            'label': str(item['label'])[:200],
            'value': str(item['value'])[:2000],
            **({'description': str(item['description'])[:4000]} if item.get('description') is not None else {}),
        }
        for item in value[:50]
        if isinstance(item, dict) and item.get('label') is not None and item.get('value') is not None
    ]
    return stored_values


def _submitted_value_elements(values: list[dict[str, str]]) -> list[dict[str, typing.Any]]:
    elements: list[dict[str, typing.Any]] = []
    for item in values:
        lines = []
        description = str(item.get('description') or '').strip()
        if description:
            lines.append(description)
        lines.append(f'✅ {item["label"]}：{item["value"]}')
        elements.append({'tag': 'markdown', 'content': '\n'.join(lines)})
    return elements


def build_interaction_card(
    request: dict[str, typing.Any],
    callback_token: str,
    reply_target: dict[str, typing.Any],
    submitted_values: list[dict[str, str]] | None = None,
) -> dict[str, typing.Any] | None:
    """Build the Lark subset that maps to a single atomic submission."""
    fields = request.get('fields') if isinstance(request.get('fields'), list) else []
    actions = request.get('actions') if isinstance(request.get('actions'), list) else []
    buttons: list[dict[str, typing.Any]] = []
    field_elements: list[dict[str, typing.Any]] | None = None

    if actions and not fields:
        for index, action in enumerate(actions):
            if not isinstance(action, dict):
                continue
            style = str(action.get('style') or 'default')
            buttons.append(
                {
                    'tag': 'button',
                    'text': {
                        'tag': 'plain_text',
                        'content': str(action.get('label') or action.get('id') or index + 1),
                    },
                    'type': 'primary' if style == 'primary' else 'danger' if style == 'danger' else 'default',
                    'behaviors': [
                        {
                            'type': 'callback',
                            'value': _callback_value(callback_token, reply_target, a=index),
                        }
                    ],
                }
            )
    elif len(fields) == 1 and not actions and isinstance(fields[0], dict):
        field = fields[0]
        field_elements = _field_form_elements(field, callback_token, reply_target)
        if field_elements is None:
            return None
    else:
        return None

    if not buttons and not field_elements:
        return None
    elements: list[dict[str, typing.Any]] = []
    elements.extend(_submitted_value_elements(submitted_values or []))
    description = str(request.get('description') or '').strip()
    if description:
        elements.append({'tag': 'markdown', 'content': description})
    if field_elements:
        elements.extend(field_elements)
    else:
        elements.append(
            {
                'tag': 'column_set',
                'horizontal_spacing': '8px',
                'columns': [
                    {
                        'tag': 'column',
                        'width': 'weighted',
                        'weight': 1,
                        'elements': [button],
                    }
                    for button in buttons
                ],
            }
        )
    return {
        'schema': '2.0',
        'config': {'update_multi': True},
        'header': {
            'title': {'tag': 'plain_text', 'content': str(request.get('title') or '')},
        },
        'body': {'direction': 'vertical', 'elements': elements},
    }


def build_submitted_card(
    request: dict[str, typing.Any],
    submission: dict[str, typing.Any],
    submitted_values: list[dict[str, str]] | None = None,
) -> dict[str, typing.Any]:
    """Render a read-only snapshot after a user submits an interaction."""
    elements: list[dict[str, typing.Any]] = []
    all_submitted_values = [
        *(submitted_values or []),
        *_submission_display_values(request, submission),
    ]
    elements.extend(_submitted_value_elements(all_submitted_values))
    return {
        'schema': '2.0',
        'config': {'update_multi': True},
        'header': {'title': {'tag': 'plain_text', 'content': str(request.get('title') or '')}},
        'body': {'direction': 'vertical', 'elements': elements},
    }


async def _update_interaction_card(
    adapter: typing.Any,
    update_target: dict[str, typing.Any],
    card: dict[str, typing.Any],
    submitted_values: list[dict[str, str]] | None = None,
) -> dict[str, typing.Any]:
    message_id = str(update_target.get('message_id') or '')
    card_id = str(update_target.get('card_id') or '')
    if not message_id or not card_id or update_target.get('rich') is not True:
        raise ValueError('Lark interaction update requires a CardKit target')
    persisted_sequence = int(update_target.get('sequence') or 0)
    current_sequence = int(adapter.card_sequence_dict.get(card_id, persisted_sequence))
    sequence = max(persisted_sequence, current_sequence) + 1
    request = (
        UpdateCardRequest.builder()
        .card_id(card_id)
        .request_body(
            UpdateCardRequestBody.builder()
            .sequence(sequence)
            .uuid(str(uuid.uuid4()))
            .card(Card.builder().type('card_json').data(json.dumps(card, ensure_ascii=False)).build())
            .build()
        )
        .build()
    )
    response: UpdateCardResponse = await adapter.api_client.cardkit.v1.card.aupdate(request)
    if not response.success():
        raise RuntimeError(f'Lark CardKit interaction update failed: {response.code} {response.msg}')
    adapter.card_sequence_dict[card_id] = sequence
    result = {
        'ok': True,
        'message_id': message_id,
        'card_id': card_id,
        'sequence': sequence,
        'rich': True,
        'updated': True,
    }
    if submitted_values:
        result['submitted_values'] = submitted_values
    return result


async def send_interaction(adapter: typing.Any, params: dict[str, typing.Any]) -> dict[str, typing.Any]:
    request = params.get('request')
    reply_target = params.get('reply_target')
    callback_token = str(params.get('callback_token') or '')
    if not isinstance(request, dict) or not isinstance(reply_target, dict) or not callback_token:
        raise ValueError('interaction.request requires request, reply_target, and callback_token')

    update_target = params.get('update_target')
    submitted_values = _stored_submitted_values(
        update_target.get('submitted_values') if isinstance(update_target, dict) else None
    )
    card = build_interaction_card(request, callback_token, reply_target, submitted_values)
    if card is None:
        fallback = str(request.get('fallback_text') or '')
        result = await adapter.send_message(
            str(reply_target.get('target_type') or ''),
            str(reply_target.get('target_id') or ''),
            adapter._plain_message(fallback),
        )
        return {'ok': True, 'message_id': result.message_id, 'rich': False}

    if isinstance(update_target, dict):
        return await _update_interaction_card(adapter, update_target, card, submitted_values)

    target_type = str(reply_target.get('target_type') or '')
    target_id = str(reply_target.get('target_id') or '')
    if target_type not in {'group', 'person'} or not target_id:
        raise ValueError('interaction.request has an invalid reply target')
    card_request = (
        CreateCardRequest.builder()
        .request_body(
            CreateCardRequestBody.builder().type('card_json').data(json.dumps(card, ensure_ascii=False)).build()
        )
        .build()
    )
    card_response: CreateCardResponse = await adapter.api_client.cardkit.v1.card.acreate(card_request)
    if not card_response.success():
        raise RuntimeError(f'Lark CardKit interaction create failed: {card_response.code} {card_response.msg}')
    card_id = str(getattr(card_response.data, 'card_id', '') or '')
    if not card_id:
        raise RuntimeError('Lark CardKit interaction create returned no card_id')

    message_request = (
        CreateMessageRequest.builder()
        .receive_id_type('chat_id' if target_type == 'group' else 'open_id')
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(target_id)
            .content(json.dumps({'type': 'card', 'data': {'card_id': card_id}}, ensure_ascii=False))
            .msg_type('interactive')
            .uuid(str(uuid.uuid4()))
            .build()
        )
        .build()
    )
    response: CreateMessageResponse = await adapter.api_client.im.v1.message.acreate(message_request)
    if not response.success():
        raise RuntimeError(f'Lark interaction send failed: {response.code} {response.msg}')
    adapter.card_sequence_dict[card_id] = 0
    return {
        'ok': True,
        'message_id': getattr(response.data, 'message_id', ''),
        'card_id': card_id,
        'sequence': 0,
        'rich': True,
    }


async def acknowledge_interaction(adapter: typing.Any, params: dict[str, typing.Any]) -> dict[str, typing.Any]:
    request = params.get('request')
    submission = params.get('submission')
    update_target = params.get('update_target')
    if not isinstance(request, dict) or not isinstance(submission, dict) or not isinstance(update_target, dict):
        raise ValueError('interaction.acknowledge requires request, submission, and update_target')
    submitted_values = [
        *_stored_submitted_values(update_target.get('submitted_values')),
        *_submission_display_values(request, submission),
    ]
    return await _update_interaction_card(
        adapter,
        update_target,
        build_submitted_card(request, submission, _stored_submitted_values(update_target.get('submitted_values'))),
        submitted_values,
    )


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


def _action_attr(action: typing.Any, name: str) -> typing.Any:
    return action.get(name) if isinstance(action, dict) else getattr(action, name, None)


def _coerce_field_value(value: typing.Any, field_type: str) -> typing.Any:
    if isinstance(value, dict):
        value = value.get('value') if value.get('value') is not None else value.get('option')
    if field_type != 'number' or isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    text = str(value).strip()
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return value


def _form_submission_values(action: typing.Any, payload: dict[str, typing.Any]) -> dict[str, typing.Any]:
    field_map = payload.get('fm') if isinstance(payload.get('fm'), dict) else {}
    field_types = payload.get('ft') if isinstance(payload.get('ft'), dict) else {}
    if not field_map:
        return {}
    form_value = _mapping(_action_attr(action, 'form_value'))
    if not form_value:
        for key in ('form_value', 'formValue', 'form_values', 'formValues'):
            form_value = _mapping(payload.get(key))
            if form_value:
                break
    if not form_value:
        action_name = _action_attr(action, 'name')
        input_value = _action_attr(action, 'input_value')
        option_value = _action_attr(action, 'option')
        if action_name and input_value not in (None, ''):
            form_value = {str(action_name): input_value}
        elif action_name and option_value not in (None, ''):
            form_value = {str(action_name): option_value}
    values: dict[str, typing.Any] = {}
    for component_name, value in form_value.items():
        field_id = field_map.get(component_name)
        if field_id and value not in (None, ''):
            values[str(field_id)] = _coerce_field_value(value, str(field_types.get(str(field_id)) or ''))
    return values


def _event_from_parts(
    *,
    raw: typing.Any,
    action: typing.Any,
    actor_id: typing.Any,
    chat_id: typing.Any,
    message_id: typing.Any,
) -> platform_events.PlatformSpecificEvent | None:
    payload = _mapping(_action_attr(action, 'value'))
    callback_token = str(payload.get('lbi') or '')
    if not callback_token:
        return None
    target_type = str(payload.get('t') or '')
    target_id = str(chat_id or '') if target_type == 'group' else str(actor_id or '')
    data: dict[str, typing.Any] = {
        'callback_token': callback_token,
        'actor_id': str(actor_id or ''),
        'target_type': target_type,
        'target_id': target_id,
        'display_text': 'submitted',
    }
    if payload.get('ck') == 1:
        data['cardkit'] = True
    if message_id:
        data['message_id'] = str(message_id)
    if payload.get('a') is not None:
        data['action_ref'] = payload['a']
    if payload.get('f') is not None or payload.get('o') is not None:
        data['field_ref'] = payload.get('f')
        data['option_ref'] = payload.get('o')
    if payload.get('fm'):
        data['values'] = _form_submission_values(action, payload)
    return platform_events.PlatformSpecificEvent(
        type='platform.specific',
        adapter_name='lark-eba',
        action='interaction.submitted',
        data=data,
        timestamp=time.time(),
        source_platform_object=raw,
    )


def interaction_event_from_callback(event: typing.Any) -> platform_events.PlatformSpecificEvent | None:
    action = getattr(getattr(event, 'event', None), 'action', None)
    operator = getattr(getattr(event, 'event', None), 'operator', None)
    context = getattr(getattr(event, 'event', None), 'context', None)
    return _event_from_parts(
        raw=event,
        action=action,
        actor_id=getattr(operator, 'open_id', None) or getattr(operator, 'user_id', None),
        chat_id=getattr(context, 'open_chat_id', None),
        message_id=getattr(context, 'open_message_id', None),
    )


def interaction_event_from_webhook(data: dict[str, typing.Any]) -> platform_events.PlatformSpecificEvent | None:
    event = data.get('event') if isinstance(data.get('event'), dict) else {}
    action = event.get('action') if isinstance(event.get('action'), dict) else {}
    operator = event.get('operator') if isinstance(event.get('operator'), dict) else {}
    context = event.get('context') if isinstance(event.get('context'), dict) else {}
    return _event_from_parts(
        raw=data,
        action=action,
        actor_id=operator.get('open_id') or operator.get('user_id'),
        chat_id=context.get('open_chat_id'),
        message_id=context.get('open_message_id'),
    )
