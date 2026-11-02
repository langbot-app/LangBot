"""End-to-end integration test verifying workspace_runner_plugin build,

manifest contract, real SQLite persistence, default authorization as an
event processor, and execution/revocation lifecycle.
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import sqlalchemy
import yaml

# Resolve SDK path
sdk_env = os.environ.get('LANGBOT_PLUGIN_SDK_PATH')
if sdk_env:
    sdk_candidate = Path(sdk_env).resolve()
    sdk_root = sdk_candidate if (sdk_candidate / 'examples').is_dir() else sdk_candidate.parent
    sdk_src = sdk_candidate / 'src' if (sdk_candidate / 'src').is_dir() else sdk_candidate
else:
    sdk_root = Path(__file__).resolve().parents[4] / 'langbot-plugin-sdk'
    sdk_src = sdk_root / 'src'

if not sdk_src.exists():
    pytest.skip(
        f'langbot-plugin-sdk not found at {sdk_src} (set LANGBOT_PLUGIN_SDK_PATH to override)', allow_module_level=True
    )

sdk_src_str = str(sdk_src)
if sdk_src_str not in sys.path:
    sys.path.insert(0, sdk_src_str)

from langbot_plugin.api.entities.builtin.runner.manifest import RunnerPermissions  # noqa: E402

if 'workspace_operations' not in getattr(RunnerPermissions, 'model_fields', {}):
    pytest.skip(
        'New SDK with workspace_operations not installed in current environment (run `uv pip install -e ../langbot-plugin-sdk`)',
        allow_module_level=True,
    )

from langbot_plugin.cli.commands import buildplugin  # noqa: E402
from langbot_plugin.entities.io.context import InstallationBinding  # noqa: E402

from langbot.pkg.agent.runner.host_models import AgentBinding, AgentEventEnvelope, ResourcePolicy  # noqa: E402
from langbot.pkg.agent.runner.registry import RunnerRegistry  # noqa: E402
from langbot.pkg.agent.runner.resource_builder import AgentResourceBuilder  # noqa: E402
from langbot.pkg.agent.runner.session_registry import get_session_registry  # noqa: E402
from langbot.pkg.api.application.api import ApplicationAPI  # noqa: E402
from langbot.pkg.api.application.execution import ExecutionAPIContext  # noqa: E402
from langbot.pkg.api.http.context import ExecutionContext  # noqa: E402
from langbot.pkg.api.http.service.agent import AgentService  # noqa: E402
from langbot.pkg.api.http.service.bot import BotService  # noqa: E402
from langbot.pkg.entity.persistence import bot as persistence_bot  # noqa: E402
from langbot.pkg.persistence.mgr import PersistenceManager  # noqa: E402
from langbot.pkg.plugin.handler import RuntimeConnectionHandler  # noqa: E402


def test_example_runner_manifest_and_build(tmp_path, monkeypatch):
    """Verify workspace_runner_plugin contains spec.events, passes lbp build, and outputs valid archive."""
    plugin_dir = sdk_root / 'examples' / 'workspace_runner_plugin'
    assert plugin_dir.is_dir(), f'Example plugin directory not found at {plugin_dir}'

    comp_yaml_path = plugin_dir / 'components' / 'runner' / 'default.yaml'
    assert comp_yaml_path.is_file(), f'Runner component not found at {comp_yaml_path}'

    with open(comp_yaml_path, 'r', encoding='utf-8') as f:
        comp_yaml = yaml.safe_load(f)

    # 1. Manifest contract assertions
    spec = comp_yaml.get('spec', {})
    assert 'event' in spec.get('usages', []), 'usages must declare event'
    assert 'agent' in spec.get('usages', []), 'usages must declare agent'
    assert spec.get('events') == ['*'], 'spec.events must be explicitly declared for event usage'
    assert 'workspace_operations' in spec.get('permissions', {}), 'permissions must declare workspace_operations'
    assert set(spec['permissions']['workspace_operations']) == {'bot.list', 'stats.basic'}

    # 2. lbp build assertion
    monkeypatch.chdir(plugin_dir)
    monkeypatch.setattr(buildplugin, 'cli_print', lambda *args, **kwargs: None)
    dist_dir = tmp_path / 'dist'
    pkg_path = buildplugin.build_plugin_process(str(dist_dir))
    assert pkg_path is not None, 'Plugin build must succeed'
    assert pkg_path.endswith('.lbpkg')
    assert Path(pkg_path).is_file()

    with zipfile.ZipFile(pkg_path) as pkg:
        names = set(pkg.namelist())
        assert 'manifest.yaml' in names
        assert 'components/runner/default.yaml' in names
        assert 'components/runner/default.py' in names


@pytest.mark.asyncio
async def test_workspace_runner_real_sqlite_event_processor_lifecycle(tmp_path, monkeypatch):
    """Verify installing example runner into real Core + SQLite as an event processor:

    - Default authorization check takes effect on creation
    - api.workspace.list() and api.workspace.call('bot.list') succeed
    - Revoking authorization results in call rejection
    """
    comp_yaml_path = sdk_root / 'examples' / 'workspace_runner_plugin' / 'components' / 'runner' / 'default.yaml'
    with open(comp_yaml_path, 'r', encoding='utf-8') as f:
        comp_yaml = yaml.safe_load(f)

    # 1. Set up real Core + SQLite Persistence
    from langbot.pkg.utils import constants

    monkeypatch.setattr(constants, 'instance_id', 'test-instance-uuid')

    db_path = tmp_path / 'langbot_e2e.db'
    app = SimpleNamespace(
        logger=logging.getLogger('test-e2e-runner'),
        instance_config=SimpleNamespace(
            data={
                'database': {
                    'use': 'sqlite',
                    'sqlite': {'path': str(db_path)},
                },
                'system': {
                    'jwt': {'secret': 'test-secret', 'expire': 3600},
                    'allow_modify_login_info': True,
                    'limitation': {},
                    'outbound_ips': [],
                },
                'api': {'global_api_key': ''},
                'plugin': {'enable_marketplace': True},
                'space': {
                    'url': 'https://space.langbot.app',
                    'models_gateway_api_url': 'https://api.langbot.cloud/v1',
                    'disable_models_service': False,
                },
                'mcp': {'stdio': {'enabled': True}},
            }
        ),
    )

    persistence = PersistenceManager(app)
    app.persistence_mgr = persistence
    await persistence.initialize()

    try:
        # 2. Build Descriptor from example manifest
        registry = RunnerRegistry(app)
        app.runner_registry = registry

        raw_runner_data = {
            'plugin_author': 'LangBot',
            'plugin_name': 'WorkspaceRunnerExample',
            'runner_name': 'default',
            'manifest': {
                'id': comp_yaml['metadata']['name'],
                'name': comp_yaml['metadata']['name'],
                'component_kind': comp_yaml['kind'],
                'usages': comp_yaml['spec']['usages'],
                'supported_event_patterns': comp_yaml['spec'].get('events') or ['*'],
                'label': comp_yaml['metadata']['label'],
                'description': comp_yaml['metadata']['description'],
                'permissions': comp_yaml['spec']['permissions'],
                'config_schema': comp_yaml['spec']['config'],
            },
        }
        descriptor = registry._validate_and_build_descriptor(raw_runner_data)
        assert descriptor is not None
        assert descriptor.id == 'plugin:LangBot/WorkspaceRunnerExample/default'
        assert descriptor.declared_workspace_operations() == ['bot.list', 'stats.basic']

        # Mock registry.get to return this descriptor when agent service queries it
        registry.get = AsyncMock(return_value=descriptor)

        # 3. Retrieve default Workspace created by persistence.initialize()
        from langbot.pkg.entity.persistence import workspace as persistence_workspace

        ws_res = await persistence.execute_async(sqlalchemy.select(persistence_workspace.Workspace))
        workspace = ws_res.scalar_one()
        workspace_uuid = getattr(workspace, 'uuid', workspace)

        app.application_api = ApplicationAPI(app)

        recorded_audits = []

        async def record_audit(ws_uuid, **kwargs):
            recorded_audits.append({'workspace_uuid': ws_uuid, **kwargs})

        app.workspace_settings_service = SimpleNamespace(
            effective_level=AsyncMock(return_value=2),
            record=AsyncMock(side_effect=record_audit),
        )
        app.llm_model_service = SimpleNamespace(
            apply_default_model=AsyncMock(side_effect=lambda ctx, schema, params: params)
        )
        app.pipeline_service = SimpleNamespace(_get_default_values_from_schema=Mock(return_value={}))

        bot_service = BotService(app)
        app.bot_service = bot_service

        agent_service = AgentService(app)
        app.agent_service = agent_service

        # Create a bot in the real SQLite database
        bot_uuid = str(uuid.uuid4())
        await persistence.execute_async(
            sqlalchemy.insert(persistence_bot.Bot).values(
                uuid=bot_uuid,
                workspace_uuid=workspace_uuid,
                name='E2E Test Assistant Bot',
                adapter='test_adapter',
                adapter_config={},
                enable=True,
                event_bindings=[],
                plugin_processors=[],
                description='Test Bot in SQLite',
            )
        )

        # 4. Create event processor using the example plugin runner with owner permissions
        from langbot.pkg.api.authz import WorkspaceRole, permissions_for_role
        from langbot.pkg.api.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext

        ws_ctx = WorkspaceContext(
            workspace_uuid=workspace_uuid,
            membership_uuid=str(uuid.uuid4()),
            role=WorkspaceRole.OWNER.value,
            permissions=permissions_for_role(WorkspaceRole.OWNER),
        )
        editor_context = RequestContext(
            instance_uuid='test-instance-uuid',
            placement_generation=1,
            request_id='req-e2e',
            auth_type='session',
            principal=PrincipalContext(principal_type=PrincipalType.ACCOUNT, account_uuid='owner-user'),
            workspace=ws_ctx,
        )

        created = await agent_service.create_agent(
            editor_context,
            {
                'name': 'E2E Workspace Event Processor',
                'kind': 'event_processor',
                'component_ref': descriptor.id,
                'parameters': {},
            },
        )
        agent_uuid = created['uuid']
        agent_info = await agent_service.get_agent(workspace_uuid, agent_uuid)

        assert agent_info['component_ref'] == descriptor.id
        config = agent_info['config']
        assert 'allowed_workspace_operations' in config
        assert set(config['allowed_workspace_operations']) == {'bot.list', 'stats.basic'}

        # 5. Runtime binding & ExecutionAPI setup
        binding = InstallationBinding(
            instance_uuid='instance-e2e',
            workspace_uuid=workspace_uuid,
            placement_generation=1,
            installation_uuid=str(uuid.uuid4()),
            runtime_revision=1,
            artifact_digest='e' * 64,
        )
        app.workspace_service = SimpleNamespace(get_execution_binding=AsyncMock(return_value=binding))

        handler = RuntimeConnectionHandler(Mock(), AsyncMock(return_value=True), app)
        handler.register_installation_binding(binding, plugin_author='LangBot', plugin_name='WorkspaceRunnerExample')
        handler._current_action_context.set(binding)
        app.plugin_connector = SimpleNamespace(handler=handler)
        exec_api = handler.execution_api

        # 6. Test with default granted operations
        run_id_granted = 'run-e2e-granted'
        event = AgentEventEnvelope.model_validate(
            {
                'event_id': run_id_granted,
                'event_type': 'message.received',
                'source': 'webui',
                'workspace_id': workspace_uuid,
                'input': {'text': 'test', 'contents': [{'type': 'text', 'text': 'test'}]},
                'delivery': {'surface': 'webui'},
            }
        )

        agent_binding_granted = AgentBinding(
            binding_id='bind-e2e',
            runner_id=descriptor.id,
            processor_type='agent',
            processor_id=agent_uuid,
            resource_policy=ResourcePolicy(allowed_workspace_operations=config['allowed_workspace_operations']),
        )

        exec_ctx = ExecutionContext(instance_uuid='instance-e2e', workspace_uuid=workspace_uuid, placement_generation=1)
        builder = AgentResourceBuilder(app)
        resources_granted = await builder.build_resources_from_binding(
            exec_ctx, event, agent_binding_granted, descriptor
        )

        granted_ops = [item['id'] for item in resources_granted.get('workspace_operations', [])]
        assert set(granted_ops) == {'bot.list', 'stats.basic'}

        session_reg = get_session_registry()
        await session_reg.register(
            run_id=run_id_granted,
            runner_id=descriptor.id,
            query_id=None,
            plugin_identity=descriptor.get_plugin_id(),
            resources=resources_granted,
            workspace_id=workspace_uuid,
            processor_type='agent',
            processor_id=agent_uuid,
        )

        call_ctx_granted = ExecutionAPIContext(binding=binding, run_id=run_id_granted)

        # 6a. list_application_operations
        list_res = await exec_api.invoke('execution.list_application_operations', call_ctx_granted, {})
        listed_ids = [op['id'] for op in list_res.get('operations', [])]
        assert set(listed_ids) == {'bot.list', 'stats.basic'}

        # 6b. call_application_operation('bot.list')
        call_res = await exec_api.invoke(
            'execution.call_application_operation',
            call_ctx_granted,
            {'operation_id': 'bot.list', 'arguments': {}},
        )
        assert call_res.get('ok') is True
        bots_returned = call_res.get('result', [])
        assert any(b['uuid'] == bot_uuid for b in bots_returned)

        # 7. Revoke authorization: update agent in SQLite to clear allowed_workspace_operations
        await agent_service.update_agent(
            editor_context,
            agent_uuid,
            {
                'config': {
                    **config,
                    'allowed_workspace_operations': [],
                }
            },
        )

        updated_agent = await agent_service.get_agent(workspace_uuid, agent_uuid)
        assert updated_agent['config']['allowed_workspace_operations'] == []

        # 8. Test execution after revocation
        run_id_revoked = 'run-e2e-revoked'
        agent_binding_revoked = AgentBinding(
            binding_id='bind-e2e',
            runner_id=descriptor.id,
            processor_type='agent',
            processor_id=agent_uuid,
            resource_policy=ResourcePolicy(allowed_workspace_operations=[]),
        )
        resources_revoked = await builder.build_resources_from_binding(
            exec_ctx, event, agent_binding_revoked, descriptor
        )
        assert resources_revoked.get('workspace_operations', []) == []

        await session_reg.register(
            run_id=run_id_revoked,
            runner_id=descriptor.id,
            query_id=None,
            plugin_identity=descriptor.get_plugin_id(),
            resources=resources_revoked,
            workspace_id=workspace_uuid,
            processor_type='agent',
            processor_id=agent_uuid,
        )

        call_ctx_revoked = ExecutionAPIContext(binding=binding, run_id=run_id_revoked)

        # 8a. list_application_operations returns empty
        list_revoked_res = await exec_api.invoke('execution.list_application_operations', call_ctx_revoked, {})
        assert list_revoked_res.get('operations', []) == []

        # 8b. call_application_operation('bot.list') is rejected
        call_revoked_res = await exec_api.invoke(
            'execution.call_application_operation',
            call_ctx_revoked,
            {'operation_id': 'bot.list', 'arguments': {}},
        )
        assert call_revoked_res.get('ok') is False
        assert call_revoked_res.get('error', {}).get('code') == 'not_found'
    finally:
        await persistence.get_db_engine().dispose()
