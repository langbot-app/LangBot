"""Unit tests for RuntimeKnowledgeBase file storage behavior."""

from __future__ import annotations

import io
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.rag.knowledge.kbmgr import RuntimeKnowledgeBase
from langbot.pkg.storage.mgr import StorageMgr
from langbot.pkg.workspace.errors import WorkspaceNotFoundError


WORKSPACE_A = '00000000-0000-0000-0000-00000000000a'
CONTEXT = ExecutionContext(
    instance_uuid='instance-a',
    workspace_uuid=WORKSPACE_A,
    placement_generation=2,
)


def _upload_key(logical_key: str, *, context: ExecutionContext = CONTEXT) -> str:
    return StorageMgr.scoped_object_key(
        context,
        owner_type='upload_document',
        owner='account:test',
        key=logical_key,
    )


def _make_zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
        zf.mkdir('emptydir')
    return buffer.getvalue()


def _make_app() -> Mock:
    app = Mock()
    app.logger = Mock()
    app.task_mgr = Mock()
    storage_mgr = StorageMgr(app)
    storage_mgr.storage_provider = Mock()
    storage_mgr.storage_provider.exists = AsyncMock(return_value=True)
    storage_mgr.storage_provider.load = AsyncMock()
    storage_mgr.storage_provider.save = AsyncMock()
    storage_mgr.storage_provider.size = AsyncMock(return_value=123)
    storage_mgr.storage_provider.delete = AsyncMock()
    app.storage_mgr = storage_mgr
    app.persistence_mgr = Mock()
    app.persistence_mgr.execute_async = AsyncMock()
    app.plugin_connector = Mock()
    app.plugin_connector.require_workspace_context = AsyncMock(side_effect=lambda context: context)
    app.workspace_service = SimpleNamespace(
        get_execution_binding=AsyncMock(
            return_value=SimpleNamespace(
                instance_uuid=CONTEXT.instance_uuid,
                workspace_uuid=CONTEXT.workspace_uuid,
                placement_generation=CONTEXT.placement_generation,
            )
        )
    )
    return app


def _make_kb(plugin_id: str | None = 'author/engine') -> RuntimeKnowledgeBase:
    kb_entity = Mock()
    kb_entity.uuid = 'test-kb-uuid'
    kb_entity.workspace_uuid = WORKSPACE_A
    kb_entity.collection_id = 'test-collection'
    kb_entity.creation_settings = {}
    kb_entity.knowledge_engine_plugin_id = plugin_id
    return RuntimeKnowledgeBase(_make_app(), kb_entity, CONTEXT)


class TestStoreFile:
    @pytest.mark.asyncio
    async def test_store_file_creates_pending_record_and_user_task(self):
        kb = _make_kb()

        def create_user_task(coro, **kwargs):
            coro.close()
            return SimpleNamespace(id='task-1', kwargs=kwargs)

        kb.ap.task_mgr.create_user_task = Mock(side_effect=create_user_task)

        object_key = _upload_key('documents/test.pdf')
        task_id = await kb.store_file(CONTEXT, object_key)

        assert task_id == 'task-1'
        kb.ap.storage_mgr.storage_provider.exists.assert_awaited_once_with(object_key)
        kb.ap.persistence_mgr.execute_async.assert_awaited_once()
        call_kwargs = kb.ap.task_mgr.create_user_task.call_args.kwargs
        assert call_kwargs['kind'] == 'knowledge-operation'
        assert call_kwargs['name'] == f'knowledge-store-file-{object_key}'
        assert call_kwargs['label'] == f'Store file {object_key}'

    @pytest.mark.asyncio
    async def test_store_file_raises_when_source_file_missing(self):
        kb = _make_kb()
        kb.ap.storage_mgr.storage_provider.exists = AsyncMock(return_value=False)

        object_key = _upload_key('missing.pdf')
        with pytest.raises(WorkspaceNotFoundError, match='Upload not found'):
            await kb.store_file(CONTEXT, object_key)

        kb.ap.persistence_mgr.execute_async.assert_not_awaited()
        kb.ap.task_mgr.create_user_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_store_file_rejects_cross_workspace_upload_key(self):
        kb = _make_kb()
        other_context = ExecutionContext(
            instance_uuid=CONTEXT.instance_uuid,
            workspace_uuid='00000000-0000-0000-0000-00000000000b',
            placement_generation=CONTEXT.placement_generation,
        )

        with pytest.raises(WorkspaceNotFoundError, match='Upload not found'):
            await kb.store_file(CONTEXT, _upload_key('stolen.pdf', context=other_context))

        kb.ap.storage_mgr.storage_provider.exists.assert_not_awaited()
        kb.ap.persistence_mgr.execute_async.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_store_file_rejects_stale_generation_and_wrong_owner_type(self):
        kb = _make_kb()
        stale_context = ExecutionContext(
            instance_uuid=CONTEXT.instance_uuid,
            workspace_uuid=CONTEXT.workspace_uuid,
            placement_generation=CONTEXT.placement_generation + 1,
        )
        plugin_key = StorageMgr.scoped_object_key(
            CONTEXT,
            owner_type='plugin_config',
            owner='plugin:test',
            key='config.pdf',
        )

        for object_key in (_upload_key('stale.pdf', context=stale_context), plugin_key, 'raw.pdf'):
            with pytest.raises(WorkspaceNotFoundError, match='Upload not found'):
                await kb.store_file(CONTEXT, object_key)

        kb.ap.storage_mgr.storage_provider.exists.assert_not_awaited()


class TestStoreZipFile:
    @pytest.mark.asyncio
    async def test_store_zip_file_extracts_supported_files_and_skips_noise(self):
        kb = _make_kb()
        kb.ap.storage_mgr.storage_provider.load = AsyncMock(
            return_value=_make_zip_bytes(
                {
                    'doc1.pdf': b'pdf',
                    'doc2.txt': b'text',
                    'subdir/doc3.md': b'markdown',
                    'page.html': b'html',
                    'image.png': b'png',
                    '.hidden': b'hidden',
                    '__MACOSX/doc1.pdf': b'metadata',
                }
            )
        )
        kb.store_file = AsyncMock(side_effect=['task-pdf', 'task-txt', 'task-md', 'task-html'])

        zip_key = _upload_key('archive.zip')
        task_id = await kb._store_zip_file(CONTEXT, zip_key, parser_plugin_id='parser/plugin')

        assert task_id == 'task-pdf'
        assert kb.ap.storage_mgr.storage_provider.save.await_count == 4
        saved_names = [call.args[0] for call in kb.ap.storage_mgr.storage_provider.save.await_args_list]
        assert {name.rsplit('.', 1)[-1] for name in saved_names} == {'pdf', 'txt', 'md', 'html'}
        for name in saved_names:
            StorageMgr.require_scoped_object_key(
                CONTEXT,
                name,
                expected_owner_type='upload_document',
            )
        forwarded_keys = [call.args[1] for call in kb.store_file.await_args_list]
        assert forwarded_keys == saved_names
        kb.ap.storage_mgr.storage_provider.delete.assert_awaited_once_with(zip_key)

    @pytest.mark.asyncio
    async def test_store_zip_file_raises_when_no_supported_files(self):
        kb = _make_kb()
        kb.ap.storage_mgr.storage_provider.load = AsyncMock(
            return_value=_make_zip_bytes({'image.png': b'png', 'video.mp4': b'video'})
        )
        kb.store_file = AsyncMock()

        with pytest.raises(Exception, match='No supported files found'):
            await kb._store_zip_file(CONTEXT, _upload_key('archive.zip'))

        kb.store_file.assert_not_awaited()
        kb.ap.storage_mgr.storage_provider.delete.assert_awaited_once_with(_upload_key('archive.zip'))


class TestStoreFileTask:
    @pytest.mark.asyncio
    async def test_store_file_task_marks_completed_and_cleans_storage(self):
        kb = _make_kb()
        kb._ingest_document = AsyncMock(return_value={'status': 'completed'})
        object_key = _upload_key('test.pdf')
        file_obj = SimpleNamespace(uuid='file-uuid', file_name=object_key, extension='pdf')
        task_context = Mock()

        await kb._store_file_task(CONTEXT, file_obj, task_context)

        task_context.set_current_action.assert_called_once_with('Processing file')
        kb.ap.storage_mgr.storage_provider.size.assert_awaited_once_with(object_key)
        kb._ingest_document.assert_awaited_once()
        assert kb.ap.persistence_mgr.execute_async.await_count == 2
        kb.ap.storage_mgr.storage_provider.delete.assert_awaited_once_with(object_key)

    @pytest.mark.asyncio
    async def test_store_file_task_marks_failed_and_cleans_storage(self):
        kb = _make_kb()
        kb._ingest_document = AsyncMock(return_value={'status': 'failed', 'error_message': 'parser failed'})
        object_key = _upload_key('bad.pdf')
        file_obj = SimpleNamespace(uuid='file-uuid', file_name=object_key, extension='pdf')
        task_context = Mock()

        with pytest.raises(Exception, match='parser failed'):
            await kb._store_file_task(CONTEXT, file_obj, task_context)

        assert kb.ap.persistence_mgr.execute_async.await_count == 2
        kb.ap.storage_mgr.storage_provider.delete.assert_awaited_once_with(object_key)


class TestDeleteDocument:
    @pytest.mark.asyncio
    async def test_delete_document_returns_false_when_no_plugin_id(self):
        kb = _make_kb(plugin_id=None)

        result = await kb._delete_document(CONTEXT, 'doc-id')

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_document_calls_configured_rag_plugin(self):
        kb = _make_kb()
        kb.ap.plugin_connector.call_rag_delete_document = AsyncMock(return_value=True)

        result = await kb._delete_document(CONTEXT, 'doc-id')

        assert result is True
        kb.ap.plugin_connector.call_rag_delete_document.assert_awaited_once_with(
            'author/engine', 'doc-id', 'test-kb-uuid'
        )

    @pytest.mark.asyncio
    async def test_delete_document_returns_false_on_plugin_error(self):
        kb = _make_kb()
        kb.ap.plugin_connector.call_rag_delete_document = AsyncMock(side_effect=Exception('plugin error'))

        result = await kb._delete_document(CONTEXT, 'doc-id')

        assert result is False
        kb.ap.logger.error.assert_called_once()
