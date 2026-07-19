"""Shared presentation helpers for platform human-input prompts."""

from __future__ import annotations

import re
import typing


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
    if not isinstance(options, list):
        return []
    normalized = []
    for item in options:
        if isinstance(item, dict):
            normalized.append(str(item.get('label') or item.get('value') or ''))
        else:
            normalized.append(str(item))
    return [item for item in normalized if item]


def _format_fields(input_defs: list[dict[str, typing.Any]]) -> str:
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


def _strip_field_placeholders(form_content: str, input_defs: list[dict[str, typing.Any]]) -> str:
    if not form_content:
        return ''
    field_names = {_field_name(field) for field in input_defs if _field_name(field)}
    kept_lines = []
    for line in form_content.splitlines():
        placeholder = re.fullmatch(r'\s*\{\{#\$output\.([^#{}]+)#\}\}\s*', line)
        if placeholder and placeholder.group(1) in field_names:
            continue
        kept_lines.append(line)
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(kept_lines).strip())


def format_human_input_text(
    node_title: str,
    form_content: str,
    actions: list[dict[str, typing.Any]],
    input_defs: list[dict[str, typing.Any]] | None = None,
) -> str:
    """Render a platform-neutral plain-text prompt for a paused workflow."""
    input_defs = input_defs or []
    form_content = _strip_field_placeholders(form_content, input_defs)
    lines = [f'[Human Input Required] {node_title or ""}'.rstrip()]
    if form_content:
        lines.extend(['', form_content])
    field_help = _format_fields(input_defs)
    if field_help:
        lines.extend(['', field_help])
    if actions:
        lines.append('')
        if input_defs:
            lines.extend([
                'Reply with action plus field values to continue:',
                '  action: <number or title>',
            ])
        else:
            lines.append('Reply with the number or title to continue:')
        for idx, action in enumerate(actions, start=1):
            title = action.get('title') or action.get('id') or ''
            lines.append(f'  {idx}. {title}')
    return '\n'.join(lines)
