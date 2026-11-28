"""Unit tests for runner workspace operations delivery and ExecutionAPI list/call."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langbot_plugin.entities.io.context import InstallationBinding

from langbot.pkg.agent.runner.descriptor import RunnerDescriptor
from langbot.pkg.agent.runner.host_models import AgentBinding, AgentEventEnvelope, ResourcePolicy
from langbot.pkg.agent.runner.resource_builder import AgentResourceBuilder
from langbot.pkg.agent.runner.session_registry import get_session_registry
from langbot.pkg.api.application.api import ApplicationAPI
from langbot.pkg.api.application.contracts import ApplicationAPIException, Input
from langbot.pkg.api.application.execution import ExecutionAPIContext
from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.entity.persistence.plugin import PluginSetting
from langbot.pkg.plugin.handler import RuntimeConnectionHandler


class DummyListOutput(Input):
    pass


@pytest.fixture
def test_env(monkeypatch):
    monkeypatch.setattr('langbot.pkg.api.application.api.get_workspace_language', AsyncMock(return_value='en_US'))

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

    from contextlib import asynccontextmanager

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
        bot_service=SimpleNamespace(get_bots=AsyncMock(return_value=[{'bot_uuid': 'bot-1', 'name': 'Test Bot'}])),
        recorded_audits=recorded_audits,
    )
    api = ApplicationAPI(host)
    host.application_api = api
    setting = PluginSetting(
        workspace_uuid=binding.workspace_uuid,
        installation_uuid=binding.installation_uuid,
        runtime_revision=binding.runtime_revision,
        artifact_digest=binding.artifact_digest,
        plugin_author='langbot-team',
        plugin_name='LocalAgent',
        enabled=True,
        permission_declaration={'workspace_operations': ['bot.list'], 'capabilities': []},
        permission_grants={'workspace_operations': ['bot.list'], 'capabilities': []},
        permission_snapshot={'workspace_operations': ['bot.list'], 'capabilities': []},
    )
    host.persistence_mgr.execute_async = AsyncMock(return_value=Mock(first=Mock(return_value=(setting,))))
    host.workspace_settings_service.get_configured_level = AsyncMock(return_value=2)

    handler = RuntimeConnectionHandler(Mock(), AsyncMock(return_value=True), host)
    handler.register_installation_binding(binding, plugin_author='langbot-team', plugin_name='LocalAgent')
    handler._current_action_context.set(binding)
    host.plugin_connector = SimpleNamespace(
        handler=handler,
        require_workspace_context=AsyncMock(),
        _setting_for_plugin=AsyncMock(return_value=(handler._execution_context(binding), setting)),
        _binding_from_setting=Mock(return_value=binding),
    )
    exec_api = handler.execution_api

    return SimpleNamespace(
        host=host,
        handler=handler,
        binding=binding,
        exec_api=exec_api,
        recorded_audits=recorded_audits,
        setting=setting,
    )


def make_local_agent_descriptor() -> RunnerDescriptor:
    return RunnerDescriptor.model_validate(
        {
            'id': 'plugin:langbot-team/LocalAgent/default',
            'source': 'plugin',
            'plugin_author': 'langbot-team',
            'plugin_name': 'LocalAgent',
            'runner_name': 'default',
            'label': {'en_US': 'Local Agent'},
            'usages': ['agent'],
            'permissions': {
                'models': ['invoke'],
                'tools': ['detail', 'call'],
            },
        }
    )


def make_external_runner_descriptor(declares_ws_ops: bool = False) -> RunnerDescriptor:
    data = {
        'id': 'plugin:custom-author/custom-runner/default',
        'source': 'plugin',
        'plugin_author': 'custom-author',
        'plugin_name': 'custom-runner',
        'runner_name': 'default',
        'label': {'en_US': 'Custom Runner'},
        'usages': ['agent'],
        'permissions': {
            'models': ['invoke'],
            'tools': ['detail', 'call'],
        },
        'raw_manifest': {
            'permissions': {
                'workspace_operations': ['bot.list'] if declares_ws_ops else [],
            }
        },
    }
    return RunnerDescriptor.model_validate(data)


def make_event(event_id: str = 'event-1', workspace_id: str = 'workspace-a') -> AgentEventEnvelope:
    return AgentEventEnvelope.model_validate(
        {
            'event_id': event_id,
            'event_type': 'message.received',
            'source': 'webui',
            'workspace_id': workspace_id,
            'input': {'text': 'hello', 'contents': [{'type': 'text', 'text': 'hello'}]},
            'delivery': {'surface': 'webui'},
        }
    )


# 1. 授权集合为空时，资源中没有 workspace_operations，或者是空列表
@pytest.mark.asyncio
async def test_empty_grants_workspace_operations_resource(test_env):
    builder = AgentResourceBuilder(test_env.host)
    event = make_event()
    binding = AgentBinding(
        binding_id='bind-1',
        runner_id='plugin:langbot-team/LocalAgent/default',
        processor_type='agent',
        processor_id='agent-1',
        resource_policy=ResourcePolicy(allowed_workspace_operations=[]),
    )
    descriptor = make_local_agent_descriptor()
    ctx = ExecutionContext(instance_uuid='instance-a', workspace_uuid='workspace-a', placement_generation=1)

    resources = await builder.build_resources_from_binding(
        ctx,
        event,
        binding,
        descriptor,
    )

    # LocalAgent qualifies, so it receives an empty list when allowed operations is empty
    assert 'workspace_operations' in resources
    assert resources['workspace_operations'] == []

    non_declaring = make_external_runner_descriptor(declares_ws_ops=False)
    resources_external = await builder.build_resources_from_binding(
        ctx,
        event,
        binding,
        non_declaring,
    )
    assert resources_external['workspace_operations'] == []


# 2. 勾选 3 个操作时，list 恰好返回这 3 个，并带完整 schema
@pytest.mark.asyncio
async def test_list_application_operations_returns_exact_three_with_full_schema(test_env):
    run_id = 'run-exact-3'
    ops_to_grant = ['bot.list', 'bot.create', 'adapter.list']
    test_env.setting.permission_declaration['workspace_operations'] = ops_to_grant
    test_env.setting.permission_grants['workspace_operations'] = ops_to_grant

    builder = AgentResourceBuilder(test_env.host)
    event = make_event(event_id=run_id)
    binding = AgentBinding(
        binding_id='bind-1',
        runner_id='plugin:langbot-team/LocalAgent/default',
        processor_type='agent',
        processor_id='agent-1',
        resource_policy=ResourcePolicy(allowed_workspace_operations=ops_to_grant),
    )
    descriptor = make_local_agent_descriptor()
    ctx = ExecutionContext(instance_uuid='instance-a', workspace_uuid='workspace-a', placement_generation=1)

    resources = await builder.build_resources_from_binding(ctx, event, binding, descriptor)
    assert 'workspace_operations' in resources
    assert len(resources['workspace_operations']) == 3

    # Register session
    registry = get_session_registry()
    await registry.register(
        run_id=run_id,
        runner_id=descriptor.id,
        query_id=None,
        plugin_identity=descriptor.get_plugin_id(),
        resources=resources,
        workspace_id='workspace-a',
        processor_type='agent',
        processor_id='agent-1',
    )

    exec_context = ExecutionAPIContext(
        binding=test_env.binding,
        run_id=run_id,
        claimed_identity='langbot-team/LocalAgent',
    )

    result = await test_env.exec_api.invoke('execution.list_application_operations', exec_context, {})
    assert 'operations' in result
    assert 'domains' in result

    ops = result['operations']
    assert len(ops) == 3
    op_ids = {op['id'] for op in ops}
    assert op_ids == set(ops_to_grant)

    # Verify full schema in each operation
    for op in ops:
        assert isinstance(op['id'], str)
        assert isinstance(op['domain'], str)
        assert isinstance(op['label'], dict)
        assert isinstance(op['summary'], str)
        assert isinstance(op['input_schema'], dict)
        assert isinstance(op['output_schema'], dict)
        assert op['risk'] in ('read', 'write', 'dangerous')
        assert isinstance(op['side_effect'], bool)

    # Verify domains summary
    domain_names = {d['domain'] for d in result['domains']}
    assert domain_names == {'bot', 'adapter'}


@pytest.mark.asyncio
async def test_call_application_operation_success_and_audit(test_env):
    run_id = 'run-call-auth-1'
    ops_to_grant = ['bot.list']

    builder = AgentResourceBuilder(test_env.host)
    event = make_event(event_id=run_id)
    binding = AgentBinding(
        binding_id='bind-1',
        runner_id='plugin:langbot-team/LocalAgent/default',
        processor_type='agent',
        processor_id='agent-uuid-999',
        resource_policy=ResourcePolicy(allowed_workspace_operations=ops_to_grant),
    )
    descriptor = make_local_agent_descriptor()
    ctx = ExecutionContext(instance_uuid='instance-a', workspace_uuid='workspace-a', placement_generation=1)

    resources = await builder.build_resources_from_binding(ctx, event, binding, descriptor)

    registry = get_session_registry()
    await registry.register(
        run_id=run_id,
        runner_id=descriptor.id,
        query_id=None,
        plugin_identity=descriptor.get_plugin_id(),
        resources=resources,
        workspace_id='workspace-a',
        processor_type='agent',
        processor_id='agent-uuid-999',
    )

    exec_context = ExecutionAPIContext(
        binding=test_env.binding,
        run_id=run_id,
        claimed_identity='langbot-team/LocalAgent',
    )

    # 1. 资源下发 (Delivery)
    assert 'workspace_operations' in resources
    assert len(resources['workspace_operations']) == 1
    ops_ids = [op['id'] for op in resources['workspace_operations']]
    print(f'\n[CHAIN] 1. 资源下发 -> operations: {ops_ids}')

    # 2. 列出授权操作 (List)
    list_result = await test_env.exec_api.invoke(
        'execution.list_application_operations',
        exec_context,
        {},
    )
    assert len(list_result['operations']) == 1
    assert list_result['operations'][0]['id'] == 'bot.list'
    print(
        f'[CHAIN] 2. list_application_operations -> '
        f'operations: {[op["id"] for op in list_result["operations"]]}, domains: {list_result["domains"]}'
    )

    # 3. 调用授权操作 (Call)
    call_result = await test_env.exec_api.invoke(
        'execution.call_application_operation',
        exec_context,
        {'operation_id': 'bot.list', 'arguments': {}},
    )
    assert call_result['ok'] is True
    assert isinstance(call_result['result'], list)
    print(f'[CHAIN] 3. call_application_operation -> ok: {call_result["ok"]}, result: {call_result["result"]}')

    # 4. 审计记录验证 (Audit Record)
    assert len(test_env.recorded_audits) > 0
    audit = next(record for record in test_env.recorded_audits if record['route'] == 'bot.list')
    assert audit['route'] == 'bot.list'
    assert audit['principal_type'] == 'plugin'
    assert audit['detail']['installation_uuid'] == test_env.binding.installation_uuid
    assert audit['detail']['run_id'] == run_id


@pytest.mark.asyncio
async def test_call_application_operation_unauthorized_returns_permission_denied(test_env):
    run_id = 'run-call-unauth'
    ops_to_grant = ['bot.list']

    builder = AgentResourceBuilder(test_env.host)
    event = make_event(event_id=run_id)
    binding = AgentBinding(
        binding_id='bind-1',
        runner_id='plugin:langbot-team/LocalAgent/default',
        processor_type='agent',
        processor_id='agent-uuid-999',
        resource_policy=ResourcePolicy(allowed_workspace_operations=ops_to_grant),
    )
    descriptor = make_local_agent_descriptor()
    ctx = ExecutionContext(instance_uuid='instance-a', workspace_uuid='workspace-a', placement_generation=1)

    resources = await builder.build_resources_from_binding(ctx, event, binding, descriptor)

    registry = get_session_registry()
    await registry.register(
        run_id=run_id,
        runner_id=descriptor.id,
        query_id=None,
        plugin_identity=descriptor.get_plugin_id(),
        resources=resources,
        workspace_id='workspace-a',
        processor_type='agent',
        processor_id='agent-uuid-999',
    )

    exec_context = ExecutionAPIContext(
        binding=test_env.binding,
        run_id=run_id,
        claimed_identity='langbot-team/LocalAgent',
    )

    # Attempt to call 'bot.delete' which is NOT in granted list
    with pytest.raises(ApplicationAPIException) as error:
        await test_env.exec_api.invoke(
            'execution.call_application_operation',
            exec_context,
            {'operation_id': 'bot.delete', 'arguments': {'bot_uuid': 'b-1'}},
        )
    assert error.value.error.code == 'permission_denied'
    assert error.value.error.details == {'denied_operations': ['bot.delete']}


@pytest.mark.asyncio
async def test_installation_grants_allow_calls_without_run(test_env):
    exec_context_outside_run = ExecutionAPIContext(
        binding=test_env.binding,
        run_id=None,
        claimed_identity='langbot-team/LocalAgent',
    )

    listed = await test_env.exec_api.invoke('execution.list_application_operations', exec_context_outside_run, {})
    assert [operation['id'] for operation in listed['operations']] == ['bot.list']
    result = await test_env.exec_api.invoke(
        'execution.call_application_operation',
        exec_context_outside_run,
        {'operation_id': 'bot.list', 'arguments': {}},
    )
    assert result['ok'] is True


# 6. 跨工作区的 run 被拒绝（覆盖 ExecutionAPI 与 SDK handler actions 两种路径）
@pytest.mark.asyncio
async def test_cross_workspace_run_is_rejected(test_env):
    run_id = 'run-cross-ws'
    registry = get_session_registry()
    await registry.register(
        run_id=run_id,
        runner_id='plugin:langbot-team/LocalAgent/default',
        query_id=None,
        plugin_identity='langbot-team/LocalAgent',
        resources={
            'models': [],
            'tools': [],
            'knowledge_bases': [],
            'skills': [],
            'storage': {},
            'platform_capabilities': {},
            'workspace_operations': [{'id': 'bot.list'}],
        },
        workspace_id='workspace-OTHER',  # Different workspace from test_env.binding (workspace-a)
        processor_type='agent',
        processor_id='agent-cross-1',
    )

    # 1. 经 ExecutionAPI 调用（from_handler=False 路径）
    exec_context = ExecutionAPIContext(
        binding=test_env.binding,  # workspace-a
        run_id=run_id,
        claimed_identity='langbot-team/LocalAgent',
    )
    with pytest.raises(ApplicationAPIException) as exc_info:
        await test_env.exec_api.invoke('execution.list_application_operations', exec_context, {})
    assert exc_info.value.error.code == 'permission_denied'
    assert 'does not belong to this installation Workspace' in exc_info.value.error.message

    with pytest.raises(ApplicationAPIException) as exc_info_call:
        await test_env.exec_api.invoke(
            'execution.call_application_operation',
            exec_context,
            {'operation_id': 'bot.list', 'arguments': {}},
        )
    assert exc_info_call.value.error.code == 'permission_denied'

    # 2. 经 SDK handler actions 调用（from_handler=True 路径）
    handler_payload = {
        'run_id': run_id,
        'caller_plugin_identity': 'langbot-team/LocalAgent',
    }
    resp_list = await test_env.handler.actions['list_application_operations'](handler_payload)
    assert resp_list.code != 0
    assert 'Run does not belong to this installation Workspace' in resp_list.message

    call_payload = {
        'run_id': run_id,
        'caller_plugin_identity': 'langbot-team/LocalAgent',
        'operation_id': 'bot.list',
        'arguments': {},
    }
    resp_call = await test_env.handler.actions['call_application_operation'](call_payload)
    assert resp_call.code != 0
    assert 'Run does not belong to this installation Workspace' in resp_call.message

    # 3. session 缺少 workspace_id 时同样严格拒绝
    run_id_no_ws = 'run-no-ws'
    await registry.register(
        run_id=run_id_no_ws,
        runner_id='plugin:langbot-team/LocalAgent/default',
        query_id=None,
        plugin_identity='langbot-team/LocalAgent',
        resources={'workspace_operations': [{'id': 'bot.list'}]},
        workspace_id=None,
        processor_type='agent',
        processor_id='agent-no-ws',
    )
    resp_no_ws = await test_env.handler.actions['list_application_operations'](
        {
            'run_id': run_id_no_ws,
            'caller_plugin_identity': 'langbot-team/LocalAgent',
        }
    )
    assert resp_no_ws.code != 0
    assert 'Run does not belong to this installation Workspace' in resp_no_ws.message

    resp_no_caller = await test_env.handler.actions['list_application_operations']({})
    assert resp_no_caller.code == 0
    assert [operation['id'] for operation in resp_no_caller.data['operations']] == ['bot.list']

    # 5. caller_plugin_identity 伪造/不匹配时被拒绝
    resp_bad_caller = await test_env.handler.actions['list_application_operations'](
        {
            'run_id': run_id,
            'caller_plugin_identity': 'evil-author/evil-plugin',
        }
    )
    assert resp_bad_caller.code != 0
    assert 'Caller plugin identity does not match the installation binding' in resp_bad_caller.message


@pytest.mark.asyncio
async def test_installation_identity_does_not_require_processor_id(test_env):
    run_id = 'run-no-proc-id'
    builder = AgentResourceBuilder(test_env.host)
    event = make_event(event_id='event-fake-id')
    descriptor = make_local_agent_descriptor()
    ctx = ExecutionContext(instance_uuid='instance-a', workspace_uuid='workspace-a', placement_generation=1)

    binding_no_proc = AgentBinding(
        binding_id='bind-no-proc',
        runner_id=descriptor.id,
        processor_type='agent',
        processor_id=None,
        resource_policy=ResourcePolicy(allowed_workspace_operations=['bot.list']),
    )
    resources_no_proc = await builder.build_resources_from_binding(ctx, event, binding_no_proc, descriptor)
    assert [operation['id'] for operation in resources_no_proc['workspace_operations']] == ['bot.list']

    registry = get_session_registry()
    await registry.register(
        run_id=run_id,
        runner_id=descriptor.id,
        query_id=None,
        plugin_identity=descriptor.get_plugin_id(),
        resources={'workspace_operations': [{'id': 'bot.list'}]},
        workspace_id='workspace-a',
        processor_type='agent',
        processor_id=None,
    )
    call_payload = {
        'run_id': run_id,
        'caller_plugin_identity': 'langbot-team/LocalAgent',
        'operation_id': 'bot.list',
        'arguments': {},
    }
    resp_call = await test_env.handler.actions['call_application_operation'](call_payload)
    assert resp_call.code == 0
    assert resp_call.data['ok'] is True


# 7. 运行期间修改配置，不影响本次运行
@pytest.mark.asyncio
async def test_runtime_config_change_does_not_affect_active_run(test_env):
    run_id = 'run-frozen-test'
    ops_initial = ['bot.list']

    builder = AgentResourceBuilder(test_env.host)
    event = make_event(event_id=run_id)
    binding = AgentBinding(
        binding_id='bind-1',
        runner_id='plugin:langbot-team/LocalAgent/default',
        processor_type='agent',
        processor_id='agent-1',
        resource_policy=ResourcePolicy(allowed_workspace_operations=ops_initial),
    )
    descriptor = make_local_agent_descriptor()
    ctx = ExecutionContext(instance_uuid='instance-a', workspace_uuid='workspace-a', placement_generation=1)

    # Build resources at start of run
    resources = await builder.build_resources_from_binding(ctx, event, binding, descriptor)

    registry = get_session_registry()
    await registry.register(
        run_id=run_id,
        runner_id=descriptor.id,
        query_id=None,
        plugin_identity=descriptor.get_plugin_id(),
        resources=resources,
        workspace_id='workspace-a',
        processor_type='agent',
        processor_id='agent-1',
    )

    # Now modify the binding's resource policy during runtime (simulate config change)
    binding.resource_policy.allowed_workspace_operations = ['bot.list', 'bot.delete']

    exec_context = ExecutionAPIContext(
        binding=test_env.binding,
        run_id=run_id,
        claimed_identity='langbot-team/LocalAgent',
    )

    list_res = await test_env.exec_api.invoke('execution.list_application_operations', exec_context, {})
    assert len(list_res['operations']) == 1
    assert list_res['operations'][0]['id'] == 'bot.list'

    # bot.delete is still not authorized in this run
    with pytest.raises(ApplicationAPIException) as error:
        await test_env.exec_api.invoke(
            'execution.call_application_operation',
            exec_context,
            {'operation_id': 'bot.delete', 'arguments': {'bot_uuid': 'b-1'}},
        )
    assert error.value.error.code == 'permission_denied'


# 8. tools 列表中没有任何工作区操作
@pytest.mark.asyncio
async def test_tools_list_never_contains_workspace_operations(test_env):
    builder = AgentResourceBuilder(test_env.host)
    event = make_event()
    binding = AgentBinding(
        binding_id='bind-1',
        runner_id='plugin:langbot-team/LocalAgent/default',
        processor_type='agent',
        processor_id='agent-1',
        resource_policy=ResourcePolicy(
            allowed_tool_names=['echo_tool'],
            allow_all_tools=False,
            allowed_workspace_operations=['bot.list', 'bot.create', 'adapter.list'],
        ),
    )
    descriptor = make_local_agent_descriptor()
    ctx = ExecutionContext(instance_uuid='instance-a', workspace_uuid='workspace-a', placement_generation=1)

    resources = await builder.build_resources_from_binding(ctx, event, binding, descriptor)

    tool_names = [t.get('tool_name') for t in resources.get('tools', [])]
    for ws_op in ('bot.list', 'bot.create', 'adapter.list'):
        assert ws_op not in tool_names, f'Workspace operation {ws_op} leaked into tools!'
