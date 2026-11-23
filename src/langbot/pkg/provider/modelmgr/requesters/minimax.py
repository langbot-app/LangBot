from __future__ import annotations

import re
from typing import Any


RECOMMENDED_MODELS = ('MiniMax-M3.1-Flash', 'MiniMax-M3')
RAW_CONTENT_FIELD = 'minimax_raw_content'
_LEGACY_TEXT_MODEL = re.compile(r'^(minimax-(m[12](?:[.\-]|$)|01(?:[.\-]|$))|abab)')


def reasoning_levels(model_name: str) -> list[str] | None:
    name = model_name.lower()
    if name == RECOMMENDED_MODELS[0].lower():
        return ['provider_default', 'enabled', 'low', 'medium', 'high', 'xhigh', 'max']
    if name == RECOMMENDED_MODELS[1].lower():
        return ['provider_default', 'enabled', 'disabled']
    return None


def reasoning_parameters(level: str) -> dict[str, Any]:
    if level == 'provider_default':
        return {}
    thinking_type = {'enabled': 'adaptive', 'disabled': 'disabled'}.get(level)
    if thinking_type is not None:
        return {'extra_body': {'thinking': {'type': thinking_type}}}
    return {'reasoning_effort': level}


def capture_content(payload: dict[str, Any]) -> dict[str, Any]:
    fields = dict(payload.get('provider_specific_fields') or {})
    if isinstance(payload.get('content'), str):
        fields[RAW_CONTENT_FIELD] = payload['content']
    return fields


def take_replay_fields(fields: dict[str, Any]) -> dict[str, Any]:
    replay = {}
    raw_content = fields.pop(RAW_CONTENT_FIELD, None)
    if isinstance(raw_content, str):
        replay['content'] = raw_content
    if isinstance(fields.get('reasoning_content'), str):
        replay['reasoning_content'] = fields['reasoning_content']
    return replay


def arrange_catalog(models: list[dict[str, Any]], *, direct: bool) -> list[dict[str, Any]]:
    priorities = {name.lower(): position for position, name in enumerate(RECOMMENDED_MODELS)}

    def model_name(model: dict[str, Any]) -> str:
        name = model['id'].lower()
        if not direct:
            if not name.startswith('minimax/'):
                return ''
            name = name.removeprefix('minimax/')
        return name.partition(':')[0]

    catalog = [
        dict(model) for model in models if model['type'] != 'llm' or not _LEGACY_TEXT_MODEL.match(model_name(model))
    ]
    if direct:
        present = {model['id'].lower() for model in catalog}
        catalog.extend(
            {'id': name, 'name': name, 'type': 'llm'} for name in RECOMMENDED_MODELS if name.lower() not in present
        )
        for model in catalog:
            if model_name(model) in priorities:
                model.setdefault('context_length', 1_000_000)
                model['abilities'] = list(
                    dict.fromkeys([*model.get('abilities', []), 'func_call', 'vision', 'reasoning'])
                )
    return sorted(catalog, key=lambda model: priorities.get(model_name(model), len(priorities)))
