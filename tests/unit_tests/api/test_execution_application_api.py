from __future__ import annotations

import asyncio
import contextlib
import contextvars
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langbot_plugin.entities.io.context import ActionContext, InstallationBinding
from langbot_plugin.entities.io.resp import ActionResponse

from langbot.pkg.api.application.contracts import ApplicationAPIException
from langbot.pkg.api.application.execution import ExecutionAPI, ExecutionAPIContext
from langbot.pkg.plugin.handler import RuntimeConnectionHandler
from langbot.pkg.agent.runner.session_registry import get_session_registry


@pytest.fixture
def host():
    binding = InstallationBinding(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=7,
        installation_uuid='00000000-0000-4000-8000-000000000001',
        runtime_revision=1,
        artifact_digest='a' * 64,
    )
    tenant = contextvars.ContextVar('execution_test_tenant', default=None)

    class Persistence:
        execute_async = AsyncMock()

        @contextlib.asynccontextmanager
        async def tenant_scope(self, workspace):
            token = tenant.set(workspace)
            try:
                yield
            finally:
                tenant.reset(token)

    ap = SimpleNamespace(
        deployment=SimpleNamespace(mode='cloud'),
        persistence_mgr=Persistence(),
        logger=Mock(),
        workspace_service=SimpleNamespace(get_execution_binding=AsyncMock(return_value=binding)),
        instance_config=SimpleNamespace(data={}),
    )
    handler = RuntimeConnectionHandler(Mock(), AsyncMock(return_value=True), ap)
    handler.register_installation_binding(binding, plugin_author='author-a', plugin_name='plugin-a')
    ap.plugin_connector = SimpleNamespace(handler=handler)
    return SimpleNamespace(ap=ap, handler=handler, binding=binding, api=ExecutionAPI(ap), tenant=tenant)


def run_session(host, **changes):
    result = {
        'run_id': 'run-a',
        'plugin_identity': 'author-a/plugin-a',
        'authorization': {
            'workspace_id': host.binding.workspace_uuid,
            'available_apis': {},
            'resources': {},
            'authorized_ids': {},
        },
    }
    result.update(changes)
    return result


def stub_run(monkeypatch, session):
    monkeypatch.setattr(get_session_registry(), 'get', AsyncMock(return_value=session))


def install_action(host, name, action):
    # The production constructor applies this wrapper after registration.
    host.handler.actions[name] = action
    host.handler._secure_plugin_actions()


@pytest.mark.asyncio
async def test_catalog_covers_all_core_business_actions_and_keeps_transport_internal(host):
    excluded = {'initialize_plugin_settings', 'get_plugin_settings'}
    expected = {name for name in host.handler.actions if not name.startswith('__') and name not in excluded}
    assert {op.action for op in host.api.operations()} == expected
    assert len(host.api.catalog()) == len(expected)
    for operation in host.api.catalog():
        assert operation['input_schema']['additionalProperties'] is False
        assert operation['output_schema']
    result = await host.api.invoke('execution.get_langbot_version', ExecutionAPIContext(host.binding))
    assert result['version']
    assert host.handler.current_action_context is None
    assert host.tenant.get() is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'name', ['__ping', '__file_chunk', 'initialize_plugin_settings', 'get_plugin_settings', 'missing']
)
async def test_runtime_control_actions_are_not_exposed(host, name):
    with pytest.raises(ApplicationAPIException) as exc:
        await host.api.invoke(f'execution.{name}', ExecutionAPIContext(host.binding))
    assert exc.value.error.code == 'unknown_operation'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'payload',
    [
        {'run_id': None},
        {'run_id': 'another-run'},
        {'workspace_uuid': 'workspace-b'},
        {'caller_plugin_identity': 'other/plugin'},
        {'action_context': {}},
        {'placement_generation': 8},
    ],
)
async def test_payload_cannot_supply_authentication_fields(host, payload):
    with pytest.raises(ApplicationAPIException) as exc:
        await host.api.invoke('execution.get_langbot_version', ExecutionAPIContext(host.binding), payload)
    assert exc.value.error.code == 'invalid_input'
    assert host.handler.current_action_context is None


@pytest.mark.asyncio
@pytest.mark.parametrize('field,value', [('runtime_revision', 2), ('artifact_digest', 'b' * 64)])
async def test_stale_installation_is_rejected_before_business_dispatch(host, field, value):
    altered = host.binding.model_copy(update={field: value})
    business = AsyncMock(return_value=ActionResponse.success({'version': 'test'}))
    install_action(host, 'get_langbot_version', business)
    with pytest.raises(ApplicationAPIException) as exc:
        await host.api.invoke('execution.get_langbot_version', ExecutionAPIContext(altered))
    assert exc.value.error.code == 'permission_denied'
    business.assert_not_called()
    assert host.handler.current_action_context is None
    assert host.tenant.get() is None


@pytest.mark.asyncio
async def test_stale_generation_and_incomplete_binding_are_rejected(host):
    host.ap.workspace_service.get_execution_binding.return_value = host.binding.model_copy(
        update={'placement_generation': 8}
    )
    with pytest.raises(ApplicationAPIException) as exc:
        await host.api.invoke('execution.get_langbot_version', ExecutionAPIContext(host.binding))
    assert exc.value.error.code == 'permission_denied'
    incomplete = ActionContext(instance_uuid='instance-a', workspace_uuid='workspace-a', placement_generation=7)
    with pytest.raises(ApplicationAPIException) as exc:
        await host.api.invoke('execution.get_langbot_version', ExecutionAPIContext(incomplete))
    assert exc.value.error.code == 'invalid_authentication'


@pytest.mark.asyncio
@pytest.mark.parametrize('session', [None, {'workspace': 'workspace-b'}, {'plugin': 'other/plugin'}])
async def test_run_context_cannot_cross_workspace_or_plugin(host, monkeypatch, session):
    actual = run_session(host)
    if session is None:
        actual = None
    elif 'workspace' in session:
        actual['authorization']['workspace_id'] = session['workspace']
    else:
        actual['plugin_identity'] = session['plugin']
    stub_run(monkeypatch, actual)
    business = AsyncMock(return_value=ActionResponse.success({'version': 'test'}))
    install_action(host, 'get_langbot_version', business)
    with pytest.raises(ApplicationAPIException) as exc:
        await host.api.invoke('execution.get_langbot_version', ExecutionAPIContext(host.binding, 'run-a'))
    assert exc.value.error.code == 'permission_denied'
    business.assert_not_called()


@pytest.mark.asyncio
async def test_run_identity_is_injected_and_cannot_fall_back_to_plugin_privileges(host, monkeypatch):
    stub_run(monkeypatch, run_session(host))
    business = AsyncMock(return_value=ActionResponse.success({'version': 'test'}))
    install_action(host, 'get_langbot_version', business)
    await host.api.invoke('execution.get_langbot_version', ExecutionAPIContext(host.binding, 'run-a'))
    assert business.call_args.args[0] == {'run_id': 'run-a', 'caller_plugin_identity': 'author-a/plugin-a'}
    with pytest.raises(ApplicationAPIException) as exc:
        await host.api.invoke('execution.get_bots', ExecutionAPIContext(host.binding, 'run-a'))
    assert exc.value.error.code == 'permission_denied'
    with pytest.raises(ApplicationAPIException) as exc:
        await host.api.invoke('execution.get_prompt', ExecutionAPIContext(host.binding))
    assert exc.value.error.code == 'permission_denied'


@pytest.mark.asyncio
async def test_resource_denial_uses_real_secured_host_action(host, monkeypatch):
    stub_run(monkeypatch, run_session(host))
    host.ap.model_mgr = SimpleNamespace(get_model_by_uuid=AsyncMock())
    with pytest.raises(ApplicationAPIException) as exc:
        await host.api.invoke(
            'execution.invoke_llm',
            ExecutionAPIContext(host.binding, 'run-a'),
            {
                'llm_model_uuid': 'ungranted-model',
                'messages': [],
            },
        )
    assert 'not authorized' in exc.value.error.message
    host.ap.model_mgr.get_model_by_uuid.assert_not_called()
    assert host.handler.current_action_context is None


@pytest.mark.asyncio
async def test_run_capability_denial_uses_real_secured_host_action(host, monkeypatch):
    stub_run(monkeypatch, run_session(host))
    with pytest.raises(ApplicationAPIException) as exc:
        await host.api.invoke(
            'execution.state_get', ExecutionAPIContext(host.binding, 'run-a'), {'scope': 'conversation', 'key': 'x'}
        )
    assert 'not authorized' in exc.value.error.message
    assert host.handler.current_action_context is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'payload',
    [
        {'llm_model_uuid': 1, 'messages': []},
        {'llm_model_uuid': 'model', 'messages': 'invalid'},
        {'llm_model_uuid': 'model', 'messages': [], 'extra_args': {'x': object()}},
    ],
)
async def test_input_type_validation_precedes_provider_calls(host, payload):
    with pytest.raises(ApplicationAPIException) as exc:
        await host.api.invoke('execution.invoke_llm', ExecutionAPIContext(host.binding), payload)
    assert exc.value.error.code == 'invalid_input'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'response',
    [
        ActionResponse.success({'tokens': 'wrong'}),
        ActionResponse.success({}),
        ActionResponse.success({'tokens': 1, 'unknown': object()}),
        {'tokens': 1},
    ],
)
async def test_invalid_output_is_not_reported_as_success(host, response):
    install_action(host, 'count_tokens', AsyncMock(return_value=response))
    with pytest.raises(ApplicationAPIException) as exc:
        await host.api.invoke(
            'execution.count_tokens', ExecutionAPIContext(host.binding), {'llm_model_uuid': 'model', 'messages': []}
        )
    assert exc.value.error.code == 'invalid_output'


@pytest.mark.asyncio
async def test_failure_and_cancellation_restore_outer_context(host):
    outer = host.binding.model_copy(update={'workspace_uuid': 'outer'})
    token = host.handler._current_action_context.set(outer)
    try:
        install_action(host, 'get_langbot_version', AsyncMock(side_effect=RuntimeError('private provider error')))
        with pytest.raises(ApplicationAPIException) as exc:
            await host.api.invoke('execution.get_langbot_version', ExecutionAPIContext(host.binding))
        assert exc.value.error.message == 'Execution operation failed'
        assert host.handler.current_action_context is outer
        install_action(host, 'get_langbot_version', AsyncMock(side_effect=asyncio.CancelledError()))
        with pytest.raises(asyncio.CancelledError):
            await host.api.invoke('execution.get_langbot_version', ExecutionAPIContext(host.binding))
        assert host.handler.current_action_context is outer
        assert host.tenant.get() is None
    finally:
        host.handler._current_action_context.reset(token)


@pytest.mark.asyncio
async def test_stream_isolates_context_from_consumer_and_closes_on_early_exit(host):
    closed = asyncio.Event()

    async def provider(data):
        try:
            assert host.handler.current_action_context == host.binding
            assert host.tenant.get() == 'workspace-a'
            yield ActionResponse.success({'chunk': {'text': 'first'}})
            await asyncio.Event().wait()
        finally:
            assert host.handler.current_action_context == host.binding
            closed.set()

    install_action(host, 'invoke_llm_stream', provider)
    stream = host.api.stream(
        'execution.invoke_llm_stream', ExecutionAPIContext(host.binding), {'llm_model_uuid': 'model', 'messages': []}
    )
    async with contextlib.aclosing(stream):
        assert await anext(stream) == {'chunk': {'text': 'first'}}
        assert host.handler.current_action_context is None
        assert host.tenant.get() is None
    assert closed.is_set()
    assert host.handler.current_action_context is None
    assert host.tenant.get() is None


@pytest.mark.asyncio
async def test_stream_reports_late_failure_and_cancels_provider(host):
    closed = asyncio.Event()

    async def provider(data):
        try:
            yield ActionResponse.success({'chunk': {'text': 'first'}})
            yield ActionResponse.error('provider refused request')
        finally:
            closed.set()

    install_action(host, 'invoke_llm_stream', provider)
    async with contextlib.aclosing(
        host.api.stream(
            'execution.invoke_llm_stream',
            ExecutionAPIContext(host.binding),
            {'llm_model_uuid': 'model', 'messages': []},
        )
    ) as stream:
        assert await anext(stream) == {'chunk': {'text': 'first'}}
        with pytest.raises(ApplicationAPIException, match='provider refused request'):
            await anext(stream)
    assert closed.is_set()
    assert host.tenant.get() is None


@pytest.mark.asyncio
async def test_stream_cancellation_closes_provider(host):
    started, closed = asyncio.Event(), asyncio.Event()

    async def provider(data):
        try:
            started.set()
            await asyncio.Event().wait()
            yield ActionResponse.success({'chunk': {}})
        finally:
            closed.set()

    install_action(host, 'invoke_llm_stream', provider)
    stream = host.api.stream(
        'execution.invoke_llm_stream', ExecutionAPIContext(host.binding), {'llm_model_uuid': 'model', 'messages': []}
    )
    consumer = asyncio.create_task(anext(stream))
    await asyncio.wait_for(started.wait(), timeout=2)
    consumer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await consumer
    assert closed.is_set()
    assert host.handler.current_action_context is None
    assert host.tenant.get() is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'operation,payload',
    [
        ('call_tool', {'tool_name': 'ungranted-tool', 'parameters': {}}),
        ('get_tool_detail', {'tool_name': 'ungranted-tool'}),
        ('retrieve_knowledge', {'kb_id': 'ungranted-kb', 'query_text': 'test'}),
        ('invoke_embedding', {'embedding_model_uuid': 'ungranted-model', 'texts': ['test']}),
        ('invoke_rerank', {'rerank_model_uuid': 'ungranted-model', 'query': 'test', 'documents': ['test']}),
        ('get_binary_storage', {'owner_type': 'workspace', 'key': 'key'}),
    ],
)
async def test_resource_families_preserve_frozen_grants(host, monkeypatch, operation, payload):
    stub_run(monkeypatch, run_session(host))
    with pytest.raises(ApplicationAPIException) as exc:
        await host.api.invoke(f'execution.{operation}', ExecutionAPIContext(host.binding, 'run-a'), payload)
    assert 'not authorized' in exc.value.error.message
    assert host.handler.current_action_context is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'operation,payload',
    [
        ('history_page', {}),
        ('event_get', {'event_id': 'event-a'}),
        ('bind_box', {'box_id': 'box-a'}),
        ('export_box_files', {'paths': ['report.txt']}),
    ],
)
async def test_run_capability_families_cannot_fall_back_to_plugin_access(host, monkeypatch, operation, payload):
    stub_run(monkeypatch, run_session(host))
    with pytest.raises(ApplicationAPIException) as exc:
        await host.api.invoke(f'execution.{operation}', ExecutionAPIContext(host.binding, 'run-a'), payload)
    assert 'not authorized' in exc.value.error.message


@pytest.mark.asyncio
async def test_box_export_preserves_structured_failure(host, monkeypatch):
    from langbot.pkg.box.export_errors import export_error

    stub_run(monkeypatch, run_session(host))
    error = export_error('file_bytes', limit=100, actual=101, path='report.txt')
    install_action(
        host,
        'export_box_files',
        AsyncMock(
            return_value=ActionResponse.error(
                str(error),
                data={'error': error.error.model_dump(mode='json')},
            )
        ),
    )
    with pytest.raises(ApplicationAPIException) as exc:
        await host.api.invoke(
            'execution.export_box_files', ExecutionAPIContext(host.binding, 'run-a'), {'paths': ['report.txt']}
        )
    assert exc.value.error.details['error']['code'] == 'box.export.limit_exceeded'
    assert exc.value.error.details['error']['details']['files_retained'] is True


@pytest.mark.asyncio
async def test_frozen_tool_source_cannot_be_replaced(host, monkeypatch):
    session = run_session(host)
    session['authorization']['authorized_ids'] = {'tool': {'tool-a'}}
    session['authorization']['resources'] = {'tools': [{'tool_name': 'tool-a'}]}
    stub_run(monkeypatch, session)
    host.ap.tool_mgr = SimpleNamespace(execute_func_call=AsyncMock())
    with pytest.raises(ApplicationAPIException) as exc:
        await host.api.invoke(
            'execution.call_tool', ExecutionAPIContext(host.binding, 'run-a'), {'tool_name': 'tool-a', 'parameters': {}}
        )
    assert 'source' in exc.value.error.message.lower()
    host.ap.tool_mgr.execute_func_call.assert_not_called()


@pytest.mark.asyncio
async def test_runner_admin_operations_do_not_grant_admin_implicitly(host):
    with pytest.raises(ApplicationAPIException) as exc:
        await host.api.invoke('execution.run_stats', ExecutionAPIContext(host.binding))
    assert 'not authorized' in exc.value.error.message


@pytest.mark.asyncio
async def test_query_identity_cannot_be_replaced_in_run_context(host, monkeypatch):
    stub_run(monkeypatch, run_session(host))
    with pytest.raises(ApplicationAPIException) as exc:
        await host.api.invoke(
            'execution.invoke_llm',
            ExecutionAPIContext(host.binding, 'run-a'),
            {
                'llm_model_uuid': 'model',
                'messages': [],
                'query_id': 'other-query',
            },
        )
    assert exc.value.error.code == 'invalid_input'


@pytest.mark.asyncio
async def test_provider_cancellation_cannot_leave_stream_consumer_waiting(host):
    async def provider(data):
        raise asyncio.CancelledError()
        yield

    install_action(host, 'invoke_llm_stream', provider)
    stream = host.api.stream(
        'execution.invoke_llm_stream', ExecutionAPIContext(host.binding), {'llm_model_uuid': 'model', 'messages': []}
    )
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(anext(stream), timeout=2)
    assert host.tenant.get() is None


@pytest.mark.asyncio
async def test_concurrent_streams_keep_independent_installation_contexts(host):
    other = host.binding.model_copy(
        update={'workspace_uuid': 'workspace-b', 'installation_uuid': '00000000-0000-4000-8000-000000000002'}
    )
    host.handler.register_installation_binding(other, plugin_author='author-a', plugin_name='plugin-a')
    host.ap.workspace_service.get_execution_binding.side_effect = (
        lambda workspace, **kwargs: host.binding if workspace == 'workspace-a' else other
    )

    async def provider(data):
        workspace = host.handler.current_action_context.workspace_uuid
        for _ in range(2):
            await asyncio.sleep(0)
            assert host.handler.current_action_context.workspace_uuid == workspace
            assert host.tenant.get() == workspace
            yield ActionResponse.success({'chunk': {'workspace': workspace}})

    install_action(host, 'invoke_llm_stream', provider)

    async def consume(binding):
        results = []
        async with contextlib.aclosing(
            host.api.stream(
                'execution.invoke_llm_stream', ExecutionAPIContext(binding), {'llm_model_uuid': 'model', 'messages': []}
            )
        ) as stream:
            async for chunk in stream:
                assert host.handler.current_action_context is None
                assert host.tenant.get() is None
                results.append(chunk['chunk']['workspace'])
        return results

    assert await asyncio.gather(consume(host.binding), consume(other)) == [['workspace-a'] * 2, ['workspace-b'] * 2]


@pytest.mark.asyncio
async def test_tool_parameters_reach_legacy_plugin_and_run_handlers(host, monkeypatch):
    business = AsyncMock(return_value=ActionResponse.success({'result': 'ok'}))
    install_action(host, 'call_tool', business)
    await host.api.invoke(
        'execution.call_tool', ExecutionAPIContext(host.binding), {'tool_name': 'tool', 'parameters': {'x': 1}}
    )
    assert business.call_args.args[0]['tool_parameters'] == {'x': 1}
    assert 'parameters' not in business.call_args.args[0]
    stub_run(monkeypatch, run_session(host))
    await host.api.invoke('execution.call_tool', ExecutionAPIContext(host.binding, 'run-a'), {'tool_name': 'tool'})
    assert business.call_args.args[0]['parameters'] == {}
    with pytest.raises(ApplicationAPIException) as exc:
        await host.api.invoke(
            'execution.call_tool',
            ExecutionAPIContext(host.binding, 'run-a'),
            {'tool_name': 'tool', 'tool_parameters': {}},
        )
    assert exc.value.error.code == 'invalid_input'


@pytest.mark.asyncio
async def test_platform_call_requires_bot_identity_outside_run(host):
    with pytest.raises(ApplicationAPIException) as exc:
        await host.api.invoke(
            'execution.call_platform_api', ExecutionAPIContext(host.binding), {'action': 'send_message'}
        )
    assert exc.value.error.code == 'invalid_input'
