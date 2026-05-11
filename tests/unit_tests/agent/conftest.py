"""Shared test fixtures for agent runner tests."""
from __future__ import annotations

import typing


def make_resources(
    models: list[dict] | None = None,
    tools: list[dict] | None = None,
    knowledge_bases: list[dict] | None = None,
    storage: dict | None = None,
) -> dict[str, typing.Any]:
    """Create a minimal AgentResources dict for testing.

    Args:
        models: List of model dicts with 'model_id' key
        tools: List of tool dicts with 'tool_name' key
        knowledge_bases: List of KB dicts with 'kb_id' key
        storage: Storage permissions dict

    Returns:
        AgentResources dict with all required fields
    """
    return {
        'models': models or [],
        'tools': tools or [],
        'knowledge_bases': knowledge_bases or [],
        'files': [],
        'storage': storage or {'plugin_storage': False, 'workspace_storage': False},
        'platform_capabilities': {},
    }


def make_session(
    run_id: str = 'test-run-id',
    runner_id: str = 'plugin:test/test-runner/default',
    query_id: int | None = 1,
    plugin_identity: str = 'test/test-runner',
    resources: dict | None = None,
) -> dict[str, typing.Any]:
    """Create a minimal AgentRunSession dict for testing.

    Args:
        run_id: Unique run identifier
        runner_id: Runner descriptor ID
        query_id: Pipeline query ID
        plugin_identity: Plugin identifier (author/name)
        resources: AgentResources dict (uses make_resources() default if None)

    Returns:
        AgentRunSession dict with all required fields including pre-computed _authorized_ids
    """
    import time
    now = int(time.time())
    res = resources or make_resources()

    # Pre-compute authorized IDs for O(1) lookup (matching production behavior)
    authorized_ids: dict[str, set[str]] = {
        'model': {m.get('model_id') for m in res.get('models', [])},
        'tool': {t.get('tool_name') for t in res.get('tools', [])},
        'knowledge_base': {kb.get('kb_id') for kb in res.get('knowledge_bases', [])},
    }

    return {
        'run_id': run_id,
        'runner_id': runner_id,
        'query_id': query_id,
        'plugin_identity': plugin_identity,
        'resources': res,
        'status': {
            'started_at': now,
            'last_activity_at': now,
        },
        '_authorized_ids': authorized_ids,
    }