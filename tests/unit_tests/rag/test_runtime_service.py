"""Tenant-aware tests for the plugin-facing RAG runtime service."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.rag.service.runtime import RAGRuntimeService
from langbot.pkg.workspace.errors import WorkspaceNotFoundError


WORKSPACE_UUID = '00000000-0000-0000-0000-00000000000a'
CONTEXT = ExecutionContext(
    instance_uuid='instance-a',
    workspace_uuid=WORKSPACE_UUID,
    placement_generation=4,
)


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def first(self):
        return None if self.value is None else (self.value,)


def _app(*, kb_uuid='kb-a', file_exists=True):
    persistence_results = [_ScalarResult(kb_uuid)]
    if file_exists is not None:
        persistence_results.append(_ScalarResult('file-a' if file_exists else None))
    return SimpleNamespace(
        workspace_service=SimpleNamespace(
            get_execution_binding=AsyncMock(return_value=SimpleNamespace(instance_uuid='instance-a'))
        ),
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock(side_effect=persistence_results)),
        vector_db_mgr=SimpleNamespace(
            upsert=AsyncMock(),
            search=AsyncMock(return_value=[{'id': 'chunk-a'}]),
            delete_by_file_id=AsyncMock(),
            delete_by_filter=AsyncMock(return_value=3),
            list_by_filter=AsyncMock(return_value=([{'id': 'chunk-a'}], 1)),
        ),
        storage_mgr=SimpleNamespace(
            load_scoped_object_key=AsyncMock(return_value=b'content'),
            storage_provider=SimpleNamespace(load=AsyncMock(return_value=b'content')),
        ),
    )


@pytest.mark.asyncio
async def test_vector_upsert_resolves_canonical_kb_and_forwards_trusted_context():
    app = _app()
    service = RAGRuntimeService(app)

    await service.vector_upsert(
        CONTEXT,
        'logical-collection',
        [[0.1, 0.2]],
        ['chunk-a'],
        metadata=[{'file_id': 'file-a'}],
        documents=['hello'],
    )

    app.vector_db_mgr.upsert.assert_awaited_once_with(
        execution_context=CONTEXT,
        knowledge_base_uuid='kb-a',
        vectors=[[0.1, 0.2]],
        ids=['chunk-a'],
        metadata=[{'file_id': 'file-a'}],
        documents=['hello'],
    )


@pytest.mark.asyncio
async def test_vector_upsert_rejects_mismatched_lengths():
    service = RAGRuntimeService(_app())
    with pytest.raises(ValueError, match='vectors and ids'):
        await service.vector_upsert(CONTEXT, 'kb-a', [[0.1]], ['a', 'b'])


@pytest.mark.asyncio
async def test_unknown_or_cross_workspace_collection_is_not_forwarded():
    app = _app(kb_uuid=None)
    service = RAGRuntimeService(app)

    with pytest.raises(WorkspaceNotFoundError):
        await service.vector_search(CONTEXT, 'kb-from-other-workspace', [0.1], 5)
    app.vector_db_mgr.search.assert_not_awaited()


@pytest.mark.asyncio
async def test_vector_search_forwards_all_search_options():
    app = _app()
    service = RAGRuntimeService(app)

    result = await service.vector_search(
        CONTEXT,
        'kb-a',
        [0.1, 0.2],
        7,
        filters={'file_id': 'file-a'},
        search_type='hybrid',
        query_text='hello',
        vector_weight=0.7,
    )

    assert result == [{'id': 'chunk-a'}]
    app.vector_db_mgr.search.assert_awaited_once_with(
        execution_context=CONTEXT,
        knowledge_base_uuid='kb-a',
        query_vector=[0.1, 0.2],
        limit=7,
        filter={'file_id': 'file-a'},
        search_type='hybrid',
        query_text='hello',
        vector_weight=0.7,
    )


@pytest.mark.asyncio
async def test_vector_delete_and_list_stay_on_canonical_kb():
    delete_app = _app()
    delete_service = RAGRuntimeService(delete_app)
    assert await delete_service.vector_delete(CONTEXT, 'logical', file_ids=['file-a']) == 1
    delete_app.vector_db_mgr.delete_by_file_id.assert_awaited_once_with(
        execution_context=CONTEXT,
        knowledge_base_uuid='kb-a',
        file_ids=['file-a'],
    )

    filter_app = _app()
    filter_service = RAGRuntimeService(filter_app)
    assert await filter_service.vector_delete(CONTEXT, 'logical', filters={'page': 1}) == 3
    filter_app.vector_db_mgr.delete_by_filter.assert_awaited_once_with(
        execution_context=CONTEXT,
        knowledge_base_uuid='kb-a',
        filter={'page': 1},
    )

    list_app = _app()
    list_service = RAGRuntimeService(list_app)
    assert await list_service.vector_list(CONTEXT, 'logical', {'page': 1}, 10, 2) == (
        [{'id': 'chunk-a'}],
        1,
    )
    list_app.vector_db_mgr.list_by_filter.assert_awaited_once_with(
        execution_context=CONTEXT,
        knowledge_base_uuid='kb-a',
        filter={'page': 1},
        limit=10,
        offset=2,
    )


@pytest.mark.asyncio
async def test_file_stream_requires_workspace_owned_file():
    app = _app(file_exists=True)
    app.persistence_mgr.execute_async = AsyncMock(return_value=_ScalarResult('file-a'))
    service = RAGRuntimeService(app)
    assert await service.get_file_stream(CONTEXT, 'nested/file.pdf') == b'content'
    app.storage_mgr.load_scoped_object_key.assert_awaited_once_with(
        CONTEXT,
        'nested/file.pdf',
        expected_owner_type='upload_document',
    )

    missing_app = _app(file_exists=False)
    missing_app.persistence_mgr.execute_async = AsyncMock(return_value=_ScalarResult(None))
    missing_service = RAGRuntimeService(missing_app)
    with pytest.raises(WorkspaceNotFoundError):
        await missing_service.get_file_stream(CONTEXT, 'other.pdf')
    missing_app.storage_mgr.load_scoped_object_key.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'unsafe_path',
    [
        '',
        '../secret.txt',
        '/absolute/path.txt',
        '..\\secret.txt',
        'nested\\..\\secret.txt',
        '%2e%2e/secret.txt',
        'nested/%2e%2e/secret.txt',
        'C:\\secret.txt',
        'safe/\x00file.txt',
    ],
)
async def test_file_stream_rejects_unsafe_paths_before_storage(unsafe_path):
    app = _app(file_exists=True)
    service = RAGRuntimeService(app)
    with pytest.raises(ValueError, match='Invalid storage path'):
        await service.get_file_stream(CONTEXT, unsafe_path)
    app.storage_mgr.load_scoped_object_key.assert_not_awaited()


@pytest.mark.asyncio
async def test_runtime_rejects_wrong_instance_binding():
    app = _app()
    app.workspace_service.get_execution_binding.return_value = SimpleNamespace(instance_uuid='instance-b')
    service = RAGRuntimeService(app)

    with pytest.raises(Exception, match='another LangBot instance'):
        await service.vector_search(CONTEXT, 'kb-a', [0.1], 1)
    app.persistence_mgr.execute_async.assert_not_awaited()


# The following classes preserve the pre-tenancy regression scenarios.  They
# intentionally exercise the same inputs through the new trusted
# ExecutionContext and assert the canonical Workspace-owned KB forwarded to the
# vector layer.
class TestRAGRuntimeServiceVectorUpsertRegression:
    @pytest.mark.asyncio
    async def test_vector_upsert_basic(self):
        app = _app()
        service = RAGRuntimeService(app)
        vectors = [[0.1, 0.2], [0.3, 0.4]]
        ids = ['id1', 'id2']

        await service.vector_upsert(CONTEXT, 'test_collection', vectors, ids)

        app.vector_db_mgr.upsert.assert_awaited_once_with(
            execution_context=CONTEXT,
            knowledge_base_uuid='kb-a',
            vectors=vectors,
            ids=ids,
            metadata=[{}, {}],
            documents=None,
        )

    @pytest.mark.asyncio
    async def test_vector_upsert_with_metadata(self):
        app = _app()
        metadata = [{'file_id': 'abc', 'page': 1}]

        await RAGRuntimeService(app).vector_upsert(
            CONTEXT,
            'test',
            [[0.1, 0.2]],
            ['id1'],
            metadata=metadata,
        )

        assert app.vector_db_mgr.upsert.await_args.kwargs['metadata'] == metadata

    @pytest.mark.asyncio
    async def test_vector_upsert_with_documents(self):
        app = _app()
        documents = ['This is a test document']

        await RAGRuntimeService(app).vector_upsert(
            CONTEXT,
            'test',
            [[0.1, 0.2]],
            ['id1'],
            documents=documents,
        )

        assert app.vector_db_mgr.upsert.await_args.kwargs['documents'] == documents


class TestRAGRuntimeServiceVectorSearchRegression:
    @pytest.mark.asyncio
    async def test_vector_search_basic(self):
        app = _app()
        query_vector = [0.1, 0.2, 0.3]

        result = await RAGRuntimeService(app).vector_search(
            CONTEXT,
            'test',
            query_vector,
            5,
        )

        assert result == [{'id': 'chunk-a'}]
        app.vector_db_mgr.search.assert_awaited_once_with(
            execution_context=CONTEXT,
            knowledge_base_uuid='kb-a',
            query_vector=query_vector,
            limit=5,
            filter=None,
            search_type='vector',
            query_text='',
            vector_weight=None,
        )

    @pytest.mark.asyncio
    async def test_vector_search_with_filters(self):
        app = _app()
        filters = {'file_id': 'abc'}

        await RAGRuntimeService(app).vector_search(
            CONTEXT,
            'test',
            [0.1, 0.2],
            10,
            filters=filters,
        )

        assert app.vector_db_mgr.search.await_args.kwargs['filter'] == filters

    @pytest.mark.asyncio
    async def test_vector_search_hybrid_mode(self):
        app = _app()

        await RAGRuntimeService(app).vector_search(
            CONTEXT,
            'test',
            [0.1, 0.2],
            10,
            search_type='hybrid',
            query_text='search query',
            vector_weight=0.7,
        )

        kwargs = app.vector_db_mgr.search.await_args.kwargs
        assert kwargs['search_type'] == 'hybrid'
        assert kwargs['query_text'] == 'search query'
        assert kwargs['vector_weight'] == 0.7


class TestRAGRuntimeServiceVectorDeleteRegression:
    @pytest.mark.asyncio
    async def test_vector_delete_by_file_ids(self):
        app = _app()

        result = await RAGRuntimeService(app).vector_delete(
            CONTEXT,
            'test',
            file_ids=['file1', 'file2', 'file3'],
        )

        assert result == 3
        app.vector_db_mgr.delete_by_file_id.assert_awaited_once_with(
            execution_context=CONTEXT,
            knowledge_base_uuid='kb-a',
            file_ids=['file1', 'file2', 'file3'],
        )

    @pytest.mark.asyncio
    async def test_vector_delete_by_filters(self):
        app = _app()
        filters = {'status': 'deleted'}
        app.vector_db_mgr.delete_by_filter.return_value = 5

        result = await RAGRuntimeService(app).vector_delete(
            CONTEXT,
            'test',
            filters=filters,
        )

        assert result == 5
        assert app.vector_db_mgr.delete_by_filter.await_args.kwargs['filter'] == filters

    @pytest.mark.asyncio
    async def test_vector_delete_no_params(self):
        app = _app()

        result = await RAGRuntimeService(app).vector_delete(CONTEXT, 'test')

        assert result == 0
        app.vector_db_mgr.delete_by_file_id.assert_not_awaited()
        app.vector_db_mgr.delete_by_filter.assert_not_awaited()


class TestRAGRuntimeServiceVectorListRegression:
    @pytest.mark.asyncio
    async def test_vector_list_basic(self):
        app = _app()

        items, total = await RAGRuntimeService(app).vector_list(CONTEXT, 'test')

        assert items == [{'id': 'chunk-a'}]
        assert total == 1
        app.vector_db_mgr.list_by_filter.assert_awaited_once_with(
            execution_context=CONTEXT,
            knowledge_base_uuid='kb-a',
            filter=None,
            limit=20,
            offset=0,
        )

    @pytest.mark.asyncio
    async def test_vector_list_with_pagination(self):
        app = _app()

        await RAGRuntimeService(app).vector_list(CONTEXT, 'test', limit=50, offset=100)

        kwargs = app.vector_db_mgr.list_by_filter.await_args.kwargs
        assert kwargs['limit'] == 50
        assert kwargs['offset'] == 100

    @pytest.mark.asyncio
    async def test_vector_list_with_filters(self):
        app = _app()
        filters = {'file_id': 'abc'}

        await RAGRuntimeService(app).vector_list(CONTEXT, 'test', filters=filters)

        assert app.vector_db_mgr.list_by_filter.await_args.kwargs['filter'] == filters


class TestRAGRuntimeServiceGetFileStreamRegression:
    @pytest.mark.asyncio
    async def test_get_file_stream_basic(self):
        app = _app(file_exists=True)
        app.persistence_mgr.execute_async = AsyncMock(return_value=_ScalarResult('file-a'))

        result = await RAGRuntimeService(app).get_file_stream(
            CONTEXT,
            'knowledge/files/doc.pdf',
        )

        assert result == b'content'
        app.storage_mgr.load_scoped_object_key.assert_awaited_once_with(
            CONTEXT,
            'knowledge/files/doc.pdf',
            expected_owner_type='upload_document',
        )

    @pytest.mark.asyncio
    async def test_get_file_stream_empty_result(self):
        app = _app(file_exists=True)
        app.persistence_mgr.execute_async = AsyncMock(return_value=_ScalarResult('file-a'))
        app.storage_mgr.load_scoped_object_key.return_value = None

        result = await RAGRuntimeService(app).get_file_stream(CONTEXT, 'nonexistent.pdf')

        assert result == b''

    @pytest.mark.asyncio
    async def test_get_file_stream_normalizes_safe_path(self):
        app = _app(file_exists=True)
        app.persistence_mgr.execute_async = AsyncMock(return_value=_ScalarResult('file-a'))

        result = await RAGRuntimeService(app).get_file_stream(
            CONTEXT,
            'knowledge/./files/doc.pdf',
        )

        assert result == b'content'
        app.storage_mgr.load_scoped_object_key.assert_awaited_once_with(
            CONTEXT,
            'knowledge/files/doc.pdf',
            expected_owner_type='upload_document',
        )

    @pytest.mark.asyncio
    async def test_get_file_stream_path_traversal_blocked(self):
        app = _app(file_exists=True)
        service = RAGRuntimeService(app)

        with pytest.raises(ValueError, match='Invalid storage path'):
            await service.get_file_stream(CONTEXT, '/etc/passwd')
        with pytest.raises(ValueError, match='Invalid storage path'):
            await service.get_file_stream(CONTEXT, 'knowledge/../../../etc/passwd')

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        'storage_path',
        [
            '',
            '../secret.txt',
            '/absolute/path.txt',
            '..\\secret.txt',
            'nested\\..\\secret.txt',
            '%2e%2e/secret.txt',
            'nested/%2e%2e/secret.txt',
            'C:\\secret.txt',
            'safe/\x00file.txt',
        ],
    )
    async def test_get_file_stream_rejects_unsafe_paths(self, storage_path: str):
        app = _app(file_exists=True)

        with pytest.raises(ValueError, match='Invalid storage path'):
            await RAGRuntimeService(app).get_file_stream(CONTEXT, storage_path)

        app.storage_mgr.load_scoped_object_key.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_file_stream_normalizes_path(self):
        app = _app(file_exists=True)
        app.persistence_mgr.execute_async = AsyncMock(return_value=_ScalarResult('file-a'))

        await RAGRuntimeService(app).get_file_stream(CONTEXT, 'knowledge/files/test.pdf')

        app.storage_mgr.load_scoped_object_key.assert_awaited_once_with(
            CONTEXT,
            'knowledge/files/test.pdf',
            expected_owner_type='upload_document',
        )
