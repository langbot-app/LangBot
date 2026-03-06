from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# metadata type -> coercion function
_COERCE_MAP = {
    'integer': lambda v: int(v),
    'number': lambda v: float(v),
    'float': lambda v: float(v),
}


def _coerce_bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        if v.lower() == 'true':
            return True
        if v.lower() == 'false':
            return False
        raise ValueError(f"Cannot convert string {v!r} to bool")
    return bool(v)


def _coerce_value(value, expected_type: str):
    """Convert a single value to the expected type.

    Returns the converted value, or the original value if no conversion needed.
    """
    if value is None:
        return value

    if expected_type == 'boolean':
        if isinstance(value, bool):
            return value
        return _coerce_bool(value)

    coerce_fn = _COERCE_MAP.get(expected_type)
    if coerce_fn is None:
        return value

    # Already the correct type
    if expected_type == 'integer' and isinstance(value, int) and not isinstance(value, bool):
        return value
    if expected_type in ('number', 'float') and isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)

    return coerce_fn(value)


def coerce_pipeline_config(
    config: dict,
    *metadata_list: dict,
) -> None:
    """Coerce pipeline config values according to metadata type definitions.

    Walks each metadata dict (trigger, safety, ai, output) and converts
    config values in-place so that strings coming from the JSON column are
    cast to their declared types (integer, number/float, boolean).

    Args:
        config: The pipeline config dict to modify in-place.
        *metadata_list: Metadata dicts loaded from the YAML templates.
    """
    for meta in metadata_list:
        section_name = meta.get('name')
        if not section_name or section_name not in config:
            continue

        section = config[section_name]
        if not isinstance(section, dict):
            continue

        for stage_def in meta.get('stages', []):
            stage_name = stage_def.get('name')
            if not stage_name or stage_name not in section:
                continue

            stage_config = section[stage_name]
            if not isinstance(stage_config, dict):
                continue

            for field_def in stage_def.get('config', []):
                field_name = field_def.get('name')
                field_type = field_def.get('type')
                if not field_name or not field_type or field_name not in stage_config:
                    continue

                old_value = stage_config[field_name]
                try:
                    new_value = _coerce_value(old_value, field_type)
                    if new_value is not old_value:
                        stage_config[field_name] = new_value
                except (ValueError, TypeError) as e:
                    logger.warning(
                        "Failed to coerce config %s.%s.%s (%r) to %s: %s",
                        section_name, stage_name, field_name,
                        old_value, field_type, e,
                    )
