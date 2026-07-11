from __future__ import annotations

import typing
import json
import time
import uuid
import base64
import mimetypes
import os
import re
from collections import OrderedDict
from urllib.parse import urlparse


from langbot.pkg.provider import runner
from langbot.pkg.core import app
import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.builtin.platform.message as platform_message
from langbot.pkg.utils import image
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
from langbot.libs.dify_service_api.v1 import client, errors
import httpx


# Module-level store for paused-workflow form state. The key isolates the bot,
# pipeline, adapter, and launcher; each value holds an insertion-ordered map of
# form_token -> form_data so one conversation can pause multiple workflows.
PendingFormKey = tuple[str, str, str, str, str]
_PENDING_FORMS: dict[PendingFormKey, 'OrderedDict[str, dict[str, typing.Any]]'] = {}
_PENDING_FORM_DEFAULT_TTL = 30 * 60  # 30 minutes safety cap
_STREAM_FORM_PLACEHOLDER = '\u200b'


def _merge_stream_text(accumulated: str, incoming: typing.Any) -> str:
    """Merge either a delta chunk or a cumulative stream snapshot."""
    incoming_text = '' if incoming is None else str(incoming)
    if not incoming_text:
        return accumulated
    if not accumulated:
        return incoming_text
    if len(incoming_text) > len(accumulated) and incoming_text.startswith(accumulated):
        return incoming_text
    return accumulated + incoming_text


def _dify_user_from_query(query: pipeline_query.Query) -> str:
    return f'{query.session.launcher_type.value}_{query.session.launcher_id}'


def _session_key_from_query(query: pipeline_query.Query) -> PendingFormKey:
    """Build a process-local pending-form key isolated by bot and pipeline."""
    adapter = getattr(query, 'adapter', None)
    adapter_type = f'{type(adapter).__module__}.{type(adapter).__qualname__}'
    return (
        str(getattr(query, 'bot_uuid', '') or ''),
        str(getattr(query, 'pipeline_uuid', '') or ''),
        adapter_type,
        str(query.session.launcher_type.value),
        str(query.session.launcher_id),
    )


def _prune_pending_forms(now: float | None = None) -> None:
    if now is None:
        now = time.time()
    for session_key in list(_PENDING_FORMS.keys()):
        forms = _PENDING_FORMS[session_key]
        expired_tokens = [token for token, data in forms.items() if data.get('_expires_at', 0) <= now]
        for token in expired_tokens:
            forms.pop(token, None)
        if not forms:
            _PENDING_FORMS.pop(session_key, None)


def _set_pending_form(session_key: PendingFormKey, form_data: dict[str, typing.Any]) -> None:
    _prune_pending_forms()
    stored = dict(form_data)
    expiration_time = stored.get('expiration_time')
    try:
        expiration_ts = float(expiration_time) if expiration_time is not None else 0.0
    except (TypeError, ValueError):
        expiration_ts = 0.0
    stored['_expires_at'] = expiration_ts or (time.time() + _PENDING_FORM_DEFAULT_TTL)
    form_token = str(stored.get('form_token') or '')
    forms = _PENDING_FORMS.setdefault(session_key, OrderedDict())
    # Re-insert at the end so this becomes the "latest" entry
    forms.pop(form_token, None)
    forms[form_token] = stored


def _get_pending_form_by_token(session_key: PendingFormKey, form_token: str) -> dict[str, typing.Any] | None:
    _prune_pending_forms()
    forms = _PENDING_FORMS.get(session_key)
    if not forms or not form_token:
        return None
    return forms.get(form_token)


def _get_pending_form_by_w_suffix(session_key: PendingFormKey, w_suffix: str) -> dict[str, typing.Any] | None:
    """Look up a pending form whose workflow_run_id ends with the given suffix.

    Used by adapters (e.g. Telegram) whose callback payload is too small to
    carry the full form_token / workflow_run_id.
    """
    _prune_pending_forms()
    forms = _PENDING_FORMS.get(session_key)
    if not forms or not w_suffix:
        return None
    for token in reversed(forms):
        form = forms[token]
        if str(form.get('workflow_run_id', '')).endswith(w_suffix):
            return form
    return None


def _get_latest_pending_form(session_key: PendingFormKey) -> dict[str, typing.Any] | None:
    _prune_pending_forms()
    forms = _PENDING_FORMS.get(session_key)
    if not forms:
        return None
    return forms[next(reversed(forms))]


def _iter_pending_forms(session_key: PendingFormKey) -> typing.Iterator[dict[str, typing.Any]]:
    """Iterate pending forms for a session, newest-first."""
    _prune_pending_forms()
    forms = _PENDING_FORMS.get(session_key)
    if not forms:
        return
    for token in reversed(list(forms.keys())):
        yield forms[token]


def _clear_pending_form(session_key: PendingFormKey, form_token: str | None = None) -> None:
    """Clear one specific pending form (by token) or all forms for the session."""
    forms = _PENDING_FORMS.get(session_key)
    if not forms:
        return
    if form_token is None:
        _PENDING_FORMS.pop(session_key, None)
        return
    forms.pop(form_token, None)
    if not forms:
        _PENDING_FORMS.pop(session_key, None)


def _format_human_input_text(
    node_title: str,
    form_content: str,
    actions: list[dict[str, typing.Any]],
    input_defs: list[dict[str, typing.Any]] | None = None,
) -> str:
    """Render a paused-workflow human-input prompt as plain text.

    Used by adapters without rich UI (no buttons/cards) so users can reply
    with the option number or the option title to resume the workflow.
    """
    input_defs = input_defs or []
    form_content = _strip_form_field_placeholders(form_content, input_defs)
    lines: list[str] = [f'[Human Input Required] {node_title or ""}'.rstrip()]
    if form_content:
        lines.append('')
        lines.append(form_content)
    field_help = _format_human_input_fields_text(input_defs)
    if field_help:
        lines.append('')
        lines.append(field_help)
    if actions:
        lines.append('')
        if input_defs:
            lines.append('Reply with action plus field values to continue:')
            lines.append('  action: <number or title>')
        else:
            lines.append('Reply with the number or title to continue:')
        for idx, action in enumerate(actions, start=1):
            title = action.get('title') or action.get('id') or ''
            lines.append(f'  {idx}. {title}')
    return '\n'.join(lines)


def _normalize_form_input_defs(raw_inputs: typing.Any) -> list[dict[str, typing.Any]]:
    if not isinstance(raw_inputs, list):
        return []
    normalized: list[dict[str, typing.Any]] = []
    for item in raw_inputs:
        if not isinstance(item, dict):
            continue
        field = dict(item)
        name = str(
            field.get('output_variable_name') or field.get('variable') or field.get('name') or field.get('id') or ''
        ).strip()
        if not name:
            continue
        field['output_variable_name'] = name
        normalized.append(field)
    return normalized


def _field_name(field: dict[str, typing.Any]) -> str:
    return str(field.get('output_variable_name') or '').strip()


def _field_type(field: dict[str, typing.Any]) -> str:
    return str(field.get('type') or 'text').strip().lower()


def _select_options(field: dict[str, typing.Any]) -> list[str]:
    source = field.get('option_source') or {}
    value = source.get('value') if isinstance(source, dict) else None
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [part.strip() for part in value.splitlines() if part.strip()]
    options = field.get('options')
    if isinstance(options, list):
        result: list[str] = []
        for item in options:
            if isinstance(item, dict):
                result.append(str(item.get('label') or item.get('value') or ''))
            else:
                result.append(str(item))
        return [item for item in result if item]
    return []


def _normalize_select_value(
    value: typing.Any,
    options: list[str],
    *,
    allow_legacy_zero_based_index: bool = False,
    allow_one_based_index: bool = False,
) -> tuple[bool, typing.Any]:
    """Resolve a select input without confusing numeric values with indexes."""
    if not options:
        return True, value

    parsed = value
    if isinstance(value, str):
        stripped = value.strip()
        try:
            json_value = json.loads(stripped)
        except json.JSONDecodeError:
            json_value = None
        if isinstance(json_value, dict):
            parsed = json_value
        else:
            parsed = stripped

    if isinstance(parsed, dict):
        explicit_value = parsed.get('value')
        if explicit_value not in (None, ''):
            candidate = str(explicit_value).strip()
            match = next((option for option in options if option.casefold() == candidate.casefold()), None)
            return (True, match) if match is not None else (False, value)
        explicit_index = parsed.get('index')
        if isinstance(explicit_index, int) and not isinstance(explicit_index, bool):
            if 0 <= explicit_index < len(options):
                return True, options[explicit_index]
            return False, value
        return False, value

    candidate = str(parsed).strip()
    match = next((option for option in options if option.casefold() == candidate.casefold()), None)
    if match is not None:
        return True, match

    if candidate.isdigit():
        index = int(candidate)
        if allow_one_based_index and 1 <= index <= len(options):
            return True, options[index - 1]
        if allow_legacy_zero_based_index and 0 <= index < len(options):
            return True, options[index]

    return False, value


def _default_field_value(field: dict[str, typing.Any]) -> typing.Any:
    default = field.get('default')
    if isinstance(default, dict):
        if default.get('type') == 'constant':
            return default.get('value')
        if 'value' in default:
            return default.get('value')
    return default


def _initial_form_inputs(
    input_defs: list[dict[str, typing.Any]],
    resolved_default_values: typing.Any = None,
) -> dict[str, typing.Any]:
    inputs: dict[str, typing.Any] = {}
    if isinstance(resolved_default_values, dict):
        inputs.update(resolved_default_values)
    for field in input_defs:
        name = _field_name(field)
        if not name or name in inputs:
            continue
        value = _default_field_value(field)
        if value not in (None, ''):
            inputs[name] = value
    return inputs


def _format_human_input_fields_text(input_defs: list[dict[str, typing.Any]]) -> str:
    if not input_defs:
        return ''

    lines = ['Fields:']
    for field in input_defs:
        name = _field_name(field)
        typ = _field_type(field)
        if typ == 'select':
            options = _select_options(field)
            option_text = ', '.join(f'{idx}. {value}' for idx, value in enumerate(options, start=1))
            lines.append(f'  - {name} (select): {option_text or "choose one option"}')
        elif typ in {'file', 'file-list'}:
            limit = field.get('number_limits') if typ == 'file-list' else 1
            allowed_types = ', '.join(field.get('allowed_file_types') or [])
            suffix = f', up to {limit}' if typ == 'file-list' and limit else ''
            allowed = f' ({allowed_types})' if allowed_types else ''
            lines.append(f'  - {name} ({typ}{allowed}{suffix}): upload file(s) or reply "{name}: <url>"')
        else:
            lines.append(f'  - {name} ({typ}): reply "{name}: <value>"')

    lines.append('You can reply with one or more lines like "field_name: value".')
    return '\n'.join(lines)


def _format_human_input_actions_text(actions: list[dict[str, typing.Any]], require_action_key: bool = False) -> str:
    if not actions:
        return ''
    lines: list[str] = []
    if require_action_key:
        lines.append('Actions: reply with "action: <number or title>" plus field values.')
    else:
        lines.append('Actions:')
    for idx, action in enumerate(actions, start=1):
        title = action.get('title') or action.get('id') or ''
        lines.append(f'  {idx}. {title}')
    return '\n'.join(lines)


def _strip_form_field_placeholders(form_content: str, input_defs: list[dict[str, typing.Any]]) -> str:
    if not form_content:
        return ''

    field_names = {_field_name(field) for field in input_defs if _field_name(field)}
    kept_lines: list[str] = []
    for line in form_content.splitlines():
        placeholder = re.fullmatch(r'\s*\{\{#\$output\.([^#{}]+)#\}\}\s*', line)
        if placeholder and placeholder.group(1) in field_names:
            continue
        kept_lines.append(line)

    cleaned = '\n'.join(kept_lines).strip()
    return re.sub(r'\n{3,}', '\n\n', cleaned)


def _form_content_for_platform(
    form_content: str,
    input_defs: list[dict[str, typing.Any]],
    actions: list[dict[str, typing.Any]],
) -> str:
    del actions
    form_content = _strip_form_field_placeholders(form_content, input_defs)
    field_help = _format_human_input_fields_text(input_defs)
    parts = [part for part in (form_content, field_help) if part]
    if not parts:
        return form_content
    return '\n\n'.join(parts)


def _extract_form_snapshot(
    workflow_run_id: str,
    reason: dict[str, typing.Any],
    user: str,
) -> tuple[dict[str, typing.Any], str, list[dict[str, typing.Any]], str]:
    raw_form_content = reason.get('form_content', '') or ''
    input_defs = _normalize_form_input_defs(reason.get('inputs', []))
    actions = reason.get('actions', [])
    display_form_content = _form_content_for_platform(raw_form_content, input_defs, actions)
    snapshot = {
        'workflow_run_id': workflow_run_id,
        'form_id': reason.get('form_id'),
        'form_token': reason.get('form_token'),
        'node_id': reason.get('node_id'),
        'node_title': reason.get('node_title', ''),
        'form_content': display_form_content,
        'raw_form_content': raw_form_content,
        'input_defs': input_defs,
        'inputs': _initial_form_inputs(input_defs, reason.get('resolved_default_values')),
        'actions': actions,
        'expiration_time': reason.get('expiration_time'),
        'user': user,
    }
    return snapshot, raw_form_content, input_defs, display_form_content


def _extract_key_value_inputs(text: str) -> dict[str, str]:
    stripped = text.strip()
    if not stripped:
        return {}
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return {str(k).strip(): str(v).strip() for k, v in parsed.items() if str(k).strip()}

    values: dict[str, str] = {}
    for line in stripped.splitlines():
        if ':' in line:
            key, value = line.split(':', 1)
        elif '=' in line:
            key, value = line.split('=', 1)
        else:
            continue
        key = key.strip()
        if key:
            values[key] = value.strip()
    return values


def _extract_urls(text: str) -> list[str]:
    return re.findall(r'https?://[^\s,，]+', text or '')


def _file_type_from_mime(content_type: str) -> str:
    if content_type and content_type.startswith('image/'):
        return 'image'
    if content_type and content_type.startswith('audio/'):
        return 'audio'
    if content_type and content_type.startswith('video/'):
        return 'video'
    return 'document'


def _format_partial_form_notice(pending_form: dict[str, typing.Any]) -> str:
    actions = pending_form.get('actions') or []
    lines = ['Received the form value(s).']
    action_help = _format_human_input_actions_text(actions, require_action_key=True)
    if action_help:
        lines.append('')
        lines.append(action_help)
    return '\n'.join(lines)


def _next_missing_form_field(form: dict[str, typing.Any], inputs: dict[str, typing.Any] | None = None) -> dict | None:
    values = inputs if inputs is not None else form.get('inputs') or {}
    for field in form.get('input_defs') or []:
        name = _field_name(field)
        if not name:
            continue
        if values.get(name) in (None, '', []):
            return field
    return None


def _format_single_form_field_text(field: dict[str, typing.Any]) -> str:
    name = _field_name(field)
    typ = _field_type(field)
    if typ == 'select':
        options = _select_options(field)
        option_text = ', '.join(f'{idx}. {value}' for idx, value in enumerate(options, start=1))
        return f'{name} (select): {option_text or "choose one option"}'
    if typ in {'file', 'file-list'}:
        limit = field.get('number_limits') if typ == 'file-list' else 1
        allowed_types = ', '.join(field.get('allowed_file_types') or [])
        suffix = f', up to {limit}' if typ == 'file-list' and limit else ''
        allowed = f' ({allowed_types})' if allowed_types else ''
        return f'{name} ({typ}{allowed}{suffix}): upload file(s) or reply "{name}: <url>"'
    return f'{name} ({typ}): reply "{name}: <value>"'


def _form_content_placeholder_matches(form_content: str) -> list[re.Match[str]]:
    return list(re.finditer(r'\{\{#\$output\.([^#{}]+)#\}\}', form_content or ''))


def _form_content_for_field(form_content: str, field: dict[str, typing.Any]) -> str:
    """Return the template section immediately preceding a field placeholder."""
    field_name = _field_name(field)
    matches = _form_content_placeholder_matches(form_content)
    for index, match in enumerate(matches):
        if match.group(1).strip() != field_name:
            continue
        start = matches[index - 1].end() if index else 0
        return form_content[start : match.start()].strip()
    return ''


def _form_content_for_actions(form_content: str, input_defs: list[dict[str, typing.Any]]) -> str:
    """Return content after the last form-field placeholder for the action step."""
    field_names = {_field_name(field) for field in input_defs if _field_name(field)}
    matches = [
        match for match in _form_content_placeholder_matches(form_content) if match.group(1).strip() in field_names
    ]
    if not matches:
        return _strip_form_field_placeholders(form_content, input_defs)
    return form_content[matches[-1].end() :].strip()


def _field_input_form_data(pending_form: dict[str, typing.Any], field: dict[str, typing.Any] | None) -> dict | None:
    if not field:
        return None
    raw_form_content = pending_form.get('raw_form_content') or ''
    field_content = _form_content_for_field(raw_form_content, field)
    return {
        'form_content': field_content or _format_single_form_field_text(field),
        'raw_form_content': pending_form.get('raw_form_content') or pending_form.get('form_content') or '',
        'input_defs': pending_form.get('input_defs') or [],
        'all_input_defs': pending_form.get('input_defs') or [],
        'inputs': pending_form.get('inputs', {}),
        'actions': pending_form.get('actions') or [],
        'node_title': pending_form.get('node_title', ''),
        'workflow_run_id': pending_form.get('workflow_run_id', ''),
        'form_token': pending_form.get('form_token', ''),
        '_current_input_field': _field_name(field),
    }


def _action_select_form_data(pending_form: dict[str, typing.Any]) -> dict[str, typing.Any] | None:
    actions = pending_form.get('actions') or []
    if not actions:
        return None
    form_content = pending_form.get('raw_form_content') or pending_form.get('form_content') or ''
    return {
        'form_content': _form_content_for_actions(form_content, pending_form.get('input_defs') or []),
        'raw_form_content': form_content,
        'input_defs': [],
        'all_input_defs': pending_form.get('input_defs') or [],
        'inputs': pending_form.get('inputs', {}),
        'actions': actions,
        'node_title': pending_form.get('node_title', ''),
        'workflow_run_id': pending_form.get('workflow_run_id', ''),
        'form_token': pending_form.get('form_token', ''),
        '_action_select_only': True,
    }


def _initial_interactive_form_data(pending_form: dict[str, typing.Any]) -> dict[str, typing.Any] | None:
    next_field = _next_missing_form_field(pending_form)
    pending_form['current_input_field'] = _field_name(next_field) if next_field else ''
    if next_field:
        return _field_input_form_data(pending_form, next_field)
    return _action_select_form_data(pending_form)


def _attach_partial_form_data(message: typing.Any, form_action: dict[str, typing.Any]) -> typing.Any:
    form_data = form_action.get('_form_data')
    if form_data:
        message._form_data = form_data
    return message


def _missing_required_form_fields(form: dict[str, typing.Any], inputs: dict[str, typing.Any]) -> list[str]:
    missing: list[str] = []
    for field in form.get('input_defs') or []:
        name = _field_name(field)
        if not name:
            continue
        value = inputs.get(name)
        if value in (None, '', []):
            missing.append(name)
    return missing


def _format_missing_form_inputs_notice(form: dict[str, typing.Any], missing: list[str]) -> str:
    lines = ['Some required form fields are still missing.']
    if missing:
        lines.append('')
        lines.append('Missing fields: ' + ', '.join(missing))
    field_help = _format_human_input_fields_text(
        [field for field in form.get('input_defs') or [] if _field_name(field) in set(missing)]
    )
    if field_help:
        lines.append('')
        lines.append(field_help)
    action_help = _format_human_input_actions_text(form.get('actions') or [], require_action_key=True)
    if action_help:
        lines.append('')
        lines.append(action_help)
    return '\n'.join(lines)


def _invalid_select_inputs(form: dict[str, typing.Any], user_text: str) -> list[str]:
    keyed_values = _extract_key_value_inputs(user_text)
    current_field_name = str(form.get('current_input_field') or '').strip()
    invalid: list[str] = []
    for field in form.get('input_defs') or []:
        if _field_type(field) != 'select':
            continue
        name = _field_name(field)
        raw_value = keyed_values.get(name)
        if raw_value is None and not keyed_values and current_field_name == name and user_text.strip():
            raw_value = user_text.strip()
        if raw_value is None:
            continue
        valid, _ = _normalize_select_value(
            raw_value,
            _select_options(field),
            allow_one_based_index=True,
        )
        if not valid:
            invalid.append(name)
    return invalid


def _format_invalid_select_notice(form: dict[str, typing.Any], invalid: list[str]) -> str:
    lines = ['Invalid select value.']
    invalid_names = set(invalid)
    for field in form.get('input_defs') or []:
        name = _field_name(field)
        if name not in invalid_names:
            continue
        options = _select_options(field)
        choices = ', '.join(f'{index}. {option}' for index, option in enumerate(options, start=1))
        lines.append(f'{name}: {choices or "choose one of the available options"}')
    return '\n'.join(lines)


def _normalize_form_action_inputs(
    pending_form: dict[str, typing.Any],
    raw_inputs: dict[str, typing.Any],
) -> dict[str, typing.Any]:
    if not raw_inputs:
        return {}
    fields = {_field_name(field): field for field in pending_form.get('input_defs') or [] if _field_name(field)}
    normalized = dict(raw_inputs)
    for name, value in list(normalized.items()):
        field = fields.get(name)
        if not field or _field_type(field) != 'select':
            continue
        valid, selected = _normalize_select_value(
            value,
            _select_options(field),
            allow_legacy_zero_based_index=True,
        )
        if valid:
            normalized[name] = selected
        else:
            normalized.pop(name, None)
    return normalized


def _build_input_progress_action(
    pending_form: dict[str, typing.Any],
    inputs: dict[str, typing.Any],
    *,
    force_partial: bool = False,
) -> dict[str, typing.Any]:
    """Update a pending form after collecting field values.

    `force_partial` is used by native card controls (for example DingTalk
    Input/SelectBlock): those callbacks mean "store this field value and
    render the next step", not "submit a workflow action" unless there is a
    single action and no further choice is required.
    """
    actions = pending_form.get('actions') or []
    pending_form['inputs'] = inputs
    next_field = _next_missing_form_field(pending_form, inputs)
    pending_form['current_input_field'] = _field_name(next_field) if next_field else ''
    form_data = (
        _field_input_form_data(pending_form, next_field) if next_field else _action_select_form_data(pending_form)
    )

    if force_partial or len(actions) > 1 or next_field:
        return {
            '_partial': True,
            'form_token': pending_form.get('form_token', ''),
            'workflow_run_id': pending_form.get('workflow_run_id', ''),
            'node_title': pending_form.get('node_title', ''),
            'inputs': inputs,
            'user': pending_form.get('user', ''),
            'notice': (
                form_data.get('form_content') if next_field and form_data else _format_partial_form_notice(pending_form)
            ),
            '_form_data': form_data,
        }

    action = actions[0] if actions else {}
    return {
        'form_token': pending_form.get('form_token', ''),
        'workflow_run_id': pending_form.get('workflow_run_id', ''),
        'action_id': action.get('id', ''),
        'action_title': action.get('title', action.get('id', '')),
        'node_title': pending_form.get('node_title', ''),
        'inputs': inputs,
        'user': pending_form.get('user', ''),
    }


@runner.runner_class('dify-service-api')
class DifyServiceAPIRunner(runner.RequestRunner):
    """Dify Service API 对话请求器"""

    dify_client: client.AsyncDifyServiceClient

    def __init__(self, ap: app.Application, pipeline_config: dict):
        self.ap = ap
        self.pipeline_config = pipeline_config

        valid_app_types = ['chat', 'agent', 'workflow', 'chatflow']
        if self.pipeline_config['ai']['dify-service-api']['app-type'] not in valid_app_types:
            raise errors.DifyAPIError(
                f'不支持的 Dify 应用类型: {self.pipeline_config["ai"]["dify-service-api"]["app-type"]}'
            )

        api_key = self.pipeline_config['ai']['dify-service-api']['api-key']

        self.dify_client = client.AsyncDifyServiceClient(
            api_key=api_key,
            base_url=self.pipeline_config['ai']['dify-service-api']['base-url'],
        )

    def _process_thinking_content(
        self,
        content: str,
    ) -> tuple[str, str]:
        """处理思维链内容

        Args:
            content: 原始内容
        Returns:
            (处理后的内容, 提取的思维链内容)
        """
        remove_think = self.pipeline_config['output'].get('misc', {}).get('remove-think')
        thinking_content = ''
        # 从 content 中提取 <think> 标签内容
        if content and '<think>' in content and '</think>' in content:
            import re

            think_pattern = r'<think>(.*?)</think>'
            think_matches = re.findall(think_pattern, content, re.DOTALL)
            if think_matches:
                thinking_content = '\n'.join(think_matches)
                # 移除 content 中的 <think> 标签
                content = re.sub(think_pattern, '', content, flags=re.DOTALL).strip()

        # 3. 根据 remove_think 参数决定是否保留思维链
        if remove_think:
            return content, ''
        else:
            # 如果有思维链内容，将其以 <think> 格式添加到 content 开头
            if thinking_content:
                content = f'<think>\n{thinking_content}\n</think>\n{content}'.strip()
            return content, thinking_content

    def _extract_dify_text_output(self, value: typing.Any) -> str:
        """Extract text content from Dify output payload."""
        if value is None:
            return ''
        if isinstance(value, dict):
            content = value.get('content')
            if isinstance(content, str):
                return content
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return ''
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return value
            if isinstance(parsed, dict) and isinstance(parsed.get('content'), str):
                return parsed['content']
            return value
        return str(value)

    async def _preprocess_user_message(self, query: pipeline_query.Query) -> tuple[str, list[dict]]:
        """预处理用户消息，提取纯文本，并将图片/文件上传到 Dify 服务

        Returns:
            tuple[str, list[dict]]: 纯文本和上传后的文件描述（包含 type 与 id）
        """
        plain_text = ''
        upload_files: list[dict] = []
        user_tag = _dify_user_from_query(query)

        async def upload_file_bytes(file_name: str, file_bytes: bytes, content_type: str) -> str:
            file_name = file_name or 'file'
            content_type = content_type or 'application/octet-stream'
            file = (file_name, file_bytes, content_type)
            resp = await self.dify_client.upload_file(file, user_tag)
            return resp['id']

        async def download_file(file_url: str) -> tuple[bytes, str]:
            """Download file from url (supports data url)."""

            async with httpx.AsyncClient() as client_session:
                resp = await client_session.get(file_url)
                resp.raise_for_status()
                content_type = (
                    resp.headers.get('content-type') or mimetypes.guess_type(file_url)[0] or 'application/octet-stream'
                )
                return resp.content, content_type

        def _detect_file_type(content_type: str) -> str:
            """Map MIME to dify file type."""
            if content_type and content_type.startswith('image/'):
                return 'image'
            if content_type and content_type.startswith('audio/'):
                return 'audio'
            if content_type and content_type.startswith('video/'):
                return 'video'
            return 'document'

        if isinstance(query.user_message.content, list):
            for ce in query.user_message.content:
                if ce.type == 'text':
                    plain_text += ce.text
                elif ce.type == 'image_base64':
                    image_b64, image_format = await image.extract_b64_and_format(ce.image_base64)
                    file_bytes = base64.b64decode(image_b64)
                    image_id = await upload_file_bytes(f'img.{image_format}', file_bytes, f'image/{image_format}')
                    upload_files.append({'type': 'image', 'id': image_id})
                elif ce.type == 'file_url':
                    file_url = getattr(ce, 'file_url', None)
                    file_name = getattr(ce, 'file_name', None) or 'file'
                    try:
                        file_bytes, content_type = await download_file(file_url)
                        file_id = await upload_file_bytes(file_name, file_bytes, content_type)
                        file_type = _detect_file_type(content_type)
                        upload_files.append({'type': file_type, 'id': file_id})
                    except Exception as e:
                        self.ap.logger.warning(f'dify file upload failed: {e}')
                elif ce.type == 'file_base64':
                    file_name = getattr(ce, 'file_name', None) or 'file'

                    header, b64_data = ce.file_base64.split(',', 1)
                    content_type = 'application/octet-stream'
                    if ';' in header:
                        content_type = header.split(';')[0][5:] or content_type
                    file_bytes = base64.b64decode(b64_data)
                    file_id = await upload_file_bytes(file_name, file_bytes, content_type)
                    file_type = _detect_file_type(content_type)
                    upload_files.append({'type': file_type, 'id': file_id})

        elif isinstance(query.user_message.content, str):
            plain_text = query.user_message.content

        plain_text = plain_text if plain_text else self.pipeline_config['ai']['dify-service-api']['base-prompt']

        return plain_text, upload_files

    async def _upload_file_bytes_for_user(
        self, file_name: str, file_bytes: bytes, content_type: str, user: str
    ) -> dict:
        file_name = file_name or 'file'
        content_type = content_type or 'application/octet-stream'
        resp = await self.dify_client.upload_file((file_name, file_bytes, content_type), user)
        return {
            'type': _file_type_from_mime(content_type),
            'transfer_method': 'local_file',
            'upload_file_id': resp['id'],
        }

    async def _download_file_for_form(self, file_url: str) -> tuple[bytes, str, str]:
        async with httpx.AsyncClient() as client_session:
            resp = await client_session.get(file_url)
            resp.raise_for_status()
            content_type = (
                resp.headers.get('content-type') or mimetypes.guess_type(file_url)[0] or 'application/octet-stream'
            )
            parsed = urlparse(file_url)
            file_name = os.path.basename(parsed.path) or 'file'
            return resp.content, content_type, file_name

    async def _platform_file_to_dify(self, item: typing.Any, user: str) -> dict | None:
        try:
            if isinstance(item, platform_message.Image):
                file_bytes, content_type = await item.get_bytes()
                ext = (content_type or 'image/jpeg').split('/')[-1] or 'jpg'
                return await self._upload_file_bytes_for_user(f'image.{ext}', file_bytes, content_type, user)
            if isinstance(item, platform_message.File):
                file_name = item.name or 'file'
                if item.base64:
                    header, b64_data = item.base64.split(',', 1) if ',' in item.base64 else ('', item.base64)
                    content_type = 'application/octet-stream'
                    if header.startswith('data:') and ';' in header:
                        content_type = header.split(';', 1)[0][5:] or content_type
                    return await self._upload_file_bytes_for_user(
                        file_name,
                        base64.b64decode(b64_data),
                        content_type,
                        user,
                    )
                if item.path:
                    with open(item.path, 'rb') as f:
                        file_bytes = f.read()
                    content_type = mimetypes.guess_type(str(item.path))[0] or 'application/octet-stream'
                    file_name = item.name or os.path.basename(str(item.path)) or 'file'
                    return await self._upload_file_bytes_for_user(file_name, file_bytes, content_type, user)
                if item.url:
                    file_bytes, content_type, downloaded_name = await self._download_file_for_form(item.url)
                    return await self._upload_file_bytes_for_user(
                        file_name or downloaded_name,
                        file_bytes,
                        content_type,
                        user,
                    )
        except Exception as e:
            self.ap.logger.warning(f'dify human-input file upload failed: {e}')
        return None

    async def _collect_form_inputs_from_query(
        self,
        query: pipeline_query.Query,
        pending_form: dict,
        user_text: str,
    ) -> dict[str, typing.Any]:
        input_defs = pending_form.get('input_defs') or []
        if not input_defs:
            return dict(pending_form.get('inputs') or {})

        values = dict(pending_form.get('inputs') or {})
        keyed_values = _extract_key_value_inputs(user_text)
        user = pending_form.get('user') or _dify_user_from_query(query)
        current_field_name = str(pending_form.get('current_input_field') or '').strip()

        file_fields = [field for field in input_defs if _field_type(field) in {'file', 'file-list'}]
        uploaded_files: list[dict] = []
        if file_fields:
            for component in query.message_chain:
                if isinstance(component, (platform_message.Image, platform_message.File)):
                    uploaded = await self._platform_file_to_dify(component, user)
                    if uploaded:
                        uploaded_files.append(uploaded)

        for field in input_defs:
            name = _field_name(field)
            typ = _field_type(field)
            if not name:
                continue

            raw_value = keyed_values.get(name)
            if raw_value is None and not keyed_values and current_field_name == name and user_text.strip():
                raw_value = user_text.strip()
            if raw_value is None and current_field_name == name and typ in {'file', 'file-list'} and uploaded_files:
                raw_value = ''
            if raw_value is None:
                continue

            if typ == 'select':
                options = _select_options(field)
                valid, selected = _normalize_select_value(
                    raw_value,
                    options,
                    allow_one_based_index=True,
                )
                if valid:
                    values[name] = selected
            elif typ == 'file':
                urls = _extract_urls(raw_value)
                if urls:
                    values[name] = {
                        'type': _file_type_from_mime(mimetypes.guess_type(urls[0])[0] or ''),
                        'transfer_method': 'remote_url',
                        'url': urls[0],
                    }
                elif uploaded_files:
                    values[name] = uploaded_files.pop(0)
            elif typ == 'file-list':
                urls = _extract_urls(raw_value)
                file_values = [
                    {
                        'type': _file_type_from_mime(mimetypes.guess_type(url)[0] or ''),
                        'transfer_method': 'remote_url',
                        'url': url,
                    }
                    for url in urls
                ]
                if uploaded_files:
                    file_values.extend(uploaded_files)
                    uploaded_files = []
                limit = field.get('number_limits')
                if isinstance(limit, int) and limit > 0:
                    file_values = file_values[:limit]
                if file_values:
                    values[name] = file_values
            else:
                values[name] = raw_value

        for field in file_fields:
            if not uploaded_files:
                break
            name = _field_name(field)
            if not name or values.get(name):
                continue
            if _field_type(field) == 'file-list':
                limit = field.get('number_limits')
                count = limit if isinstance(limit, int) and limit > 0 else len(uploaded_files)
                values[name] = uploaded_files[:count]
                uploaded_files = uploaded_files[count:]
            else:
                values[name] = uploaded_files.pop(0)

        text_field_names = [
            _field_name(field)
            for field in input_defs
            if _field_type(field) not in {'file', 'file-list', 'select'} and _field_name(field)
        ]
        if not current_field_name and not keyed_values and len(text_field_names) == 1 and user_text.strip():
            values[text_field_names[0]] = user_text.strip()

        return values

    async def _chat_messages(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.Message, None]:
        """调用聊天助手"""
        # Check if this is a form action resume (button click or text match)
        form_action_raw = query.variables.get('_dify_form_action')
        session_key = _session_key_from_query(query)

        if form_action_raw:
            form_action = self._merge_pending_form_action(session_key, form_action_raw)
        else:
            form_action = await self._match_pending_form_action(query, session_key, str(query.message_chain))

        if form_action:
            if form_action.get('_partial'):
                yield _attach_partial_form_data(
                    provider_message.Message(role='assistant', content=form_action.get('notice', 'Received.')),
                    form_action,
                )
                return
            async for msg in self._submit_workflow_form_blocking(form_action, session_key):
                yield msg
            _clear_pending_form(session_key, form_action.get('form_token') or None)
            return

        cov_id = query.session.using_conversation.uuid or None
        query.variables['conversation_id'] = cov_id

        plain_text, upload_files = await self._preprocess_user_message(query)

        files = [
            {
                'type': f['type'],
                'transfer_method': 'local_file',
                'upload_file_id': f['id'],
            }
            for f in upload_files
        ]

        mode = 'basic'  # 标记是基础编排还是工作流编排

        basic_mode_pending_chunk = ''

        inputs = {}

        inputs.update(query.variables)

        chunk = None  # 初始化chunk变量，防止在没有响应时引用错误

        async for chunk in self.dify_client.chat_messages(
            inputs=inputs,
            query=plain_text,
            user=_dify_user_from_query(query),
            conversation_id=cov_id,
            files=files,
            timeout=120,
        ):
            self.ap.logger.debug('dify-chat-chunk: ' + str(chunk))

            if chunk['event'] == 'workflow_started':
                mode = 'workflow'

            if mode == 'workflow':
                if chunk['event'] == 'workflow_paused':
                    reasons = chunk['data'].get('reasons', [])
                    workflow_run_id = chunk['data'].get('workflow_run_id', '')
                    for reason in reasons:
                        if reason.get('TYPE') != 'human_input_required':
                            continue
                        user = _dify_user_from_query(query)
                        form_snapshot, raw_form_content, input_defs, _ = _extract_form_snapshot(
                            workflow_run_id,
                            reason,
                            user,
                        )
                        actions = form_snapshot.get('actions', [])
                        node_title = form_snapshot.get('node_title', '')

                        _set_pending_form(_session_key_from_query(query), form_snapshot)

                        query.variables['_dify_form_render'] = {
                            'form_content': raw_form_content,
                            'input_defs': input_defs,
                            'actions': actions,
                            'node_title': node_title,
                        }

                        display_text = _format_human_input_text(node_title, raw_form_content, actions, input_defs)
                        yield provider_message.Message(
                            role='assistant',
                            content=display_text,
                        )
                    return

                if chunk['event'] == 'node_finished':
                    if chunk['data']['node_type'] == 'answer':
                        answer = self._extract_dify_text_output(chunk['data']['outputs'].get('answer'))
                        content, _ = self._process_thinking_content(answer)

                        yield provider_message.Message(
                            role='assistant',
                            content=content,
                        )
            elif mode == 'basic':
                if chunk['event'] == 'message':
                    basic_mode_pending_chunk = _merge_stream_text(basic_mode_pending_chunk, chunk['answer'])
                elif chunk['event'] == 'message_end':
                    content, _ = self._process_thinking_content(basic_mode_pending_chunk)
                    yield provider_message.Message(
                        role='assistant',
                        content=content,
                    )
                    basic_mode_pending_chunk = ''

        if chunk is None:
            raise errors.DifyAPIError('Dify API 没有返回任何响应，请检查网络连接和API配置')

        query.session.using_conversation.uuid = chunk['conversation_id']

    async def _agent_chat_messages(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.Message, None]:
        """调用聊天助手"""
        cov_id = query.session.using_conversation.uuid or None
        query.variables['conversation_id'] = cov_id

        plain_text, upload_files = await self._preprocess_user_message(query)

        files = [
            {
                'type': f['type'],
                'transfer_method': 'local_file',
                'upload_file_id': f['id'],
            }
            for f in upload_files
        ]

        ignored_events = []

        inputs = {}

        inputs.update(query.variables)

        pending_agent_message = ''

        chunk = None  # 初始化chunk变量，防止在没有响应时引用错误

        async for chunk in self.dify_client.chat_messages(
            inputs=inputs,
            query=plain_text,
            user=_dify_user_from_query(query),
            response_mode='streaming',
            conversation_id=cov_id,
            files=files,
            timeout=120,
        ):
            self.ap.logger.debug('dify-agent-chunk: ' + str(chunk))

            if chunk['event'] in ignored_events:
                continue

            if chunk['event'] == 'agent_message' or chunk['event'] == 'message':
                pending_agent_message = _merge_stream_text(pending_agent_message, chunk['answer'])
            else:
                if pending_agent_message.strip() != '':
                    pending_agent_message = pending_agent_message.replace('</details>Action:', '</details>')
                    content, _ = self._process_thinking_content(pending_agent_message)
                    yield provider_message.Message(
                        role='assistant',
                        content=content,
                    )
                pending_agent_message = ''

                if chunk['event'] == 'agent_thought':
                    if chunk['tool'] != '' and chunk['observation'] != '':  # 工具调用结果，跳过
                        continue

                    if chunk['tool']:
                        msg = provider_message.Message(
                            role='assistant',
                            tool_calls=[
                                provider_message.ToolCall(
                                    id=chunk['id'],
                                    type='function',
                                    function=provider_message.FunctionCall(
                                        name=chunk['tool'],
                                        arguments=json.dumps({}),
                                    ),
                                )
                            ],
                        )
                        yield msg
                if chunk['event'] == 'message_file':
                    if chunk['type'] == 'image' and chunk['belongs_to'] == 'assistant':
                        # 检查URL是否已经是完整的连接
                        if chunk['url'].startswith('http://') or chunk['url'].startswith('https://'):
                            image_url = chunk['url']
                        else:
                            base_url = self.dify_client.base_url

                            if base_url.endswith('/v1'):
                                base_url = base_url[:-3]

                            image_url = base_url + chunk['url']

                        yield provider_message.Message(
                            role='assistant',
                            content=[provider_message.ContentElement.from_image_url(image_url)],
                        )
                if chunk['event'] == 'error':
                    raise errors.DifyAPIError('dify 服务错误: ' + chunk['message'])

        if chunk is None:
            raise errors.DifyAPIError('Dify API 没有返回任何响应，请检查网络连接和API配置')

        query.session.using_conversation.uuid = chunk['conversation_id']

    async def _submit_workflow_form_blocking(
        self, form_action: dict, session_key: PendingFormKey
    ) -> typing.AsyncGenerator[provider_message.Message, None]:
        """Submit human input to resume a paused Dify workflow (non-streaming)."""

        form_token = form_action['form_token']
        workflow_run_id = form_action['workflow_run_id']
        user = form_action['user']
        action_id = form_action.get('action_id', '')
        inputs = form_action.get('inputs', {})
        pending_content = ''
        saw_event = False
        answer_node_seen = False

        async for chunk in self.dify_client.workflow_submit(
            form_token=form_token,
            workflow_run_id=workflow_run_id,
            inputs=inputs,
            user=user,
            action=action_id,
            timeout=120,
        ):
            saw_event = True
            self.ap.logger.debug('dify-workflow-submit-chunk: ' + str(chunk))
            event = chunk.get('event')

            if event == 'error':
                raise errors.DifyAPIError(chunk.get('message') or 'Dify workflow resume failed')

            if event in ('message', 'agent_message') and not answer_node_seen:
                pending_content = _merge_stream_text(
                    pending_content,
                    self._extract_dify_text_output(chunk.get('answer')),
                )

            if event == 'text_chunk':
                pending_content = _merge_stream_text(
                    pending_content,
                    self._extract_dify_text_output(chunk.get('data', {}).get('text')),
                )

            if event == 'node_finished' and chunk.get('data', {}).get('node_type') == 'answer':
                answer = self._extract_dify_text_output(chunk.get('data', {}).get('outputs', {}).get('answer'))
                if answer:
                    # Answer-node output is the complete answer and may duplicate
                    # preceding message events, so prefer it over the accumulator.
                    pending_content = answer
                    answer_node_seen = True

            if event == 'workflow_finished':
                data = chunk.get('data', {})
                if data.get('error'):
                    raise errors.DifyAPIError(data['error'])
                if not pending_content:
                    pending_content = self._extract_dify_text_output(data.get('outputs', {}).get('summary'))
                content, _ = self._process_thinking_content(pending_content)
                yield provider_message.Message(
                    role='assistant',
                    content=content,
                )
                return

            if event == 'workflow_paused':
                reasons = chunk.get('data', {}).get('reasons', [])
                new_run_id = chunk.get('data', {}).get('workflow_run_id', workflow_run_id)
                for reason in reasons:
                    if reason.get('TYPE') != 'human_input_required':
                        continue
                    form_snapshot, raw_form_content, input_defs, _ = _extract_form_snapshot(
                        new_run_id,
                        reason,
                        user,
                    )
                    actions = form_snapshot.get('actions', [])
                    paused_node_title = form_snapshot.get('node_title', '')

                    _set_pending_form(session_key, form_snapshot)

                    display_text = _format_human_input_text(
                        paused_node_title,
                        raw_form_content,
                        actions,
                        input_defs,
                    )
                    yield provider_message.Message(
                        role='assistant',
                        content=display_text,
                    )
                    return

        if not saw_event:
            raise errors.DifyAPIError('Dify API did not return any workflow resume events')
        raise errors.DifyAPIError('Dify workflow resume stream ended before a terminal event')

    def _resolve_pending_form(self, session_key: PendingFormKey, form_action: dict) -> dict | None:
        """Locate the pending form this action targets.

        Tries identifiers in order of specificity: form_token, full
        workflow_run_id, workflow_run_id suffix (Telegram-style compact id),
        then falls back to the newest pending form for the session.
        """
        form_token = form_action.get('form_token')
        if form_token:
            form = _get_pending_form_by_token(session_key, form_token)
            if form:
                return form

        workflow_run_id = form_action.get('workflow_run_id')
        if workflow_run_id:
            for form in _iter_pending_forms(session_key):
                if form.get('workflow_run_id') == workflow_run_id:
                    return form

        w_suffix = form_action.get('w_suffix')
        if w_suffix:
            form = _get_pending_form_by_w_suffix(session_key, w_suffix)
            if form:
                return form

        return _get_latest_pending_form(session_key)

    def _merge_pending_form_action(self, session_key: PendingFormKey, form_action: dict | None) -> dict | None:
        """Backfill resume fields from the matching pending form."""
        if not form_action:
            return None

        merged_action = dict(form_action)
        merged_action.pop('w_suffix', None)
        pending_form = self._resolve_pending_form(session_key, form_action)
        if pending_form:
            merged_action['form_token'] = merged_action.get('form_token') or pending_form.get('form_token', '')
            merged_action['workflow_run_id'] = merged_action.get('workflow_run_id') or pending_form.get(
                'workflow_run_id', ''
            )
            inputs = dict(pending_form.get('inputs') or {})
            component_inputs = merged_action.get('inputs') or {}
            current_field_name = str(
                merged_action.pop('_current_input_field', None) or pending_form.get('current_input_field') or ''
            ).strip()
            if current_field_name and current_field_name not in component_inputs:
                for component_key in ('input', 'select'):
                    if component_key in component_inputs:
                        component_inputs[current_field_name] = component_inputs.pop(component_key)
                        break
            component_inputs = _normalize_form_action_inputs(pending_form, component_inputs)
            inputs.update(component_inputs)
            merged_action['inputs'] = inputs
            merged_action.setdefault('user', pending_form.get('user', ''))
            merged_action.setdefault('node_title', pending_form.get('node_title', ''))
            if merged_action.pop('_input_progress', False):
                return _build_input_progress_action(pending_form, inputs, force_partial=True)
            missing_fields = _missing_required_form_fields(pending_form, inputs)
            if missing_fields:
                pending_form['inputs'] = inputs
                next_field = _next_missing_form_field(pending_form, inputs)
                pending_form['current_input_field'] = _field_name(next_field) if next_field else ''
                form_data = (
                    _field_input_form_data(pending_form, next_field)
                    if next_field
                    else _action_select_form_data(pending_form)
                )
                merged_action['_partial'] = True
                merged_action['notice'] = _format_missing_form_inputs_notice(pending_form, missing_fields)
                merged_action['_form_data'] = form_data

            # Resolve clicked action's display title from the stored actions list
            if 'action_title' not in merged_action:
                clicked_id = merged_action.get('action_id', '')
                for action in pending_form.get('actions', []):
                    if str(action.get('id', '')) == str(clicked_id):
                        merged_action['action_title'] = action.get('title', clicked_id)
                        break

        return merged_action

    async def _match_pending_form_action(
        self,
        query: pipeline_query.Query,
        session_key: PendingFormKey,
        user_text: str,
    ) -> dict | None:
        """Match plain text replies against pending Dify form actions.

        Resolution order:
        1. A pure digit reply (e.g. "1", "2") maps to the 1-indexed action of
           the most recent pending form. Lets users on plain-text platforms
           pick options without retyping titles.
        2. Otherwise, iterate pending forms newest-first and match each
           action's title/id case-insensitively. The first hit wins, so when
           two forms share a button label the newer one resolves.
        """
        normalized_text = user_text.strip().lower()
        latest_form = _get_latest_pending_form(session_key)
        has_file_upload = bool(
            latest_form
            and latest_form.get('input_defs')
            and any(_field_type(field) in {'file', 'file-list'} for field in latest_form.get('input_defs') or [])
            and any(
                isinstance(component, (platform_message.Image, platform_message.File))
                for component in query.message_chain
            )
        )
        if not normalized_text and not has_file_upload:
            return None
        keyed_values = _extract_key_value_inputs(user_text)
        requested_action = (
            keyed_values.get('action')
            or keyed_values.get('Action')
            or keyed_values.get('action_id')
            or keyed_values.get('actionId')
        )
        normalized_action = requested_action.strip().lower() if requested_action else ''

        def _build(pending_form: dict, action: dict) -> dict:
            return {
                'form_token': pending_form.get('form_token', ''),
                'workflow_run_id': pending_form.get('workflow_run_id', ''),
                'action_id': action.get('id', ''),
                'action_title': action.get('title', action.get('id', '')),
                'node_title': pending_form.get('node_title', ''),
                'inputs': pending_form.get('inputs', {}),
                'user': pending_form.get('user', ''),
            }

        if latest_form:
            invalid_selects = _invalid_select_inputs(latest_form, user_text)
            if invalid_selects:
                inputs = await self._collect_form_inputs_from_query(query, latest_form, user_text)
                form_action = _build_input_progress_action(latest_form, inputs, force_partial=True)
                form_action['notice'] = _format_invalid_select_notice(latest_form, invalid_selects)
                return form_action

        if latest_form and latest_form.get('current_input_field') and not normalized_action:
            inputs = await self._collect_form_inputs_from_query(query, latest_form, user_text)
            if inputs != (latest_form.get('inputs') or {}):
                return _build_input_progress_action(latest_form, inputs)

        if latest_form and latest_form.get('input_defs') and not normalized_action:
            current_inputs = dict(latest_form.get('inputs') or {})
            missing_fields = _missing_required_form_fields(latest_form, current_inputs)
            if missing_fields:
                next_field = _next_missing_form_field(latest_form, current_inputs)
                if next_field:
                    latest_form['current_input_field'] = _field_name(next_field)
                inputs = await self._collect_form_inputs_from_query(query, latest_form, user_text)
                if inputs != current_inputs:
                    return _build_input_progress_action(latest_form, inputs)

        if normalized_text.isdigit() or normalized_action.isdigit():
            position = int(normalized_action or normalized_text)
            if latest_form is not None:
                actions = latest_form.get('actions', [])
                if 1 <= position <= len(actions):
                    form_action = _build(latest_form, actions[position - 1])
                    form_action['inputs'] = await self._collect_form_inputs_from_query(
                        query,
                        latest_form,
                        user_text,
                    )
                    return form_action

        for pending_form in _iter_pending_forms(session_key):
            for action in pending_form.get('actions', []):
                titles = {
                    str(action.get('title', '')).strip().lower(),
                    str(action.get('id', '')).strip().lower(),
                }
                if normalized_text in titles or (normalized_action and normalized_action in titles):
                    form_action = _build(pending_form, action)
                    form_action['inputs'] = await self._collect_form_inputs_from_query(
                        query,
                        pending_form,
                        user_text,
                    )
                    return form_action

        if latest_form and latest_form.get('input_defs'):
            inputs = await self._collect_form_inputs_from_query(query, latest_form, user_text)
            if inputs != (latest_form.get('inputs') or {}):
                return _build_input_progress_action(latest_form, inputs)

        return None

    async def _workflow_messages(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.Message, None]:
        """调用工作流"""

        # Check if this is a form action resume (button click or text match)
        form_action_raw = query.variables.get('_dify_form_action')
        session_key = _session_key_from_query(query)

        if form_action_raw:
            form_action = self._merge_pending_form_action(session_key, form_action_raw)
        else:
            form_action = await self._match_pending_form_action(query, session_key, str(query.message_chain))

        if form_action:
            if form_action.get('_partial'):
                yield _attach_partial_form_data(
                    provider_message.Message(role='assistant', content=form_action.get('notice', 'Received.')),
                    form_action,
                )
                return
            async for msg in self._submit_workflow_form_blocking(form_action, session_key):
                yield msg
            _clear_pending_form(session_key, form_action.get('form_token') or None)
            return

        if not query.session.using_conversation.uuid:
            query.session.using_conversation.uuid = str(uuid.uuid4())

        query.variables['conversation_id'] = query.session.using_conversation.uuid

        plain_text, upload_files = await self._preprocess_user_message(query)

        files = [
            {
                'type': f['type'],
                'transfer_method': 'local_file',
                'upload_file_id': f['id'],
            }
            for f in upload_files
        ]

        ignored_events = ['text_chunk', 'workflow_started']

        inputs = {  # these variables are legacy variables, we need to keep them for compatibility
            'langbot_user_message_text': plain_text,
            'langbot_session_id': query.variables['session_id'],
            'langbot_conversation_id': query.variables['conversation_id'],
            'langbot_msg_create_time': query.variables['msg_create_time'],
        }

        inputs.update(query.variables)
        human_input_yielded = False

        async for chunk in self.dify_client.workflow_run(
            inputs=inputs,
            user=_dify_user_from_query(query),
            files=files,
            timeout=120,
        ):
            self.ap.logger.debug('dify-workflow-chunk: ' + str(chunk))
            if chunk['event'] in ignored_events:
                continue

            if chunk['event'] == 'workflow_paused':
                reasons = chunk['data'].get('reasons', [])
                workflow_run_id = chunk['data'].get('workflow_run_id', '')
                for reason in reasons:
                    if reason.get('TYPE') == 'human_input_required':
                        user = _dify_user_from_query(query)
                        form_snapshot, raw_form_content, input_defs, _ = _extract_form_snapshot(
                            workflow_run_id,
                            reason,
                            user,
                        )
                        actions = form_snapshot.get('actions', [])
                        node_title = form_snapshot.get('node_title', '')

                        _set_pending_form(_session_key_from_query(query), form_snapshot)

                        query.variables['_dify_form_render'] = {
                            'form_content': raw_form_content,
                            'input_defs': input_defs,
                            'actions': actions,
                            'node_title': node_title,
                        }

                        display_text = _format_human_input_text(node_title, raw_form_content, actions, input_defs)

                        human_input_yielded = True
                        yield provider_message.Message(
                            role='assistant',
                            content=display_text,
                        )

            if chunk['event'] == 'node_started':
                if chunk['data']['node_type'] == 'start' or chunk['data']['node_type'] == 'end':
                    continue

                msg = provider_message.Message(
                    role='assistant',
                    content=None,
                    tool_calls=[
                        provider_message.ToolCall(
                            id=chunk['data']['node_id'],
                            type='function',
                            function=provider_message.FunctionCall(
                                name=chunk['data']['title'],
                                arguments=json.dumps({}),
                            ),
                        )
                    ],
                )

                yield msg

            elif chunk['event'] == 'workflow_finished':
                if human_input_yielded:
                    break
                if chunk['data']['error']:
                    raise errors.DifyAPIError(chunk['data']['error'])
                content, _ = self._process_thinking_content(chunk['data']['outputs']['summary'])

                msg = provider_message.Message(
                    role='assistant',
                    content=content,
                )

                yield msg

    async def _chat_messages_chunk(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.MessageChunk, None]:
        """调用聊天助手"""
        # Check if this is a form action resume (button click or text match)
        form_action_raw = query.variables.get('_dify_form_action')
        session_key = _session_key_from_query(query)

        if form_action_raw:
            form_action = self._merge_pending_form_action(session_key, form_action_raw)
        else:
            form_action = await self._match_pending_form_action(query, session_key, str(query.message_chain))

        if form_action:
            if form_action.get('_partial'):
                yield _attach_partial_form_data(
                    provider_message.MessageChunk(
                        role='assistant',
                        content=form_action.get('notice', 'Received.'),
                        is_final=True,
                    ),
                    form_action,
                )
                return
            async for msg in self._submit_workflow_form(form_action, session_key):
                yield msg
            _clear_pending_form(session_key, form_action.get('form_token') or None)
            return

        cov_id = query.session.using_conversation.uuid or None
        query.variables['conversation_id'] = cov_id

        plain_text, upload_files = await self._preprocess_user_message(query)

        files = [
            {
                'type': f['type'],
                'transfer_method': 'local_file',
                'upload_file_id': f['id'],
            }
            for f in upload_files
        ]

        mode = 'basic'
        basic_mode_pending_chunk = ''

        inputs = {}

        inputs.update(query.variables)
        message_idx = 0

        chunk = None  # 初始化chunk变量，防止在没有响应时引用错误

        is_final = False
        yielded_final = False
        human_input_yielded = False
        pending_form_data = None

        remove_think = self.pipeline_config['output'].get('misc', {}).get('remove-think')

        def visible_content(content: str) -> str:
            if not remove_think:
                return content
            if '<think>' in content and '</think>' not in content:
                return content.split('<think>', 1)[0].rstrip()
            return self._process_thinking_content(content)[0]

        async for chunk in self.dify_client.chat_messages(
            inputs=inputs,
            query=plain_text,
            user=_dify_user_from_query(query),
            conversation_id=cov_id,
            files=files,
            timeout=120,
        ):
            self.ap.logger.debug('dify-chat-chunk: ' + str(chunk))

            if chunk['event'] == 'workflow_started':
                mode = 'workflow'
            elif chunk['event'] in ('node_started', 'node_finished', 'workflow_finished', 'workflow_paused'):
                # Some Dify deployments may omit workflow_started in streamed chunks.
                mode = 'workflow'

            if chunk['event'] == 'message':
                message_idx += 1
                basic_mode_pending_chunk = _merge_stream_text(basic_mode_pending_chunk, chunk['answer'])

            if chunk['event'] == 'message_end':
                is_final = True
            elif chunk['event'] == 'workflow_finished':
                is_final = True
                if human_input_yielded:
                    break
                if chunk['data'].get('error'):
                    raise errors.DifyAPIError(chunk['data']['error'])

            if mode == 'workflow' and chunk['event'] == 'workflow_paused':
                reasons = chunk['data'].get('reasons', [])
                workflow_run_id = chunk['data'].get('workflow_run_id', '')
                for reason in reasons:
                    if reason.get('TYPE') != 'human_input_required':
                        continue
                    user = _dify_user_from_query(query)
                    form_snapshot, raw_form_content, input_defs, display_form_content = _extract_form_snapshot(
                        workflow_run_id,
                        reason,
                        user,
                    )
                    actions = form_snapshot.get('actions', [])
                    node_title = form_snapshot.get('node_title', '')

                    _set_pending_form(_session_key_from_query(query), form_snapshot)

                    query.variables['_dify_form_render'] = {
                        'form_content': raw_form_content,
                        'input_defs': input_defs,
                        'actions': actions,
                        'node_title': node_title,
                    }

                    # Use a zero-width space so ResponseWrapper lets the chunk
                    # propagate to SendResponseBackStage, but the adapter
                    # detects _form_data and renders buttons instead of the
                    # plain-text prompt (mirrors _workflow_messages_chunk).
                    if not basic_mode_pending_chunk:
                        basic_mode_pending_chunk = '​'

                    pending_form_data = _initial_interactive_form_data(form_snapshot) or {
                        'form_content': display_form_content,
                        'raw_form_content': raw_form_content,
                        'input_defs': input_defs,
                        'inputs': form_snapshot.get('inputs', {}),
                        'actions': actions,
                        'node_title': node_title,
                        'workflow_run_id': workflow_run_id,
                        'form_token': reason.get('form_token', ''),
                    }
                    human_input_yielded = True

            if mode == 'workflow' and chunk['event'] == 'node_finished':
                if chunk['data'].get('node_type') == 'answer':
                    answer = self._extract_dify_text_output(chunk['data'].get('outputs', {}).get('answer'))
                    if answer:
                        basic_mode_pending_chunk = answer

            if (
                not yielded_final
                and (is_final or message_idx % 8 == 0)
                and (basic_mode_pending_chunk != '' or is_final)
            ):
                final_content = visible_content(basic_mode_pending_chunk)
                if not final_content.strip() and is_final and pending_form_data:
                    final_content = _STREAM_FORM_PLACEHOLDER
                if not final_content and not is_final:
                    continue
                msg = provider_message.MessageChunk(
                    role='assistant',
                    content=final_content,
                    is_final=is_final,
                )
                if is_final and pending_form_data:
                    msg._form_data = pending_form_data
                    pending_form_data = None
                yield msg
                if is_final:
                    yielded_final = True

        # If the stream ended after workflow_paused without a
        # workflow_finished event, yield a final chunk so the adapter
        # can update the card and add buttons.
        if human_input_yielded and not yielded_final:
            final_content = visible_content(basic_mode_pending_chunk)
            msg = provider_message.MessageChunk(
                role='assistant',
                content=final_content or _STREAM_FORM_PLACEHOLDER,
                is_final=True,
            )
            msg._form_data = pending_form_data
            yield msg

        if chunk is None:
            raise errors.DifyAPIError('Dify API 没有返回任何响应，请检查网络连接和API配置')

        query.session.using_conversation.uuid = chunk['conversation_id']

    async def _agent_chat_messages_chunk(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.MessageChunk, None]:
        """调用聊天助手"""
        cov_id = query.session.using_conversation.uuid or None
        query.variables['conversation_id'] = cov_id

        plain_text, upload_files = await self._preprocess_user_message(query)

        files = [
            {
                'type': f['type'],
                'transfer_method': 'local_file',
                'upload_file_id': f['id'],
            }
            for f in upload_files
        ]

        ignored_events = []

        inputs = {}

        inputs.update(query.variables)

        pending_agent_message = ''

        chunk = None  # 初始化chunk变量，防止在没有响应时引用错误
        message_idx = 0
        is_final = False
        think_start = False
        think_end = False

        remove_think = self.pipeline_config['output'].get('misc', {}).get('remove-think')

        async for chunk in self.dify_client.chat_messages(
            inputs=inputs,
            query=plain_text,
            user=_dify_user_from_query(query),
            response_mode='streaming',
            conversation_id=cov_id,
            files=files,
            timeout=120,
        ):
            self.ap.logger.debug('dify-agent-chunk: ' + str(chunk))

            if chunk['event'] in ignored_events:
                continue

            if chunk['event'] == 'agent_message':
                message_idx += 1
                if remove_think:
                    if '<think>' in chunk['answer'] and not think_start:
                        think_start = True
                        continue
                    if '</think>' in chunk['answer'] and not think_end:
                        import re

                        content = re.sub(r'^\n</think>', '', chunk['answer'])
                        pending_agent_message = _merge_stream_text(pending_agent_message, content)
                        think_end = True
                    elif think_end or not think_start:
                        pending_agent_message = _merge_stream_text(pending_agent_message, chunk['answer'])
                    if think_start and not think_end:
                        continue

                else:
                    pending_agent_message = _merge_stream_text(pending_agent_message, chunk['answer'])
            elif chunk['event'] == 'message_end':
                is_final = True
            else:
                if chunk['event'] == 'agent_thought':
                    if chunk['tool'] != '' and chunk['observation'] != '':  # 工具调用结果，跳过
                        continue
                    message_idx += 1
                    if chunk['tool']:
                        msg = provider_message.MessageChunk(
                            role='assistant',
                            tool_calls=[
                                provider_message.ToolCall(
                                    id=chunk['id'],
                                    type='function',
                                    function=provider_message.FunctionCall(
                                        name=chunk['tool'],
                                        arguments=json.dumps({}),
                                    ),
                                )
                            ],
                        )
                        yield msg
                if chunk['event'] == 'message_file':
                    message_idx += 1
                    if chunk['type'] == 'image' and chunk['belongs_to'] == 'assistant':
                        # 检查URL是否已经是完整的连接
                        if chunk['url'].startswith('http://') or chunk['url'].startswith('https://'):
                            image_url = chunk['url']
                        else:
                            base_url = self.dify_client.base_url

                            if base_url.endswith('/v1'):
                                base_url = base_url[:-3]

                            image_url = base_url + chunk['url']

                        yield provider_message.MessageChunk(
                            role='assistant',
                            content=[provider_message.ContentElement.from_image_url(image_url)],
                            is_final=is_final,
                        )

                if chunk['event'] == 'error':
                    raise errors.DifyAPIError('dify 服务错误: ' + chunk['message'])
            if message_idx % 8 == 0 or is_final:
                yield provider_message.MessageChunk(
                    role='assistant',
                    content=pending_agent_message,
                    is_final=is_final,
                )

        if chunk is None:
            raise errors.DifyAPIError('Dify API 没有返回任何响应，请检查网络连接和API配置')

        query.session.using_conversation.uuid = chunk['conversation_id']

    async def _submit_workflow_form(
        self, form_action: dict, session_key: PendingFormKey
    ) -> typing.AsyncGenerator[provider_message.MessageChunk, None]:
        """Submit human input to resume a paused Dify workflow."""

        form_token = form_action['form_token']
        workflow_run_id = form_action['workflow_run_id']
        user = form_action['user']
        action_id = form_action.get('action_id', '')
        action_title = form_action.get('action_title', '') or action_id
        node_title = form_action.get('node_title', '')
        inputs = form_action.get('inputs', {})

        messsage_idx = 0
        is_final = False
        think_start = False
        think_end = False
        workflow_contents = ''
        repause_form_data: dict | None = None

        remove_think = self.pipeline_config['output'].get('misc', {}).get('remove-think')
        async for chunk in self.dify_client.workflow_submit(
            form_token=form_token,
            workflow_run_id=workflow_run_id,
            inputs=inputs,
            user=user,
            action=action_id,
            timeout=120,
        ):
            self.ap.logger.debug('dify-workflow-submit-chunk: ' + str(chunk))

            yield_this_iteration = False

            if chunk['event'] == 'workflow_finished':
                is_final = True
                yield_this_iteration = True
                if chunk['data'].get('error'):
                    raise errors.DifyAPIError(chunk['data']['error'])

            if chunk['event'] == 'workflow_paused':
                reasons = chunk['data'].get('reasons', [])
                new_run_id = chunk['data'].get('workflow_run_id', workflow_run_id)
                for reason in reasons:
                    if reason.get('TYPE') != 'human_input_required':
                        continue
                    form_snapshot, raw_form_content, input_defs, display_form_content = _extract_form_snapshot(
                        new_run_id,
                        reason,
                        user,
                    )
                    actions = form_snapshot.get('actions', [])
                    # Use a distinct name — `node_title` (the just-resolved step)
                    # must keep its value so the resume notice on the previous
                    # card still shows which step the user acted on.
                    paused_node_title = form_snapshot.get('node_title', '')

                    _set_pending_form(session_key, form_snapshot)

                    repause_form_data = _initial_interactive_form_data(form_snapshot) or {
                        'form_content': display_form_content,
                        'raw_form_content': raw_form_content,
                        'input_defs': input_defs,
                        'inputs': form_snapshot.get('inputs', {}),
                        'actions': actions,
                        'node_title': paused_node_title,
                        'workflow_run_id': new_run_id,
                        'form_token': reason.get('form_token', ''),
                    }
                    # Ensure the final chunk has non-empty content so
                    # ResponseWrapper (which skips empty-content chunks) lets it
                    # propagate to SendResponseBackStage. Use a zero-width space
                    # so neither Lark nor Telegram renders visible noise — the
                    # adapter substitutes its own card text from _form_data.
                    if not workflow_contents:
                        workflow_contents = '​'
                    is_final = True
                    yield_this_iteration = True
                    break

            if chunk['event'] == 'text_chunk':
                messsage_idx += 1
                if remove_think:
                    if '<think>' in chunk['data']['text'] and not think_start:
                        think_start = True
                        continue
                    if '</think>' in chunk['data']['text'] and not think_end:
                        import re

                        content = re.sub(r'^\n</think>', '', chunk['data']['text'])
                        workflow_contents += content
                        think_end = True
                    elif think_end:
                        workflow_contents = _merge_stream_text(workflow_contents, chunk['data']['text'])
                    if think_start:
                        continue
                else:
                    workflow_contents = _merge_stream_text(workflow_contents, chunk['data']['text'])
                if messsage_idx % 8 == 0:
                    yield_this_iteration = True

            # Chatflow apps return answers via 'message' events (answer field),
            # not 'text_chunk' events (data.text field).
            if chunk['event'] == 'message':
                answer = chunk.get('answer', '')
                if answer:
                    messsage_idx += 1
                    if remove_think:
                        if '<think>' in answer and not think_start:
                            think_start = True
                            continue
                        if '</think>' in answer and not think_end:
                            import re

                            content = re.sub(r'^\n</think>', '', answer)
                            workflow_contents += content
                            think_end = True
                        elif think_end:
                            workflow_contents = _merge_stream_text(workflow_contents, answer)
                        if think_start:
                            continue
                    else:
                        workflow_contents = _merge_stream_text(workflow_contents, answer)
                    if messsage_idx % 8 == 0:
                        yield_this_iteration = True

            if yield_this_iteration:
                msg = provider_message.MessageChunk(
                    role='assistant',
                    content=workflow_contents,
                    is_final=is_final,
                )
                msg._resume_from_form = True
                if action_title:
                    msg._resume_action_title = action_title
                if node_title:
                    msg._resume_node_title = node_title
                if is_final and repause_form_data:
                    msg._form_data = repause_form_data
                    msg._open_new_card = True
                yield msg
                if is_final:
                    return

        raise errors.DifyAPIError('Dify workflow resume stream ended before a terminal event')

    async def _workflow_messages_chunk(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.MessageChunk, None]:
        """调用工作流"""

        # Check if this is a form action resume (button click or text match)
        form_action_raw = query.variables.get('_dify_form_action')
        session_key = _session_key_from_query(query)

        if form_action_raw:
            form_action = self._merge_pending_form_action(session_key, form_action_raw)
        else:
            form_action = await self._match_pending_form_action(query, session_key, str(query.message_chain))

        if form_action:
            if form_action.get('_partial'):
                yield _attach_partial_form_data(
                    provider_message.MessageChunk(
                        role='assistant',
                        content=form_action.get('notice', 'Received.'),
                        is_final=True,
                    ),
                    form_action,
                )
                return
            # Resume paused workflow via submit endpoint
            async for msg in self._submit_workflow_form(form_action, session_key):
                yield msg
            _clear_pending_form(session_key, form_action.get('form_token') or None)
            return

        if not query.session.using_conversation.uuid:
            query.session.using_conversation.uuid = str(uuid.uuid4())

        query.variables['conversation_id'] = query.session.using_conversation.uuid

        plain_text, upload_files = await self._preprocess_user_message(query)

        files = [
            {
                'type': f['type'],
                'transfer_method': 'local_file',
                'upload_file_id': f['id'],
            }
            for f in upload_files
        ]

        ignored_events = ['workflow_started']

        inputs = {  # these variables are legacy variables, we need to keep them for compatibility
            'langbot_user_message_text': plain_text,
            'langbot_session_id': query.variables['session_id'],
            'langbot_conversation_id': query.variables['conversation_id'],
            'langbot_msg_create_time': query.variables['msg_create_time'],
        }

        inputs.update(query.variables)
        messsage_idx = 0
        is_final = False
        think_start = False
        think_end = False
        workflow_contents = ''
        workflow_run_id = ''
        human_input_yielded = False

        # Saved form data to attach to the final MessageChunk so the adapter
        # can detect it when is_final=True and render buttons.
        pending_form_data = None

        remove_think = self.pipeline_config['output'].get('misc', {}).get('remove-think')
        async for chunk in self.dify_client.workflow_run(
            inputs=inputs,
            user=_dify_user_from_query(query),
            files=files,
            timeout=120,
        ):
            self.ap.logger.debug('dify-workflow-chunk: ' + str(chunk))
            if chunk['event'] in ignored_events:
                if chunk['event'] == 'workflow_started':
                    workflow_run_id = chunk['data'].get('workflow_run_id', '')
                continue

            if chunk['event'] == 'workflow_paused':
                reasons = chunk['data'].get('reasons', [])
                workflow_run_id = chunk['data'].get('workflow_run_id', workflow_run_id)
                for reason in reasons:
                    if reason.get('TYPE') == 'human_input_required':
                        user = _dify_user_from_query(query)
                        form_snapshot, raw_form_content, input_defs, display_form_content = _extract_form_snapshot(
                            workflow_run_id,
                            reason,
                            user,
                        )
                        actions = form_snapshot.get('actions', [])
                        node_title = form_snapshot.get('node_title', '')

                        _set_pending_form(_session_key_from_query(query), form_snapshot)

                        # Pass form render metadata to downstream stages
                        query.variables['_dify_form_render'] = {
                            'form_content': raw_form_content,
                            'input_defs': input_defs,
                            'actions': actions,
                            'node_title': node_title,
                        }

                        # Save form data to attach to the final chunk later.
                        # We do NOT yield here — the form content will be sent
                        # as the final MessageChunk (with is_final=True and
                        # _form_data) so the adapter can update the card and
                        # add buttons in one pass.
                        pending_form_data = _initial_interactive_form_data(form_snapshot) or {
                            'form_content': display_form_content,
                            'raw_form_content': raw_form_content,
                            'input_defs': input_defs,
                            'inputs': form_snapshot.get('inputs', {}),
                            'actions': actions,
                            'node_title': node_title,
                            'workflow_run_id': workflow_run_id,
                            'form_token': reason.get('form_token', ''),
                        }
                        human_input_yielded = True

            if chunk['event'] == 'workflow_finished':
                is_final = True
                if chunk['data']['error']:
                    raise errors.DifyAPIError(chunk['data']['error'])

            if chunk['event'] == 'text_chunk':
                messsage_idx += 1
                if remove_think:
                    if '<think>' in chunk['data']['text'] and not think_start:
                        think_start = True
                        continue
                    if '</think>' in chunk['data']['text'] and not think_end:
                        import re

                        content = re.sub(r'^\n</think>', '', chunk['data']['text'])
                        workflow_contents += content
                        think_end = True
                    elif think_end:
                        workflow_contents = _merge_stream_text(workflow_contents, chunk['data']['text'])
                    if think_start:
                        continue

                else:
                    workflow_contents = _merge_stream_text(workflow_contents, chunk['data']['text'])

            if chunk['event'] == 'node_started':
                if chunk['data']['node_type'] == 'start' or chunk['data']['node_type'] == 'end':
                    continue
                messsage_idx += 1
                msg = provider_message.MessageChunk(
                    role='assistant',
                    content=None,
                    tool_calls=[
                        provider_message.ToolCall(
                            id=chunk['data']['node_id'],
                            type='function',
                            function=provider_message.FunctionCall(
                                name=chunk['data']['title'],
                                arguments=json.dumps({}),
                            ),
                        )
                    ],
                )

                yield msg

            if messsage_idx % 8 == 0 or is_final:
                final_content = (
                    workflow_contents
                    if workflow_contents.strip()
                    else (_STREAM_FORM_PLACEHOLDER if is_final and pending_form_data else '')
                )
                msg = provider_message.MessageChunk(
                    role='assistant',
                    content=final_content,
                    is_final=is_final,
                )
                # Attach form data to the final chunk for the adapter
                if is_final and pending_form_data:
                    msg._form_data = pending_form_data
                    pending_form_data = None
                yield msg

        # If the stream ended after workflow_paused without a
        # workflow_finished event, yield a final chunk so the adapter
        # can update the card and add buttons.
        if human_input_yielded and not is_final:
            msg = provider_message.MessageChunk(
                role='assistant',
                content=workflow_contents if workflow_contents.strip() else _STREAM_FORM_PLACEHOLDER,
                is_final=True,
            )
            msg._form_data = pending_form_data
            yield msg

    async def run(self, query: pipeline_query.Query) -> typing.AsyncGenerator[provider_message.Message, None]:
        """运行请求"""
        if await query.adapter.is_stream_output_supported():
            msg_idx = 0
            if self.pipeline_config['ai']['dify-service-api']['app-type'] in ('chat', 'chatflow'):
                async for msg in self._chat_messages_chunk(query):
                    msg_idx += 1
                    msg.msg_sequence = msg_idx
                    yield msg
            elif self.pipeline_config['ai']['dify-service-api']['app-type'] == 'agent':
                async for msg in self._agent_chat_messages_chunk(query):
                    msg_idx += 1
                    msg.msg_sequence = msg_idx
                    yield msg
            elif self.pipeline_config['ai']['dify-service-api']['app-type'] == 'workflow':
                async for msg in self._workflow_messages_chunk(query):
                    msg_idx += 1
                    msg.msg_sequence = msg_idx
                    yield msg
            else:
                raise errors.DifyAPIError(
                    f'不支持的 Dify 应用类型: {self.pipeline_config["ai"]["dify-service-api"]["app-type"]}'
                )
        else:
            if self.pipeline_config['ai']['dify-service-api']['app-type'] in ('chat', 'chatflow'):
                async for msg in self._chat_messages(query):
                    yield msg
            elif self.pipeline_config['ai']['dify-service-api']['app-type'] == 'agent':
                async for msg in self._agent_chat_messages(query):
                    yield msg
            elif self.pipeline_config['ai']['dify-service-api']['app-type'] == 'workflow':
                async for msg in self._workflow_messages(query):
                    yield msg
            else:
                raise errors.DifyAPIError(
                    f'不支持的 Dify 应用类型: {self.pipeline_config["ai"]["dify-service-api"]["app-type"]}'
                )
