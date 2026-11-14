"""Shape of a bot's message policy and the one legacy conversion.

A message policy says which incoming messages a bot answers (``trigger``),
what is checked on the way in and out (``safety``) and how replies are sent
(``output``). It keeps the key names those settings had while they lived in a
Messaging (formerly "pipeline") config, so existing plugins that read them
from ``query.pipeline_config`` keep working.

Everything here is pure: no IO, no application state. The database migration,
the Messaging HTTP/MCP writes and legacy imports all share
``split_legacy_config``.
"""

from __future__ import annotations

import copy
import functools
import json
import logging
import typing
from pathlib import Path

logger = logging.getLogger(__name__)

SECTIONS = ('trigger', 'safety', 'output')

_BOOL = 'boolean'
_INT = 'integer'
_NUMBER = 'number'
_STR = 'string'
_STR_LIST = 'array[string]'


def _choice(*options: str) -> tuple[str, ...]:
    return options


# section -> block -> key -> type. A tuple is a closed set of string options.
POLICY_SCHEMA: dict[str, dict[str, dict[str, typing.Any]]] = {
    'trigger': {
        'group-respond-rules': {
            'enabled': _BOOL,
            'at': _BOOL,
            'prefix': _STR_LIST,
            'regexp': _STR_LIST,
            'random': _NUMBER,
        },
        'access-control': {
            'mode': _choice('blacklist', 'whitelist'),
            'blacklist': _STR_LIST,
            'whitelist': _STR_LIST,
        },
        'ignore-rules': {
            'prefix': _STR_LIST,
            'regexp': _STR_LIST,
        },
        'message-aggregation': {
            'enabled': _BOOL,
            'delay': _NUMBER,
        },
        'misc': {
            'combine-quote-message': _BOOL,
        },
    },
    'safety': {
        'content-filter': {
            'scope': _choice('all', 'income-msg', 'output-msg'),
            'check-sensitive-words': _BOOL,
        },
        'rate-limit': {
            'enabled': _BOOL,
            'window-length': _INT,
            'limitation': _INT,
            'strategy': _choice('drop', 'wait'),
        },
    },
    'output': {
        'long-text-processing': {
            'threshold': _INT,
            'strategy': _choice('forward', 'image', 'none'),
            'font-path': _STR,
        },
        'force-delay': {
            'min': _NUMBER,
            'max': _NUMBER,
        },
        'misc': {
            'exception-handling': _choice('show-error', 'show-hint', 'hide'),
            'failure-hint': _STR,
            'rate-limit-hint': _STR,
            'content-filter-hint': _STR,
            'content-filter-error-hint': _STR,
            'at-sender': _BOOL,
            'quote-origin': _BOOL,
        },
    },
}

# Blocks that only became switchable with the policy. A legacy config had no
# way to turn them off, so a converted one states that they are on.
_SWITCHABLE_BLOCKS = (('trigger', 'group-respond-rules'), ('safety', 'rate-limit'))

# "Let everything through, change nothing": the policy of bots that existed
# before policies did (their routes carry the real settings as overrides), of
# the WebUI debug chat, and the base every stored policy is completed from.
_NEUTRAL_POLICY: dict[str, typing.Any] = {
    'trigger': {
        'group-respond-rules': {'enabled': False, 'at': False, 'prefix': [], 'regexp': [], 'random': 0.0},
        'access-control': {'mode': 'blacklist', 'blacklist': [], 'whitelist': []},
        'ignore-rules': {'prefix': [], 'regexp': []},
        'message-aggregation': {'enabled': False, 'delay': 1.5},
        'misc': {'combine-quote-message': False},
    },
    'safety': {
        'content-filter': {'scope': 'all', 'check-sensitive-words': False},
        'rate-limit': {'enabled': False, 'window-length': 60, 'limitation': 60, 'strategy': 'drop'},
    },
    'output': {
        'long-text-processing': {'threshold': 1000, 'strategy': 'none', 'font-path': ''},
        'force-delay': {'min': 0, 'max': 0},
        'misc': {
            'exception-handling': 'show-hint',
            'failure-hint': '',
            'rate-limit-hint': '',
            'content-filter-hint': '',
            'content-filter-error-hint': '',
            'at-sender': False,
            'quote-origin': False,
        },
    },
}


def neutral_policy() -> dict[str, typing.Any]:
    """Return a policy that admits every message and leaves replies untouched."""
    return copy.deepcopy(_NEUTRAL_POLICY)


@functools.lru_cache(maxsize=1)
def _default_policy_template() -> str:
    path = Path(__file__).resolve().parents[2] / 'templates' / 'default-message-policy.json'
    return path.read_text(encoding='utf-8')


def default_policy() -> dict[str, typing.Any]:
    """Return the policy a newly created bot starts with."""
    return merge_policy(neutral_policy(), json.loads(_default_policy_template()))


def merge_policy(base: typing.Any, override: typing.Any) -> dict[str, typing.Any]:
    """Return ``base`` with ``override`` applied key by key; lists are replaced whole."""
    result = copy.deepcopy(base) if isinstance(base, dict) else {}
    if not isinstance(override, dict):
        return result
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_policy(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def resolve_policy(bot_policy: typing.Any, route_override: typing.Any = None) -> dict[str, typing.Any]:
    """Return the complete policy in effect for one route of a bot."""
    return merge_policy(merge_policy(neutral_policy(), bot_policy), route_override)


def _is_policy_key(section: str, block: str, key: str) -> bool:
    return key in POLICY_SCHEMA.get(section, {}).get(block, {})


def extract_legacy_policy(config: typing.Any) -> tuple[dict[str, typing.Any], dict[str, typing.Any]]:
    """Split a legacy config into (what Messaging keeps, the keys that moved).

    The moved keys are returned verbatim, unknown leftovers included, so that
    ``restore_legacy_config`` rebuilds the original exactly. ``trigger`` and
    ``safety`` move whole; ``output`` moves its general blocks and the general
    ``misc`` keys, leaving the AI-specific ones behind.
    """
    remaining = copy.deepcopy(config) if isinstance(config, dict) else {}
    moved: dict[str, typing.Any] = {}
    for section in ('trigger', 'safety'):
        if section in remaining:
            moved[section] = remaining.pop(section)
    output = remaining.get('output')
    if isinstance(output, dict):
        moved_output: dict[str, typing.Any] = {}
        for block in tuple(output):
            if block not in POLICY_SCHEMA['output']:
                continue
            value = output[block]
            if block != 'misc':
                moved_output[block] = output.pop(block)
                continue
            if not isinstance(value, dict):
                continue
            moved_misc = {key: value.pop(key) for key in tuple(value) if _is_policy_key('output', 'misc', key)}
            if moved_misc:
                moved_output['misc'] = moved_misc
        if moved_output:
            moved['output'] = moved_output
    return remaining, moved


def policy_from_legacy(moved: typing.Any) -> dict[str, typing.Any]:
    """Turn moved legacy keys into a policy override that behaves the same."""
    policy = copy.deepcopy(moved) if isinstance(moved, dict) else {}
    for section, block in _SWITCHABLE_BLOCKS:
        value = policy.get(section)
        if isinstance(value, dict) and isinstance(value.get(block), dict):
            value[block].setdefault('enabled', True)
    return policy


def policy_to_legacy(policy: typing.Any) -> dict[str, typing.Any]:
    """Express a policy in the legacy keys alone, for versions without the switches.

    A switched-off block is rewritten to settings that have the same effect:
    group rules that always match, a rate limit that is never reached.
    """
    legacy = copy.deepcopy(policy) if isinstance(policy, dict) else {}
    trigger = legacy.get('trigger')
    rules = trigger.get('group-respond-rules') if isinstance(trigger, dict) else None
    if isinstance(rules, dict) and rules.pop('enabled', True) is False:
        rules['random'] = 1.0
    safety = legacy.get('safety')
    rate_limit = safety.get('rate-limit') if isinstance(safety, dict) else None
    if isinstance(rate_limit, dict) and rate_limit.pop('enabled', True) is False:
        rate_limit.update({'limitation': 2**31 - 1, 'strategy': 'drop'})
    return legacy


def split_legacy_config(config: typing.Any) -> tuple[dict[str, typing.Any], dict[str, typing.Any]]:
    """Convert a legacy config into (Messaging config, message policy override).

    The override holds only what the legacy config stated; a config that is
    already in the new shape yields an empty override.
    """
    remaining, moved = extract_legacy_policy(config)
    return remaining, policy_from_legacy(moved)


def restore_legacy_config(config: typing.Any, moved: typing.Any) -> dict[str, typing.Any]:
    """Inverse of ``extract_legacy_policy``: put moved keys back into a config."""
    restored = copy.deepcopy(config) if isinstance(config, dict) else {}
    if not isinstance(moved, dict):
        return restored
    for section in ('trigger', 'safety'):
        if section in moved:
            restored[section] = copy.deepcopy(moved[section])
    moved_output = moved.get('output')
    if isinstance(moved_output, dict):
        output = restored.setdefault('output', {})
        if isinstance(output, dict):
            for block, value in moved_output.items():
                if block == 'misc' and isinstance(value, dict) and isinstance(output.get('misc'), dict):
                    output['misc'] = {**output['misc'], **copy.deepcopy(value)}
                else:
                    output[block] = copy.deepcopy(value)
    return restored


def overlay_policy(config: typing.Any, policy: dict[str, typing.Any]) -> dict[str, typing.Any]:
    """Lay a complete policy over a Messaging config under the legacy key names.

    The result is what ``query.pipeline_config`` carries, so stages and plugins
    that read the moved keys see the policy in effect. Sub-dicts are shared,
    not copied: treat the result as read-only.
    """
    merged = dict(config) if isinstance(config, dict) else {}
    merged['trigger'] = policy['trigger']
    merged['safety'] = policy['safety']
    output = dict(merged['output']) if isinstance(merged.get('output'), dict) else {}
    policy_output = policy['output']
    for block, value in policy_output.items():
        if block == 'misc':
            current = output.get('misc')
            output['misc'] = {**(current if isinstance(current, dict) else {}), **value}
        else:
            output[block] = value
    merged['output'] = output
    return merged


def _coerce(kind: typing.Any, value: typing.Any) -> typing.Any:
    """Coerce one value to its declared type; raise ValueError if it cannot be."""
    if isinstance(kind, tuple):
        if value not in kind:
            raise ValueError(f'must be one of {", ".join(kind)}')
        return value
    if kind == _BOOL:
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        raise ValueError('must be a boolean')
    if kind == _INT:
        if isinstance(value, bool):
            raise ValueError('must be an integer')
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            return int(value)
        raise ValueError('must be an integer')
    if kind == _NUMBER:
        if isinstance(value, bool):
            raise ValueError('must be a number')
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            return float(value)
        raise ValueError('must be a number')
    if kind == _STR:
        if not isinstance(value, str):
            raise ValueError('must be a string')
        return value
    if kind == _STR_LIST:
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError('must be a list of strings')
        return list(value)
    return value


def coerce_policy(policy: dict[str, typing.Any]) -> dict[str, typing.Any]:
    """Coerce known values in place, keeping (and logging) the ones that cannot be.

    Mirrors what loading a Messaging config does for values that reached the
    JSON column as strings. Never raises: a stored policy must stay loadable.
    """
    for section, blocks in POLICY_SCHEMA.items():
        section_value = policy.get(section)
        if not isinstance(section_value, dict):
            continue
        for block, keys in blocks.items():
            block_value = section_value.get(block)
            if not isinstance(block_value, dict):
                continue
            for key, kind in keys.items():
                if key not in block_value or block_value[key] is None:
                    continue
                try:
                    block_value[key] = _coerce(kind, block_value[key])
                except (TypeError, ValueError) as exc:
                    logger.warning(
                        'Message policy value %s.%s.%s (%r) is invalid: %s',
                        section,
                        block,
                        key,
                        block_value[key],
                        exc,
                    )
    return policy


def validate_policy(value: typing.Any, *, field: str = 'message_policy') -> dict[str, typing.Any]:
    """Validate a policy written through the API and return a clean copy.

    A policy may be partial: a bot policy is completed from the neutral
    policy, a route override from the bot policy. Unknown sections, blocks and
    keys are rejected so a typo cannot silently do nothing.
    """
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f'{field} must be an object')
    cleaned: dict[str, typing.Any] = {}
    for section, section_value in value.items():
        if section not in POLICY_SCHEMA:
            raise ValueError(f'{field}.{section} is not a message policy section')
        if not isinstance(section_value, dict):
            raise ValueError(f'{field}.{section} must be an object')
        cleaned_section: dict[str, typing.Any] = {}
        for block, block_value in section_value.items():
            keys = POLICY_SCHEMA[section].get(block)
            if keys is None:
                raise ValueError(f'{field}.{section}.{block} is not a message policy setting')
            if not isinstance(block_value, dict):
                raise ValueError(f'{field}.{section}.{block} must be an object')
            cleaned_block: dict[str, typing.Any] = {}
            for key, item in block_value.items():
                if key not in keys:
                    raise ValueError(f'{field}.{section}.{block}.{key} is not a message policy setting')
                try:
                    cleaned_block[key] = _coerce(keys[key], item)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f'{field}.{section}.{block}.{key} {exc}') from None
            cleaned_section[block] = cleaned_block
        cleaned[section] = cleaned_section
    _validate_ranges(cleaned, field)
    return cleaned


def _validate_ranges(policy: dict[str, typing.Any], field: str) -> None:
    def get(section: str, block: str, key: str) -> typing.Any:
        return policy.get(section, {}).get(block, {}).get(key)

    random_rate = get('trigger', 'group-respond-rules', 'random')
    if random_rate is not None and not 0 <= random_rate <= 1:
        raise ValueError(f'{field}.trigger.group-respond-rules.random must be between 0 and 1')
    window_length = get('safety', 'rate-limit', 'window-length')
    if window_length is not None and window_length < 1:
        raise ValueError(f'{field}.safety.rate-limit.window-length must be at least 1')
    limitation = get('safety', 'rate-limit', 'limitation')
    if limitation is not None and limitation < 0:
        raise ValueError(f'{field}.safety.rate-limit.limitation must not be negative')
    threshold = get('output', 'long-text-processing', 'threshold')
    if threshold is not None and threshold < 0:
        raise ValueError(f'{field}.output.long-text-processing.threshold must not be negative')
    delay_min = get('output', 'force-delay', 'min')
    delay_max = get('output', 'force-delay', 'max')
    for key, number in (('min', delay_min), ('max', delay_max)):
        if number is not None and number < 0:
            raise ValueError(f'{field}.output.force-delay.{key} must not be negative')
    if delay_min is not None and delay_max is not None and delay_min > delay_max:
        raise ValueError(f'{field}.output.force-delay.min must not exceed max')
