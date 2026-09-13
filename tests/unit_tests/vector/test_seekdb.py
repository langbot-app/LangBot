from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from langbot.pkg.vector.vdbs.seekdb import SeekDBVectorDatabase


def _adapter_with_collection(collection: MagicMock) -> SeekDBVectorDatabase:
    adapter = SeekDBVectorDatabase.__new__(SeekDBVectorDatabase)
    adapter.ap = SimpleNamespace(logger=MagicMock())
    adapter.client = MagicMock()
    adapter.client.has_collection.return_value = True
    adapter._collections = {'knowledge_base': collection}
    adapter._runtime_cache_limit = 16
    return adapter


@pytest.mark.asyncio
async def test_add_embeddings_upserts_and_preserves_text() -> None:
    collection = MagicMock()
    adapter = _adapter_with_collection(collection)
    adapter._get_or_create_collection_internal = AsyncMock(return_value=collection)
    original = 'He said "hello".\nC:\\notes\\file.txt isn\'t empty. 中文'

    await adapter.add_embeddings(
        collection='knowledge_base',
        ids=['document-a'],
        embeddings_list=[[1.0, 0.0, 0.0]],
        metadatas=[{'text': original}],
        documents=[original],
    )

    collection.upsert.assert_called_once_with(
        ids=['document-a'],
        embeddings=[[1.0, 0.0, 0.0]],
        metadatas=[{'text': original}],
        documents=[original],
    )
    collection.add.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('search_type', 'scores', 'expected_distances'),
    [
        ('full_text', [0.4508196721, 0.25], [0.5491803279, 0.75]),
        ('hybrid', [0.0328, 0.0323, 0.0159], [0.9672, 0.9677, 0.9841]),
    ],
)
async def test_search_converts_relevance_scores_to_distances(
    search_type: str,
    scores: list[float],
    expected_distances: list[float],
) -> None:
    collection = MagicMock()
    collection.hybrid_search.return_value = {
        'ids': [['best', 'weak', 'noise'][: len(scores)]],
        'metadatas': [[{} for _ in scores]],
        'distances': [scores],
    }
    adapter = _adapter_with_collection(collection)

    results = await adapter.search(
        collection='knowledge_base',
        query_embedding=[1.0, 0.0, 0.0],
        k=len(scores),
        search_type=search_type,
        query_text='orchid',
        vector_weight=0.65,
    )

    assert results['distances'][0] == pytest.approx(expected_distances)
    assert results['distances'][0] == sorted(results['distances'][0])


@pytest.mark.asyncio
async def test_vector_search_keeps_seekdb_cosine_distances() -> None:
    collection = MagicMock()
    collection.query.return_value = {
        'ids': [['best', 'weak']],
        'metadatas': [[{}, {}]],
        'distances': [[0.1, 0.25]],
    }
    adapter = _adapter_with_collection(collection)

    results = await adapter.search(
        collection='knowledge_base',
        query_embedding=[1.0, 0.0, 0.0],
        k=2,
        search_type='vector',
    )

    assert results['distances'] == [[0.1, 0.25]]
