"""Helpers for interpreting AgentRunner DynamicForm configuration."""
from __future__ import annotations

import typing

from .descriptor import AgentRunnerDescriptor


LLM_MODEL_SELECTOR_TYPES = {'model-fallback-selector', 'llm-model-selector'}
KB_SELECTOR_TYPES = {'knowledge-base-multi-selector'}
PROMPT_EDITOR_TYPES = {'prompt-editor'}
NONE_SENTINELS = {'', '__none__', '__none'}


def iter_schema_items(
    descriptor: AgentRunnerDescriptor | None,
    field_types: set[str],
) -> typing.Iterator[dict[str, typing.Any]]:
    """Yield descriptor config schema items whose type is in field_types."""
    if descriptor is None:
        return
    for item in descriptor.config_schema or []:
        if not isinstance(item, dict):
            continue
        if item.get('type') in field_types:
            yield item


def uses_host_models(descriptor: AgentRunnerDescriptor | None) -> bool:
    """Return whether LangBot should resolve model resources for this runner."""
    return any(True for _ in iter_schema_items(descriptor, LLM_MODEL_SELECTOR_TYPES))


def uses_host_tools(descriptor: AgentRunnerDescriptor | None) -> bool:
    """Return whether LangBot should expose tool resources to this runner."""
    return descriptor is not None and descriptor.supports_tool_calling()


def uses_host_knowledge_bases(descriptor: AgentRunnerDescriptor | None) -> bool:
    """Return whether LangBot should expose knowledge-base resources to this runner."""
    return descriptor is not None and descriptor.supports_knowledge_retrieval()


def supports_skill_authoring(descriptor: AgentRunnerDescriptor | None) -> bool:
    """Return whether the runner wants Host skill-authoring tools."""
    if descriptor is None:
        return False
    return descriptor.capabilities.skill_authoring


def extract_prompt_config(
    descriptor: AgentRunnerDescriptor | None,
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
    descriptor: AgentRunnerDescriptor | None,
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
        if item.get('type') == 'model-fallback-selector':
            if isinstance(value, str):
                primary_uuid = value
            elif isinstance(value, dict):
                primary_uuid = value.get('primary') or ''
                fallbacks = value.get('fallbacks', [])
                if isinstance(fallbacks, list):
                    fallback_uuids = [fallback for fallback in fallbacks if isinstance(fallback, str)]
            break

        if item.get('type') == 'llm-model-selector' and isinstance(value, str):
            primary_uuid = value
            break

    return primary_uuid, fallback_uuids


def extract_knowledge_base_uuids(
    descriptor: AgentRunnerDescriptor | None,
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
            kb_uuids.extend(
                kb_uuid for kb_uuid in value if isinstance(kb_uuid, str) and kb_uuid not in NONE_SENTINELS
            )

    return list(dict.fromkeys(kb_uuids))


def iter_config_model_refs(
    descriptor: AgentRunnerDescriptor,
    runner_config: dict[str, typing.Any],
) -> typing.Iterator[tuple[str, str]]:
    """Yield model references declared by schema-defined model selector fields."""
    for item in descriptor.config_schema or []:
        if not isinstance(item, dict):
            continue

        field_name = item.get('name')
        field_type = item.get('type')
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
    descriptor: AgentRunnerDescriptor,
    runner_config: dict[str, typing.Any],
    model_uuid: str,
) -> bool:
    """Set the first empty schema-defined LLM selector to model_uuid."""
    for item in iter_schema_items(descriptor, LLM_MODEL_SELECTOR_TYPES):
        field_name = item.get('name')
        field_type = item.get('type')
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
