"""Runner resolution errors name the actual misconfiguration (LANG-358)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from langbot.pkg.agent.runner.errors import RunnerNotFoundError
from langbot.pkg.agent.runner.query_bridge import QueryRunBridge


def _build(pipeline_config):
    bridge = QueryRunBridge(binding_resolver=SimpleNamespace())
    return bridge.build_plan(SimpleNamespace(pipeline_config=pipeline_config))


@pytest.mark.parametrize(
    'config',
    [
        {'ai': {'runner': {'id': '', 'expire-time': 0}, 'runner_config': {}}},
        {'ai': {}},
        {},
    ],
)
def test_unselected_runner_is_not_reported_as_legacy(config):
    with pytest.raises(RunnerNotFoundError) as exc_info:
        _build(config)
    message = str(exc_info.value)
    assert 'no runner selected' in message
    assert 'legacy' not in message


@pytest.mark.parametrize(
    'config',
    [
        {'ai': {'runner': {'runner': 'local-agent', 'expire-time': 0}, 'local-agent': {}}},
        {'ai': {'runner': 'local-agent'}},
        {'ai': {'runner': {'id': ''}, 'dify-service-api': {}}},
    ],
)
def test_legacy_pipeline_keeps_migration_hint(config):
    with pytest.raises(RunnerNotFoundError, match='legacy \\(pre-4.11\\) pipelines must be migrated'):
        _build(config)


def test_legacy_runner_name_in_id_points_to_plugin_runner():
    with pytest.raises(RunnerNotFoundError) as exc_info:
        _build({'ai': {'runner': {'id': 'local-agent'}, 'runner_config': {'local-agent': {}}}})
    assert exc_info.value.runner_id.startswith('local-agent is a pre-4.11 runner name')
    assert 'plugin:langbot-team/LocalAgent/default' in str(exc_info.value)
