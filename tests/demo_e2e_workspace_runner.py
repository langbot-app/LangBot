"""Reproducible end-to-end verification script for runner workspace operations.

Demonstrates:
1. Loading manifest permissions via RunnerRegistry._validate_and_build_descriptor
2. Default operations resolution via get_default_workspace_operations
3. Runtime resource building via AgentResourceBuilder with resolve_authorized_workspace_operations
4. Listing operations via execution.list_application_operations
5. Invoking operation via execution.call_application_operation (bot.list)
6. Recording audit logs
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import yaml

# Ensure new SDK from repo is in sys.path
sdk_src = str(Path(__file__).resolve().parents[2] / 'langbot-plugin-sdk' / 'src')
if sdk_src not in sys.path:
    sys.path.insert(0, sdk_src)

from langbot_plugin.api.entities.builtin.runner.manifest import RunnerPermissions  # noqa: E402
from langbot_plugin.entities.io.context import InstallationBinding  # noqa: E402

from langbot.pkg.agent.runner.host_models import AgentBinding, AgentEventEnvelope, ResourcePolicy  # noqa: E402
from langbot.pkg.agent.runner.registry import RunnerRegistry  # noqa: E402
from langbot.pkg.agent.runner.resource_builder import AgentResourceBuilder  # noqa: E402
from langbot.pkg.agent.runner.session_registry import get_session_registry  # noqa: E402
from langbot.pkg.api.application.api import ApplicationAPI  # noqa: E402
from langbot.pkg.api.application.execution import ExecutionAPIContext  # noqa: E402
from langbot.pkg.api.application.tool_grants import get_default_workspace_operations  # noqa: E402
from langbot.pkg.api.http.context import ExecutionContext  # noqa: E402
from langbot.pkg.plugin.handler import RuntimeConnectionHandler  # noqa: E402


async def run_demo():
    print('======================================================================')
    print('LANG-232 端到端全链路运行验证 (E2E Workspace Operations Execution)')
    print('======================================================================\n')

    # Step 1: Manifest Reading via Registry
    print('--- Step 1: 清单声明读取 (RunnerRegistry._validate_and_build_descriptor) ---')
    manifest_yaml_path = (
        Path(__file__).resolve().parents[2]
        / 'langbot-plugin-sdk'
        / 'examples'
        / 'workspace_runner_plugin'
        / 'components'
        / 'runner'
        / 'default.yaml'
    )
    with open(manifest_yaml_path, 'r', encoding='utf-8') as f:
        comp_yaml = yaml.safe_load(f)

    print(
        f'SDK RunnerPermissions.model_fields has workspace_operations: {"workspace_operations" in RunnerPermissions.model_fields}'
    )

    registry = RunnerRegistry(Mock())
    raw_runner_data = {
        'plugin_author': 'LangBot',
        'plugin_name': 'WorkspaceRunnerExample',
        'runner_name': 'default',
        'manifest': {
            'id': comp_yaml['metadata']['name'],
            'name': comp_yaml['metadata']['name'],
            'component_kind': comp_yaml['kind'],
            'usages': comp_yaml['spec']['usages'],
            'label': comp_yaml['metadata']['label'],
            'description': comp_yaml['metadata']['description'],
            'permissions': comp_yaml['spec']['permissions'],
            'config_schema': comp_yaml['spec']['config'],
        },
    }

    descriptor = registry._validate_and_build_descriptor(raw_runner_data)
    assert descriptor is not None
    declared = descriptor.declared_workspace_operations()
    print(f'Runner ID: {descriptor.id}')
    print(f'Declared workspace_operations: {declared}')
    assert declared == ['bot.list', 'stats.basic']

    # Step 2: Default Selection
    print('\n--- Step 2: 默认勾选范围 (get_default_workspace_operations) ---')
    app_dummy = SimpleNamespace(application_api=None)
    defaults = get_default_workspace_operations(app_dummy, declared)
    print(f'Default selected (declared ∩ exposure == "all"): {defaults}')
    assert defaults == ['bot.list', 'stats.basic']

    # Step 3: Runtime Binding & Resource Building
    print('\n--- Step 3: 运行时交集授权与资源构建 (AgentResourceBuilder) ---')
    binding = InstallationBinding(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=1,
        installation_uuid='00000000-0000-4000-8000-000000000001',
        runtime_revision=1,
        artifact_digest='a' * 64,
    )
    recorded_audits = []

    async def record_audit(workspace_uuid, **kwargs):
        recorded_audits.append({'workspace_uuid': workspace_uuid, **kwargs})

    @asynccontextmanager
    async def tenant_scope(workspace):
        yield

    host = SimpleNamespace(
        logger=Mock(),
        workspace_service=SimpleNamespace(get_execution_binding=AsyncMock(return_value=binding)),
        persistence_mgr=SimpleNamespace(tenant_scope=tenant_scope),
        workspace_settings_service=SimpleNamespace(
            effective_level=AsyncMock(return_value=2),
            record=AsyncMock(side_effect=record_audit),
        ),
        bot_service=SimpleNamespace(
            get_bots=AsyncMock(return_value=[{'bot_uuid': 'bot-test-01', 'name': 'Demo Assistant Bot'}])
        ),
        recorded_audits=recorded_audits,
        skill_mgr=None,
    )
    host.application_api = ApplicationAPI(host)

    handler = RuntimeConnectionHandler(Mock(), AsyncMock(return_value=True), host)
    handler.register_installation_binding(binding, plugin_author='LangBot', plugin_name='WorkspaceRunnerExample')
    handler._current_action_context.set(binding)
    host.plugin_connector = SimpleNamespace(handler=handler)
    exec_api = handler.execution_api

    run_id = 'run-demo-e2e-232'
    event = AgentEventEnvelope.model_validate(
        {
            'event_id': run_id,
            'event_type': 'message.received',
            'source': 'webui',
            'workspace_id': 'workspace-a',
            'input': {'text': 'list bots', 'contents': [{'type': 'text', 'text': 'list bots'}]},
            'delivery': {'surface': 'webui'},
        }
    )

    # Suppose user configured declared ops + extra un-declared op ('audit.log.list')
    configured_by_user = ['bot.list', 'stats.basic', 'audit.log.list']
    agent_binding = AgentBinding(
        binding_id='bind-demo',
        runner_id=descriptor.id,
        processor_type='agent',
        processor_id='agent-demo-001',
        resource_policy=ResourcePolicy(allowed_workspace_operations=configured_by_user),
    )
    ctx = ExecutionContext(instance_uuid='instance-a', workspace_uuid='workspace-a', placement_generation=1)
    builder = AgentResourceBuilder(host)
    resources = await builder.build_resources_from_binding(ctx, event, agent_binding, descriptor)

    granted_ids = [item['id'] for item in resources.get('workspace_operations', [])]
    print(f'Configured: {configured_by_user}')
    print(f'Runtime Granted (configured ∩ declared): {granted_ids}')
    assert granted_ids == ['bot.list', 'stats.basic']

    # Step 4: Register Run Session
    registry_session = get_session_registry()
    await registry_session.register(
        run_id=run_id,
        runner_id=descriptor.id,
        query_id=None,
        plugin_identity=descriptor.get_plugin_id(),
        resources=resources,
        workspace_id='workspace-a',
        processor_type='agent',
        processor_id='agent-demo-001',
    )
    exec_context = ExecutionAPIContext(binding=binding, run_id=run_id)

    # Step 5: Execution API list_application_operations
    print('\n--- Step 4: api.workspace.list() 调用 ---')
    list_res = await exec_api.invoke('execution.list_application_operations', exec_context, {})
    ops = [op['id'] for op in list_res.get('operations', [])]
    print(f'Returned operations count: {len(ops)}')
    print(f'Operations: {ops}')
    assert set(ops) == {'bot.list', 'stats.basic'}

    # Step 6: Execution API call_application_operation
    print('\n--- Step 5: api.workspace.call("bot.list") 调用 ---')
    call_res = await exec_api.invoke(
        'execution.call_application_operation',
        exec_context,
        {'operation_id': 'bot.list', 'arguments': {}},
    )
    print(f'Call response ok: {call_res.get("ok")}')
    print(f'Call result data: {call_res.get("result")}')
    assert call_res.get('ok') is True
    assert isinstance(call_res.get('result'), list)
    assert len(call_res.get('result', [])) == 1

    # Step 7: Audit Logging
    print('\n--- Step 6: 审计记录 (Audit Records) ---')
    print(f'Recorded audit count: {len(recorded_audits)}')
    for idx, item in enumerate(recorded_audits, 1):
        print(
            f'  [{idx}] workspace: {item.get("workspace_uuid")}, route: {item.get("route")}, status: {item.get("status")}'
        )
    assert len(recorded_audits) >= 1
    assert recorded_audits[-1]['route'] == 'bot.list'

    print('\n======================================================================')
    print('端到端全链路运行成功验证完成！')
    print('======================================================================')


if __name__ == '__main__':
    asyncio.run(run_demo())
