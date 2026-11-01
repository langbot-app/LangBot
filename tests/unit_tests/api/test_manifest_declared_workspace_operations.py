"""Unit tests for plugin runner manifest declared workspace operations, default grants, and SDK compatibility."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pydantic
import pytest

from langbot.pkg.agent.runner.descriptor import (
    RunnerDescriptor,
    is_local_agent,
    resolve_authorized_workspace_operations,
)
from langbot.pkg.agent.runner.registry import RunnerRegistry
from langbot.pkg.api.application.tool_grants import get_default_workspace_operations
from langbot.pkg.api.http.service.agent import AgentService


def test_declared_workspace_operations_reading():
    """Test reading workspace operations from descriptor permissions."""
    # With declared operations
    desc = RunnerDescriptor.model_validate(
        {
            'id': 'plugin:author/my-plugin/runner',
            'source': 'plugin',
            'plugin_author': 'author',
            'plugin_name': 'my-plugin',
            'runner_name': 'runner',
            'label': {'en_US': 'Test'},
            'usages': ['agent'],
            'permissions': {
                'workspace_operations': ['bot.list', 'stats.basic'],
            },
        }
    )
    assert desc.declared_workspace_operations() == ['bot.list', 'stats.basic']
    assert desc.workspace_operations == ['bot.list', 'stats.basic']

    # Without permissions or workspace_operations
    desc_empty = RunnerDescriptor.model_validate(
        {
            'id': 'plugin:author/my-plugin/runner2',
            'source': 'plugin',
            'plugin_author': 'author',
            'plugin_name': 'my-plugin',
            'runner_name': 'runner2',
            'label': {'en_US': 'Test'},
            'usages': ['agent'],
            'permissions': {},
        }
    )
    assert desc_empty.declared_workspace_operations() == []


def test_declared_workspace_operations_sdk_0719_compat():
    """Test compatibility with older SDK where RunnerPermissions lacks workspace_operations."""

    class LegacyPermissions(pydantic.BaseModel):
        models: list[str] = []
        tools: list[str] = []
        model_config = pydantic.ConfigDict(extra='forbid')

    desc = RunnerDescriptor.model_validate(
        {
            'id': 'plugin:author/my-plugin/runner',
            'source': 'plugin',
            'plugin_author': 'author',
            'plugin_name': 'my-plugin',
            'runner_name': 'runner',
            'label': {'en_US': 'Test'},
            'usages': ['agent'],
        }
    )
    desc.permissions = LegacyPermissions(models=['invoke'])
    # Must not raise and must return empty list
    assert desc.declared_workspace_operations() == []


def test_resolve_authorized_workspace_operations_local_agent():
    """LocalAgent is not constrained by manifest; receives all configured operations."""
    # Builtin LocalAgent via ID
    desc_builtin = RunnerDescriptor.model_validate(
        {
            'id': 'plugin:langbot-team/LocalAgent/default',
            'source': 'plugin',
            'plugin_author': 'langbot-team',
            'plugin_name': 'LocalAgent',
            'runner_name': 'default',
            'label': {'en_US': 'LocalAgent'},
            'usages': ['agent'],
            'permissions': {},  # No manifest declarations
        }
    )
    assert is_local_agent(desc_builtin) is True
    configured = ['bot.list', 'bot.create', 'stats.basic']
    effective = resolve_authorized_workspace_operations(desc_builtin, configured)
    assert effective == configured

    # None descriptor does not pass is_local_agent and returns empty
    assert is_local_agent(None) is False
    assert resolve_authorized_workspace_operations(None, configured) == []


def test_resolve_authorized_workspace_operations_plugin_intersection_and_narrowing():
    """Plugin runner is restricted to intersection of configured and declared operations, narrowing on upgrade."""
    desc_v1 = RunnerDescriptor.model_validate(
        {
            'id': 'plugin:author/plugin/runner',
            'source': 'plugin',
            'plugin_author': 'author',
            'plugin_name': 'plugin',
            'runner_name': 'runner',
            'label': {'en_US': 'Plugin'},
            'usages': ['agent'],
            'permissions': {
                'workspace_operations': ['bot.list', 'stats.basic', 'audit.log.list'],
            },
        }
    )
    # Configured operations by user
    user_configured = ['bot.list', 'stats.basic', 'bot.delete']

    # Effective is configured ∩ declared: 'bot.list' and 'stats.basic' (bot.delete was not declared)
    effective_v1 = resolve_authorized_workspace_operations(desc_v1, user_configured)
    assert effective_v1 == ['bot.list', 'stats.basic']

    # Plugin v2 upgrades and drops 'stats.basic' from manifest
    desc_v2 = RunnerDescriptor.model_validate(
        {
            'id': 'plugin:author/plugin/runner',
            'source': 'plugin',
            'plugin_author': 'author',
            'plugin_name': 'plugin',
            'runner_name': 'runner',
            'label': {'en_US': 'Plugin'},
            'usages': ['agent'],
            'permissions': {
                'workspace_operations': ['bot.list', 'audit.log.list'],
            },
        }
    )
    # Even though user configuration still has 'stats.basic', runtime narrows automatically
    effective_v2 = resolve_authorized_workspace_operations(desc_v2, user_configured)
    assert effective_v2 == ['bot.list']


def test_registry_real_installed_sdk_0719_manifest_loading():
    """Test registry with real installed SDK 0.7.19 without mocking: strips workspace_operations, returns empty declared."""
    import langbot.pkg.agent.runner.registry as reg_module

    # Verify if running against SDK 0.7.19
    is_old_sdk = 'workspace_operations' not in getattr(reg_module.RunnerPermissions, 'model_fields', {})

    app_mock = MagicMock()
    registry = RunnerRegistry(app_mock)

    raw_runner_data = {
        'plugin_author': 'test-author',
        'plugin_name': 'test-plugin',
        'runner_name': 'default',
        'manifest': {
            'id': 'default',
            'name': 'default',
            'component_kind': 'Runner',
            'usages': ['agent'],
            'label': {'en_US': 'Test'},
            'permissions': {
                'workspace_operations': ['bot.list', 'stats.basic'],
            },
            'config_schema': [],
        },
    }

    # Must validate successfully without raising extra_forbidden
    desc = registry._validate_and_build_descriptor(raw_runner_data)
    assert desc is not None
    assert desc.id == 'plugin:test-author/test-plugin/default'

    if is_old_sdk:
        # In 0.7.19, declared workspace operations must be empty (feature disabled cleanly)
        assert desc.declared_workspace_operations() == []
        assert resolve_authorized_workspace_operations(desc, ['bot.list', 'stats.basic']) == []
    else:
        # In new SDK, declared workspace operations are preserved
        assert desc.declared_workspace_operations() == ['bot.list', 'stats.basic']
        assert resolve_authorized_workspace_operations(desc, ['bot.list', 'stats.basic']) == ['bot.list', 'stats.basic']


def test_registry_real_new_sdk_manifest_loading_subprocess():
    """Test registry with real new SDK from langbot-plugin-sdk repo in a clean subprocess."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    sdk_path = Path(__file__).resolve().parents[4] / 'langbot-plugin-sdk' / 'src'
    if not sdk_path.exists():
        pytest.skip('langbot-plugin-sdk repo not found')

    code = f"""
import sys
sys.path.insert(0, {repr(str(sdk_path))})

from langbot_plugin.api.entities.builtin.runner.manifest import RunnerPermissions
assert "workspace_operations" in RunnerPermissions.model_fields, "New SDK must have workspace_operations"

from langbot.pkg.agent.runner.registry import RunnerRegistry
from langbot.pkg.agent.runner.descriptor import resolve_authorized_workspace_operations
from unittest.mock import Mock

registry = RunnerRegistry(Mock())
raw_runner_data = {{
    'plugin_author': 'test-author',
    'plugin_name': 'test-plugin',
    'runner_name': 'default',
    'manifest': {{
        'id': 'default',
        'name': 'default',
        'component_kind': 'Runner',
        'usages': ['agent'],
        'label': {{'en_US': 'Test'}},
        'permissions': {{
            'workspace_operations': ['bot.list', 'stats.basic'],
        }},
        'config_schema': [],
    }},
}}
desc = registry._validate_and_build_descriptor(raw_runner_data)
assert desc is not None
assert desc.declared_workspace_operations() == ['bot.list', 'stats.basic'], f"Got {{desc.declared_workspace_operations()}}"
authorized = resolve_authorized_workspace_operations(desc, ['bot.list', 'stats.basic', 'other'])
assert authorized == ['bot.list', 'stats.basic'], f"Got {{authorized}}"
print("REAL_NEW_SDK_PASSED")
"""
    res = subprocess.run(
        [sys.executable, '-c', code],
        env={**os.environ, 'PYTHONPATH': f'{sdk_path}:{os.environ.get("PYTHONPATH", "")}'},
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f'STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}'
    assert 'REAL_NEW_SDK_PASSED' in res.stdout


@pytest.mark.asyncio
async def test_registry_pipeline_metadata_includes_workspace_operations():
    """get_runner_metadata_for_pipeline includes workspace_operations in runner options."""
    app_mock = MagicMock()
    registry = RunnerRegistry(app_mock)

    desc = RunnerDescriptor.model_validate(
        {
            'id': 'plugin:author/plugin/runner',
            'source': 'plugin',
            'plugin_author': 'author',
            'plugin_name': 'plugin',
            'runner_name': 'runner',
            'label': {'en_US': 'Runner Label'},
            'usages': ['agent'],
            'permissions': {
                'workspace_operations': ['bot.list', 'stats.basic'],
            },
            'config_schema': [],
        }
    )
    registry.list_runners = AsyncMock(return_value=[desc])

    options, stages = await registry.get_runner_metadata_for_pipeline(MagicMock())
    assert len(options) == 1
    assert options[0]['name'] == desc.id
    assert options[0]['workspace_operations'] == ['bot.list', 'stats.basic']


def test_get_default_workspace_operations():
    """get_default_workspace_operations filters declared operations to exposure == 'all' and non-streaming."""
    from types import SimpleNamespace

    app = SimpleNamespace(application_api=None)

    # Empty declared operations
    assert get_default_workspace_operations(app, []) == []
    assert get_default_workspace_operations(app, None) == []

    # Valid operations with real ApplicationAPI
    defaults = get_default_workspace_operations(app, ['bot.list', 'stats.basic', 'invalid.operation'])
    assert 'bot.list' in defaults
    assert 'stats.basic' in defaults
    assert 'invalid.operation' not in defaults


@pytest.mark.asyncio
async def test_prepare_event_processor_defaults_workspace_operations():
    """_prepare_event_processor defaults allowed_workspace_operations on creation."""
    app_mock = MagicMock()
    app_mock.application_api = None
    app_mock.llm_model_service.apply_default_model = AsyncMock(side_effect=lambda ctx, schema, params: params)
    app_mock.pipeline_service._get_default_values_from_schema = MagicMock(return_value={})
    service = AgentService(app_mock)

    desc = RunnerDescriptor.model_validate(
        {
            'id': 'plugin:author/plugin/processor',
            'source': 'plugin',
            'plugin_author': 'author',
            'plugin_name': 'plugin',
            'runner_name': 'processor',
            'label': {'en_US': 'Processor'},
            'usages': ['event'],
            'supported_event_patterns': ['message.*'],
            'permissions': {
                'workspace_operations': ['bot.list', 'stats.basic'],
            },
            'config_schema': [],
        }
    )
    app_mock.runner_registry.get = AsyncMock(return_value=desc)

    # Creating draft event processor without config
    data = {'component_ref': 'plugin:author/plugin/processor'}
    config, ref, patterns = await service._prepare_event_processor(MagicMock(), data, existing=None)

    assert ref == 'plugin:author/plugin/processor'
    assert 'allowed_workspace_operations' in config
    assert 'bot.list' in config['allowed_workspace_operations']
    assert 'stats.basic' in config['allowed_workspace_operations']
