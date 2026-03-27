from __future__ import annotations

import logging
from typing import Any


_logger = logging.getLogger('langbot')


WECOMCS_RUNTIME_DEFAULTS = {
    'history_message_drop_threshold_seconds': 90,
    'nickname_lookup_timeout_seconds': 30.0,
    'retry_max_attempts': 3,
    'retry_backoff_seconds': [15, 30, 45],
    'lock_ttl_seconds': 60,
    'pull_stream_shard_count': 1,
    'process_stream_shard_count': 1,
}


def _coerce_int(raw_value: Any, *, minimum: int, field_name: str, source: str) -> int | None:
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError):
        if raw_value not in (None, ''):
            _logger.warning(
                f'[wecomcs][config] 整数配置非法，回退上层默认: field={field_name}, source={source}, raw_value={raw_value}'
            )
        return None
    if parsed < minimum:
        _logger.warning(
            f'[wecomcs][config] 整数配置低于最小值，回退上层默认: field={field_name}, source={source}, raw_value={raw_value}, minimum={minimum}'
        )
        return None
    return parsed


def _coerce_float(raw_value: Any, *, minimum: float, field_name: str, source: str) -> float | None:
    try:
        parsed = float(raw_value)
    except (TypeError, ValueError):
        if raw_value not in (None, ''):
            _logger.warning(
                f'[wecomcs][config] 浮点配置非法，回退上层默认: field={field_name}, source={source}, raw_value={raw_value}'
            )
        return None
    if parsed < minimum:
        _logger.warning(
            f'[wecomcs][config] 浮点配置低于最小值，回退上层默认: field={field_name}, source={source}, raw_value={raw_value}, minimum={minimum}'
        )
        return None
    return parsed


def _coerce_retry_backoff(raw_value: Any, *, source: str) -> list[int] | None:
    if raw_value in (None, ''):
        return None

    if isinstance(raw_value, str):
        parts = [item.strip() for item in raw_value.split(',') if item.strip()]
    elif isinstance(raw_value, (list, tuple)):
        parts = list(raw_value)
    else:
        _logger.warning(
            f'[wecomcs][config] 重试间隔配置类型非法，回退上层默认: source={source}, raw_value={raw_value}'
        )
        return None

    parsed_values: list[int] = []
    for item in parts:
        try:
            parsed = int(item)
        except (TypeError, ValueError):
            _logger.warning(
                f'[wecomcs][config] 重试间隔配置包含非法项，回退上层默认: source={source}, raw_value={raw_value}'
            )
            return None
        if parsed <= 0:
            _logger.warning(
                f'[wecomcs][config] 重试间隔配置包含非正整数，回退上层默认: source={source}, raw_value={raw_value}'
            )
            return None
        parsed_values.append(parsed)

    return parsed_values or None


# 中文注释：bot 配置优先级最高，其次是全局默认，最后才是代码默认值。
def resolve_wecomcs_runtime_settings(bot_config: dict[str, Any], global_scheduler_config: dict[str, Any]) -> dict[str, Any]:
    resolved = dict(global_scheduler_config or {})

    resolved['history_message_drop_threshold_seconds'] = (
        _coerce_int(
            bot_config.get('history_message_drop_threshold_seconds'),
            minimum=0,
            field_name='history_message_drop_threshold_seconds',
            source='bot',
        )
        or _coerce_int(
            global_scheduler_config.get('history_message_drop_threshold_seconds'),
            minimum=0,
            field_name='history_message_drop_threshold_seconds',
            source='global',
        )
        or WECOMCS_RUNTIME_DEFAULTS['history_message_drop_threshold_seconds']
    )

    resolved['retry_max_attempts'] = (
        _coerce_int(
            bot_config.get('retry_max_attempts'),
            minimum=0,
            field_name='retry_max_attempts',
            source='bot',
        )
        or _coerce_int(
            global_scheduler_config.get('retry_max_attempts'),
            minimum=0,
            field_name='retry_max_attempts',
            source='global',
        )
        or WECOMCS_RUNTIME_DEFAULTS['retry_max_attempts']
    )

    resolved['lock_ttl_seconds'] = (
        _coerce_int(
            bot_config.get('lock_ttl_seconds'),
            minimum=1,
            field_name='lock_ttl_seconds',
            source='bot',
        )
        or _coerce_int(
            global_scheduler_config.get('lock_ttl_seconds'),
            minimum=1,
            field_name='lock_ttl_seconds',
            source='global',
        )
        or WECOMCS_RUNTIME_DEFAULTS['lock_ttl_seconds']
    )

    resolved['nickname_lookup_timeout_seconds'] = (
        _coerce_float(
            bot_config.get('nickname_lookup_timeout_seconds'),
            minimum=0.1,
            field_name='nickname_lookup_timeout_seconds',
            source='bot',
        )
        or _coerce_float(
            global_scheduler_config.get('nickname_lookup_timeout_seconds'),
            minimum=0.1,
            field_name='nickname_lookup_timeout_seconds',
            source='global',
        )
        or WECOMCS_RUNTIME_DEFAULTS['nickname_lookup_timeout_seconds']
    )

    resolved['retry_backoff_seconds'] = (
        _coerce_retry_backoff(bot_config.get('retry_backoff_seconds'), source='bot')
        or _coerce_retry_backoff(global_scheduler_config.get('retry_backoff_seconds'), source='global')
        or list(WECOMCS_RUNTIME_DEFAULTS['retry_backoff_seconds'])
    )

    # English comment: We currently pin WeCom CS scheduling to one pull stream and one process stream per bot.
    # This keeps routing deterministic and avoids cross-bot queue coupling until a broader runtime redesign lands.
    resolved['pull_stream_shard_count'] = WECOMCS_RUNTIME_DEFAULTS['pull_stream_shard_count']
    resolved['process_stream_shard_count'] = WECOMCS_RUNTIME_DEFAULTS['process_stream_shard_count']

    return resolved
