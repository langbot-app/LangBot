from __future__ import annotations

import asyncio
import contextlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction
from langbot_plugin.entities.io.context import ActionContext, InstallationBinding, PluginWorkerPolicy, RuntimeIdentity
from langbot_plugin.entities.io.resp import ActionResponse
from langbot_plugin.runtime.io.connection import Connection

from langbot.pkg.plugin.handler import RuntimeConnectionHandler
from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.persistence.mgr import PersistenceManager, PersistenceMode


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
        deployment=SimpleNamespace(mode='cloud'),
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
    )
    installation_context = InstallationBinding(
        **context.model_dump(exclude_none=True),
        installation_uuid='00000000-0000-4000-8000-000000000001',
        runtime_revision=1,
        artifact_digest='a' * 64,
    )
    runtime_handler.register_installation_binding(
        installation_context,
        plugin_author='author-a',
        plugin_name='plugin-a',
    )
    return runtime_handler, app, installation_context


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

    with pytest.raises(ValueError, match='trusted Workspace context'):
        await runtime_handler.actions[PluginToRuntimeAction.GET_LANGBOT_VERSION.value]({})


@pytest.mark.asyncio
async def test_runtime_action_enters_trusted_workspace_scope():
    runtime_handler, app, installation_context = make_handler()
    scope_events: list[tuple[str, str]] = []

    @contextlib.asynccontextmanager
    async def tenant_scope(workspace_uuid: str):
        scope_events.append(('enter', workspace_uuid))
        try:
            yield SimpleNamespace()
        finally:
            scope_events.append(('exit', workspace_uuid))

    class RecordingPersistenceManager:
        def __init__(self, execute_async):
            self.execute_async = execute_async

        def tenant_scope(self, workspace_uuid: str):
            return tenant_scope(workspace_uuid)

    app.persistence_mgr = RecordingPersistenceManager(app.persistence_mgr.execute_async)

    response = await invoke_with_context(
        runtime_handler,
        installation_context,
        PluginToRuntimeAction.GET_LANGBOT_VERSION,
        {},
    )

    assert response.code == 0
    assert scope_events == [('enter', 'workspace-a'), ('exit', 'workspace-a')]


@pytest.mark.asyncio
async def test_blocked_llm_provider_does_not_hold_tenant_database_session():
    entered = asyncio.Event()
    release = asyncio.Event()
    observations: list[bool] = []
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    manager.db = SimpleNamespace(get_engine=lambda: engine)
    runtime_handler, app, installation_context = make_handler()
    app.persistence_mgr = manager

    async def invoke_llm(**_kwargs):
        observations.append(manager.current_session() is None)
        entered.set()
        await release.wait()
        observations.append(manager.current_session() is None)
        return SimpleNamespace(model_dump=lambda: {'role': 'assistant', 'content': 'ok'})

    app.model_mgr = SimpleNamespace(
        get_model_by_uuid=AsyncMock(
            return_value=SimpleNamespace(
                model_entity=SimpleNamespace(workspace_uuid='workspace-a'),
                provider=SimpleNamespace(invoke_llm=invoke_llm),
            )
        )
    )
    runtime_handler._require_plugin_action_context = AsyncMock(return_value=(installation_context, SimpleNamespace()))
    runtime_handler._require_active_action_context = AsyncMock()
    runtime_handler._resource_exists = AsyncMock(return_value=True)

    action = asyncio.create_task(
        invoke_with_context(
            runtime_handler,
            installation_context,
            PluginToRuntimeAction.INVOKE_LLM,
            {
                'llm_model_uuid': 'model-a',
                'messages': [],
            },
        )
    )
    try:
        await entered.wait()
        assert observations == [True]
        release.set()
        response = await action
        assert response.code == 0
        assert observations == [True, True]
    finally:
        release.set()
        if not action.done():
            await action
        await engine.dispose()


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


def test_runtime_connection_is_instance_scoped_and_unbound():
    runtime_handler, _app, _installation_context = make_handler()
    assert runtime_handler.bound_action_context is None


def test_inbound_tenant_action_requires_complete_installation_envelope():
    runtime_handler, _app, installation_context = make_handler()

    assert (
        runtime_handler.validate_inbound_action_context(
            PluginToRuntimeAction.GET_BOTS.value,
            installation_context,
        )
        == installation_context
    )
    with pytest.raises(ValueError, match='complete InstallationBinding'):
        runtime_handler.validate_inbound_action_context(
            PluginToRuntimeAction.GET_BOTS.value,
            workspace_context('workspace-b').for_installation('installation-b'),
        )


@pytest.mark.asyncio
async def test_legacy_oss_worker_capability_remains_usable_after_identity_migration():
    runtime_handler, app, installation_context = make_handler()
    app.deployment = SimpleNamespace(mode='oss')
    setting = SimpleNamespace(
        plugin_author='author-a',
        plugin_name='plugin-a',
        installation_uuid=installation_context.installation_uuid,
        runtime_revision=installation_context.runtime_revision,
        artifact_digest=installation_context.artifact_digest,
    )
    result = Mock()
    result.first.return_value = setting
    app.persistence_mgr.execute_async.return_value = result
    legacy_context = workspace_context().for_installation(installation_context.installation_uuid)

    assert (
        runtime_handler.validate_inbound_action_context(
            PluginToRuntimeAction.GET_LANGBOT_VERSION.value,
            legacy_context,
        )
        == legacy_context
    )
    response = await invoke_with_context(
        runtime_handler,
        legacy_context,
        PluginToRuntimeAction.GET_LANGBOT_VERSION,
        {},
    )

    assert response.code == 0


def test_installation_uuid_cannot_move_between_workspaces():
    runtime_handler, _app, binding = make_handler()
    moved = binding.model_copy(update={'workspace_uuid': 'workspace-b', 'runtime_revision': 2})

    with pytest.raises(ValueError, match='cannot move between Workspaces'):
        runtime_handler.register_installation_binding(
            moved,
            plugin_author='author-a',
            plugin_name='plugin-a',
        )


@pytest.mark.asyncio
async def test_newer_revision_fences_old_binding():
    runtime_handler, _app, binding = make_handler()
    newer = binding.model_copy(update={'runtime_revision': 2, 'artifact_digest': 'b' * 64})
    runtime_handler.register_installation_binding(
        newer,
        plugin_author='author-a',
        plugin_name='plugin-a',
    )
    with pytest.raises(ValueError, match='revision or artifact is stale'):
        await runtime_handler._resolve_installation_identity(binding)


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
    connection = RecordingConnection()
    runtime_handler = RuntimeConnectionHandler(
        connection,
        AsyncMock(return_value=True),
        app,
    )

    task = asyncio.create_task(
        runtime_handler.set_runtime_config(
            runtime_identity=RuntimeIdentity(instance_uuid='instance-a', runtime_id='runtime-a'),
            worker_policy=PluginWorkerPolicy(
                max_cpus=1.0,
                max_memory_mb=256,
                max_pids=32,
                max_open_files=64,
                max_file_size_mb=128,
            ),
            runtime_profile='oss_dev',
            cloud_service_url=None,
        )
    )
    for _ in range(10):
        if connection.sent:
            break
        await asyncio.sleep(0)
    request = json.loads(connection.sent[0])
    runtime_handler.resp_waiters[request['seq_id']].set_result(ActionResponse.success({}))
    await task

    assert request['data']['runtime_identity'] == {
        'instance_uuid': 'instance-a',
        'runtime_id': 'runtime-a',
    }
    assert request.get('context') is None
