"""Integration tests verifying full ExecutionAPI facade routing and SDK 0.7.19 compatibility."""

from __future__ import annotations

import contextlib
import contextvars
import types
from types import SimpleNamespace
import typing
from unittest.mock import AsyncMock, Mock

import pytest
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.builtin.provider import message as provider_message
from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
from langbot_plugin.api.entities.builtin.runner.resources import (
    AgentResources,
    KnowledgeBaseResource,
    ModelResource,
    ToolResource,
)
from langbot_plugin.api.entities.builtin.runner.result import RunnerResult
from langbot_plugin.api.proxies.langbot_api import LangBotAPIProxy
from langbot_plugin.api.proxies.query_based_api import QueryBasedAPIProxy
from langbot_plugin.api.proxies.runner.admin import RunnerAdminAPIProxy
from langbot_plugin.api.proxies.runner.api import RunnerAPIProxy
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction, RuntimeToLangBotAction
from langbot_plugin.entities.io.context import InstallationBinding
from langbot_plugin.entities.io.resp import ActionResponse
from langbot_plugin.runtime.io.handler import Handler

from langbot.pkg.api.application.execution import ExecutionOperation
from langbot.pkg.plugin.handler import RuntimeConnectionHandler


pytestmark = pytest.mark.integration

NON_EXECUTION_ACTIONS = frozenset(
    {
        '__cancel_action',
        '__file_chunk',
        '__ping',
        '__stream_ack',
        'get_plugin_settings',
        'initialize_plugin_settings',
    }
)


@pytest.fixture
def test_host():
    binding = InstallationBinding(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=1,
        installation_uuid='00000000-0000-4000-8000-000000000001',
        runtime_revision=1,
        artifact_digest='a' * 64,
    )
    tenant = contextvars.ContextVar('routing_test_tenant', default=None)

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
    handler._current_action_context.set(binding)
    ap.plugin_connector = SimpleNamespace(handler=handler)
    return SimpleNamespace(ap=ap, handler=handler, binding=binding, api=handler.execution_api, tenant=tenant)


def _is_union(t: typing.Any) -> bool:
    return isinstance(t, types.UnionType) or typing.get_origin(t) in (typing.Union, types.UnionType)


def _dummy_for_type(annotation: typing.Any) -> typing.Any:
    if _is_union(annotation):
        args = typing.get_args(annotation)
        if type(None) in args:
            return None
        return _dummy_for_type(args[0])
    origin = typing.get_origin(annotation)
    if annotation in (str,):
        return 'test'
    if annotation in (int,):
        return 1
    if annotation in (float,):
        return 1.0
    if annotation in (bool,):
        return True
    if origin is list:
        return []
    if origin is dict:
        return {}
    return {}


def _make_dummy_output(op: ExecutionOperation) -> dict[str, typing.Any]:
    out_t = op.output_type
    if _is_union(out_t):
        out_t = typing.get_args(out_t)[0]
    data: dict[str, typing.Any] = {}
    if hasattr(out_t, 'model_fields'):
        for fname, field in out_t.model_fields.items():
            if field.is_required():
                data[fname] = _dummy_for_type(field.annotation)
    return data


async def _capture_sdk_payloads() -> dict[str, dict[str, typing.Any]]:
    """Drive SDK 0.7.19 proxy methods against a mock handler to capture actual outgoing payloads."""
    recorded: dict[str, dict[str, typing.Any]] = {}

    class Interceptor(Handler):
        def __init__(self):
            super().__init__(Mock())

        async def call_action(self, action, payload=None, timeout=None, **kwargs):
            name = getattr(action, 'value', str(action))
            recorded[name] = payload or {}
            if 'page' in name or 'list' in name:
                return {'items': [], 'total_count': 0, 'has_more': False, 'next_cursor': None, 'prev_cursor': None}
            return {'id': 'dummy', 'status': 'online', 'runtime_id': 'rt-1', 'run_id': 'r-1', 'token': 't'}

        async def call_action_generator(self, action, payload=None, timeout=None, **kwargs):
            name = getattr(action, 'value', str(action))
            recorded[name] = payload or {}
            if False:
                yield {}

    interceptor = Interceptor()
    api = LangBotAPIProxy(interceptor)
    admin = RunnerAdminAPIProxy(interceptor)
    query_proxy = QueryBasedAPIProxy(query_id='123', query_uuid='uuid-123', plugin_runtime_handler=interceptor)

    ctx = RunnerContext.model_construct(
        run_id='run-123',
        conversation_id='conv-1',
        runtime=SimpleNamespace(deadline_at=None),
        resources=AgentResources(
            models=[ModelResource(model_id='m-1', operations=['invoke', 'stream', 'count_tokens'])],
            tools=[
                ToolResource(tool_name='t-1', operations=['call', 'detail']),
                ToolResource(tool_name='event_reply', operations=['call']),
            ],
            knowledge_bases=[KnowledgeBaseResource(kb_id='kb-1', operations=['retrieve', 'list'])],
        ),
        context={
            'available_apis': {
                'prompt_get': True,
                'history_page': True,
                'history_search': True,
                'event_get': True,
                'event_page': True,
                'steering_pull': True,
                'state': True,
                'reply_stream': True,
            }
        },
        state={},
    )
    runner = RunnerAPIProxy(ctx, interceptor)
    msg_chain = platform_message.MessageChain([platform_message.Plain(text='hi')])
    llm_msgs = [provider_message.Message(role='user', content='hi')]

    async def try_call(coro):
        with contextlib.suppress(Exception):
            await coro

    # LangBotAPIProxy
    await try_call(api.acquire_box('test-key'))
    await try_call(api.list_boxes())
    await try_call(api.get_box_status())
    await try_call(api.call_platform_api('bot-1', 'custom_action', {}))
    await try_call(api.call_tool('t-1', parameters={'a': 1}, session={'id': 'sess-1'}, query_id=123))
    await try_call(api.get_tool_detail('t-1'))
    await try_call(api.get_bot_info('bot-1'))
    await try_call(api.get_bots())
    await try_call(api.get_config_file('cfg-1'))
    await try_call(api.get_knowledge_file_stream('storage/path'))
    await try_call(api.get_langbot_version())
    await try_call(api.get_llm_models())
    await try_call(api.invoke_embedding('emb-1', ['text']))
    await try_call(api.invoke_llm('m-1', llm_msgs))
    try:
        async for _ in api.invoke_llm_stream('m-1', llm_msgs):
            pass
    except Exception:
        pass
    await try_call(api.invoke_parser('author', 'plugin', 'storage/path', 'text/plain', 'doc.txt'))
    await try_call(api.invoke_rerank('rerank-1', 'query', ['doc']))
    await try_call(api.list_knowledge_bases())
    await try_call(api.list_parsers())
    await try_call(api.retrieve_knowledge('kb-1', 'query'))
    await try_call(api.send_message('bot-1', 'person', 'target-1', msg_chain))
    await try_call(api.vector_delete('col-1'))
    await try_call(api.vector_list('col-1'))
    await try_call(api.vector_search('col-1', [0.1, 0.2], 5))
    await try_call(api.vector_upsert('col-1', [[0.1, 0.2]], ['id1']))

    # QueryBasedAPIProxy
    await try_call(query_proxy.get_bot_uuid())
    await try_call(query_proxy.get_query_var('var1'))
    await try_call(query_proxy.get_query_vars())
    await try_call(query_proxy.set_query_var('var1', 'val1'))
    await try_call(query_proxy.create_new_conversation())
    await try_call(query_proxy.list_pipeline_knowledge_bases())
    await try_call(query_proxy.retrieve_knowledge('kb-1', 'query'))
    await try_call(query_proxy.reply(msg_chain))

    # RunnerAdminAPIProxy
    await try_call(admin.run_append_result(RunnerResult(type='content', data={'text': 'test'}, run_id='run-1')))
    await try_call(admin.run_cancel('run-1'))
    await try_call(admin.run_claim('rt-1'))
    await try_call(admin.run_renew_claim('run-1', 'rt-1', 'token-1'))
    await try_call(admin.run_release_claim('run-1', 'rt-1', 'token-1'))
    await try_call(admin.run_events_page('run-1'))
    await try_call(admin.run_finalize('run-1', 'success'))
    await try_call(admin.run_get('run-1'))
    await try_call(admin.run_list())
    await try_call(admin.run_stats())
    await try_call(admin.runner_list())
    await try_call(admin.runner_stats())
    await try_call(admin.runtime_heartbeat('rt-1'))
    await try_call(admin.runtime_list())
    await try_call(admin.runtime_reconcile())
    await try_call(admin.runtime_register('rt-1'))
    await try_call(admin.runtime_stats())

    # RunnerAPIProxy
    try:
        async with runner.reply_stream() as s:
            await s.update('chunk')
    except Exception:
        pass
    await try_call(runner.count_tokens('m-1', llm_msgs))
    await try_call(runner.get_prompt())
    await try_call(runner.history_page())
    await try_call(runner.history_search('query'))
    await try_call(runner.event_get('evt-1'))
    await try_call(runner.event_page())
    await try_call(runner.steering_pull())
    await try_call(runner.state_get('run', 'k'))
    await try_call(runner.state_set('run', 'k', 'v'))
    await try_call(runner.state_delete('run', 'k'))
    await try_call(runner.state_list('run'))

    # Box operations in 0.7.19
    for box_act, payload in [
        (PluginToRuntimeAction.BIND_BOX, {'box_id': 'b-1', 'run_id': 'run-123'}),
        (PluginToRuntimeAction.IMPORT_BOX_ATTACHMENTS, {'attachment_ids': ['att-1'], 'run_id': 'run-123'}),
        (PluginToRuntimeAction.EXPORT_BOX_FILES, {'paths': ['/p'], 'run_id': 'run-123'}),
    ]:
        await interceptor.call_action(box_act, payload)

    # 4 binary storage operations forwarded from Runtime to LangBot Core
    for stor_act, payload in [
        (
            RuntimeToLangBotAction.SET_BINARY_STORAGE,
            {'key': 'k', 'owner_type': 'plugin', 'owner': 'a/p', 'value_base64': 'dGVzdA=='},
        ),
        (RuntimeToLangBotAction.GET_BINARY_STORAGE, {'key': 'k', 'owner_type': 'plugin', 'owner': 'a/p'}),
        (RuntimeToLangBotAction.DELETE_BINARY_STORAGE, {'key': 'k', 'owner_type': 'plugin', 'owner': 'a/p'}),
        (RuntimeToLangBotAction.GET_BINARY_STORAGE_KEYS, {'owner_type': 'plugin', 'owner': 'a/p'}),
    ]:
        await interceptor.call_action(stor_act, payload)

    return recorded


def test_action_audit_and_catalog_completeness(test_host):
    """Audit that all business actions map to ExecutionAPI and transport controls stay internal."""
    operations = test_host.api.operations()
    assert len(operations) == 69
    assert len(test_host.api.catalog()) == 69

    execution_action_names = {op.action for op in operations}
    handler_actions = set(test_host.handler.actions.keys())

    # Every operation in ExecutionAPI must be provided by handler
    missing_from_handler = execution_action_names - handler_actions
    assert not missing_from_handler, f'Actions missing from handler: {missing_from_handler}'

    # Actions not in ExecutionAPI must be exactly the 6 internal actions
    non_execution_actions = handler_actions - execution_action_names
    assert non_execution_actions == NON_EXECUTION_ACTIONS, (
        f'Unexpected non-ExecutionAPI actions: {non_execution_actions - NON_EXECUTION_ACTIONS}'
    )


def test_all_69_operations_secured_through_facade(test_host):
    """Verify that every ExecutionAPI operation in handler is wrapped by the security facade."""
    operations = test_host.api.operations()
    for op in operations:
        action_fn = test_host.handler.actions.get(op.action)
        assert action_fn is not None, f'Action {op.action} not found on handler'
        assert getattr(action_fn, '_is_secured', False) is True, f'Action {op.action} is not secured'
        assert op.action in test_host.handler._raw_actions, f'Action {op.action} missing from _raw_actions'


@pytest.mark.asyncio
async def test_all_69_operations_route_through_execution_api(test_host):
    """Drive all 69 operations through handler with real SDK payloads and verify raw dispatch."""
    sdk_payloads = await _capture_sdk_payloads()
    operations = test_host.api.operations()
    assert len(sdk_payloads) == 69, f'Expected 69 SDK payloads, got {len(sdk_payloads)}'

    for op in operations:
        raw_called = False
        dummy_data = _make_dummy_output(op)

        async def mock_unary(data, *args, _d=dummy_data, **kwargs):
            nonlocal raw_called
            raw_called = True
            return ActionResponse.success(_d)

        def mock_stream(data, *args, _d=dummy_data, **kwargs):
            nonlocal raw_called
            raw_called = True

            async def gen():
                yield ActionResponse.success(_d)

            return gen()

        test_host.handler._raw_actions[op.action] = mock_stream if op.streaming else mock_unary

        payload = dict(sdk_payloads[op.action])
        payload['caller_plugin_identity'] = 'author-a/plugin-a'
        if op.scope == 'run' and 'run_id' not in payload:
            payload['run_id'] = 'run-123'

        if op.streaming:
            async for _ in test_host.handler.actions[op.action](payload):
                pass
        else:
            resp = await test_host.handler.actions[op.action](payload)
            assert resp.code == 0, f'{op.action} failed input validation: {resp.message}'

        assert raw_called is True, f'{op.action} did not call raw handler implementation'


@pytest.mark.asyncio
async def test_sdk_0_7_19_runtime_list_cursor_compatibility(test_host):
    """SDK 0.7.19 sends cursor (default None) in runtime_list calls."""
    raw_called = False

    async def raw_runtime_list(data):
        nonlocal raw_called
        raw_called = True
        return ActionResponse.success(
            {'items': [], 'next_cursor': None, 'prev_cursor': None, 'has_more': False, 'total_count': 0}
        )

    test_host.handler._raw_actions['runtime_list'] = raw_runtime_list

    resp = await test_host.handler.actions['runtime_list'](
        {
            'statuses': None,
            'labels': {},
            'cursor': None,
            'limit': 50,
            'caller_plugin_identity': 'author-a/plugin-a',
        }
    )
    assert resp.code == 0, f'runtime_list failed: {resp.message}'
    assert raw_called is True


@pytest.mark.asyncio
async def test_sdk_0_7_19_runtime_reconcile_compatibility(test_host):
    """SDK 0.7.19 sends stale_after_seconds as None by default or as float."""
    reconcile_called = False

    async def raw_reconcile(data):
        nonlocal reconcile_called
        reconcile_called = True
        return ActionResponse.success({})

    test_host.handler._raw_actions['runtime_reconcile'] = raw_reconcile

    # 1. SDK default with stale_after_seconds: None
    reconcile_called = False
    resp1 = await test_host.handler.actions['runtime_reconcile'](
        {
            'stale_after_seconds': None,
            'caller_plugin_identity': 'author-a/plugin-a',
        }
    )
    assert resp1.code == 0, f'runtime_reconcile None failed: {resp1.message}'
    assert reconcile_called is True

    # 2. SDK explicit float value 30.0
    reconcile_called = False
    resp2 = await test_host.handler.actions['runtime_reconcile'](
        {
            'stale_after_seconds': 30.0,
            'caller_plugin_identity': 'author-a/plugin-a',
        }
    )
    assert resp2.code == 0, f'runtime_reconcile 30.0 failed: {resp2.message}'
    assert reconcile_called is True


@pytest.mark.asyncio
async def test_sdk_0_7_19_query_uuid_payload_compatibility(test_host):
    """SDK 0.7.19 sends query_uuid in query-based actions."""
    mock_raw = AsyncMock(return_value=ActionResponse.success({'bot_uuid': 'bot-1'}))
    test_host.handler._raw_actions['get_bot_uuid'] = mock_raw

    # SDK 0.7.19 payload format: query_id, query_uuid, caller_plugin_identity
    resp = await test_host.handler.actions['get_bot_uuid'](
        {
            'query_id': 123,
            'query_uuid': 'query-uuid-123',
            'caller_plugin_identity': 'author-a/plugin-a',
        }
    )
    assert resp.code == 0
    assert resp.data == {'bot_uuid': 'bot-1'}


@pytest.mark.asyncio
async def test_sdk_0_7_19_model_call_payload_compatibility(test_host):
    """SDK 0.7.19 sends timeout: 120.0 and caller_plugin_identity in LLM calls."""
    mock_raw = AsyncMock(return_value=ActionResponse.success({'message': {'role': 'assistant', 'content': 'hello'}}))
    test_host.handler._raw_actions['invoke_llm'] = mock_raw

    resp = await test_host.handler.actions['invoke_llm'](
        {
            'llm_model_uuid': 'model-uuid-1',
            'messages': [{'role': 'user', 'content': 'hi'}],
            'timeout': 120.0,
            'caller_plugin_identity': 'author-a/plugin-a',
        }
    )
    assert resp.code == 0
    assert resp.data == {'message': {'role': 'assistant', 'content': 'hello'}}


@pytest.mark.asyncio
async def test_sdk_0_7_19_binary_storage_owner_payload_compatibility(test_host):
    """SDK 0.7.19 sends owner in storage actions."""
    mock_raw = AsyncMock(return_value=ActionResponse.success({}))
    test_host.handler._raw_actions['set_binary_storage'] = mock_raw

    resp = await test_host.handler.actions['set_binary_storage'](
        {
            'key': 'test_key',
            'owner_type': 'plugin',
            'owner': 'author-a/plugin-a',
            'value_base64': 'dGVzdA==',
            'caller_plugin_identity': 'author-a/plugin-a',
        }
    )
    assert resp.code == 0


@pytest.mark.asyncio
async def test_sdk_0_7_19_vector_search_null_weight_compatibility(test_host):
    """SDK 0.7.19 sends vector_weight=None in vector_search."""
    mock_raw = AsyncMock(return_value=ActionResponse.success({'results': []}))
    test_host.handler._raw_actions['vector_search'] = mock_raw

    resp = await test_host.handler.actions['vector_search'](
        {
            'collection_id': 'test_coll',
            'query_vector': [0.1, 0.2, 0.3],
            'top_k': 5,
            'vector_weight': None,
            'caller_plugin_identity': 'author-a/plugin-a',
        }
    )
    assert resp.code == 0
    assert resp.data == {'results': []}


@pytest.mark.asyncio
async def test_sdk_0_7_19_call_tool_parameters_and_session_compatibility(test_host):
    """SDK 0.7.19 sends tool_parameters and session in call_tool."""
    mock_raw = AsyncMock(return_value=ActionResponse.success({'result': 'tool-result'}))
    test_host.handler._raw_actions['call_tool'] = mock_raw

    resp = await test_host.handler.actions['call_tool'](
        {
            'tool_name': 'test_tool',
            'parameters': {'arg1': 'val1'},
            'session': {'id': 'sess-1'},
            'caller_plugin_identity': 'author-a/plugin-a',
        }
    )
    assert resp.code == 0
    assert resp.data == {'result': 'tool-result'}


@pytest.mark.asyncio
async def test_run_scoped_action_missing_run_id_returns_run_id_is_required(test_host):
    """When a run-scoped action is called from handler without run_id, error message is 'run_id is required'."""
    resp = await test_host.handler.actions['state_get']({'scope': 'conversation', 'key': 'test_key'})
    assert resp.code != 0
    assert 'run_id is required' in resp.message
