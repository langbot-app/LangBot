from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction
from langbot_plugin.entities.io.context import ActionContext
from langbot_plugin.entities.io.resp import ActionResponse
from langbot_plugin.runtime.io.connection import Connection

from langbot.pkg.plugin.handler import RuntimeConnectionHandler
from langbot.pkg.api.http.context import ExecutionContext


class EmptyResult:
    def first(self):
        return None

    def all(self):
        return []


class RecordingConnection(Connection):
    def __init__(self):
        self.sent: list[str] = []

    async def send(self, message: str) -> None:
        self.sent.append(message)

    async def receive(self) -> str:
        raise NotImplementedError

    async def close(self) -> None:
        return None


def workspace_context(workspace_uuid: str = 'workspace-a') -> ActionContext:
    return ActionContext(
        instance_uuid='instance-a',
        workspace_uuid=workspace_uuid,
        placement_generation=7,
    )


def make_handler(workspace_uuid: str = 'workspace-a'):
    context = workspace_context(workspace_uuid)
    app = SimpleNamespace(
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock(return_value=EmptyResult())),
        logger=Mock(),
        workspace_service=SimpleNamespace(
            get_execution_binding=AsyncMock(
                return_value=SimpleNamespace(
                    instance_uuid=context.instance_uuid,
                    workspace_uuid=context.workspace_uuid,
                    placement_generation=context.placement_generation,
                )
            )
        ),
    )
    runtime_handler = RuntimeConnectionHandler(
        Mock(),
        AsyncMock(return_value=True),
        app,
        context,
    )
    installation_uuid = runtime_handler._remember_installation(
        context,
        'author-a',
        'plugin-a',
    )
    return runtime_handler, app, context.for_installation(installation_uuid)


async def invoke_with_context(
    runtime_handler: RuntimeConnectionHandler,
    action_context: ActionContext,
    action: PluginToRuntimeAction,
    data: dict,
):
    token = runtime_handler._current_action_context.set(action_context)
    try:
        return await runtime_handler.actions[action.value](data)
    finally:
        runtime_handler._current_action_context.reset(token)


@pytest.mark.asyncio
async def test_plugin_action_requires_installation_capability():
    runtime_handler, _app, _installation_context = make_handler()

    with pytest.raises(ValueError, match='missing installation_uuid'):
        await runtime_handler.actions[PluginToRuntimeAction.GET_LANGBOT_VERSION.value]({})


@pytest.mark.asyncio
async def test_plugin_action_rejects_forged_installation_capability():
    runtime_handler, _app, installation_context = make_handler()
    forged = installation_context.model_copy(update={'installation_uuid': 'forged-installation'})

    with pytest.raises(
        ValueError,
        match='installation is not registered in this Workspace',
    ):
        await invoke_with_context(
            runtime_handler,
            forged,
            PluginToRuntimeAction.GET_LANGBOT_VERSION,
            {},
        )


@pytest.mark.asyncio
async def test_plugin_action_rejects_stale_workspace_generation():
    runtime_handler, app, installation_context = make_handler()
    app.workspace_service.get_execution_binding.side_effect = ValueError('generation is fenced')

    with pytest.raises(ValueError, match='generation is fenced'):
        await invoke_with_context(
            runtime_handler,
            installation_context,
            PluginToRuntimeAction.GET_LANGBOT_VERSION,
            {},
        )

    app.workspace_service.get_execution_binding.assert_awaited_once_with(
        'workspace-a',
        expected_generation=7,
    )


@pytest.mark.asyncio
async def test_query_uuid_and_forged_payload_workspace_cannot_cross_tenants():
    runtime_handler, app, installation_context = make_handler()
    query_a = SimpleNamespace(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=7,
        bot_uuid='bot-a',
    )
    query_b = SimpleNamespace(
        instance_uuid='instance-a',
        workspace_uuid='workspace-b',
        placement_generation=7,
        bot_uuid='bot-b',
    )

    async def get_query(workspace_uuid, query_uuid):
        return {
            ('workspace-a', 'query-a'): query_a,
            ('workspace-b', 'query-b'): query_b,
        }.get((workspace_uuid, query_uuid))

    app.query_pool = SimpleNamespace(
        get_query=AsyncMock(side_effect=get_query),
        get_query_by_legacy_id=AsyncMock(),
    )

    response = await invoke_with_context(
        runtime_handler,
        installation_context,
        PluginToRuntimeAction.GET_BOT_UUID,
        {
            'query_id': 2,
            'query_uuid': 'query-b',
            'workspace_uuid': 'workspace-b',
        },
    )

    assert response.code != 0
    app.query_pool.get_query.assert_awaited_once_with('workspace-a', 'query-b')


@pytest.mark.asyncio
async def test_legacy_query_id_fallback_is_workspace_scoped():
    runtime_handler, app, installation_context = make_handler()
    query = SimpleNamespace(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=7,
        bot_uuid='bot-a',
    )
    app.query_pool = SimpleNamespace(
        get_query=AsyncMock(),
        get_query_by_legacy_id=AsyncMock(return_value=query),
    )

    response = await invoke_with_context(
        runtime_handler,
        installation_context,
        PluginToRuntimeAction.GET_BOT_UUID,
        {'query_id': 19},
    )

    assert response.code == 0
    assert response.data == {'bot_uuid': 'bot-a'}
    app.query_pool.get_query_by_legacy_id.assert_awaited_once_with(
        'workspace-a',
        19,
    )


def test_runtime_connection_rejects_workspace_rebinding():
    runtime_handler, _app, _installation_context = make_handler()

    with pytest.raises(ValueError, match='another Workspace'):
        runtime_handler.bind_action_context(workspace_context('workspace-b'))


def test_inbound_installation_envelope_is_preserved_only_inside_bound_workspace():
    runtime_handler, _app, installation_context = make_handler()

    assert (
        runtime_handler.validate_inbound_action_context(
            PluginToRuntimeAction.GET_BOTS.value,
            installation_context,
        )
        == installation_context
    )
    with pytest.raises(ValueError, match='does not match connection Workspace'):
        runtime_handler.validate_inbound_action_context(
            PluginToRuntimeAction.GET_BOTS.value,
            workspace_context('workspace-b').for_installation('installation-b'),
        )


def test_installation_uuid_is_stable_and_workspace_specific():
    context_a = workspace_context('workspace-a')
    context_b = workspace_context('workspace-b')

    first = RuntimeConnectionHandler.derive_installation_uuid(
        context_a,
        'author-a',
        'plugin-a',
    )
    repeated = RuntimeConnectionHandler.derive_installation_uuid(
        context_a,
        'author-a',
        'plugin-a',
    )
    other_workspace = RuntimeConnectionHandler.derive_installation_uuid(
        context_b,
        'author-a',
        'plugin-a',
    )

    assert first == repeated
    assert first != other_workspace


@pytest.mark.asyncio
async def test_plugin_vector_action_forwards_trusted_context_and_logical_collection():
    runtime_handler, app, installation_context = make_handler()
    app.rag_runtime_service = SimpleNamespace(vector_upsert=AsyncMock())

    response = await invoke_with_context(
        runtime_handler,
        installation_context,
        PluginToRuntimeAction.VECTOR_UPSERT,
        {
            'workspace_uuid': 'workspace-forged',
            'collection_id': 'plugin-supplied-name',
            'vectors': [[0.1]],
            'ids': ['point-a'],
        },
    )

    assert response.code == 0
    execution_context = app.rag_runtime_service.vector_upsert.await_args.args[0]
    assert execution_context == ExecutionContext(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=7,
    )
    assert app.rag_runtime_service.vector_upsert.await_args.args[1] == 'plugin-supplied-name'


@pytest.mark.asyncio
async def test_host_to_runtime_action_carries_trusted_connector_context():
    app = SimpleNamespace(logger=Mock())
    context = workspace_context()
    connection = RecordingConnection()
    runtime_handler = RuntimeConnectionHandler(
        connection,
        AsyncMock(return_value=True),
        app,
        context,
    )

    task = asyncio.create_task(runtime_handler.set_runtime_config(None))
    for _ in range(10):
        if connection.sent:
            break
        await asyncio.sleep(0)
    request = json.loads(connection.sent[0])
    runtime_handler.resp_waiters[request['seq_id']].set_result(ActionResponse.success({}))
    await task

    assert request['data'] == {}
    assert request['context'] == context.model_dump(exclude_none=True)
