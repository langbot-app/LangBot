from __future__ import annotations

import asyncio
import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langbot_plugin.api.proxies.invocation import audit_correlation_scope
from langbot_plugin.entities.io.context import InstallationBinding
from langbot_plugin.entities.io.resp import ActionResponse

from langbot.pkg.api.application.contracts import ApplicationAPIException
from langbot.pkg.api.application.api import ApplicationAPI
from langbot.pkg.api.application.execution import ExecutionAPIContext
from langbot.pkg.api.application.plugin_audit import audit_action, outbound_tool_call
from langbot.pkg.api.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext
from langbot.pkg.operation_trace.service import OPERATION_LEVEL_MUTATION, OPERATION_LEVEL_READ
from langbot.pkg.plugin.handler import RuntimeConnectionHandler


@pytest.fixture
def host(monkeypatch):
    caller = InstallationBinding(
        instance_uuid='instance',
        workspace_uuid='workspace',
        placement_generation=1,
        installation_uuid='caller',
        runtime_revision=1,
        artifact_digest='a' * 64,
    )
    target = caller.model_copy(update={'installation_uuid': 'target'})

    @contextlib.asynccontextmanager
    async def tenant_scope(workspace):
        yield

    ap = SimpleNamespace(
        deployment=SimpleNamespace(mode='cloud'),
        persistence_mgr=SimpleNamespace(tenant_scope=tenant_scope),
        workspace_service=SimpleNamespace(get_execution_binding=AsyncMock(return_value=caller)),
        workspace_settings_service=SimpleNamespace(
            get_configured_level=AsyncMock(return_value=OPERATION_LEVEL_READ),
            record=AsyncMock(),
            effective_level=AsyncMock(return_value=OPERATION_LEVEL_READ),
        ),
        logger=Mock(),
        instance_config=SimpleNamespace(data={}),
        tool_mgr=SimpleNamespace(
            get_resolved_tool_catalog=AsyncMock(
                return_value=[
                    {'name': 'target-tool', 'source': 'plugin', 'source_id': 'author/target'},
                ]
            )
        ),
    )
    handler = RuntimeConnectionHandler(Mock(), AsyncMock(return_value=True), ap)
    handler.register_installation_binding(caller, plugin_author='author', plugin_name='caller')
    handler.register_installation_binding(target, plugin_author='author', plugin_name='target')
    ap.plugin_connector = SimpleNamespace(handler=handler, _runtime_handler=lambda: handler)
    settings = {
        'caller': SimpleNamespace(
            enabled=True, permission_declaration=None, permission_grants={'capabilities': ['plugin_tools']}
        ),
        'target': SimpleNamespace(
            enabled=True, permission_declaration=None, permission_grants={'capabilities': ['langbot.info']}
        ),
    }

    async def load(ap, workspace, installation):
        return settings[installation]

    monkeypatch.setattr('langbot.pkg.api.application.plugin_permissions.load_installation', load)
    return SimpleNamespace(ap=ap, handler=handler, caller=caller, target=target, settings=settings)


def records(host):
    return [call.kwargs for call in host.ap.workspace_settings_service.record.await_args_list]


@pytest.mark.asyncio
async def test_cross_plugin_tool_chain_authorizes_each_installation(host):
    correlations = []

    async def peer(action, data, **kwargs):
        correlation = data['_host_audit_id']
        correlations.append(correlation)
        assert host.ap._plugin_audit_calls[correlation][0] == host.target
        with audit_correlation_scope(correlation):
            result = await host.handler.execution_api.invoke(
                'execution.get_langbot_version',
                ExecutionAPIContext(host.target),
                {},
            )
        return {'tool_response': result}

    async def call_target(data):
        assert data['_permission_tool_source']['source'] == 'plugin'
        with host.handler.installation_scope(host.target):
            result = await host.handler.call_tool('target-tool', {'secret': 'private-payload'}, {}, 1)
        return ActionResponse.success({'tool_response': result})

    host.handler.call_action = peer
    host.handler.actions['call_tool'] = call_target
    host.handler._secure_plugin_actions()
    await host.handler.execution_api.invoke(
        'execution.call_tool',
        ExecutionAPIContext(host.caller),
        {'tool_name': 'target-tool'},
    )
    nested, parent = records(host)
    assert nested['outcome'] == parent['outcome'] == 'ok'
    assert nested['detail']['chain'] == [
        {'installation_uuid': 'caller', 'action': 'call_tool'},
        {'installation_uuid': 'target', 'action': 'tool.invoke'},
        {'installation_uuid': 'target', 'action': 'get_langbot_version'},
    ]
    assert host.ap._plugin_audit_calls == {}
    assert correlations[0] not in repr(records(host))
    assert 'private-payload' not in repr(records(host))

    host.settings['target'].permission_grants = {'capabilities': []}
    with pytest.raises(ApplicationAPIException) as denied:
        await host.handler.execution_api.invoke(
            'execution.call_tool',
            ExecutionAPIContext(host.caller),
            {'tool_name': 'target-tool'},
        )
    assert denied.value.error.code == 'permission_denied'
    assert records(host)[-2]['outcome'] == 'denied'
    assert records(host)[-2]['detail']['chain'] == nested['detail']['chain']
    assert host.ap._plugin_audit_calls == {}

    host.settings['caller'].permission_grants = {'capabilities': []}
    with pytest.raises(ApplicationAPIException):
        await host.handler.execution_api.invoke(
            'execution.call_tool',
            ExecutionAPIContext(host.caller),
            {'tool_name': 'target-tool'},
        )
    assert len(correlations) == 2
    assert records(host)[-1]['outcome'] == 'denied'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'kind', ['forged', 'wrong_target', 'wrong_workspace', 'stale_revision', 'expired', 'not_string']
)
async def test_rejects_untrusted_correlations_before_action(host, kind):
    called = AsyncMock(return_value=ActionResponse.success({'version': 'test'}))
    host.handler.actions['get_langbot_version'] = called
    host.handler._secure_plugin_actions()
    with outbound_tool_call(host.ap, host.target) as correlation:
        if kind == 'wrong_target':
            binding = host.caller
        else:
            binding = host.target
        if kind in {'wrong_workspace', 'stale_revision'}:
            field, value = ('workspace_uuid', 'foreign') if kind == 'wrong_workspace' else ('runtime_revision', 2)
            host.ap._plugin_audit_calls[correlation] = (
                host.target.model_copy(update={field: value}),
                host.ap._plugin_audit_calls[correlation][1],
            )
        if kind == 'forged':
            correlation = 'plugin-controlled-chain'
        if kind == 'not_string':
            correlation = {'chain': 'forged'}
        if kind == 'expired':
            host.ap._plugin_audit_calls[correlation][1].active = False
        with audit_correlation_scope(correlation), pytest.raises(ApplicationAPIException) as error:
            await host.handler.execution_api.invoke(
                'execution.get_langbot_version',
                ExecutionAPIContext(binding),
                {},
            )
        assert error.value.error.code == 'permission_denied'
    called.assert_not_awaited()
    assert records(host)[-1]['outcome'] == 'denied'
    assert records(host)[-1]['detail']['chain'] == [
        {'installation_uuid': binding.installation_uuid, 'action': 'get_langbot_version'},
    ]


@pytest.mark.asyncio
async def test_closed_correlation_cannot_be_replayed(host):
    with outbound_tool_call(host.ap, host.target) as correlation:
        pass
    with audit_correlation_scope(correlation), pytest.raises(ApplicationAPIException):
        async with audit_action(host.ap, host.target, 'get_langbot_version'):
            pytest.fail('Expired correlation entered action')


@pytest.mark.asyncio
async def test_concurrent_nested_calls_do_not_mix_ancestry(host):
    ready = asyncio.Event()
    arrivals = []

    async def invoke(caller):
        with audit_correlation_scope(None):
            async with audit_action(host.ap, caller, 'call_tool'):
                with outbound_tool_call(host.ap, host.target) as correlation:
                    arrivals.append(correlation)
                    if len(arrivals) == 2:
                        ready.set()
                    await ready.wait()
                    with audit_correlation_scope(correlation):
                        async with audit_action(host.ap, host.target, 'get_langbot_version'):
                            await asyncio.sleep(0)

    await asyncio.gather(invoke(host.caller), invoke(host.caller.model_copy(update={'installation_uuid': 'other'})))
    nested = [row['detail']['chain'] for row in records(host) if row['route'] == 'execution.get_langbot_version']
    assert {chain[0]['installation_uuid'] for chain in nested} == {'caller', 'other'}
    assert len(set(arrivals)) == 2
    assert host.ap._plugin_audit_calls == {}


@pytest.mark.asyncio
async def test_binary_action_denial_success_and_payload_free_failure(host):
    called = AsyncMock(return_value=ActionResponse.success({'value_base64': 'private-result'}))
    host.handler.actions['get_binary_storage'] = called
    host.handler._secure_plugin_actions()
    payload = {'owner_type': 'plugin', 'key': 'private-key'}
    context = ExecutionAPIContext(host.target)
    with pytest.raises(ApplicationAPIException):
        await host.handler.execution_api.invoke('execution.get_binary_storage', context, payload)
    called.assert_not_awaited()
    host.settings['target'].permission_grants = {'capabilities': ['storage.plugin']}
    await host.handler.execution_api.invoke('execution.get_binary_storage', context, payload)
    called.side_effect = RuntimeError('private-exception')
    with pytest.raises(ApplicationAPIException):
        await host.handler.execution_api.invoke('execution.get_binary_storage', context, payload)
    assert [row['outcome'] for row in records(host)] == ['denied', 'ok', 'error']
    assert 'private' not in repr(records(host))


@pytest.mark.asyncio
async def test_internal_legacy_action_audits_authorization_and_response_errors(host):
    called = AsyncMock(return_value=ActionResponse.success({'commands': []}))
    host.handler.actions['list_commands'] = called
    host.handler._secure_plugin_actions()
    token = host.handler._current_action_context.set(host.target)
    try:
        response = await host.handler.actions['list_commands']({})
        assert response.code != 0
        called.assert_not_awaited()
        host.settings['target'].permission_grants = {'capabilities': ['plugin.read']}
        response = await host.handler.actions['list_commands']({'chain': 'forged', 'workspace_uuid': 'foreign'})
        assert response.data['code'] == 'invalid_input'
        response = await host.handler.actions['list_commands']({})
        assert response.code == 0
        assert 'workspace_uuid' not in called.await_args.args[0]
        called.return_value = ActionResponse.error('private-failure')
        assert (await host.handler.actions['list_commands']({})).code != 0
    finally:
        host.handler._current_action_context.reset(token)
    assert [row['outcome'] for row in records(host)] == ['denied', 'ok', 'error']
    assert all(
        row['detail']['chain'] == [{'installation_uuid': 'target', 'action': 'list_commands'}] for row in records(host)
    )
    assert 'forged' not in repr(records(host))
    assert 'private' not in repr(records(host))


@pytest.mark.asyncio
async def test_stream_denial_success_and_cancellation(host):
    async def chunks(data):
        yield ActionResponse.success({'chunk': {'content': 'private-chunk'}})

    host.handler.actions['invoke_llm_stream'] = chunks
    host.handler._secure_plugin_actions()
    payload = {'llm_model_uuid': 'private-model', 'messages': []}
    context = ExecutionAPIContext(host.target)
    with pytest.raises(ApplicationAPIException):
        async for _ in host.handler.execution_api.stream('execution.invoke_llm_stream', context, payload):
            pytest.fail('Denied stream returned a chunk')
    host.settings['target'].permission_grants = {'capabilities': ['models.invoke']}
    assert (
        len(
            [
                chunk
                async for chunk in host.handler.execution_api.stream('execution.invoke_llm_stream', context, payload)
            ]
        )
        == 1
    )
    with pytest.raises(asyncio.CancelledError):
        async with audit_action(host.ap, host.target, 'send_message', side_effect=True):
            raise asyncio.CancelledError
    assert [row['outcome'] for row in records(host)] == ['denied', 'ok', 'unknown']
    assert records(host)[-1]['status_code'] == 499
    assert 'private' not in repr(records(host))


@pytest.mark.asyncio
async def test_capture_policy_and_writer_failure_do_not_change_action(host):
    service = host.ap.workspace_settings_service
    service.get_configured_level.return_value = OPERATION_LEVEL_MUTATION
    async with audit_action(host.ap, host.target, 'get_langbot_version'):
        pass
    service.record.assert_not_awaited()
    async with audit_action(host.ap, host.target, 'send_message', side_effect=True):
        pass
    assert records(host)[-1]['rule'].bucket == 'write'
    service.record.side_effect = RuntimeError('writer unavailable')
    async with audit_action(host.ap, host.target, 'send_message', side_effect=True):
        pass


@pytest.mark.asyncio
async def test_recursive_chain_and_workspace_operation_audit(host):
    third = host.target.model_copy(update={'installation_uuid': 'third'})
    context = RequestContext(
        'instance',
        1,
        'request',
        'plugin',
        PrincipalContext(PrincipalType.PLUGIN, installation_uuid='third'),
        WorkspaceContext('workspace', None, None, frozenset()),
    )
    spec = SimpleNamespace(operation_id='bot.list', version='1', side_effect=False)
    api = ApplicationAPI(host.ap, operations=[])
    async with audit_action(host.ap, host.caller, 'call_tool'):
        with outbound_tool_call(host.ap, host.target) as first:
            with audit_correlation_scope(first):
                async with audit_action(host.ap, host.target, 'call_tool'):
                    with outbound_tool_call(host.ap, third) as second:
                        with audit_correlation_scope(second):
                            async with audit_action(host.ap, third, 'call_application_operation'):
                                await api._record(spec, context, 0, started=True)
    assert records(host)[0]['detail']['chain'] == [
        {'installation_uuid': 'caller', 'action': 'call_tool'},
        {'installation_uuid': 'target', 'action': 'tool.invoke'},
        {'installation_uuid': 'target', 'action': 'call_tool'},
        {'installation_uuid': 'third', 'action': 'tool.invoke'},
        {'installation_uuid': 'third', 'action': 'call_application_operation'},
        {'installation_uuid': 'third', 'action': 'bot.list'},
    ]
    assert host.ap._plugin_audit_calls == {}


@pytest.mark.asyncio
async def test_repeated_outcomes_have_distinct_persistence_dedupe_keys(host, monkeypatch):
    from langbot.pkg.operation_trace.service import WorkspaceSettingsService

    queued = []
    service = WorkspaceSettingsService(host.ap)
    monkeypatch.setattr(service, 'get_configured_level', AsyncMock(return_value=OPERATION_LEVEL_READ))
    monkeypatch.setattr(service, '_enqueue', lambda row: queued.append(row) or True)
    host.ap.workspace_settings_service = service
    for _ in range(2):
        async with audit_action(host.ap, host.target, 'get_langbot_version'):
            pass
    assert len(queued) == 2
    assert queued[0]['_dedupe_material'] != queued[1]['_dedupe_material']
    assert queued[0]['request_id'] != queued[1]['request_id']


@pytest.mark.asyncio
async def test_ended_parent_cannot_issue_outbound_correlations(host):
    release = asyncio.Event()

    async def escaped():
        await release.wait()
        with outbound_tool_call(host.ap, host.target):
            pytest.fail('Ended parent issued a new correlation')

    async with audit_action(host.ap, host.caller, 'call_tool'):
        task = asyncio.create_task(escaped())
    release.set()
    with pytest.raises(RuntimeError, match='invocation has ended'):
        await task
    assert not getattr(host.ap, '_plugin_audit_calls', {})


def test_core_does_not_relay_target_correlation_to_unrelated_outbound_actions(host):
    with audit_correlation_scope('parent-for-target'):
        assert host.handler._outbound_action_data({'key': 'value'}) == {'key': 'value'}
        explicit = {'_host_audit_id': 'new-target-id'}
        assert host.handler._outbound_action_data(explicit) == explicit
