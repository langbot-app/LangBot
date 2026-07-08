"""Unit tests for RuntimeKnowledgeBase file storage behavior."""

from __future__ import annotations

import io
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.rag.knowledge.kbmgr import RuntimeKnowledgeBase


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
    app.storage_mgr = Mock()
    app.storage_mgr.storage_provider = Mock()
    app.storage_mgr.storage_provider.exists = AsyncMock(return_value=True)
    app.storage_mgr.storage_provider.load = AsyncMock()
    app.storage_mgr.storage_provider.save = AsyncMock()
    app.storage_mgr.storage_provider.size = AsyncMock(return_value=123)
    app.storage_mgr.storage_provider.delete = AsyncMock()
    app.persistence_mgr = Mock()
    app.persistence_mgr.execute_async = AsyncMock()
    app.plugin_connector = Mock()
    return app


def _make_kb(plugin_id: str | None = 'author/engine') -> RuntimeKnowledgeBase:
    kb_entity = Mock()
    kb_entity.uuid = 'test-kb-uuid'
    kb_entity.collection_id = 'test-collection'
    kb_entity.creation_settings = {}
    kb_entity.knowledge_engine_plugin_id = plugin_id
    return RuntimeKnowledgeBase(_make_app(), kb_entity)


class TestStoreFile:
    @pytest.mark.asyncio
    async def test_store_file_creates_pending_record_and_user_task(self):
        kb = _make_kb()

        def create_user_task(coro, **kwargs):
            coro.close()
            return SimpleNamespace(id='task-1', kwargs=kwargs)

        kb.ap.task_mgr.create_user_task = Mock(side_effect=create_user_task)

        task_id = await kb.store_file('documents/test.pdf')

        assert task_id == 'task-1'
        kb.ap.storage_mgr.storage_provider.exists.assert_awaited_once_with('documents/test.pdf')
        kb.ap.persistence_mgr.execute_async.assert_awaited_once()
        call_kwargs = kb.ap.task_mgr.create_user_task.call_args.kwargs
        assert call_kwargs['kind'] == 'knowledge-operation'
        assert call_kwargs['name'] == 'knowledge-store-file-documents/test.pdf'
        assert call_kwargs['label'] == 'Store file documents/test.pdf'

    @pytest.mark.asyncio
    async def test_store_file_raises_when_source_file_missing(self):
        kb = _make_kb()
        kb.ap.storage_mgr.storage_provider.exists = AsyncMock(return_value=False)

        with pytest.raises(Exception, match='File missing.pdf not found'):
            await kb.store_file('missing.pdf')

        kb.ap.persistence_mgr.execute_async.assert_not_awaited()
        kb.ap.task_mgr.create_user_task.assert_not_called()


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

        task_id = await kb._store_zip_file('archive.zip', parser_plugin_id='parser/plugin')

        assert task_id == 'task-pdf'
        assert kb.ap.storage_mgr.storage_provider.save.await_count == 4
        saved_names = [call.args[0] for call in kb.ap.storage_mgr.storage_provider.save.await_args_list]
        assert any(name.startswith('doc1_') and name.endswith('.pdf') for name in saved_names)
        assert any(name.startswith('doc2_') and name.endswith('.txt') for name in saved_names)
        assert any(name.startswith('subdir_doc3_') and name.endswith('.md') for name in saved_names)
        assert any(name.startswith('page_') and name.endswith('.html') for name in saved_names)
        assert not any('image' in name for name in saved_names)
        assert not any('hidden' in name for name in saved_names)
        assert not any('__MACOSX' in name for name in saved_names)
        kb.ap.storage_mgr.storage_provider.delete.assert_awaited_once_with('archive.zip')

    @pytest.mark.asyncio
    async def test_store_zip_file_raises_when_no_supported_files(self):
        kb = _make_kb()
        kb.ap.storage_mgr.storage_provider.load = AsyncMock(
            return_value=_make_zip_bytes({'image.png': b'png', 'video.mp4': b'video'})
        )
        kb.store_file = AsyncMock()

        with pytest.raises(Exception, match='No supported files found'):
            await kb._store_zip_file('archive.zip')

        kb.store_file.assert_not_awaited()
        kb.ap.storage_mgr.storage_provider.delete.assert_awaited_once_with('archive.zip')


class TestStoreFileTask:
    @pytest.mark.asyncio
    async def test_store_file_task_marks_completed_and_cleans_storage(self):
        kb = _make_kb()
        kb._ingest_document = AsyncMock(return_value={'status': 'completed'})
        file_obj = SimpleNamespace(uuid='file-uuid', file_name='test.pdf', extension='pdf')
        task_context = Mock()

        await kb._store_file_task(file_obj, task_context)

        task_context.set_current_action.assert_called_once_with('Processing file')
        kb.ap.storage_mgr.storage_provider.size.assert_awaited_once_with('test.pdf')
        kb._ingest_document.assert_awaited_once()
        assert kb.ap.persistence_mgr.execute_async.await_count == 2
        kb.ap.storage_mgr.storage_provider.delete.assert_awaited_once_with('test.pdf')

    @pytest.mark.asyncio
    async def test_store_file_task_marks_failed_and_cleans_storage(self):
        kb = _make_kb()
        kb._ingest_document = AsyncMock(return_value={'status': 'failed', 'error_message': 'parser failed'})
        file_obj = SimpleNamespace(uuid='file-uuid', file_name='bad.pdf', extension='pdf')
        task_context = Mock()

        with pytest.raises(Exception, match='parser failed'):
            await kb._store_file_task(file_obj, task_context)

        assert kb.ap.persistence_mgr.execute_async.await_count == 2
        kb.ap.storage_mgr.storage_provider.delete.assert_awaited_once_with('bad.pdf')


class TestDeleteDocument:
    @pytest.mark.asyncio
    async def test_delete_document_returns_false_when_no_plugin_id(self):
        kb = _make_kb(plugin_id=None)

        result = await kb._delete_document('doc-id')

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_document_calls_configured_rag_plugin(self):
        kb = _make_kb()
        kb.ap.plugin_connector.call_rag_delete_document = AsyncMock(return_value=True)

        result = await kb._delete_document('doc-id')

        assert result is True
        kb.ap.plugin_connector.call_rag_delete_document.assert_awaited_once_with(
            'author/engine', 'doc-id', 'test-kb-uuid'
        )

    @pytest.mark.asyncio
    async def test_delete_document_returns_false_on_plugin_error(self):
        kb = _make_kb()
        kb.ap.plugin_connector.call_rag_delete_document = AsyncMock(side_effect=Exception('plugin error'))

        result = await kb._delete_document('doc-id')

        assert result is False
        kb.ap.logger.error.assert_called_once()
