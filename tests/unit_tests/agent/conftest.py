"""Shared test fixtures for agent runner tests."""
from __future__ import annotations

import typing


def make_resources(
    models: list[dict] | None = None,
    tools: list[dict] | None = None,
    knowledge_bases: list[dict] | None = None,
    skills: list[dict] | None = None,
    storage: dict | None = None,
    files: list[dict] | None = None,
) -> dict[str, typing.Any]:
    """Create a minimal AgentResources dict for testing.

    Args:
        models: List of model dicts with 'model_id' key
        tools: List of tool dicts with 'tool_name' key
        knowledge_bases: List of KB dicts with 'kb_id' key
        skills: List of skill dicts with 'skill_name' key
        storage: Storage permissions dict
        files: List of file dicts with 'file_id' key

    Returns:
        AgentResources dict with all required fields
    """
    return {
        'models': models or [],
        'tools': tools or [],
        'knowledge_bases': knowledge_bases or [],
        'skills': skills or [],
        'files': files or [],
        'storage': storage or {'plugin_storage': False, 'workspace_storage': False},
        'platform_capabilities': {},
    }


def make_session(
    run_id: str = 'test-run-id',
    runner_id: str = 'plugin:test/test-runner/default',
    query_id: int | None = 1,
    plugin_identity: str = 'test/test-runner',
    resources: dict | None = None,
    conversation_id: str | None = None,
    available_apis: dict[str, bool] | None = None,
    state_policy: dict[str, typing.Any] | None = None,
    state_context: dict[str, typing.Any] | None = None,
) -> dict[str, typing.Any]:
    """Create a minimal AgentRunSession dict for testing.

    Args:
        run_id: Unique run identifier
        runner_id: Runner descriptor ID
        query_id: Host entry query ID
        plugin_identity: Plugin identifier (author/name)
        resources: AgentResources dict (uses make_resources() default if None)

    Returns:
        AgentRunSession dict with run-scoped authorization snapshot
    """
    import time
    now = int(time.time())
    res = resources if resources is not None else make_resources()
    apis = available_apis if available_apis is not None else {}
    policy = (
        state_policy
        if state_policy is not None
        else {'enable_state': True, 'state_scopes': ['conversation', 'actor']}
    )
    context = state_context if state_context is not None else {}

    authorized_ids: dict[str, set[str]] = {
        'model': {m.get('model_id') for m in res.get('models', [])},
        'tool': {t.get('tool_name') for t in res.get('tools', [])},
        'knowledge_base': {kb.get('kb_id') for kb in res.get('knowledge_bases', [])},
        'skill': {s.get('skill_name') for s in res.get('skills', [])},
        'file': {f.get('file_id') for f in res.get('files', [])},
    }

    return {
        'run_id': run_id,
        'runner_id': runner_id,
        'query_id': query_id,
        'plugin_identity': plugin_identity,
        'authorization': {
            'resources': res,
            'available_apis': apis,
            'conversation_id': conversation_id,
            'state_policy': policy,
            'state_context': context,
            'authorized_ids': authorized_ids,
        },
        'status': {
            'started_at': now,
            'last_activity_at': now,
        },
    }
