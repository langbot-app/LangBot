"""Strict, opt-in settings for the existing LangBot traffic scheduler.

The configurable profile selects built-in catalogue cases, never defining a
command, endpoint, credential, or case expectation. A compiled phase carries
the stock phase options and its own weighted case list.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
import json
import math
from pathlib import Path
import random
import re
from typing import Any


_MAX_TOTAL_WEIGHT = 1_000
_MAX_PLANNED_SLOTS = 10_000_000
_NAME = re.compile(r'[a-zA-Z][a-zA-Z0-9_-]*')
_PHASE_FIELDS = frozenset(
    {'name', 'duration_seconds', 'rps', 'workers', 'cooldown_seconds', 'groups', 'members_per_group', 'max_requests'}
)
_REQUIRED_PHASE_FIELDS = frozenset({'name', 'duration_seconds', 'rps', 'workers'})


@dataclass(frozen=True)
class MixloadProfile:
    include: tuple[str, ...] | None
    exclude: tuple[str, ...]
    weights: dict[str, int]
    phases: tuple[dict[str, Any], ...] | None
    seed: int | None


@dataclass(frozen=True)
class CompiledPhase:
    phase: dict[str, Any]
    cases: list[dict[str, Any]]
    min_delivery_ratio: float | None = None


def _fields(value, *, allowed, required, label):
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f'{label} must be an object with string keys')
    if extra := set(value) - allowed:
        raise ValueError(f'{label} has unknown fields: {", ".join(sorted(extra))}')
    if missing := required - set(value):
        raise ValueError(f'{label} is missing required fields: {", ".join(sorted(missing))}')


def _number(value, label, *, minimum=0, maximum=None, integer=False):
    # Booleans are integers in Python but not useful numeric profile settings.
    if type(value) not in (int, float) or (integer and type(value) is not int):
        raise ValueError(f'{label} must be {"an integer" if integer else "a finite number"}')
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite or value < minimum or (maximum is not None and value > maximum):
        bounds = f'{minimum}..{maximum}' if maximum is not None else f'>= {minimum}'
        raise ValueError(f'{label} must be finite and within {bounds}')


def _scenario_name(value, label):
    if not isinstance(value, str) or _NAME.fullmatch(value) is None:
        raise ValueError(f'{label} must be a simple scenario name')


def _scenario_names(value, label):
    if not isinstance(value, list):
        raise ValueError(f'{label} must be an array of scenario names')
    for name in value:
        _scenario_name(name, label)
    if len(set(value)) != len(value):
        raise ValueError(f'{label} repeats a scenario')
    return tuple(value)


def _weights(value, label, *, minimum):
    if not isinstance(value, dict):
        raise ValueError(f'{label} must be an object mapping scenario names to integer weights')
    for name, weight in value.items():
        _scenario_name(name, label)
        _number(weight, f'{label}.{name}', minimum=minimum, maximum=_MAX_TOTAL_WEIGHT, integer=True)
    return dict(value)


def _phases(value):
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError('phases must be a non-empty array')
    seen = set()
    result = []
    for index, phase in enumerate(value):
        label = f'phases[{index}]'
        _fields(
            phase,
            allowed=_PHASE_FIELDS | {'weights', 'min_delivery_ratio'},
            required=_REQUIRED_PHASE_FIELDS,
            label=label,
        )
        name = phase['name']
        _scenario_name(name, f'{label}.name')
        if name in seen:
            raise ValueError(f'duplicate phase name: {name}')
        seen.add(name)
        label = f'phase {name}'
        for setting in ('duration_seconds', 'rps'):
            _number(phase[setting], f'{label}.{setting}', minimum=0.001)
        _number(phase['workers'], f'{label}.workers', minimum=1, maximum=32, integer=True)
        if 'cooldown_seconds' in phase:
            _number(phase['cooldown_seconds'], f'{label}.cooldown_seconds')
        if 'groups' in phase:
            _number(phase['groups'], f'{label}.groups', maximum=4096, integer=True)
        if 'members_per_group' in phase:
            _number(phase['members_per_group'], f'{label}.members_per_group', minimum=1, maximum=1000, integer=True)
        if 'min_delivery_ratio' in phase:
            _number(phase['min_delivery_ratio'], f'{label}.min_delivery_ratio', maximum=1)
        if 'max_requests' in phase:
            _number(phase['max_requests'], f'{label}.max_requests', minimum=1, integer=True)
        slot_budget = float(phase['duration_seconds']) * float(phase['rps'])
        if not math.isfinite(slot_budget):
            raise ValueError(f'{label}: duration_seconds * rps must be finite')
        nominal_slots = math.ceil(slot_budget)
        effective_slots = min(nominal_slots, phase.get('max_requests', nominal_slots))
        if effective_slots > _MAX_PLANNED_SLOTS:
            raise ValueError(f'{label}: planned request slots must be <= {_MAX_PLANNED_SLOTS}')
        entry = dict(phase)
        if 'weights' in entry:
            entry['weights'] = _weights(entry['weights'], f'{label}.weights', minimum=0)
        result.append(entry)
    return tuple(result)


def parse_mixload(value) -> MixloadProfile:
    """Validate a profile object without resolving case references yet."""
    _fields(
        value,
        allowed={'version', 'seed', 'include', 'exclude', 'weights', 'phases'},
        required={'version'},
        label='mixload profile',
    )
    if type(value['version']) is not int or value['version'] != 1:
        raise ValueError('mixload profile version must be 1')
    include = _scenario_names(value['include'], 'include') if 'include' in value else None
    exclude = _scenario_names(value.get('exclude', []), 'exclude')
    if include is not None and (overlap := set(include) & set(exclude)):
        raise ValueError(f'scenarios are both included and excluded: {", ".join(sorted(overlap))}')
    if 'seed' in value:
        _number(value['seed'], 'seed', maximum=2**32 - 1, integer=True)
    return MixloadProfile(
        include=include,
        exclude=exclude,
        weights=_weights(value.get('weights', {}), 'weights', minimum=1),
        phases=_phases(value['phases']) if 'phases' in value else None,
        seed=value.get('seed'),
    )


def _unique_keys(items):
    fields = {}
    for key, value in items:
        if key in fields:
            raise ValueError(f'duplicate JSON key: {key}')
        fields[key] = value
    return fields


def _invalid_constant(value):
    raise ValueError(f'non-finite JSON number: {value}')


def load_mixload(path: str | Path) -> MixloadProfile:
    """Read and validate a UTF-8 JSON configuration file."""
    return parse_mixload(
        json.loads(
            Path(path).read_text(encoding='utf-8'),
            object_pairs_hook=_unique_keys,
            parse_constant=_invalid_constant,
        )
    )


def _check_references(names, available, label):
    if unknown := set(names) - available:
        raise ValueError(f'{label} references unknown scenario(s): {", ".join(sorted(unknown))}')


def _replayable(cases, phase):
    group_cases = ['http_group' in case for case in cases]
    if any(set(case) & {'scenario', 'http_probe', 'reject_group', 'reset_group', 'mock_requests'} for case in cases):
        raise ValueError(f'{phase["name"]}: finite/control scenarios cannot be used as repeating load cases')
    groups = phase.get('groups', 0)
    if any(group_cases):
        if not all(group_cases) or not groups:
            raise ValueError(f'{phase["name"]}: group traffic cannot mix with CLI traffic and requires groups')
        if groups < sum(case['weight'] for case in cases):
            raise ValueError(f'{phase["name"]}: groups must cover the complete weighted case sequence')
    elif groups:
        raise ValueError(f'{phase["name"]}: groups require only http_group cases')
    elif 'members_per_group' in phase:
        raise ValueError(f'{phase["name"]}: members_per_group requires group traffic')


def compile_mixload(base_cases, config: MixloadProfile, *, default_phases=()) -> list[CompiledPhase]:
    """Resolve a profile to fresh per-phase stock options and weighted cases.

    The original catalogue supplies request/validation data and default weights.
    Global weights override defaults; phase weights take precedence, with zero
    selecting a case out of that one phase. Ordering follows the catalogue
    unless a seed requests a deterministic phase-local shuffle.
    """
    if not isinstance(base_cases, (list, tuple)) or not base_cases:
        raise ValueError('mixload case catalogue must be non-empty')
    catalog = {}
    for case in base_cases:
        if not isinstance(case, dict):
            raise ValueError('mixload case catalogue entries must be objects')
        name = case.get('name')
        _scenario_name(name, 'catalogue case name')
        if name in catalog:
            raise ValueError(f'duplicate catalogue case: {name}')
        _number(
            case.get('weight', 1), f'catalogue case {name}.weight', minimum=1, maximum=_MAX_TOTAL_WEIGHT, integer=True
        )
        catalog[name] = case
    available = set(catalog)
    _check_references(config.include or (), available, 'include')
    _check_references(config.exclude, available, 'exclude')
    selected = (available if config.include is None else set(config.include)) - set(config.exclude)
    if not selected:
        raise ValueError('mixload profile selects no scenarios')
    _check_references(config.weights, selected, 'weights (selected scenarios only)')
    compiled = []
    for entry in config.phases if config.phases is not None else _phases(default_phases):
        phase = {key: value for key, value in entry.items() if key in _PHASE_FIELDS}
        overrides = entry.get('weights', {})
        label = f'phase {phase["name"]}'
        _check_references(overrides, selected, f'{label}.weights (selected scenarios only)')
        cases = []
        for name, item in catalog.items():
            if name not in selected:
                continue
            weight = overrides.get(name, config.weights.get(name, item.get('weight', 1)))
            if weight:
                case = copy.deepcopy(item)
                case['weight'] = weight
                cases.append(case)
        if not cases:
            raise ValueError(f'{label} selects no scenarios')
        if sum(case['weight'] for case in cases) > _MAX_TOTAL_WEIGHT:
            raise ValueError(f'{label}: total case weight must be <= {_MAX_TOTAL_WEIGHT}')
        _replayable(cases, phase)
        if config.seed is not None:
            random.Random(f'{config.seed}:{phase["name"]}').shuffle(cases)
        compiled.append(CompiledPhase(phase=phase, cases=cases, min_delivery_ratio=entry.get('min_delivery_ratio')))
    return compiled
