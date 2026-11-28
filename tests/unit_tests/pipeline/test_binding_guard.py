from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.api.http.service.pipeline import default_stage_order
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.pipeline import LegacyPipeline
from langbot.pkg.entity.persistence.workspace import Workspace, WorkspaceExecutionState
from langbot.pkg.message_policy.manager import MessagePolicyManager
from langbot.pkg.pipeline import entities as pipeline_entities
from langbot.pkg.pipeline.binding_guard import (
    anext_tracking_suspension,
    await_tracking_suspension,
    ensure_execution_binding_active,
    execution_binding_scope,
)
from langbot.pkg.pipeline.controller import Controller
from langbot.pkg.pipeline.pipelinemgr import PipelineManager, StageInstContainer
from langbot.pkg.pipeline.pool import QueryPool
from langbot.pkg.workspace import WorkspaceService
from langbot.pkg.workspace.errors import (
    WorkspaceExecutionUnavailableError,
    WorkspaceGenerationMismatchError,
)
from langbot_plugin.api.entities.builtin.provider import message as provider_message
from langbot_plugin.api.entities.builtin.provider import prompt as provider_prompt
from langbot_plugin.api.entities.builtin.provider import session as provider_session
from langbot_plugin.api.entities.context import EventContext

from tests.factories import mock_platform_adapter, text_query
from tests.factories.platform import FakePlatform


def _default_pipeline_config() -> dict:
    return {
        'trigger': {
            'misc': {'combine-quote-message': False, 'ignore-prefix': []},
            'access-control': {'mode': 'blacklist', 'blacklist': [], 'whitelist': []},
            'group-respond-rules': {'at': True, 'prefix': [], 'regexp': [], 'random': 0.0},
        },
        'safety': {
            'content-filter': {'scope': 'all', 'filters': []},
            'rate-limit': {
                'enabled': False,
                'algo': 'fixwin',
                'limitation': 20,
                'window-length': 60,
                'strategy': 'drop',
            },
        },
        'speech': {
            'speech-recognition': {'enable': False},
            'text-to-speech': {'enable': False},
        },
        'ai': {
            'runner': {'id': 'plugin:langbot-team/LocalAgent/default', 'expire-time': 0},
            'runner_config': {
                'plugin:langbot-team/LocalAgent/default': {
                    'model': {'primary': 'test-model', 'fallbacks': []},
                    'prompt': 'default',
                    'tools': [],
                }
            },
        },
        'output': {
            'misc': {
                'quote-origin': False,
                'at-sender': False,
                'track-function-calls': False,
                'force-delay': [0, 0],
            },
            'long-text-processing': {'strategy': 'none', 'threshold': 4096},
        },
    }


async def _build_sqlite_pipeline_harness(
    tmp_path,
    *,
    outputs: list,
    stream: bool = False,
    emit_hook=None,
    runner_hook=None,
    with_monitoring_adapter_hook: bool = True,
    extensions_preferences: dict | None = None,
):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "pipeline_guard.db"}')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    ap = SimpleNamespace()
    ap.logger = Mock()
    ap.instance_config = SimpleNamespace(data={'concurrency': {'pipeline': 4}, 'system': {'response_limits': {}}})
    ap.deployment = SimpleNamespace(mode='oss')
    ap.persistence_mgr = SimpleNamespace(
        get_db_engine=lambda: engine,
        mode=SimpleNamespace(value='oss'),
        execute_async=AsyncMock(return_value=Mock(all=Mock(return_value=[]))),
        current_session=lambda: None,
    )
    ws_service = WorkspaceService(ap, instance_uuid='inst-1')
    ws = await ws_service.ensure_singleton_workspace()
    ap.workspace_service = ws_service

    binding_calls: list[tuple] = []
    orig_get = ws_service.get_execution_binding

    async def counted_get(*args, **kwargs):
        binding_calls.append((args, kwargs))
        return await orig_get(*args, **kwargs)

    ws_service.get_execution_binding = counted_get

    ap.message_policy_mgr = MessagePolicyManager(ap)
    ap.platform_mgr = SimpleNamespace(find_runtime_bot=Mock(return_value=None))
    ap.bot_service = SimpleNamespace(get_bot=AsyncMock(return_value={'name': 'TestBot'}))
    ap.monitoring_service = SimpleNamespace(
        record_message=AsyncMock(return_value='msg-1'),
        update_message_status=AsyncMock(),
        record_error=AsyncMock(),
        record_policy_event=AsyncMock(),
    )
    ap.telemetry = SimpleNamespace(start_send_task=AsyncMock())
    ap.survey = None
    ap.skill_mgr = None
    ap.runner_registry = SimpleNamespace(get=AsyncMock(return_value=None))

    conv = provider_session.Conversation(
        prompt=provider_prompt.Prompt(name='default', messages=[]),
        messages=[],
        pipeline_uuid='pipe-1',
        bot_uuid='bot-1',
        uuid='conv-1',
    )

    def make_session(launcher_id: str = 'u1'):
        sess = provider_session.Session(
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=launcher_id,
            sender_id=launcher_id,
        )
        sess._semaphore = asyncio.Semaphore(1)
        return sess

    sessions_by_launcher: dict[str, provider_session.Session] = {}

    async def get_sess(query):
        launcher_id = str(query.launcher_id)
        sess = sessions_by_launcher.get(launcher_id)
        if sess is None:
            sess = make_session(launcher_id)
            sessions_by_launcher[launcher_id] = sess
        ctx = query._execution_context
        sess.instance_uuid = ctx.instance_uuid
        sess.workspace_uuid = ctx.workspace_uuid
        sess.placement_generation = ctx.placement_generation
        sess.bot_uuid = query.bot_uuid
        return sess

    ap.sess_mgr = SimpleNamespace(
        get_session=AsyncMock(side_effect=get_sess),
        get_conversation=AsyncMock(return_value=conv),
    )
    model = SimpleNamespace(model_entity=SimpleNamespace(uuid='test-model', name='m', abilities=['func_call']))
    ap.model_mgr = SimpleNamespace(get_model_by_uuid=AsyncMock(return_value=model))
    ap.tool_mgr = SimpleNamespace(get_resolved_tool_catalog=AsyncMock(return_value=[]))

    async def fake_emit(event, bound_plugins=None):
        await asyncio.sleep(0)
        if emit_hook is not None:
            await emit_hook(event, bound_plugins)
        return EventContext.model_validate(EventContext.from_event(event).model_dump())

    ap.plugin_connector = SimpleNamespace(emit_event=AsyncMock(side_effect=fake_emit))

    async def fake_run_from_query(query):
        for out in outputs:
            await asyncio.sleep(0)
            if runner_hook is not None:
                await runner_hook(query, out)
            yield out

    ap.agent_run_orchestrator = SimpleNamespace(
        try_claim_steering_from_query=AsyncMock(return_value=False),
        run_from_query=fake_run_from_query,
        resolve_runner_id_for_telemetry=Mock(return_value='plugin:langbot-team/LocalAgent/default'),
    )
    ap.query_pool = QueryPool()

    ctx = ExecutionContext(
        instance_uuid='inst-1',
        workspace_uuid=ws.uuid,
        placement_generation=1,
        pipeline_uuid='pipe-1',
    )
    pipeline_mgr = PipelineManager(ap)
    await pipeline_mgr.initialize()
    entity = LegacyPipeline(
        uuid='pipe-1',
        workspace_uuid=ws.uuid,
        name='GuardTestPipeline',
        description='',
        for_version='4.11.9',
        stages=list(default_stage_order),
        config=_default_pipeline_config(),
        is_default=True,
        extensions_preferences=extensions_preferences
        or {'enable_all_plugins': True, 'enable_all_mcp_servers': True, 'plugins': [], 'mcp_servers': []},
    )
    await pipeline_mgr.load_pipeline(ctx, entity)
    ap.pipeline_mgr = pipeline_mgr

    binding_calls.clear()
    selects: list[str] = []
    sqlalchemy.event.listen(
        engine.sync_engine,
        'before_cursor_execute',
        lambda _c, _cur, stmt, *_a: selects.append(stmt) if stmt.lstrip().upper().startswith('SELECT') else None,
    )

    def build_query(query_uuid: str = 'q-1', launcher_id: str = 'u1', generation: int = 1):
        platform = FakePlatform(stream_output_supported=stream)
        adapter = mock_platform_adapter(platform)
        adapter.create_message_card = AsyncMock()
        if with_monitoring_adapter_hook:
            adapter.on_monitoring_message_created = AsyncMock()
        elif hasattr(adapter, 'on_monitoring_message_created'):
            delattr(adapter, 'on_monitoring_message_created')
        q_ctx = ExecutionContext(
            instance_uuid='inst-1',
            workspace_uuid=ws.uuid,
            placement_generation=generation,
            pipeline_uuid='pipe-1',
        )
        query = text_query(
            'hello',
            pipeline_config=_default_pipeline_config(),
            pipeline_uuid='pipe-1',
            bot_uuid='bot-1',
            workspace_uuid=ws.uuid,
            instance_uuid='inst-1',
            placement_generation=generation,
        )
        query.launcher_id = launcher_id
        query.sender_id = launcher_id
        query.query_uuid = query_uuid
        query.resp_messages = []
        query.resp_message_chain = []
        query.adapter = adapter
        query._execution_context = q_ctx
        sess = make_session(launcher_id)
        sessions_by_launcher[launcher_id] = sess
        return query, sess, adapter

    return SimpleNamespace(
        ap=ap,
        engine=engine,
        workspace=ws,
        ctx=ctx,
        binding_calls=binding_calls,
        selects=selects,
        build_query=build_query,
    )


@pytest.mark.asyncio
async def test_full_default_pipeline_reduces_binding_checks_single_turn(tmp_path):
    harness = await _build_sqlite_pipeline_harness(
        tmp_path,
        outputs=[provider_message.Message(role='assistant', content='LANGBOT_CHAT_OK')],
        stream=False,
    )
    try:
        query, session, adapter = harness.build_query()
        await session._semaphore.acquire()
        await Controller(harness.ap)._process_query(query, selected_session=session)

        assert adapter.reply_message.await_count == 1
        assert not query.variables.get('_monitoring_has_error')
        # Baseline on master before #2709 was 31 binding checks (32 SQL SELECTs).
        assert len(harness.binding_calls) == 13
        assert len(harness.selects) == 14
    finally:
        await harness.engine.dispose()


@pytest.mark.asyncio
async def test_full_default_pipeline_reduces_binding_checks_streaming_chunks(tmp_path):
    chunks = [
        provider_message.MessageChunk(
            role='assistant',
            content=f'chunk-{index}',
            all_content=f'chunk-{index}',
            is_final=(index == 4),
        )
        for index in range(5)
    ]
    harness = await _build_sqlite_pipeline_harness(tmp_path, outputs=chunks, stream=True)
    try:
        query, session, adapter = harness.build_query()
        await session._semaphore.acquire()
        await Controller(harness.ap)._process_query(query, selected_session=session)

        assert adapter.reply_message_chunk.await_count == 5
        assert not query.variables.get('_monitoring_has_error')
        # Baseline on master before #2709 was 75 binding checks (76 SQL SELECTs).
        assert len(harness.binding_calls) == 25
        assert len(harness.selects) == 26
    finally:
        await harness.engine.dispose()


@pytest.mark.asyncio
async def test_controller_handoff_shares_binding_check_but_standalone_lookup_still_checks(tmp_path):
    harness = await _build_sqlite_pipeline_harness(
        tmp_path,
        outputs=[provider_message.Message(role='assistant', content='ok')],
        stream=False,
    )
    try:
        pipeline = await harness.ap.pipeline_mgr.get_pipeline_by_uuid(harness.ctx, 'pipe-1')
        assert pipeline is not None
        assert len(harness.binding_calls) == 1

        # A second standalone lookup outside a request scope must still revalidate.
        pipeline_again = await harness.ap.pipeline_mgr.get_pipeline_by_uuid(harness.ctx, 'pipe-1')
        assert pipeline_again is not None
        assert len(harness.binding_calls) == 2
    finally:
        await harness.engine.dispose()


@pytest.mark.asyncio
async def test_sequential_requests_never_reuse_binding_lease_after_write_fence(tmp_path):
    harness = await _build_sqlite_pipeline_harness(
        tmp_path,
        outputs=[provider_message.Message(role='assistant', content='first-ok')],
        stream=False,
    )
    try:
        controller = Controller(harness.ap)
        query1, session1, adapter1 = harness.build_query(query_uuid='q-1', launcher_id='u1')
        await session1._semaphore.acquire()
        await controller._process_query(query1, selected_session=session1)
        assert adapter1.reply_message.await_count == 1
        events_after_q1 = harness.ap.plugin_connector.emit_event.await_count
        assert events_after_q1 == 4

        # Fence the Workspace in SQLite between requests.
        async with harness.engine.begin() as conn:
            await conn.execute(
                sqlalchemy.update(WorkspaceExecutionState)
                .where(WorkspaceExecutionState.workspace_uuid == harness.workspace.uuid)
                .values(write_fenced=True)
            )

        query2, session2, adapter2 = harness.build_query(query_uuid='q-2', launcher_id='u2')
        await session2._semaphore.acquire()
        await controller._process_query(query2, selected_session=session2)

        adapter2.reply_message.assert_not_awaited()
        assert harness.ap.plugin_connector.emit_event.await_count == events_after_q1
    finally:
        await harness.engine.dispose()


@pytest.mark.asyncio
async def test_mid_flight_write_fence_during_runner_blocks_outbound_delivery(tmp_path):
    harness_holder: dict[str, object] = {}

    async def fence_during_runner(_query, _out):
        harness = harness_holder['harness']
        async with harness.engine.begin() as conn:
            await conn.execute(
                sqlalchemy.update(WorkspaceExecutionState)
                .where(WorkspaceExecutionState.workspace_uuid == harness.workspace.uuid)
                .values(write_fenced=True)
            )

    harness = await _build_sqlite_pipeline_harness(
        tmp_path,
        outputs=[provider_message.Message(role='assistant', content='must-not-send')],
        stream=False,
        runner_hook=fence_during_runner,
    )
    harness_holder['harness'] = harness
    try:
        query, session, adapter = harness.build_query()
        await session._semaphore.acquire()
        await Controller(harness.ap)._process_query(query, selected_session=session)

        adapter.reply_message.assert_not_awaited()
        assert query.variables.get('_monitoring_has_error') is True
    finally:
        await harness.engine.dispose()


@pytest.mark.asyncio
async def test_mid_flight_generation_bump_during_response_wrapper_blocks_send(tmp_path):
    harness_holder: dict[str, object] = {}

    async def bump_on_normal_message_responded(event, _bound_plugins):
        if type(event).__name__ == 'NormalMessageResponded':
            harness = harness_holder['harness']
            async with harness.engine.begin() as conn:
                await conn.execute(
                    sqlalchemy.update(WorkspaceExecutionState)
                    .where(WorkspaceExecutionState.workspace_uuid == harness.workspace.uuid)
                    .values(active_generation=2)
                )

    harness = await _build_sqlite_pipeline_harness(
        tmp_path,
        outputs=[provider_message.Message(role='assistant', content='must-not-send')],
        stream=False,
        emit_hook=bump_on_normal_message_responded,
    )
    harness_holder['harness'] = harness
    try:
        query, session, adapter = harness.build_query()
        await session._semaphore.acquire()
        await Controller(harness.ap)._process_query(query, selected_session=session)

        adapter.reply_message.assert_not_awaited()
        assert query.variables.get('_monitoring_has_error') is True
    finally:
        await harness.engine.dispose()


@pytest.mark.asyncio
async def test_mid_flight_workspace_deactivation_during_preproc_blocks_runner(tmp_path):
    harness_holder: dict[str, object] = {}
    runner_entered = False

    async def deactivate_on_prompt_preproc(event, _bound_plugins):
        if type(event).__name__ == 'PromptPreProcessing':
            harness = harness_holder['harness']
            async with harness.engine.begin() as conn:
                await conn.execute(
                    sqlalchemy.update(Workspace)
                    .where(Workspace.uuid == harness.workspace.uuid)
                    .values(status='disabled')
                )

    async def track_runner(_query, _out):
        nonlocal runner_entered
        runner_entered = True

    harness = await _build_sqlite_pipeline_harness(
        tmp_path,
        outputs=[provider_message.Message(role='assistant', content='blocked')],
        stream=False,
        emit_hook=deactivate_on_prompt_preproc,
        runner_hook=track_runner,
    )
    harness_holder['harness'] = harness
    try:
        query, session, adapter = harness.build_query()
        await session._semaphore.acquire()
        await Controller(harness.ap)._process_query(query, selected_session=session)

        assert runner_entered is False
        adapter.reply_message.assert_not_awaited()
        assert query.variables.get('_monitoring_has_error') is True
    finally:
        await harness.engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_requests_isolate_leases_and_reject_after_concurrent_fence(tmp_path):
    task_a_in_runner = asyncio.Event()
    release_task_a = asyncio.Event()

    async def pause_task_a(query, _out):
        if query.query_uuid == 'q-a':
            task_a_in_runner.set()
            await release_task_a.wait()

    harness = await _build_sqlite_pipeline_harness(
        tmp_path,
        outputs=[provider_message.Message(role='assistant', content='concurrent-reply')],
        stream=False,
        runner_hook=pause_task_a,
    )
    try:
        controller = Controller(harness.ap)
        query_a, session_a, adapter_a = harness.build_query(query_uuid='q-a', launcher_id='user-a')
        query_b, session_b, adapter_b = harness.build_query(query_uuid='q-b', launcher_id='user-b')
        await session_a._semaphore.acquire()
        await session_b._semaphore.acquire()

        task_a = asyncio.create_task(controller._process_query(query_a, selected_session=session_a))
        await asyncio.wait_for(task_a_in_runner.wait(), timeout=2)

        # Concurrently fence the workspace while Task A is in flight.
        async with harness.engine.begin() as conn:
            await conn.execute(
                sqlalchemy.update(WorkspaceExecutionState)
                .where(WorkspaceExecutionState.workspace_uuid == harness.workspace.uuid)
                .values(write_fenced=True)
            )

        # Task B starts concurrently and must fail immediately at controller entry.
        await controller._process_query(query_b, selected_session=session_b)
        adapter_b.reply_message.assert_not_awaited()

        # Release Task A; it must detect the fence before sending any reply.
        release_task_a.set()
        await asyncio.wait_for(task_a, timeout=2)
        adapter_a.reply_message.assert_not_awaited()
        assert query_a.variables.get('_monitoring_has_error') is True
    finally:
        await harness.engine.dispose()


@pytest.mark.asyncio
async def test_spawned_child_task_cannot_inherit_parent_binding_lease():
    get_binding = AsyncMock(
        return_value=SimpleNamespace(
            instance_uuid='inst-1',
            workspace_uuid='ws-1',
            placement_generation=1,
        )
    )
    ap = SimpleNamespace(workspace_service=SimpleNamespace(get_execution_binding=get_binding))
    ctx = ExecutionContext(instance_uuid='inst-1', workspace_uuid='ws-1', placement_generation=1)

    with execution_binding_scope():
        await ensure_execution_binding_active(ap, ctx)
        assert get_binding.await_count == 1
        # Same task reuses the active lease.
        await ensure_execution_binding_active(ap, ctx)
        assert get_binding.await_count == 1

        # A child task inherits the ContextVar copy, but must NEVER reuse the parent's lease.
        async def child():
            await ensure_execution_binding_active(ap, ctx)

        await asyncio.create_task(child())
        assert get_binding.await_count == 2


@pytest.mark.asyncio
async def test_unflushed_session_fence_and_generation_changes_bypass_lease_immediately(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "session_bypass.db"}')
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        active_session = None
        ap = SimpleNamespace(
            persistence_mgr=SimpleNamespace(
                get_db_engine=lambda: engine,
                current_session=lambda: active_session,
            )
        )
        service = WorkspaceService(ap, instance_uuid='inst-1')
        workspace = await service.ensure_singleton_workspace()
        ap.workspace_service = service
        ctx = ExecutionContext(
            instance_uuid='inst-1',
            workspace_uuid=workspace.uuid,
            placement_generation=1,
        )

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            active_session = session
            state = (
                await session.execute(
                    sqlalchemy.select(WorkspaceExecutionState).where(
                        WorkspaceExecutionState.workspace_uuid == workspace.uuid
                    )
                )
            ).scalar_one()

            # Route service calls through this active SQLAlchemy Session.
            orig_get = service.get_execution_binding
            ap.workspace_service = SimpleNamespace(
                get_execution_binding=lambda ws_uuid, expected_generation=None: orig_get(
                    ws_uuid,
                    expected_generation=expected_generation,
                    session=session,
                )
            )

            with execution_binding_scope():
                await ensure_execution_binding_active(ap, ctx)

                # Unflushed ORM fence change inside the same Session must reject immediately.
                state.write_fenced = True
                with pytest.raises(WorkspaceExecutionUnavailableError):
                    await ensure_execution_binding_active(ap, ctx)

                state.write_fenced = False
                await ensure_execution_binding_active(ap, ctx)

                # Unflushed ORM generation change inside the same Session must reject immediately.
                state.active_generation = 2
                with pytest.raises(WorkspaceGenerationMismatchError):
                    await ensure_execution_binding_active(ap, ctx)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_pipeline_unbind_and_extension_update_take_effect_immediately_on_next_request(tmp_path):
    observed_bound_plugins: list[list[str] | None] = []

    async def capture_plugins(_event, bound_plugins):
        observed_bound_plugins.append(bound_plugins)

    harness = await _build_sqlite_pipeline_harness(
        tmp_path,
        outputs=[provider_message.Message(role='assistant', content='ok')],
        stream=False,
        emit_hook=capture_plugins,
        extensions_preferences={
            'enable_all_plugins': False,
            'enable_all_mcp_servers': True,
            'plugins': [{'author': 'acme', 'name': 'alpha'}],
            'mcp_servers': [],
        },
    )
    try:
        controller = Controller(harness.ap)
        q1, s1, adapter1 = harness.build_query(query_uuid='q-1', launcher_id='u1')
        await s1._semaphore.acquire()
        await controller._process_query(q1, selected_session=s1)
        assert adapter1.reply_message.await_count == 1
        assert observed_bound_plugins and all(item == ['acme/alpha'] for item in observed_bound_plugins)

        # Update pipeline plugin binding (revoke acme/alpha, bind acme/beta).
        observed_bound_plugins.clear()
        await harness.ap.pipeline_mgr.remove_pipeline(harness.ctx, 'pipe-1')
        updated_entity = LegacyPipeline(
            uuid='pipe-1',
            workspace_uuid=harness.workspace.uuid,
            name='GuardTestPipeline',
            description='',
            for_version='4.11.9',
            stages=list(default_stage_order),
            config=_default_pipeline_config(),
            is_default=True,
            extensions_preferences={
                'enable_all_plugins': False,
                'enable_all_mcp_servers': True,
                'plugins': [{'author': 'acme', 'name': 'beta'}],
                'mcp_servers': [],
            },
        )
        await harness.ap.pipeline_mgr.load_pipeline(harness.ctx, updated_entity)

        q2, s2, adapter2 = harness.build_query(query_uuid='q-2', launcher_id='u2')
        await s2._semaphore.acquire()
        await controller._process_query(q2, selected_session=s2)
        assert adapter2.reply_message.await_count == 1
        assert observed_bound_plugins and all(item == ['acme/beta'] for item in observed_bound_plugins)

        # Unbind / remove the pipeline completely: next request must drop cleanly.
        await harness.ap.pipeline_mgr.remove_pipeline(harness.ctx, 'pipe-1')
        q3, s3, adapter3 = harness.build_query(query_uuid='q-3', launcher_id='u3')
        await s3._semaphore.acquire()
        await controller._process_query(q3, selected_session=s3)
        adapter3.reply_message.assert_not_awaited()
    finally:
        await harness.engine.dispose()


@pytest.mark.asyncio
async def test_suspension_tracking_handles_sync_async_errors_and_cancellation():
    async def immediate():
        return 'fast'

    async def delayed():
        await asyncio.sleep(0)
        return 'slow'

    assert await await_tracking_suspension(immediate()) == ('fast', False)
    assert await await_tracking_suspension(delayed()) == ('slow', True)

    cleaned = False

    async def cancellable():
        nonlocal cleaned
        try:
            await asyncio.sleep(10)
        finally:
            await asyncio.sleep(0)
            cleaned = True

    task = asyncio.create_task(await_tracking_suspension(cancellable()))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cleaned is True

    async def mixed_gen():
        yield 'first'
        await asyncio.sleep(0)
        yield 'second'
        await asyncio.sleep(0)

    iterator = mixed_gen().__aiter__()
    assert await anext_tracking_suspension(iterator) == (True, 'first', False)
    assert await anext_tracking_suspension(iterator) == (True, 'second', True)
    assert await anext_tracking_suspension(iterator) == (False, None, True)


@pytest.mark.asyncio
async def test_suspending_local_stage_invalidates_lease_and_blocks_next_stage(tmp_path):
    harness = await _build_sqlite_pipeline_harness(
        tmp_path,
        outputs=[provider_message.Message(role='assistant', content='must-not-run')],
        stream=False,
    )
    try:
        pipeline = await harness.ap.pipeline_mgr.get_pipeline_by_uuid(harness.ctx, 'pipe-1')
        assert pipeline is not None
        # Inject a concurrent generation bump when the built-in PreContentFilterStage suspends.
        policy = await harness.ap.message_policy_mgr.neutral_runtime()
        orig_filter = policy.filter_inbound

        async def suspending_filter(query, message):
            await asyncio.sleep(0)
            async with harness.engine.begin() as conn:
                await conn.execute(
                    sqlalchemy.update(WorkspaceExecutionState)
                    .where(WorkspaceExecutionState.workspace_uuid == harness.workspace.uuid)
                    .values(active_generation=2)
                )
            return await orig_filter(query, message)

        policy.filter_inbound = suspending_filter
        try:
            query, session, adapter = harness.build_query()
            await session._semaphore.acquire()
            await Controller(harness.ap)._process_query(query, selected_session=session)

            adapter.reply_message.assert_not_awaited()
            assert query.variables.get('_monitoring_has_error') is True
            # PreProcessor must never run after PreContentFilterStage suspended across a generation bump.
            harness.ap.model_mgr.get_model_by_uuid.assert_not_awaited()
        finally:
            policy.filter_inbound = orig_filter
    finally:
        await harness.engine.dispose()


@pytest.mark.asyncio
async def test_notice_delivery_failure_invalidates_lease_before_recovery(tmp_path):
    harness = await _build_sqlite_pipeline_harness(
        tmp_path,
        outputs=[provider_message.Message(role='assistant', content='unused')],
        stream=False,
    )
    try:
        query, _session, _adapter = harness.build_query()
        pipeline = await harness.ap.pipeline_mgr.get_pipeline_by_uuid(harness.ctx, 'pipe-1')
        assert pipeline is not None
        policy = await harness.ap.message_policy_mgr.neutral_runtime()
        original_send_notice = policy.send_notice

        async def fail_send_notice(*_args, **_kwargs):
            raise RuntimeError('delivery failed')

        policy.send_notice = fail_send_notice
        try:
            before = len(harness.binding_calls)
            result = pipeline_entities.StageProcessResult(
                result_type=pipeline_entities.ResultType.INTERRUPT,
                new_query=query,
                user_notice='must fail',
            )
            with execution_binding_scope():
                with pytest.raises(RuntimeError, match='delivery failed'):
                    await pipeline._check_output(query, result)
                await ensure_execution_binding_active(harness.ap, harness.ctx)
            # The recovery check after the failed notice must not reuse the lease
            # established by before_send().
            assert len(harness.binding_calls) >= before + 2
        finally:
            policy.send_notice = original_send_notice
    finally:
        await harness.engine.dispose()


@pytest.mark.asyncio
async def test_monitoring_status_cancel_invalidates_lease_before_terminal_cleanup(tmp_path):
    harness = await _build_sqlite_pipeline_harness(
        tmp_path,
        outputs=[provider_message.Message(role='assistant', content='unused')],
        stream=False,
    )
    try:
        query, _session, _adapter = harness.build_query()
        pipeline = await harness.ap.pipeline_mgr.get_pipeline_by_uuid(harness.ctx, 'pipe-1')
        assert pipeline is not None
        query.variables['_monitoring_message_id'] = 'message-1'
        harness.ap.monitoring_service.update_message_status.side_effect = asyncio.CancelledError()
        before = len(harness.binding_calls)
        result = pipeline_entities.StageProcessResult(
            result_type=pipeline_entities.ResultType.INTERRUPT,
            new_query=query,
            error_notice='failed stage',
        )
        with execution_binding_scope():
            with pytest.raises(asyncio.CancelledError):
                await pipeline._check_output(query, result)
            async with harness.engine.begin() as conn:
                await conn.execute(
                    sqlalchemy.update(WorkspaceExecutionState)
                    .where(WorkspaceExecutionState.workspace_uuid == harness.workspace.uuid)
                    .values(write_fenced=True)
                )
            with pytest.raises(WorkspaceExecutionUnavailableError):
                await ensure_execution_binding_active(harness.ap, harness.ctx)
        assert len(harness.binding_calls) >= before + 2
    finally:
        await harness.engine.dispose()


@pytest.mark.asyncio
async def test_reentrant_binding_check_after_first_suspension_does_not_reuse_lease():
    context = ExecutionContext(instance_uuid='inst-1', workspace_uuid='ws-1', placement_generation=1)
    binding = SimpleNamespace(instance_uuid='inst-1', workspace_uuid='ws-1', placement_generation=1)
    get_binding = AsyncMock(side_effect=[binding, WorkspaceGenerationMismatchError('fenced during await')])
    ap = SimpleNamespace(workspace_service=SimpleNamespace(get_execution_binding=get_binding))

    async def reentrant_work():
        await asyncio.sleep(0)
        await ensure_execution_binding_active(ap, context)

    with execution_binding_scope():
        await ensure_execution_binding_active(ap, context)
        with pytest.raises(WorkspaceGenerationMismatchError, match='fenced during await'):
            await await_tracking_suspension(reentrant_work())
    assert get_binding.await_count == 2


@pytest.mark.asyncio
async def test_cloud_lease_hit_runs_synchronous_admission_and_projection_guards():
    context = ExecutionContext(instance_uuid='inst-1', workspace_uuid='ws-1', placement_generation=1)
    binding = SimpleNamespace(instance_uuid='inst-1', workspace_uuid='ws-1', placement_generation=1)

    class Guards:
        def __init__(self):
            self.admission_calls = 0
            self.projection_calls = 0
            self.admission_error = None

        def require_admission(self):
            self.admission_calls += 1
            if self.admission_error:
                raise self.admission_error

        def require_projection(self):
            self.projection_calls += 1

    guards = Guards()
    workspace_service = SimpleNamespace(
        get_execution_binding=AsyncMock(return_value=binding),
        _require_deployment_admission=guards.require_admission,
        _require_directory_projection=guards.require_projection,
    )
    ap = SimpleNamespace(workspace_service=workspace_service)

    with execution_binding_scope():
        await ensure_execution_binding_active(ap, context)
        assert workspace_service.get_execution_binding.await_count == 1
        await ensure_execution_binding_active(ap, context)
        assert workspace_service.get_execution_binding.await_count == 1
        assert guards.admission_calls == 1
        assert guards.projection_calls == 1

        guards.admission_error = RuntimeError('manifest expired')
        with pytest.raises(RuntimeError, match='manifest expired'):
            await ensure_execution_binding_active(ap, context)
        guards.admission_error = None
        await ensure_execution_binding_active(ap, context)
        assert workspace_service.get_execution_binding.await_count == 2


@pytest.mark.asyncio
async def test_sync_custom_async_generator_rechecks_before_first_anext(tmp_path):
    harness = await _build_sqlite_pipeline_harness(
        tmp_path,
        outputs=[provider_message.Message(role='assistant', content='unused')],
        stream=False,
    )
    try:
        pipeline = await harness.ap.pipeline_mgr.get_pipeline_by_uuid(harness.ctx, 'pipe-1')
        assert pipeline is not None
        query, _session, _adapter = harness.build_query()
        binding_calls = 0
        original_get = harness.ap.workspace_service.get_execution_binding

        async def stale_after_entry(*args, **kwargs):
            nonlocal binding_calls
            binding_calls += 1
            if binding_calls >= 2:
                raise WorkspaceGenerationMismatchError('stale before custom generator')
            return await original_get(*args, **kwargs)

        harness.ap.workspace_service.get_execution_binding = stale_after_entry

        class CustomGeneratorStage:
            def process(self, _query, _stage_name):
                async def generate():
                    await ensure_execution_binding_active(harness.ap, harness.ctx)
                    yield pipeline_entities.StageProcessResult(
                        result_type=pipeline_entities.ResultType.CONTINUE,
                        new_query=query,
                    )

                return generate()

        pipeline.stage_containers = [StageInstContainer('CustomGenerator', CustomGeneratorStage())]
        with pytest.raises(WorkspaceGenerationMismatchError, match='stale before custom generator'):
            await pipeline._execute_from_stage(0, query)
        assert binding_calls == 2
    finally:
        await harness.engine.dispose()
