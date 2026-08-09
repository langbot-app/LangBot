from __future__ import annotations

import typing


ReasoningLevel = typing.Literal[
    'provider_default',
    'disabled',
    'enabled',
    'minimal',
    'low',
    'medium',
    'high',
    'xhigh',
    'max',
]

REASONING_LEVELS: tuple[str, ...] = (
    'provider_default',
    'disabled',
    'enabled',
    'minimal',
    'low',
    'medium',
    'high',
    'xhigh',
    'max',
)
DEFAULT_REASONING_CONFIG: dict[str, str] = {'level': 'provider_default'}

_CONFLICTING_TOP_LEVEL_ARGS = {
    'reasoning_effort',
    'thinking',
    'enable_thinking',
    'thinking_budget',
    'reasoning',
}
_CONFLICTING_EXTRA_BODY_ARGS = {
    'reasoning_effort',
    'thinking',
    'enable_thinking',
    'thinking_budget',
    'reasoning',
}


def normalize_reasoning_config(value: typing.Any) -> dict[str, str]:
    """Return the canonical model reasoning configuration."""
    if value is None:
        return dict(DEFAULT_REASONING_CONFIG)
    if not isinstance(value, dict):
        raise ValueError('reasoning_config must be an object')

    unknown_fields = set(value) - {'level'}
    if unknown_fields:
        raise ValueError(f'Unsupported reasoning_config fields: {", ".join(sorted(unknown_fields))}')

    level = value.get('level', 'provider_default')
    if level not in REASONING_LEVELS:
        raise ValueError(f'Unsupported reasoning level: {level}')
    return {'level': typing.cast(str, level)}


def validate_reasoning_config(
    value: typing.Any,
    abilities: typing.Iterable[str] | None,
    extra_args: typing.Any,
) -> dict[str, str]:
    """Validate a model-facing reasoning config and conflicting raw arguments."""
    config = normalize_reasoning_config(value)
    if config['level'] == 'provider_default':
        return config

    if 'reasoning' not in set(abilities or []):
        raise ValueError('The reasoning ability must be enabled before selecting a reasoning level')

    conflicts = find_reasoning_arg_conflicts(extra_args)
    if conflicts:
        raise ValueError('reasoning_config conflicts with advanced parameters: ' + ', '.join(conflicts))
    return config


def find_reasoning_arg_conflicts(extra_args: typing.Any) -> list[str]:
    if not isinstance(extra_args, dict):
        return []

    conflicts = [key for key in sorted(_CONFLICTING_TOP_LEVEL_ARGS) if key in extra_args]
    extra_body = extra_args.get('extra_body')
    if isinstance(extra_body, dict):
        conflicts.extend(f'extra_body.{key}' for key in sorted(_CONFLICTING_EXTRA_BODY_ARGS) if key in extra_body)
    return conflicts


def validate_reasoning_capabilities(
    config: typing.Any,
    capabilities: typing.Mapping[str, typing.Any],
    model_name: str,
) -> None:
    """Ensure an explicit reasoning level can be honored by the requester."""
    level = normalize_reasoning_config(config)['level']
    if level == 'provider_default':
        return

    available_levels = capabilities.get('levels')
    if not isinstance(available_levels, list):
        available_levels = []
    legacy_levels = capabilities.get('legacy_levels')
    if not isinstance(legacy_levels, list):
        legacy_levels = []
    if capabilities.get('supported') is not True or (level not in available_levels and level not in legacy_levels):
        available_text = ', '.join(str(item) for item in available_levels) or 'provider_default'
        raise ValueError(
            f'Reasoning level "{level}" is not supported by model {model_name}. Available levels: {available_text}'
        )


def default_reasoning_capabilities(
    supported: bool = False,
    source: str = 'unknown',
) -> dict[str, typing.Any]:
    return {
        'supported': supported,
        'levels': ['provider_default'],
        'source': source,
    }
