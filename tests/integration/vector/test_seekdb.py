"""Real embedded SeekDB regression tests.

Install the optional dependency before running these slow tests::

    uv sync --dev --extra seekdb
    uv run pytest tests/integration/vector/test_seekdb.py -m slow -q
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
import uuid

import pytest

pytest.importorskip('pyseekdb')

from langbot.pkg.vector.vdbs.seekdb import SeekDBVectorDatabase


pytestmark = [pytest.mark.integration, pytest.mark.slow]


@pytest.fixture
async def backend(tmp_path):
    app = SimpleNamespace(
        instance_config=SimpleNamespace(
            data={
                'vdb': {
                    'runtime_cache_limit': 16,
                    'seekdb': {
                        'mode': 'embedded',
                        'path': str(tmp_path),
                        'database': 'langbot_test',
                    },
                }
            }
        ),
        logger=SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
        ),
    )
    database = SeekDBVectorDatabase(app)
    collection = f'test_{uuid.uuid4().hex}'
    yield database, collection

    await database.delete_collection(collection)
    await database.close()


@pytest.mark.asyncio
async def test_upsert_and_text_round_trip(backend) -> None:
    database, collection = backend
    original = 'He said "hello".\nC:\\notes\\file.txt isn\'t empty. 中文'
    updated = f'Updated: {original}'

    await database.add_embeddings(
        collection,
        ['document-a'],
        [[1.0, 0.0, 0.0]],
        [{'file_id': 'file-a', 'text': original}],
        [original],
    )
    await database.add_embeddings(
        collection,
        ['document-a'],
        [[0.0, 1.0, 0.0]],
        [{'file_id': 'file-a', 'text': updated}],
        [updated],
    )

    items, _ = await database.list_by_filter(collection, {'file_id': 'file-a'})

    assert len(items) == 1
    assert items[0]['id'] == 'document-a'
    assert items[0]['document'] == updated
    assert items[0]['metadata']['text'] == updated


@pytest.mark.asyncio
async def test_full_text_and_hybrid_results_keep_relevance_order(backend) -> None:
    database, collection = backend
    documents = [
        'orchid orchid orchid flower',
        'orchid grows in a garden with many other beautiful plants',
        'a completely unrelated topic',
    ]

    await database.add_embeddings(
        collection,
        ['best', 'weak', 'noise'],
        [[1.0, 0.0, 0.0], [0.9, 0.1, 0.0], [0.0, 0.0, 1.0]],
        [
            {'file_id': item_id, 'document_id': item_id, 'text': document}
            for item_id, document in zip(['best', 'weak', 'noise'], documents, strict=True)
        ],
        documents,
    )
    seekdb_collection = await database.get_or_create_collection(collection)
    await asyncio.to_thread(seekdb_collection.refresh_index)

    full_text = await database.search(
        collection,
        [1.0, 0.0, 0.0],
        k=3,
        search_type='full_text',
        query_text='orchid',
    )
    hybrid = await database.search(
        collection,
        [1.0, 0.0, 0.0],
        k=3,
        search_type='hybrid',
        query_text='orchid',
        vector_weight=0.65,
    )

    assert full_text['ids'][0][:2] == ['best', 'weak']
    assert full_text['distances'][0] == sorted(full_text['distances'][0])
    assert hybrid['ids'][0] == ['best', 'weak', 'noise']
    assert hybrid['distances'][0] == sorted(hybrid['distances'][0])
