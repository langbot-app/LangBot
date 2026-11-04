"""Versioned, data-only scenario documents and portable configuration projection."""

from __future__ import annotations

import copy
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .secrets import is_sensitive_key, redact_url_secrets

MAX_PACKAGE_BYTES = 2 * 1024 * 1024
SAFE_TYPES = {'boolean', 'integer', 'float', 'number', 'select', 'multi-select', 'prompt-editor'}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ScenarioSelection(StrictModel):
    pipeline_uuids: list[str] = Field(default_factory=list, max_length=100)
    agent_uuids: list[str] = Field(default_factory=list, max_length=100)
    event_processor_uuids: list[str] = Field(default_factory=list, max_length=100)
    plugin_ids: list[str] = Field(default_factory=list, max_length=100)
    mcp_server_uuids: list[str] = Field(default_factory=list, max_length=100)
    knowledge_base_uuids: list[str] = Field(default_factory=list, max_length=100)


class ScenarioInput(StrictModel):
    resource: str = Field(min_length=1, max_length=100)
    path: list[str | int] = Field(min_length=1, max_length=20)
    kind: Literal['credential', 'configuration', 'model', 'knowledge', 'extensions', 'environment']
    label: str | dict[str, str]
    required: bool = True
    model_type: Literal['llm', 'embedding', 'rerank'] = 'llm'


class ScenarioResource(StrictModel):
    id: str = Field(pattern=r'^[a-z][a-z0-9_-]{0,63}$')
    kind: Literal['bot', 'pipeline', 'agent', 'event_processor', 'knowledge_base', 'mcp_server']
    data: dict[str, Any]


class ScenarioDependency(StrictModel):
    kind: Literal['runner', 'knowledge_plugin', 'plugin']
    id: str = Field(min_length=1, max_length=255)
    plugin_id: str = Field(max_length=255)
    version: str | None = Field(default=None, max_length=100)
    config: dict[str, Any] | None = None


class ScenarioMetadata(StrictModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default='', max_length=4000)
    version: str = Field(default='1.0.0', max_length=100)
    author: str = Field(default='', max_length=255)
    instructions: str = Field(default='', max_length=10000)


class ScenarioPackage(StrictModel):
    format: Literal['langbot-scenario'] = 'langbot-scenario'
    format_version: Literal[1] = 1
    metadata: ScenarioMetadata
    resources: list[ScenarioResource] = Field(min_length=1, max_length=100)
    dependencies: list[ScenarioDependency] = Field(default_factory=list, max_length=200)
    inputs: list[ScenarioInput] = Field(default_factory=list, max_length=1000)

    @model_validator(mode='after')
    def validate_graph(self):
        resources = {item.id: item for item in self.resources}
        if len(resources) != len(self.resources):
            raise ValueError('Duplicate scenario resource ID')
        bots = [item for item in self.resources if item.kind == 'bot']
        if len(bots) != 1:
            raise ValueError('A scenario must contain exactly one bot')
        for item in self.inputs:
            if item.resource not in resources:
                raise ValueError('Unknown input resource')
            if item.path[0] not in {
                'config',
                'adapter_config',
                'extensions_preferences',
                'event_bindings',
                'creation_settings',
                'retrieval_settings',
                'initialized',
                'extra_args',
                'enable',
            }:
                raise ValueError('Invalid input configuration path')
            read_path(resources[item.resource].data, item.path)
        for item in self.inputs:
            if item.kind != 'knowledge':
                continue
            value = read_path(resources[item.resource].data, item.path)
            for reference in value if isinstance(value, list) else ([value] if value else []):
                target = resources.get(reference)
                if target is None or target.kind != 'knowledge_base':
                    raise ValueError('Invalid scenario knowledge reference')
        for binding in bots[0].data.get('event_bindings', []):
            if not isinstance(binding, dict):
                raise ValueError('Scenario route must be an object')
            kind = binding.get('target_type')
            if kind == 'discard':
                continue
            target = resources.get(binding.get('target_uuid'))
            if target is None or target.kind != kind:
                raise ValueError('Invalid scenario route reference')
        for subscription in bots[0].data.get('plugin_processors', []):
            if not isinstance(subscription, dict):
                raise ValueError('Scenario subscription must be an object')
            target = resources.get(subscription.get('processor_uuid'))
            if target is None or target.kind != 'event_processor':
                raise ValueError('Invalid scenario subscription reference')
        return self


def parse_package(data: Any) -> ScenarioPackage:
    if len(json.dumps(data, ensure_ascii=False, allow_nan=False).encode()) > MAX_PACKAGE_BYTES:
        raise ValueError('Scenario package exceeds 2 MiB')
    return ScenarioPackage.model_validate(data)


def read_path(data: Any, path: list[str | int]) -> Any:
    for key in path:
        if isinstance(data, dict) and isinstance(key, str) and key in data:
            data = data[key]
        elif isinstance(data, list) and type(key) is int and 0 <= key < len(data):
            data = data[key]
        else:
            raise ValueError('Invalid scenario input path')
    return data


def empty_value(value: Any) -> Any:
    if isinstance(value, list):
        return []
    if isinstance(value, dict):
        return {}
    return ''


def complete_pipeline_config(config: dict) -> dict:
    """Fill absent Host stage settings without replacing scene configuration."""
    from ....utils import paths

    with open(paths.get_resource_path('templates/default-pipeline-config.json'), encoding='utf-8') as source:
        defaults = json.load(source)

    def complete(template, supplied):
        if not isinstance(supplied, dict):
            raise ValueError('Invalid scenario pipeline stage configuration')
        result = copy.deepcopy(supplied)
        for key, value in template.items():
            if key not in result:
                result[key] = copy.deepcopy(value)
            elif isinstance(value, dict):
                result[key] = complete(value, result[key])
        return result

    return complete(defaults, config)


def field_is_visible(field: dict, values: dict) -> bool:
    """Match the dynamic form's simple conditional visibility rules."""
    condition = field.get('show_if')
    if not condition:
        return True
    try:
        actual = read_path(values, condition['field'].split('.'))
    except ValueError:
        actual = None
    expected = condition.get('value')
    operator = condition.get('operator')
    if operator == 'eq':
        return actual == expected
    if operator == 'neq':
        return actual != expected
    if operator == 'in' and isinstance(expected, list):
        return actual in expected
    return True


def project_config(
    config: dict, schema: list[dict], resource: str, prefix: list[str | int], *, platform: bool = False
) -> tuple[dict, list[ScenarioInput]]:
    """Preserve explicitly portable values; unknown fields become setup inputs.

    Platform string values are installation-specific by default. Runner text is
    portable only for prompt editors or an explicit scenario_portable declaration.
    Schema defaults are never used as replacements for removed credentials.
    """
    fields = {item['name']: item for item in schema if item.get('name')}
    result, inputs = {}, []
    for name in dict.fromkeys([*config, *fields]):
        field = fields.get(name, {})
        if name not in config and not field.get('required'):
            continue
        value = config.get(name, '')
        field_type = field.get('type', '')
        field_type = {
            'select-llm-model': 'llm-model-selector',
            'select-knowledge-bases': 'knowledge-base-multi-selector',
        }.get(field_type, field_type)
        kind = 'configuration'
        if is_sensitive_key(name) or field_type in {'password', 'secret'} or field.get('secret'):
            kind = 'credential'
        elif 'model' in field_type and 'selector' in field_type:
            kind = 'model'
        elif 'knowledge' in field_type:
            kind = 'knowledge'
        elif any(word in field_type for word in ('mcp', 'plugin', 'tool', 'skill')):
            kind = 'extensions'
        elif field_type == 'webhook-url' or name.startswith('__system.'):
            continue
        elif not platform and (
            field_type in SAFE_TYPES | {'string', 'text', 'textarea', 'array', 'object'}
            or field.get('scenario_portable') is True
        ):
            result[name] = scrub_nested(value)
            continue
        elif platform and field_type in {
            'boolean',
            'integer',
            'float',
            'number',
            'select',
            'string',
            'text',
            'textarea',
        }:
            result[name] = scrub_nested(value)
            continue
        elif platform:
            kind = 'environment'
        result[name] = empty_value(value)
        if kind == 'model' and field_type == 'model-fallback-selector':
            result[name] = {'primary': '', 'fallbacks': [], 'reasoning': {}}
        inputs.append(
            ScenarioInput(
                resource=resource,
                path=[*prefix, name],
                kind=kind,
                model_type='embedding' if 'embedding' in field_type else 'rerank' if 'rerank' in field_type else 'llm',
                label=field.get('label') or name,
                required=field_is_visible(field, config)
                and bool(field.get('required') or value not in ('', None, [], {})),
            )
        )
    return result, inputs


def scrub_nested(value: Any) -> Any:
    """Remove conventional structured secrets even inside portable composite fields."""
    if isinstance(value, dict):
        return {key: empty_value(item) if is_sensitive_key(key) else scrub_nested(item) for key, item in value.items()}
    if isinstance(value, list):
        return [scrub_nested(item) for item in value]
    if isinstance(value, str) and '://' in value:
        cleaned = redact_url_secrets(value)
        return '' if cleaned != value else value
    return copy.deepcopy(value)
