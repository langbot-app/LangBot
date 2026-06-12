"""Integration tests for the Valkey Search VDB backend.

These are SLOW, real-server tests.  They are gated on ``TEST_VALKEY_URL`` and
skipped when it is unset (same precedent as the PostgreSQL migration tests).

Run locally against valkey/valkey-bundle:9.1.0::

    podman run -d --name valkey-test-langbot -p 6380:6379 valkey/valkey-bundle:9.1.0
    TEST_VALKEY_URL=valkey://localhost:6380 \\
        uv run pytest tests/integration/vector/test_valkey_search.py -m slow -q

The default upstream fast CI lane (``-m "not slow"``) skips these; the local
supervisor validator MUST run them.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from types import SimpleNamespace
from urllib.parse import urlparse

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def _parse_valkey_url(url: str) -> tuple[str, int, int]:
    """Parse ``valkey://host:port/db`` into ``(host, port, db)``."""
    parsed = urlparse(url)
    host = parsed.hostname or 'localhost'
    port = parsed.port or 6379
    db = 0
    if parsed.path and parsed.path.strip('/'):
        try:
            db = int(parsed.path.strip('/'))
        except ValueError:
            db = 0
    return host, port, db


@pytest.fixture
def valkey_config():
    url = os.environ.get('TEST_VALKEY_URL')
    if not url:
        pytest.skip('TEST_VALKEY_URL not set')
    host, port, db = _parse_valkey_url(url)
    return {
        'host': host,
        'port': port,
        'db': db,
        'password': '',
        'username': '',
        'tls': False,
        'index_algorithm': 'HNSW',
        'distance_metric': 'COSINE',
    }


def _make_ap(valkey_config):
    """Build a minimal fake ``ap`` with the config + a no-op logger."""
    logger = SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        error=lambda *a, **k: None,
        debug=lambda *a, **k: None,
    )
    instance_config = SimpleNamespace(data={'vdb': {'valkey_search': valkey_config}})
    return SimpleNamespace(instance_config=instance_config, logger=logger)


@pytest.fixture
async def backend(valkey_config):
    """Create a Valkey Search backend, skip if module/server unavailable."""
    from langbot.pkg.vector.vdbs.valkey_search import (
        ValkeySearchVectorDatabase,
        VALKEY_SEARCH_AVAILABLE,
    )
    from glide import ft

    if not VALKEY_SEARCH_AVAILABLE:
        pytest.skip('valkey-glide not installed')

    ap = _make_ap(valkey_config)
    db = ValkeySearchVectorDatabase(ap)
    client = await db._ensure_client()

    # Module-presence gate: FT.LIST must be available (Search module loaded).
    try:
        await ft.list(client)
    except Exception as exc:  # noqa: BLE001
        await client.close()
        pytest.skip(f'Valkey Search module not available: {exc}')

    collection = f'test_{uuid.uuid4().hex[:12]}'
    yield db, collection

    # Cleanup
    try:
        await db.delete_collection(collection)
    except Exception:
        pass
    if db._client is not None:
        await db._client.close()


async def _poll_until(coro_factory, predicate, timeout=5.0, interval=0.2):
    """Poll an async result until predicate is true (indexer is async)."""
    deadline = asyncio.get_event_loop().time() + timeout
    result = await coro_factory()
    while not predicate(result) and asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(interval)
        result = await coro_factory()
    return result


def _sample_docs():
    ids = ['d1', 'd2', 'd3']
    embeddings = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.9, 0.1, 0.0, 0.0],
    ]
    metadatas = [
        {'file_id': 'fileA', 'topic': 'cats'},
        {'file_id': 'fileB', 'topic': 'dogs'},
        {'file_id': 'fileA', 'topic': 'cats'},
    ]
    documents = [
        'the quick brown fox',
        'lazy dogs sleeping',
        'foxes and cats playing',
    ]
    return ids, embeddings, metadatas, documents


@pytest.mark.asyncio
async def test_add_and_vector_search(backend):
    db, collection = backend
    ids, embeddings, metadatas, documents = _sample_docs()
    await db.add_embeddings(collection, ids, embeddings, metadatas, documents)

    result = await _poll_until(
        lambda: db.search(collection, [1.0, 0.0, 0.0, 0.0], k=3, search_type='vector'),
        lambda r: len(r['ids'][0]) >= 1,
    )
    assert len(result['ids'][0]) >= 1
    # Closest to [1,0,0,0] should be d1.
    assert result['ids'][0][0] == 'd1'
    assert all(isinstance(d, float) for d in result['distances'][0])


@pytest.mark.asyncio
async def test_full_text_search(backend):
    db, collection = backend
    ids, embeddings, metadatas, documents = _sample_docs()
    await db.add_embeddings(collection, ids, embeddings, metadatas, documents)

    result = await _poll_until(
        lambda: db.search(collection, [0.0, 0.0, 0.0, 0.0], k=5, search_type='full_text', query_text='dogs'),
        lambda r: len(r['ids'][0]) >= 1,
    )
    assert 'd2' in result['ids'][0]


@pytest.mark.asyncio
async def test_hybrid_filter_then_knn(backend):
    db, collection = backend
    ids, embeddings, metadatas, documents = _sample_docs()
    await db.add_embeddings(collection, ids, embeddings, metadatas, documents)

    result = await _poll_until(
        lambda: db.search(
            collection,
            [1.0, 0.0, 0.0, 0.0],
            k=5,
            search_type='hybrid',
            query_text='cats',
            filter={'file_id': 'fileA'},
        ),
        lambda r: len(r['ids'][0]) >= 1,
    )
    # Only fileA docs (d1, d3) should be candidates.
    assert set(result['ids'][0]).issubset({'d1', 'd3'})


@pytest.mark.asyncio
async def test_vector_weight_not_honored(backend):
    """Passing different vector_weight values must NOT change ranking."""
    db, collection = backend
    ids, embeddings, metadatas, documents = _sample_docs()
    await db.add_embeddings(collection, ids, embeddings, metadatas, documents)

    common = dict(
        collection=collection, query_embedding=[1.0, 0.0, 0.0, 0.0], k=3, search_type='hybrid', query_text='cats'
    )
    await _poll_until(lambda: db.search(**common), lambda r: len(r['ids'][0]) >= 1)

    r_low = await db.search(**common, vector_weight=0.1)
    r_high = await db.search(**common, vector_weight=0.9)
    assert r_low['ids'][0] == r_high['ids'][0]


@pytest.mark.asyncio
async def test_filter_operators(backend):
    db, collection = backend
    ids, embeddings, metadatas, documents = _sample_docs()
    await db.add_embeddings(collection, ids, embeddings, metadatas, documents)

    # Wait for indexing.
    await _poll_until(
        lambda: db.list_by_filter(collection, limit=10),
        lambda r: r[1] >= 3,
    )

    # $eq
    items, total = await db.list_by_filter(collection, filter={'file_id': 'fileA'})
    assert total == 2
    assert {it['id'] for it in items} == {'d1', 'd3'}

    # $ne
    items, total = await db.list_by_filter(collection, filter={'file_id': {'$ne': 'fileA'}})
    assert {it['id'] for it in items} == {'d2'}

    # $in
    items, total = await db.list_by_filter(collection, filter={'file_id': {'$in': ['fileA', 'fileB']}})
    assert total == 3

    # $nin
    items, total = await db.list_by_filter(collection, filter={'file_id': {'$nin': ['fileB']}})
    assert {it['id'] for it in items} == {'d1', 'd3'}


@pytest.mark.asyncio
async def test_delete_by_file_id(backend):
    db, collection = backend
    ids, embeddings, metadatas, documents = _sample_docs()
    await db.add_embeddings(collection, ids, embeddings, metadatas, documents)
    await _poll_until(lambda: db.list_by_filter(collection, limit=10), lambda r: r[1] >= 3)

    await db.delete_by_file_id(collection, 'fileA')
    items, total = await _poll_until(
        lambda: db.list_by_filter(collection, limit=10),
        lambda r: r[1] <= 1,
    )
    assert {it['id'] for it in items} == {'d2'}


@pytest.mark.asyncio
async def test_delete_by_filter_returns_count(backend):
    db, collection = backend
    ids, embeddings, metadatas, documents = _sample_docs()
    await db.add_embeddings(collection, ids, embeddings, metadatas, documents)
    await _poll_until(lambda: db.list_by_filter(collection, limit=10), lambda r: r[1] >= 3)

    deleted = await db.delete_by_filter(collection, filter={'file_id': 'fileA'})
    assert deleted == 2


@pytest.mark.asyncio
async def test_list_by_filter_pagination(backend):
    db, collection = backend
    ids, embeddings, metadatas, documents = _sample_docs()
    await db.add_embeddings(collection, ids, embeddings, metadatas, documents)
    await _poll_until(lambda: db.list_by_filter(collection, limit=10), lambda r: r[1] >= 3)

    page1, total = await db.list_by_filter(collection, limit=2, offset=0)
    assert total == 3
    assert len(page1) == 2

    page2, total = await db.list_by_filter(collection, limit=2, offset=2)
    assert total == 3
    assert len(page2) == 1


@pytest.mark.asyncio
async def test_delete_collection(backend):
    db, collection = backend
    ids, embeddings, metadatas, documents = _sample_docs()
    await db.add_embeddings(collection, ids, embeddings, metadatas, documents)
    await _poll_until(lambda: db.list_by_filter(collection, limit=10), lambda r: r[1] >= 3)

    await db.delete_collection(collection)

    # After dropping, search on a missing index returns empty.
    result = await db.search(collection, [1.0, 0.0, 0.0, 0.0], k=3, search_type='vector')
    assert result['ids'][0] == []
