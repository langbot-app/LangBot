from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.core.stages.load_config import _complete_runtime_policy_defaults, _apply_env_overrides_to_config
from langbot.pkg.plugin.connector import PluginRuntimeConnector


@pytest.mark.parametrize('mode', ['cloud', 'oss'])
def test_mode_overrides_only_reach_cloud_runtime(mode, monkeypatch):
    monkeypatch.setenv('PLUGIN__WORKER__DEDICATED__MAX_CPUS', '0.5')
    monkeypatch.setenv('PLUGIN__WORKER__DEDICATED__MAX_MEMORY_MB', '256')
    monkeypatch.setenv('PLUGIN__WORKER__SHARED__MAX_CPUS', '1.0')
    monkeypatch.setenv('PLUGIN__WORKER__SHARED__MAX_MEMORY_MB', '512')
    config = _apply_env_overrides_to_config(_complete_runtime_policy_defaults({'plugin': {'enable': True}}))
    app = SimpleNamespace(instance_config=SimpleNamespace(data=config), deployment=SimpleNamespace(mode=mode))
    connector = PluginRuntimeConnector(app, AsyncMock())
    policy = connector._load_worker_policy()
    if mode == 'cloud':
        assert policy.dedicated.max_cpus == 0.5
        assert policy.dedicated.max_memory_mb == 256
        assert policy.shared.max_cpus == 1.0
        assert policy.shared.max_memory_mb == 512
    else:
        assert policy.dedicated is None
        assert policy.shared is None
        assert policy.max_cpus == 1.0
        assert policy.max_memory_mb == 512


def test_cloud_unset_overrides_inherit_existing_limits():
    config = _complete_runtime_policy_defaults(
        {'plugin': {'enable': True, 'worker': {'max_cpus': 1.5, 'max_memory_mb': 768}}}
    )
    app = SimpleNamespace(instance_config=SimpleNamespace(data=config), deployment=SimpleNamespace(mode='cloud'))
    policy = PluginRuntimeConnector(app, AsyncMock())._load_worker_policy()
    for mode in ('dedicated', 'shared-runtime-v1'):
        resolved = policy.for_execution_mode(mode, 'shared')
        assert resolved.max_cpus == 1.5
        assert resolved.max_memory_mb == 768
