"""Helpers for interpreting Runner DynamicForm configuration."""

from __future__ import annotations

import typing

from .descriptor import RunnerDescriptor


FORM_ITEM_TYPE_ALIASES = {
    'select-llm-model': 'llm-model-selector',
    'select-knowledge-bases': 'knowledge-base-multi-selector',
}
LLM_MODEL_SELECTOR_TYPES = {'model-fallback-selector', 'llm-model-selector'}
KB_SELECTOR_TYPES = {'knowledge-base-multi-selector'}
PROMPT_EDITOR_TYPES = {'prompt-editor'}
NONE_SENTINELS = {'', '__none__', '__none'}

# Selector field types that pick a Host resource. The Runner config form is
# plugin-declared and open-ended (DynamicFormItemSchema allows extra types), so
# this is a registry, not a fixed list: a new selector type is one line here and
# is then reported by telemetry without touching the extraction call sites.
RESOURCE_SELECTOR_TYPES: dict[str, str] = {
    'knowledge-base-multi-selector': 'knowledge_bases',
    'tool-multi-selector': 'tools',
    'mcp-server-multi-selector': 'mcp_servers',
    'skill-multi-selector': 'skills',
}


def declared_resource_selectors(descriptor: RunnerDescriptor | None) -> dict[str, list[str]]:
    """Map each selected resource kind to the schema field names that select it.

    Only the descriptor is read, so this reports what a Runner *can* select even
    when the current configuration leaves the field empty.
    """
    declared: dict[str, list[str]] = {}
    if descriptor is None:
        return declared
    for item in descriptor.config_schema or []:
        if not isinstance(item, dict):
            continue
        kind = RESOURCE_SELECTOR_TYPES.get(normalize_schema_item_type(item.get('type')))
        field_name = item.get('name')
        if not kind or not isinstance(field_name, str) or not field_name:
            continue
        declared.setdefault(kind, [])
        if field_name not in declared[kind]:
            declared[kind].append(field_name)
    return declared


def extract_selected_resources(
    descriptor: RunnerDescriptor | None,
    runner_config: dict[str, typing.Any] | None,
) -> dict[str, list[str]]:
    """Extract the resource ids selected through schema-declared selector fields.

    Field names are never hard-coded: they come from the Runner's own config
    schema, so a form that renames or adds a selector keeps working.
    """
    selected: dict[str, list[str]] = {}
    if not isinstance(runner_config, dict):
        return selected
    for kind, field_names in declared_resource_selectors(descriptor).items():
        values: list[str] = []
        for field_name in field_names:
            value = runner_config.get(field_name)
            if isinstance(value, str):
                if value not in NONE_SENTINELS:
                    values.append(value)
            elif isinstance(value, (list, tuple)):
                values.extend(item for item in value if isinstance(item, str) and item not in NONE_SENTINELS)
        if values:
            selected[kind] = list(dict.fromkeys(values))
    return selected


def normalize_schema_item_type(item_type: typing.Any) -> typing.Any:
    """Normalize legacy/frontend DynamicForm aliases to protocol field types."""
    if not isinstance(item_type, str):
        return item_type
    return FORM_ITEM_TYPE_ALIASES.get(item_type, item_type)


def iter_schema_items(
    descriptor: RunnerDescriptor | None,
    field_types: set[str],
) -> typing.Iterator[dict[str, typing.Any]]:
    """Yield descriptor config schema items whose type is in field_types."""
    if descriptor is None:
        return
    for item in descriptor.config_schema or []:
        if not isinstance(item, dict):
            continue
        if normalize_schema_item_type(item.get('type')) in field_types:
            yield item


def uses_host_models(descriptor: RunnerDescriptor | None) -> bool:
    """Return whether LangBot should resolve model resources for this runner."""
    return any(True for _ in iter_schema_items(descriptor, LLM_MODEL_SELECTOR_TYPES))


def uses_host_tools(descriptor: RunnerDescriptor | None) -> bool:
    """Return whether LangBot should expose tool resources to this runner."""
    return descriptor is not None and descriptor.supports_tool_calling()


def uses_host_knowledge_bases(descriptor: RunnerDescriptor | None) -> bool:
    """Return whether LangBot should expose knowledge-base resources to this runner."""
    return descriptor is not None and descriptor.supports_knowledge_retrieval()


def supports_skill_authoring(descriptor: RunnerDescriptor | None) -> bool:
    """Return whether the runner wants Host skill-authoring tools."""
    if descriptor is None:
        return False
    return descriptor.capabilities.skill_authoring


def extract_prompt_config(
    descriptor: RunnerDescriptor | None,
    runner_config: dict[str, typing.Any],
    default_prompt: list[dict[str, typing.Any]],
) -> list[dict[str, typing.Any]]:
    """Extract the prompt-editor value selected by the runner schema."""
    for item in iter_schema_items(descriptor, PROMPT_EDITOR_TYPES):
        field_name = item.get('name')
        if field_name and field_name in runner_config:
            configured_prompt = runner_config[field_name]
            if isinstance(configured_prompt, list):
                return configured_prompt
        default_value = item.get('default')
        if isinstance(default_value, list):
            return default_value
    return default_prompt


def extract_model_selection(
    descriptor: RunnerDescriptor | None,
    runner_config: dict[str, typing.Any],
) -> tuple[str, list[str]]:
    """Extract primary/fallback LLM selections from schema-defined fields."""
    primary_uuid = ''
    fallback_uuids: list[str] = []

    for item in iter_schema_items(descriptor, LLM_MODEL_SELECTOR_TYPES):
        field_name = item.get('name')
        if not field_name:
            continue

        value = runner_config.get(field_name, item.get('default'))
        item_type = normalize_schema_item_type(item.get('type'))
        if item_type == 'model-fallback-selector':
            if isinstance(value, str):
                primary_uuid = value
            elif isinstance(value, dict):
                primary_uuid = value.get('primary') or ''
                fallbacks = value.get('fallbacks', [])
                if isinstance(fallbacks, list):
                    fallback_uuids = [fallback for fallback in fallbacks if isinstance(fallback, str)]
            break

        if item_type == 'llm-model-selector' and isinstance(value, str):
            primary_uuid = value
            break

    return primary_uuid, fallback_uuids


def extract_knowledge_base_uuids(
    descriptor: RunnerDescriptor | None,
    runner_config: dict[str, typing.Any],
) -> list[str]:
    """Extract configured knowledge-base UUIDs from schema-defined fields."""
    if not uses_host_knowledge_bases(descriptor):
        return []

    kb_uuids: list[str] = []
    for item in iter_schema_items(descriptor, KB_SELECTOR_TYPES):
        field_name = item.get('name')
        if not field_name:
            continue
        value = runner_config.get(field_name, item.get('default', []))
        if isinstance(value, list):
            kb_uuids.extend(kb_uuid for kb_uuid in value if isinstance(kb_uuid, str) and kb_uuid not in NONE_SENTINELS)

    return list(dict.fromkeys(kb_uuids))


def iter_config_model_refs(
    descriptor: RunnerDescriptor,
    runner_config: dict[str, typing.Any],
) -> typing.Iterator[tuple[str, str]]:
    """Yield model references declared by schema-defined model selector fields."""
    for item in descriptor.config_schema or []:
        if not isinstance(item, dict):
            continue

        field_name = item.get('name')
        field_type = normalize_schema_item_type(item.get('type'))
        if not field_name or field_name not in runner_config:
            continue

        value = runner_config.get(field_name)
        if field_type == 'model-fallback-selector':
            if isinstance(value, str) and value not in NONE_SENTINELS:
                yield 'llm', value
            elif isinstance(value, dict):
                primary = value.get('primary')
                if isinstance(primary, str) and primary not in NONE_SENTINELS:
                    yield 'llm', primary
                fallbacks = value.get('fallbacks', [])
                if isinstance(fallbacks, list):
                    for fallback_uuid in fallbacks:
                        if isinstance(fallback_uuid, str) and fallback_uuid not in NONE_SENTINELS:
                            yield 'llm', fallback_uuid
        elif field_type == 'llm-model-selector':
            if isinstance(value, str) and value not in NONE_SENTINELS:
                yield 'llm', value
        elif field_type == 'rerank-model-selector':
            if isinstance(value, str) and value not in NONE_SENTINELS:
                yield 'rerank', value


def set_empty_llm_model_selection(
    descriptor: RunnerDescriptor,
    runner_config: dict[str, typing.Any],
    model_uuid: str,
) -> bool:
    """Set the first empty schema-defined LLM selector to model_uuid."""
    for item in iter_schema_items(descriptor, LLM_MODEL_SELECTOR_TYPES):
        field_name = item.get('name')
        field_type = normalize_schema_item_type(item.get('type'))
        if not field_name:
            continue

        value = runner_config.get(field_name, item.get('default'))
        if field_type == 'model-fallback-selector':
            if isinstance(value, dict):
                primary = value.get('primary') or ''
                if primary not in NONE_SENTINELS:
                    return False
                fallbacks = value.get('fallbacks', [])
                runner_config[field_name] = {
                    'primary': model_uuid,
                    'fallbacks': fallbacks if isinstance(fallbacks, list) else [],
                }
                return True
            if isinstance(value, str) and value not in NONE_SENTINELS:
                return False
            runner_config[field_name] = {'primary': model_uuid, 'fallbacks': []}
            return True

        if field_type == 'llm-model-selector':
            if isinstance(value, str) and value not in NONE_SENTINELS:
                return False
            runner_config[field_name] = model_uuid
            return True

    return False
