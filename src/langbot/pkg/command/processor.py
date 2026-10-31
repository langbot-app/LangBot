"""Command processor instances: per-bot configuration of plugin Command components."""

from __future__ import annotations

import copy
import typing

COMMAND_PROCESSOR_KIND = 'command_processor'
COMMAND_PROCESSOR_EVENT_PATTERNS = ['message.received']
COMPONENT_REF_PREFIX = 'plugin:'


def component_ref_for_plugin(plugin_id: str) -> str:
    return f'{COMPONENT_REF_PREFIX}{plugin_id}'


def plugin_id_from_component_ref(component_ref: typing.Any) -> str | None:
    """Return ``author/name`` for a command processor component reference."""
    if not isinstance(component_ref, str) or not component_ref.startswith(COMPONENT_REF_PREFIX):
        return None
    plugin_id = component_ref[len(COMPONENT_REF_PREFIX) :].strip()
    author, _, name = plugin_id.partition('/')
    if not author or not name or '/' in name:
        return None
    return plugin_id


def command_config_schema(manifest: typing.Any) -> list[dict[str, typing.Any]]:
    """Read the ``spec.config`` form declared by a Command component manifest."""
    spec = getattr(manifest, 'spec', None)
    if spec is None and isinstance(manifest, dict):
        spec = manifest.get('spec')
    if not isinstance(spec, dict):
        return []
    schema = spec.get('config')
    if not isinstance(schema, list):
        return []
    return [item for item in schema if isinstance(item, dict) and item.get('name')]


def command_name(manifest: typing.Any) -> str:
    metadata = getattr(manifest, 'metadata', None)
    return str(getattr(metadata, 'name', '') or '')


def merge_command_config(schema: list[dict[str, typing.Any]], values: typing.Any) -> dict[str, typing.Any]:
    """Fill schema defaults under instance values so newly declared fields stay usable."""
    merged = {item['name']: copy.deepcopy(item['default']) for item in schema if 'default' in item}
    if isinstance(values, dict):
        merged.update(copy.deepcopy(values))
    return merged


def instance_command_config(agent: typing.Mapping[str, typing.Any] | None, name: str) -> dict[str, typing.Any]:
    config = (agent or {}).get('config')
    if not isinstance(config, dict):
        return {}
    command_config = config.get('command_config')
    if not isinstance(command_config, dict):
        return {}
    values = command_config.get(name)
    return dict(values) if isinstance(values, dict) else {}
