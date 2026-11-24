"""pgvector search-type handling.

pgvector only implements vector similarity. LangRAG lets users pick ``hybrid``
or ``full_text`` retrieval, and before this fix every retrieval of such a
knowledge base failed on pgvector deployments (LangBot Cloud) with
"pgvector currently supports vector search only". Hybrid queries carry a
query embedding, so they now degrade to vector search like the other
vector-only backends (Qdrant, Milvus); full-text queries carry no embedding
and fail with an actionable message before touching the database.
"""

from __future__ import annotations

import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.vector.vdbs.pgvector_db import PgVectorDatabase, PgVectorScope

pytestmark = pytest.mark.asyncio


def _database():
    database = object.__new__(PgVectorDatabase)
    database.allowed_dimensions = frozenset({2})
    database.ap = SimpleNamespace(logger=Mock())
    database.get_or_create_collection = AsyncMock()
    rows = [SimpleNamespace(vector_id='v1', text='hello', file_id='f1', chunk_uuid='c1', distance=0.25)]
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: rows)))

    @contextlib.asynccontextmanager
    async def _session(_scope):
        yield session

    database._session = _session
    return database, session


def _scope():
    return PgVectorScope(workspace_uuid='ws-a', knowledge_base_uuid='kb-a', embedding_dimension=2)


async def test_vector_search_returns_rows():
    database, session = _database()

    result = await database.search('kb-a', [0.1, 0.2], k=3, scope=_scope())

    assert result == {
        'ids': [['v1']],
        'distances': [[0.25]],
        'metadatas': [[{'text': 'hello', 'file_id': 'f1', 'uuid': 'c1'}]],
    }
    session.execute.assert_awaited_once()
    database.ap.logger.warning.assert_not_called()


async def test_hybrid_search_degrades_to_vector_search_and_warns_once_per_collection():
    database, session = _database()

    first = await database.search(
        'kb-a', [0.1, 0.2], k=3, search_type='hybrid', query_text='hello', vector_weight=0.7, scope=_scope()
    )
    second = await database.search('kb-a', [0.1, 0.2], k=3, search_type='hybrid', query_text='hi', scope=_scope())

    assert first['ids'] == [['v1']]
    assert second['ids'] == [['v1']]
    assert session.execute.await_count == 2
    database.ap.logger.warning.assert_called_once()
    assert 'hybrid' in database.ap.logger.warning.call_args.args[0]


@pytest.mark.parametrize(
    ('search_type', 'embedding'),
    [('full_text', []), ('hybrid', []), ('semantic', [0.1, 0.2])],
)
async def test_unsupported_search_fails_with_actionable_error_before_querying(search_type, embedding):
    database, session = _database()

    with pytest.raises(ValueError, match="change the knowledge base retrieval type to 'vector'"):
        await database.search('kb-a', embedding, k=3, search_type=search_type, query_text='hello', scope=_scope())

    session.execute.assert_not_awaited()
    database.get_or_create_collection.assert_not_awaited()
