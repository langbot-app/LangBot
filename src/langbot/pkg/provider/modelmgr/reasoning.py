from __future__ import annotations

import typing
import copy

if typing.TYPE_CHECKING:
    from ...api.http.service.tenant import TenantContext
    from ...core.app import Application
    from .requester import RuntimeLLMModel


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


def normalize_reasoning_config(value: typing.Any) -> dict[str, typing.Any]:
    """Return the canonical model reasoning configuration."""
    if value is None:
        return dict(DEFAULT_REASONING_CONFIG)
    if not isinstance(value, dict):
        raise ValueError('reasoning_config must be an object')

    unknown_fields = set(value) - {'level', 'budget_tokens'}
    if unknown_fields:
        raise ValueError(f'Unsupported reasoning_config fields: {", ".join(sorted(unknown_fields))}')

    budget = value.get('budget_tokens')
    level = value.get('level', 'enabled' if budget is not None else 'provider_default')
    if level not in REASONING_LEVELS:
        raise ValueError(f'Unsupported reasoning level: {level}')
    if budget is not None:
        if type(budget) is not int or budget <= 0:
            raise ValueError('budget_tokens must be a positive integer')
        if level != 'enabled':
            raise ValueError('budget_tokens requires level enabled; do not combine a token budget with an effort level')
        return {'level': level, 'budget_tokens': budget}
    return {'level': typing.cast(str, level)}


def validate_reasoning_config(
    value: typing.Any,
    abilities: typing.Iterable[str] | None,
    extra_args: typing.Any,
) -> dict[str, typing.Any]:
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
    config = normalize_reasoning_config(config)
    level = config['level']
    if 'budget_tokens' in config:
        limits = capabilities.get('budget_tokens')
        if not isinstance(limits, dict) or not limits['min'] <= config['budget_tokens'] <= limits['max']:
            raise ValueError(f'Unsupported reasoning token budget for model {model_name}: {config["budget_tokens"]}')
        return
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


def model_with_reasoning_level(
    model: RuntimeLLMModel,
    level: ReasoningLevel | None,
) -> RuntimeLLMModel:
    """Clone only the runtime wrapper, after the caller has authorized the model.

    Do not mutate shared model entities or providers. Requesters retain ownership
    of ability/capability validation and provider-specific argument translation.
    """
    if level is None:
        return model
    abilities = set(model.model_entity.abilities or [])
    # Managed Space models are read-only. Their detected capability is also what
    # the model API and UI expose, even when the catalog omits the ability flag.
    # Custom providers still require the user's explicit ability setting.
    if (
        'reasoning' not in abilities
        and model.provider.provider_entity.requester == 'space-chat-completions'
        and model.provider.requester.get_reasoning_capabilities(model).get('supported') is True
    ):
        abilities.add('reasoning')
    config = validate_reasoning_config({'level': level}, abilities, model.model_entity.extra_args)
    scoped_model = copy.copy(model)
    scoped_model.reasoning_config_override = copy.deepcopy(config)
    return scoped_model


async def validate_runner_reasoning_levels(
    ap: Application,
    context: TenantContext,
    runner_config: typing.Mapping[str, typing.Any],
) -> None:
    """Reject reasoning levels in a Runner's model selection that the models cannot honor.

    Such a level is a static config error that would otherwise save cleanly and
    only fail at run time behind a generic Runner error. This applies the same
    checks as the model API and the run-time path, so they cannot disagree.
    """
    selection = runner_config.get('model')
    if not isinstance(selection, dict) or 'reasoning' not in selection:
        return
    levels = selection['reasoning']
    if not isinstance(levels, dict):
        # Runners fail the run on any other value, including an explicit null.
        raise ValueError('Model reasoning settings must be an object')

    fallbacks = selection.get('fallbacks')
    selected_models = [selection.get('primary'), *(fallbacks if isinstance(fallbacks, list) else [])]
    for model_uuid, level in levels.items():
        # Runners only read the levels of selected models, and None means no override.
        if model_uuid not in selected_models or level in (None, 'provider_default'):
            continue
        try:
            model = await ap.model_mgr.get_model_by_uuid(context, model_uuid)
        except ValueError:
            # A deleted or unloadable model is a separate problem; it must not block saving.
            continue
        scoped_model = model_with_reasoning_level(model, level)
        capabilities = model.provider.requester.get_reasoning_capabilities(scoped_model)
        validate_reasoning_capabilities({'level': level}, capabilities, model.model_entity.name)


def resolve_reasoning_config(model, extra_args=None):
    """Runner policy wins; a call object replaces, rather than merges, a model policy."""
    value = getattr(model.model_entity, 'reasoning_config', None)
    if value is not None and not isinstance(value, (dict, str, int, float, bool, list, tuple)):
        value = None
    for args in (model.model_entity.extra_args, extra_args):
        if isinstance(args, dict) and 'reasoning_config' in args:
            value = args['reasoning_config']
    override = getattr(model, 'reasoning_config_override', None)
    if override is not None:
        value = override
    return normalize_reasoning_config(value)
