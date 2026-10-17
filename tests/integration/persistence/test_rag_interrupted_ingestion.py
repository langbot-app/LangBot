"""B1 lifecycle regressions; isolated databases, no external engines or customer data."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from tests.integration.persistence import test_rag_document_identity as identity
from tests.integration.persistence.test_rag_document_identity import CONTEXT, read_file_row, seed
from langbot.pkg.core.entities import LifecycleControlScope
from langbot.pkg.core.taskmgr import AsyncTaskManager, TaskContext
from langbot.pkg.rag.knowledge.kbmgr import RuntimeKnowledgeBase

# Reuse the real isolated-database fixtures without duplicating their lifecycle.
database = identity.database
runtime = identity.runtime


def attach_task_manager(runtime):
    runtime.ap.event_loop = asyncio.get_running_loop()
    runtime.ap.instance_config = SimpleNamespace(data={})
    runtime.ap.task_mgr = AsyncTaskManager(runtime.ap)
    return runtime.ap.task_mgr


@pytest.mark.asyncio
@pytest.mark.contract('rag_recovery')
async def test_cancelled_ingestion_retains_recovery_resources(runtime):
    """Local cancellation is interrupted observation, not remote quiescence."""
    file = await seed(runtime)
    entered, terminal = asyncio.Event(), asyncio.Event()

    async def ingest(*_):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            terminal.set()

    runtime.ap.plugin_connector.call_rag_ingest.side_effect = ingest
    manager = attach_task_manager(runtime)
    wrapper = manager.create_user_task(
        runtime._store_file_task(CONTEXT, file, TaskContext.new()),
        kind='knowledge-operation',
        name=f'knowledge-store-file-{file.file_name}',
        instance_uuid=CONTEXT.instance_uuid,
        workspace_uuid=CONTEXT.workspace_uuid,
        placement_generation=CONTEXT.placement_generation,
    )
    try:
        await asyncio.wait_for(entered.wait(), 5)
        manager.cancel_by_scope(LifecycleControlScope.APPLICATION)
        with pytest.raises(asyncio.CancelledError):
            await wrapper.task
        assert terminal.is_set()
        assert wrapper.task.cancelled()
        assert (await read_file_row(runtime))['status'] == 'interrupted'
        runtime.ap.storage_mgr.delete_scoped_object_key.assert_not_awaited()
        with pytest.raises(RuntimeError, match='interrupted'):
            await runtime.delete_file(CONTEXT, file.uuid)
        runtime.ap.plugin_connector.call_rag_delete_document.assert_not_awaited()
        assert await read_file_row(runtime) is not None
    finally:
        if not wrapper.task.done():
            wrapper.task.cancel()
            await asyncio.gather(wrapper.task, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['pending', 'processing'])
async def test_recreated_host_marks_abandoned_rows_interrupted(runtime, status):
    """Fresh Host state recovers observation without authorizing remote deletion."""
    await seed(runtime, status=status)
    new_ap = SimpleNamespace(**vars(runtime.ap))
    recreated = RuntimeKnowledgeBase(new_ap, runtime.knowledge_base_entity, CONTEXT)
    manager = attach_task_manager(recreated)
    assert manager.get_all_tasks() == []
    await recreated.initialize()
    assert (await read_file_row(recreated))['status'] == 'interrupted'
    with pytest.raises(RuntimeError, match='interrupted'):
        await recreated.delete_file(CONTEXT, 'host-id')
    recreated.ap.plugin_connector.call_rag_delete_document.assert_not_awaited()
    recreated.ap.storage_mgr.delete_scoped_object_key.assert_not_awaited()


@pytest.mark.asyncio
async def test_b1_live_task_still_blocks_delete_after_runtime_object_recreation(runtime):
    file = await seed(runtime)
    entered, release = asyncio.Event(), asyncio.Event()

    async def ingest(*_):
        entered.set()
        await release.wait()
        return {'document_id': file.uuid, 'status': 'completed'}

    runtime.ap.plugin_connector.call_rag_ingest.side_effect = ingest
    manager = attach_task_manager(runtime)
    wrapper = manager.create_user_task(
        runtime._store_file_task(CONTEXT, file, Mock()),
        kind='knowledge-operation',
        name=f'knowledge-store-file-{file.file_name}',
        instance_uuid=CONTEXT.instance_uuid,
        workspace_uuid=CONTEXT.workspace_uuid,
        placement_generation=CONTEXT.placement_generation,
    )
    try:
        await asyncio.wait_for(entered.wait(), 5)
        recreated = RuntimeKnowledgeBase(runtime.ap, runtime.knowledge_base_entity, CONTEXT)
        await recreated.initialize()
        assert not wrapper.task.done()
        with pytest.raises(RuntimeError, match='ingest'):
            await recreated.delete_file(CONTEXT, file.uuid)
        recreated.ap.plugin_connector.call_rag_delete_document.assert_not_awaited()
        assert (await read_file_row(recreated))['status'] == 'processing'
    finally:
        release.set()
        await asyncio.wait_for(wrapper.task, 5)
    await recreated.delete_file(CONTEXT, file.uuid)
    assert await read_file_row(recreated) is None


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [TimeoutError('timeout'), ConnectionError('disconnect')])
async def test_transport_failure_is_interrupted_not_failed(runtime, failure):
    file = await seed(runtime)
    runtime.ap.plugin_connector.call_rag_ingest.side_effect = failure
    with pytest.raises(type(failure)):
        await runtime._store_file_task(CONTEXT, file, Mock())
    assert (await read_file_row(runtime))['status'] == 'interrupted'
    runtime.ap.storage_mgr.delete_scoped_object_key.assert_not_awaited()


@pytest.mark.asyncio
async def test_recovered_row_cannot_be_replayed_by_delayed_old_task(runtime):
    file = await seed(runtime)
    await runtime.initialize()
    with pytest.raises(Exception):
        await runtime._store_file_task(CONTEXT, file, Mock())
    assert (await read_file_row(runtime))['status'] == 'interrupted'
    runtime.ap.plugin_connector.call_rag_ingest.assert_not_awaited()
    runtime.ap.storage_mgr.delete_scoped_object_key.assert_not_awaited()


@pytest.mark.asyncio
async def test_reconciliation_preserves_other_scopes_and_terminal_states(runtime):
    await seed(runtime, status='processing')
    await seed(runtime, file_id='other-kb', kb='kb-other', status='processing')
    await seed(runtime, file_id='other-workspace', workspace='workspace-b', kb='kb-b', status='processing')
    for status in ('completed', 'failed', 'interrupted'):
        await seed(runtime, file_id=status, status=status)
    await runtime.initialize()
    assert (await read_file_row(runtime))['status'] == 'interrupted'
    for file_id in ('other-kb', 'other-workspace'):
        assert (await read_file_row(runtime, file_id))['status'] == 'processing'
    for status in ('completed', 'failed', 'interrupted'):
        assert (await read_file_row(runtime, status))['status'] == status


@pytest.mark.asyncio
async def test_cancellation_after_result_retains_identity(runtime):
    file = await seed(runtime)
    original = runtime._set_file_status

    async def cancel_completion(context, uuid, status, **kwargs):
        if status == 'completed':
            raise asyncio.CancelledError()
        return await original(context, uuid, status, **kwargs)

    runtime._set_file_status = cancel_completion
    with pytest.raises(asyncio.CancelledError):
        await runtime._store_file_task(CONTEXT, file, Mock())
    row = await read_file_row(runtime)
    assert row['status'] == 'interrupted'
    assert row['engine_document_id'] == 'upstream-id'
    runtime.ap.storage_mgr.delete_scoped_object_key.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancellation_after_completion_commit_does_not_downgrade(runtime):
    file = await seed(runtime)
    original = runtime._set_file_status

    async def cancel_after_commit(context, uuid, status, **kwargs):
        result = await original(context, uuid, status, **kwargs)
        if status == 'completed':
            raise asyncio.CancelledError()
        return result

    runtime._set_file_status = cancel_after_commit
    with pytest.raises(asyncio.CancelledError):
        await runtime._store_file_task(CONTEXT, file, Mock())
    row = await read_file_row(runtime)
    assert row['status'] == 'completed'
    assert row['engine_document_id'] == 'upstream-id'
    runtime.ap.storage_mgr.delete_scoped_object_key.assert_not_awaited()


def make_service(runtime):
    from langbot.pkg.api.http.service.knowledge import KnowledgeService

    runtime.ap.rag_mgr = SimpleNamespace(
        get_knowledge_base_details=AsyncMock(return_value={'uuid': 'kb-a'}),
        get_knowledge_base_by_uuid=AsyncMock(return_value=runtime),
        delete_knowledge_base=AsyncMock(),
    )
    return KnowledgeService(runtime.ap)


@pytest.mark.asyncio
async def test_file_list_recovers_abandoned_task_without_restart(runtime):
    await seed(runtime, status='processing')
    files = await make_service(runtime).get_files_by_knowledge_base(CONTEXT, 'kb-a')
    assert files[0]['status'] == 'interrupted'
    assert (await read_file_row(runtime))['status'] == 'interrupted'


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['pending', 'processing', 'interrupted'])
async def test_bulk_kb_delete_cannot_discard_unsettled_ingestion(runtime, status):
    from langbot.pkg.entity.persistence.rag import Chunk

    async with runtime.ap.persistence_mgr.get_db_engine().begin() as conn:
        await conn.run_sync(lambda sync: Chunk.__table__.create(sync))
    await seed(runtime, status=status)
    service = make_service(runtime)
    with pytest.raises(RuntimeError, match='ingestion'):
        await service.delete_knowledge_base(CONTEXT, 'kb-a')
    assert await read_file_row(runtime) is not None
    runtime.ap.rag_mgr.delete_knowledge_base.assert_not_awaited()


@pytest.mark.asyncio
async def test_queued_task_cancelled_before_start_recovers_on_file_list(runtime):
    runtime.ap.storage_mgr.exists_scoped_object_key = AsyncMock(return_value=True)
    manager = attach_task_manager(runtime)
    await runtime.store_file(CONTEXT, 'upload.txt')
    wrapper = manager.get_all_tasks()[0]
    wrapper.task.cancel()
    await asyncio.gather(wrapper.task, return_exceptions=True)
    assert wrapper.task.cancelled()
    files = await make_service(runtime).get_files_by_knowledge_base(CONTEXT, 'kb-a')
    assert files[0]['status'] == 'interrupted'
    runtime.ap.plugin_connector.call_rag_ingest.assert_not_awaited()
    runtime.ap.storage_mgr.delete_scoped_object_key.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('disconnect', [False, True], ids=['cancel-waiter', 'close-host-connection'])
async def test_actual_sdk_late_write_preserves_interrupted_state(runtime, tmp_path, monkeypatch, disconnect):
    from langbot.pkg.api.http.context import ExecutionContext
    from langbot_plugin.entities.io.actions.enums import RuntimeToPluginAction
    from langbot_plugin.runtime.io.handler import ActionResponse
    from tests.integration.plugin.test_rag_file_transfer_protocol import BINDING, protocol_stack

    context = ExecutionContext(instance_uuid='instance-a', workspace_uuid='workspace-a', placement_generation=7)
    runtime.execution_context = context
    file = await seed(runtime)
    async with protocol_stack(tmp_path, monkeypatch, 'shared', BINDING) as stack:
        entered, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()
        selected = SimpleNamespace(_runtime_plugin_handler=stack.bridge)
        monkeypatch.setattr(stack.runtime.plugin_mgr, '_get_connected_rag_plugin', lambda *_: (selected, 'engine'))
        vectors = set()

        @stack.plugin.action(RuntimeToPluginAction.INGEST_DOCUMENT)
        async def ingest(data):
            entered.set()
            await release.wait()
            vectors.add('opaque-upstream-id')
            finished.set()
            return ActionResponse.success({'document_id': 'opaque-upstream-id', 'status': 'completed'})

        async def send_ingest(_plugin_id, data):
            with stack.core.installation_scope(BINDING):
                return await stack.core.rag_ingest_document('tester', 'engine', data)

        runtime.ap.plugin_connector.call_rag_ingest = send_ingest
        task = asyncio.create_task(runtime._store_file_task(context, file, Mock()))
        try:
            await asyncio.wait_for(entered.wait(), 5)
            if disconnect:
                await stack.core.close()
            else:
                task.cancel()
            outcome = await asyncio.gather(task, return_exceptions=True)
            assert isinstance(outcome[0], BaseException)
            assert (await read_file_row(runtime))['status'] == 'interrupted'
            assert not finished.is_set()
            with pytest.raises(RuntimeError, match='interrupted'):
                await runtime.delete_file(context, file.uuid)
            runtime.ap.plugin_connector.call_rag_delete_document.assert_not_awaited()
            release.set()
            await asyncio.wait_for(finished.wait(), 5)
            assert vectors == {'opaque-upstream-id'}
            assert (await read_file_row(runtime))['status'] == 'interrupted'
            assert (await read_file_row(runtime))['engine_document_id'] is None
            runtime.ap.storage_mgr.delete_scoped_object_key.assert_not_awaited()
        finally:
            release.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_late_observed_identity_survives_recovery_without_false_completion(runtime):
    file = await seed(runtime)
    entered, release = asyncio.Event(), asyncio.Event()

    async def ingest(*_):
        entered.set()
        await release.wait()
        return {'document_id': 'late-id', 'status': 'completed'}

    runtime.ap.plugin_connector.call_rag_ingest.side_effect = ingest
    task = asyncio.create_task(runtime._store_file_task(CONTEXT, file, Mock()))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        # Independent Host observation, not shared process state.
        new_ap = SimpleNamespace(**{k: v for k, v in vars(runtime.ap).items() if not k.startswith('_knowledge_')})
        recreated = RuntimeKnowledgeBase(new_ap, runtime.knowledge_base_entity, CONTEXT)
        await recreated.initialize()
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        row = await read_file_row(runtime)
        assert row['status'] == 'interrupted'
        assert row['engine_document_id'] == 'late-id'
        runtime.ap.storage_mgr.delete_scoped_object_key.assert_not_awaited()
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_parser_transport_failure_retains_upload(runtime):
    file = await seed(runtime)
    runtime.ap.storage_mgr.load_scoped_object_key = AsyncMock(return_value=b'file')
    runtime.ap.plugin_connector.call_parser = AsyncMock(side_effect=TimeoutError())
    with pytest.raises(TimeoutError):
        await runtime._store_file_task(CONTEXT, file, Mock(), parser_plugin_id='author/parser')
    assert (await read_file_row(runtime))['status'] == 'interrupted'
    runtime.ap.storage_mgr.delete_scoped_object_key.assert_not_awaited()
    runtime.ap.plugin_connector.call_rag_ingest.assert_not_awaited()


@pytest.mark.asyncio
async def test_kb_delete_serializes_with_new_upload_admission(runtime):
    from langbot.pkg.entity.persistence.rag import Chunk

    async with runtime.ap.persistence_mgr.get_db_engine().begin() as conn:
        await conn.run_sync(lambda sync: Chunk.__table__.create(sync))
    runtime.ap.storage_mgr.exists_scoped_object_key = AsyncMock(return_value=True)
    attach_task_manager(runtime)
    service = make_service(runtime)
    entered, release = asyncio.Event(), asyncio.Event()

    async def pause_delete(*_):
        entered.set()
        await release.wait()

    runtime.ap.rag_mgr.delete_knowledge_base.side_effect = pause_delete
    deletion = asyncio.create_task(service.delete_knowledge_base(CONTEXT, 'kb-a'))
    upload = None
    try:
        await asyncio.wait_for(entered.wait(), 5)
        upload = asyncio.create_task(runtime.store_file(CONTEXT, 'upload.txt'))
        await asyncio.sleep(0.1)
        assert not upload.done(), 'upload admission must wait for the in-progress KB deletion'
        runtime.ap.plugin_connector.call_rag_ingest.assert_not_awaited()
        release.set()
        await deletion
        with pytest.raises(Exception):
            await upload  # FK rejects admission after the KB was deleted.
        runtime.ap.plugin_connector.call_rag_ingest.assert_not_awaited()
    finally:
        release.set()
        await asyncio.gather(deletion, *([upload] if upload else []), return_exceptions=True)
        await asyncio.gather(*(wrapper.task for wrapper in runtime.ap.task_mgr.get_all_tasks()), return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize('provider_name', ['LocalStorageProvider', 'S3StorageProvider'])
async def test_retention_cleanup_preserves_ingestion_recovery_upload(runtime, tmp_path, provider_name):
    from langbot.pkg.api.http.service.maintenance import MaintenanceService

    await seed(runtime, status='interrupted')
    retained = tmp_path / 'retained.txt'
    expired = tmp_path / 'expired.txt'
    retained.write_text('recovery source')
    expired.write_text('unreferenced upload')
    provider = type(provider_name, (), {})()
    provider.delete = AsyncMock()
    runtime.ap.storage_mgr.storage_provider = provider
    candidates = [
        {'key': 'upload.txt', 'path': str(retained)},
        {'key': 'unreferenced.txt', 'path': str(expired)},
    ]
    service = MaintenanceService(runtime.ap)
    service._expired_local_upload_candidates = Mock(return_value=candidates)
    service._expired_s3_upload_candidates = AsyncMock(return_value=candidates)
    count = await service._cleanup_expired_uploaded_files(CONTEXT, 7)
    assert count == 1
    if provider_name == 'LocalStorageProvider':
        assert retained.read_text() == 'recovery source'
        assert not expired.exists()
    else:
        provider.delete.assert_awaited_once_with('unreferenced.txt')
