"""Plugin declarations and model selection use separate permission boundaries."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import yaml
from pydantic import ValidationError
from langbot_plugin.api.entities.builtin.runner.manifest import RunnerPermissions

from langbot.pkg.agent.runner.descriptor import RunnerDescriptor
from langbot.pkg.agent.runner.resource_builder import AgentResourceBuilder
from langbot.pkg.api.application.contracts import Input, Operation
from langbot.pkg.api.application.plugin_permissions import read_declaration
from langbot.pkg.api.authz import Permission
from langbot.pkg.api.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext


def test_runner_no_longer_accepts_workspace_grants():
    with pytest.raises(ValidationError):
        RunnerPermissions(workspace_operations=['bot.list'])
    assert 'workspace_operations' not in RunnerDescriptor.model_fields


def test_local_agent_declares_at_plugin_level():
    root = Path(__file__).resolve().parents[3]
    manifest = yaml.safe_load((root / 'plugins/Runner/LocalAgent/manifest.yaml').read_text())
    declaration = read_declaration(manifest)
    assert 'stats.basic' in declaration['workspace_operations']
    assert 'models.invoke' in declaration['capabilities']


@pytest.mark.asyncio
async def test_resource_selection_is_intersected_with_installation_grants(monkeypatch):
    from langbot.pkg.api.application import plugin_permissions

    context = RequestContext(
        'instance',
        1,
        'request',
        'plugin',
        PrincipalContext(PrincipalType.PLUGIN),
        WorkspaceContext('workspace', None, None, frozenset({Permission.RESOURCE_VIEW})),
        allowed_operation_ids=frozenset({'bot.list'}),
    )
    monkeypatch.setattr(plugin_permissions, 'installation_context', AsyncMock(return_value=context))
    connector = SimpleNamespace(
        require_workspace_context=AsyncMock(),
        _setting_for_plugin=AsyncMock(return_value=(None, object())),
        _binding_from_setting=lambda *args: object(),
    )
    operations = {
        name: Operation(name, Permission.RESOURCE_VIEW, AsyncMock(), Input, dict)
        for name in ['bot.list', 'stats.basic']
    }
    app = SimpleNamespace(plugin_connector=connector, application_api=SimpleNamespace(_operations=operations))
    builder = AgentResourceBuilder(app)
    descriptor = SimpleNamespace(plugin_author='author', plugin_name='plugin')
    binding = SimpleNamespace(resource_policy=SimpleNamespace(allowed_workspace_operations=['bot.list', 'stats.basic']))
    result = await builder._build_workspace_operations_from_binding(
        context, SimpleNamespace(event_id='event'), binding, descriptor
    )
    assert [operation['id'] for operation in result] == ['bot.list']
    binding.resource_policy.allowed_workspace_operations = []
    assert (
        await builder._build_workspace_operations_from_binding(
            context, SimpleNamespace(event_id='event'), binding, descriptor
        )
        == []
    )
