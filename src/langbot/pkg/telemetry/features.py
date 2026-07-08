"""Per-query telemetry feature counters.

Collects anonymous, content-free usage signals (tool call counts, knowledge
base usage, sandbox executions, ...) into ``query.variables`` during query
processing. The chat handler reads the accumulated dict when building the
telemetry payload and ships it as the ``features`` JSON object.

Every helper here is defensive: telemetry must NEVER break the pipeline, so
all mutations are wrapped and failures are silently ignored.
"""

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


FEATURES_KEY = '_telemetry_features'


def get_features(query: pipeline_query.Query) -> dict:
    """Return the mutable features dict for this query, creating it if needed."""
    try:
        return query.variables.setdefault(FEATURES_KEY, {})
    except Exception:
        return {}


def increment(query: pipeline_query.Query, group: str, key: str | None = None, amount: int = 1) -> None:
    """Increment a counter.

    ``increment(q, 'sandbox', 'execs')`` -> features['sandbox']['execs'] += 1
    ``increment(q, 'tool_call_rounds')`` -> features['tool_call_rounds'] += 1
    """
    try:
        features = get_features(query)
        if key is None:
            features[group] = int(features.get(group, 0)) + amount
        else:
            nested = features.setdefault(group, {})
            if isinstance(nested, dict):
                nested[key] = int(nested.get(key, 0)) + amount
    except Exception:
        pass


def set_value(query: pipeline_query.Query, group: str, value: typing.Any) -> None:
    """Set a feature value (overwrites)."""
    try:
        get_features(query)[group] = value
    except Exception:
        pass


def collect_features(query: pipeline_query.Query) -> dict:
    """Build the final ``features`` object for the telemetry payload.

    Combines the counters accumulated during processing with end-of-query
    snapshots (activated skills, bound MCP servers). Returns a plain dict
    that must be JSON-serializable; non-serializable values are dropped.
    """
    features: dict = {}
    try:
        accumulated = query.variables.get(FEATURES_KEY)
        if isinstance(accumulated, dict):
            features.update(accumulated)
    except Exception:
        pass

    # Activated skills (names only, registered by the activate tool)
    try:
        activated = query.variables.get('_activated_skills', {})
        if isinstance(activated, dict) and activated:
            features['activated_skills'] = sorted(activated.keys())
    except Exception:
        pass

    # MCP servers bound to the pipeline (names only; None means "all enabled")
    try:
        bound_mcp = query.variables.get('_pipeline_bound_mcp_servers', None)
        if bound_mcp is not None:
            features['mcp_servers'] = list(bound_mcp)
    except Exception:
        pass

    # Drop anything that is not JSON-serializable
    import json

    try:
        json.dumps(features)
        return features
    except Exception:
        safe: dict = {}
        for k, v in features.items():
            try:
                json.dumps({k: v})
                safe[k] = v
            except Exception:
                continue
        return safe
