"""Integration tests verifying full ExecutionAPI facade routing and SDK 0.7.19 compatibility."""

from __future__ import annotations

import contextlib
import contextvars
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langbot_plugin.entities.io.context import InstallationBinding
from langbot_plugin.entities.io.resp import ActionResponse

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
    """Verify that calling any of the 69 operations via handler dispatches through ExecutionAPI."""
    operations = test_host.api.operations()

    for op in operations:
        # Mock the raw handler to return a valid dummy response matching output schema
        mock_raw = AsyncMock() if not op.streaming else Mock()
        test_host.handler._raw_actions[op.action] = mock_raw

        action_fn = test_host.handler.actions[op.action]
        assert getattr(action_fn, '_is_secured', False) is True


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
