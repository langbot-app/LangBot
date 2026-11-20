"""Knowledge file consumers retain only their own authorized Artifact bindings."""

# ruff: noqa: F811
import asyncio
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import uuid

import pytest
import sqlalchemy as sa

from langbot.pkg.api.context import ExecutionContext, PrincipalContext, PrincipalType
from langbot.pkg.api.http.service.knowledge import KnowledgeService
from langbot.pkg.entity.persistence.artifact import ArtifactReference
from langbot.pkg.entity.persistence.rag import File, KnowledgeBase
from langbot.pkg.rag.knowledge.kbmgr import RuntimeKnowledgeBase
from langbot.pkg.rag.service.runtime import RAGRuntimeService
from langbot.pkg.workspace.errors import WorkspaceNotFoundError
from tests.integration.storage.test_artifacts import artifact_replicas, persistence_case, replicas  # noqa: F401

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def setup(case, replica=None, kb_id=None):
    ap = (replica or case.a).app
    ctx = ExecutionContext.from_request(case.context)
    kb = KnowledgeBase(
        uuid=kb_id or str(uuid.uuid4()),
        workspace_uuid=ctx.workspace_uuid,
        name='Artifacts',
        knowledge_engine_plugin_id='test/engine',
    )
    if kb_id is None:
        await ap.persistence_mgr.execute_async(
            sa.insert(KnowledgeBase).values(
                uuid=kb.uuid,
                workspace_uuid=ctx.workspace_uuid,
                name=kb.name,
                knowledge_engine_plugin_id='test/engine',
                initialized=True,
            )
        )
    tasks = []

    def schedule(coroutine, **kwargs):
        task = asyncio.create_task(coroutine)
        tasks.append(task)
        return SimpleNamespace(id=len(tasks), task=task)

    ap.task_mgr = SimpleNamespace(create_user_task=schedule)
    ap.plugin_connector = SimpleNamespace(
        require_workspace_context=AsyncMock(side_effect=lambda context: context),
        call_rag_ingest=AsyncMock(return_value={'status': 'completed', 'document_id': 'engine-doc'}),
        call_rag_delete_document=AsyncMock(return_value=True),
        rag_on_kb_delete=AsyncMock(),
    )
    return RuntimeKnowledgeBase(ap, kb, ctx), tasks, ctx


async def rows(runtime):
    return (
        await runtime.ap.persistence_mgr.execute_async(sa.select(File).where(File.kb_id == runtime.get_uuid()))
    ).all()


async def test_two_kbs_share_artifact_and_engine_stream_is_bound(artifact_replicas):
    case = artifact_replicas
    first, tasks1, ctx = await setup(case)
    second, tasks2, _ = await setup(case, case.b)
    artifact = await case.a.app.artifact_service.create(case.context, 'guide.txt', b'knowledge source', 'text/plain')
    assert await first.store_artifact(case.context, artifact['id']) == 1
    assert await second.store_artifact(case.context, artifact['id']) == 1
    await asyncio.gather(*tasks1, *tasks2)
    a, b = (await rows(first))[0], (await rows(second))[0]
    assert a.status == b.status == 'completed'
    stream = RAGRuntimeService(first.ap)
    assert await stream.get_file_stream(ctx, f'artifact:{a.uuid}', plugin_id='test/engine') == b'knowledge source'
    for plugin in (None, 'other/engine'):
        with pytest.raises(WorkspaceNotFoundError):
            await stream.get_file_stream(ctx, f'artifact:{a.uuid}', plugin_id=plugin)
    with pytest.raises((ValueError, WorkspaceNotFoundError)):
        await stream.get_file_stream(ctx, artifact['id'], plugin_id='test/engine')
    with pytest.raises(Exception, match='in use'):
        await first.ap.artifact_service.delete(case.context, artifact['id'])
    await first.delete_file(ctx, a.uuid)
    assert (
        await RAGRuntimeService(second.ap).get_file_stream(ctx, f'artifact:{b.uuid}', plugin_id='test/engine')
        == b'knowledge source'
    )
    await second.delete_file(ctx, b.uuid)
    assert (await first.ap.artifact_service.read(case.context, artifact['id']))['content'] == b'knowledge source'
    await first.ap.artifact_service.delete(case.context, artifact['id'])


async def test_import_source_owner_and_capacity_failure_leave_no_holder(artifact_replicas):
    case = artifact_replicas
    runtime, tasks, ctx = await setup(case)
    artifact = await runtime.ap.artifact_service.create(case.context, 'guide.txt', b'bytes', 'text/plain')
    other = replace(case.context, principal=PrincipalContext(PrincipalType.ACCOUNT, account_uuid=str(uuid.uuid4())))
    with pytest.raises(FileNotFoundError):
        await runtime.store_artifact(other, artifact['id'])

    def refuse(*args, **kwargs):
        raise RuntimeError('capacity refused')

    runtime.ap.task_mgr.create_user_task = refuse
    with pytest.raises(RuntimeError, match='capacity'):
        await runtime.store_artifact(case.context, artifact['id'])
    assert not await rows(runtime)
    refs = await runtime.ap.persistence_mgr.execute_async(
        sa.select(ArtifactReference).where(ArtifactReference.artifact_id == artifact['id'])
    )
    assert not refs.all()
    assert not tasks


async def test_delete_fence_survives_upstream_failure_and_blocks_other_core(artifact_replicas):
    case = artifact_replicas
    runtime, tasks, ctx = await setup(case)
    other, _, _ = await setup(case, case.b, runtime.get_uuid())
    artifact = await runtime.ap.artifact_service.create(case.context, 'guide.txt', b'bytes', 'text/plain')
    await runtime.store_artifact(case.context, artifact['id'])
    await asyncio.gather(*tasks)
    entered, release = asyncio.Event(), asyncio.Event()

    async def fail_delete(*args):
        entered.set()
        await release.wait()
        raise RuntimeError('upstream unknown')

    runtime.ap.rag_mgr = SimpleNamespace(delete_knowledge_base=fail_delete)
    service = KnowledgeService(runtime.ap)
    deletion = asyncio.create_task(service._delete_knowledge_base_records(case.context, runtime.get_uuid()))
    await asyncio.wait_for(entered.wait(), 5)
    with pytest.raises(ValueError, match='deletion is pending'):
        await other.store_artifact(case.context, artifact['id'])
    release.set()
    with pytest.raises(RuntimeError, match='upstream unknown'):
        await deletion
    assert len(await rows(runtime)) == 1
    with pytest.raises(Exception, match='in use'):
        await runtime.ap.artifact_service.delete(case.context, artifact['id'])
    runtime.ap.rag_mgr.delete_knowledge_base = AsyncMock()
    await service._delete_knowledge_base_records(case.context, runtime.get_uuid())
    assert not await rows(runtime)
    await runtime.ap.artifact_service.delete(case.context, artifact['id'])


async def test_http_artifact_import_envelopes_and_legacy_task_field(artifact_replicas):
    from langbot.pkg.api.http.controller.groups.knowledge.base import KnowledgeBaseRouterGroup
    from langbot.pkg.api.authz import PermissionDeniedError

    case = artifact_replicas
    service = SimpleNamespace(store_artifact=AsyncMock(return_value=42))
    case.a.app.knowledge_service = service
    await KnowledgeBaseRouterGroup(case.a.app, case.a.client.app).initialize()
    url = '/api/v1/knowledge/bases/kb-test/files/artifact'
    response = await case.a.client.post(url, headers=case.headers, json={'artifact_id': 'art_example'})
    assert response.status_code == 200
    assert (await response.get_json())['data'] == {'task_id': 42}
    for payload in ({}, {'artifact_id': ''}, {'artifact_id': 'art_example', 'storage_key': 'private'}):
        response = await case.a.client.post(url, headers=case.headers, json=payload)
        assert response.status_code == 400
    for error, status in ((PermissionDeniedError('resource.view'), 403), (FileNotFoundError('hidden'), 404)):
        service.store_artifact.side_effect = error
        response = await case.a.client.post(url, headers=case.headers, json={'artifact_id': 'art_example'})
        assert response.status_code == status


async def test_cancelled_ingestion_retains_source_holder_for_reconciliation(artifact_replicas):
    runtime, tasks, ctx = await setup(artifact_replicas)
    artifact = await runtime.ap.artifact_service.create(artifact_replicas.context, 'guide.txt', b'bytes', 'text/plain')
    entered = asyncio.Event()

    async def waiting(*args):
        entered.set()
        await asyncio.Event().wait()

    runtime.ap.plugin_connector.call_rag_ingest.side_effect = waiting
    await runtime.store_artifact(artifact_replicas.context, artifact['id'])
    await asyncio.wait_for(entered.wait(), 5)
    tasks[0].cancel()
    with pytest.raises(asyncio.CancelledError):
        await tasks[0]
    file = (await rows(runtime))[0]
    assert file.status == 'interrupted'
    with pytest.raises(RuntimeError, match='interrupted'):
        await runtime.delete_file(ctx, file.uuid)
    with pytest.raises(Exception, match='in use'):
        await runtime.ap.artifact_service.delete(artifact_replicas.context, artifact['id'])


async def test_upstream_kb_failure_propagates_and_runtime_is_not_discarded(artifact_replicas):
    from langbot.pkg.rag.knowledge.kbmgr import RAGManager

    runtime, _, ctx = await setup(artifact_replicas)
    runtime.ap.plugin_connector.rag_on_kb_delete.side_effect = RuntimeError('upstream delete failed')
    manager = SimpleNamespace(
        _to_execution_context=AsyncMock(return_value=ctx),
        get_knowledge_base_by_uuid=AsyncMock(return_value=runtime),
        _pop_runtime=Mock(),
    )
    with pytest.raises(RuntimeError, match='upstream delete failed'):
        await RAGManager.delete_knowledge_base(manager, ctx, runtime.get_uuid())
    manager._pop_runtime.assert_not_called()
    runtime.ap.plugin_connector.rag_on_kb_delete.side_effect = None
    await RAGManager.delete_knowledge_base(manager, ctx, runtime.get_uuid())
    manager._pop_runtime.assert_called_once()


async def test_engine_rebinding_during_read_does_not_return_bytes(artifact_replicas, monkeypatch):
    case = artifact_replicas
    runtime, tasks, ctx = await setup(case)
    artifact = await runtime.ap.artifact_service.create(case.context, 'guide.txt', b'private', 'text/plain')
    await runtime.store_artifact(case.context, artifact['id'])
    await asyncio.gather(*tasks)
    file = (await rows(runtime))[0]
    original = runtime.ap.artifact_service.read_business

    async def changed(*args, **kwargs):
        result = await original(*args, **kwargs)
        await case.b.app.persistence_mgr.execute_async(
            sa.update(KnowledgeBase)
            .where(KnowledgeBase.uuid == runtime.get_uuid())
            .values(knowledge_engine_plugin_id='replacement/engine')
        )
        return result

    monkeypatch.setattr(runtime.ap.artifact_service, 'read_business', changed)
    with pytest.raises(WorkspaceNotFoundError):
        await RAGRuntimeService(runtime.ap).get_file_stream(ctx, f'artifact:{file.uuid}', plugin_id='test/engine')


async def test_file_detach_during_read_does_not_return_bytes(artifact_replicas, monkeypatch):
    case = artifact_replicas
    runtime, tasks, ctx = await setup(case)
    artifact = await runtime.ap.artifact_service.create(case.context, 'guide.txt', b'private', 'text/plain')
    await runtime.store_artifact(case.context, artifact['id'])
    await asyncio.gather(*tasks)
    file = (await rows(runtime))[0]
    content = runtime.ap.artifact_service.content
    original = content._read

    async def detached(*args, **kwargs):
        value = await original(*args, **kwargs)
        async with case.b.app.persistence_mgr.tenant_uow(ctx.workspace_uuid):
            await case.b.app.artifact_service.release_business(
                ctx,
                artifact['id'],
                holder_type='knowledge_file',
                holder_id=file.uuid,
            )
            await case.b.app.persistence_mgr.execute_async(sa.delete(File).where(File.uuid == file.uuid))
        return value

    monkeypatch.setattr(content, '_read', detached)
    with pytest.raises(FileNotFoundError):
        await RAGRuntimeService(runtime.ap).get_file_stream(ctx, f'artifact:{file.uuid}', plugin_id='test/engine')
