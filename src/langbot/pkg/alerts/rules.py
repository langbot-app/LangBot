"""Built-in alert rules and validation of Workspace overrides."""

from __future__ import annotations

import dataclasses
import typing


@dataclasses.dataclass(frozen=True, slots=True)
class RuleSpec:
    name: str
    default_threshold: int
    min_threshold: int
    max_threshold: int
    default_window_minutes: int
    min_window_minutes: int
    max_window_minutes: int
    # Auto-resolve after this many quiet minutes. ``None`` resolves only on an
    # explicit recovery signal (a bot that starts again).
    quiet_minutes: int | None


RULES: dict[str, RuleSpec] = {
    # Pipeline processing errors recorded by monitoring, per Pipeline.
    'pipeline_failures': RuleSpec('pipeline_failures', 5, 3, 100, 10, 1, 60, 15),
    # Failed model calls, per model.
    'model_failures': RuleSpec('model_failures', 10, 3, 200, 10, 1, 60, 15),
    # A platform adapter that exited with an error, per bot. A crash is a hard
    # stop, so a single event opens the incident.
    'bot_offline': RuleSpec('bot_offline', 1, 1, 1, 1, 1, 1, None),
}

# Reminders while an incident keeps firing: 6h, then 12h, then every 24h.
REMINDER_INTERVALS_HOURS = (6, 12, 24)


def reminder_interval_hours(reminders_sent: int) -> int:
    return REMINDER_INTERVALS_HOURS[min(reminders_sent, len(REMINDER_INTERVALS_HOURS) - 1)]


def _bounded_int(value: typing.Any, low: int, high: int, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, low), high)


def normalize_rules(raw: typing.Any) -> dict[str, dict[str, typing.Any]]:
    """Return a complete, clamped rule map; unknown rules are dropped."""

    raw = raw if isinstance(raw, dict) else {}
    result: dict[str, dict[str, typing.Any]] = {}
    for name, spec in RULES.items():
        override = raw.get(name) if isinstance(raw.get(name), dict) else {}
        result[name] = {
            'enabled': bool(override.get('enabled', True)),
            'threshold': _bounded_int(
                override.get('threshold'), spec.min_threshold, spec.max_threshold, spec.default_threshold
            ),
            'window_minutes': _bounded_int(
                override.get('window_minutes'),
                spec.min_window_minutes,
                spec.max_window_minutes,
                spec.default_window_minutes,
            ),
        }
    return result


def rule_catalog() -> list[dict[str, typing.Any]]:
    return [
        {
            'name': spec.name,
            'default_threshold': spec.default_threshold,
            'min_threshold': spec.min_threshold,
            'max_threshold': spec.max_threshold,
            'default_window_minutes': spec.default_window_minutes,
            'min_window_minutes': spec.min_window_minutes,
            'max_window_minutes': spec.max_window_minutes,
            'auto_resolve_minutes': spec.quiet_minutes,
        }
        for spec in RULES.values()
    ]
