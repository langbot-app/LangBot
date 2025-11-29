"""
Unit tests for SeekDB vector database adapter.

Tests the SeekDB integration with LangBot's knowledge base system.

Note: These tests use a test adapter that mirrors the SeekDBVectorDatabase
implementation. This is necessary because LangBot's module structure has
circular imports that prevent direct import of the real adapter in test
context. The test adapter implementation is kept in sync with the real
adapter to ensure test accuracy.
"""

import asyncio
import os
import tempfile

import pytest

# Skip tests if pyseekdb is not available
pyseekdb = pytest.importorskip('pyseekdb')
HNSWConfiguration = pyseekdb.HNSWConfiguration


class MockLogger:
    """Mock logger for testing."""

    def info(self, msg):
        pass

    def warning(self, msg):
        pass


class MockApplication:
    """Mock application for testing."""

    def __init__(self, config):
        self.instance_config = type('obj', (object,), {'data': config})()
        self.logger = MockLogger()


class SeekDBTestAdapter:
    """Test adapter that mirrors SeekDBVectorDatabase implementation.

    This adapter replicates the logic from langbot.pkg.vector.vdbs.seekdb.SeekDBVectorDatabase
    to enable testing without triggering LangBot's circular import chain.
    Any changes to the real adapter should be reflected here to maintain test accuracy.
    """

    def __init__(self, ap):
        self.ap = ap
        config = self.ap.instance_config.data['vdb']['seekdb']

        mode = config.get('mode', 'embedded')

        if mode == 'embedded':
            path = config.get('path', './data/seekdb')
            database = config.get('database', 'langbot')

            # Create database if it doesn't exist
            # Note: create_database is idempotent in SeekDB, but we wrap in try/except
            # as a safety net for any unexpected filesystem or permission errors
            temp_client = pyseekdb.Client(path=path)
            if hasattr(temp_client, '_server') and hasattr(temp_client._server, 'create_database'):
                try:
                    temp_client._server.create_database(database)
                except Exception:
                    # Database creation may fail for various reasons
                    pass

            self.client = pyseekdb.Client(path=path, database=database)
        else:
            raise ValueError(f'Invalid SeekDB mode: {mode}')

        self._collections = {}
        self._collection_configs = {}

    async def _get_or_create_collection_internal(self, collection, vector_size=None):
        if collection in self._collections:
            return self._collections[collection]

        if await asyncio.to_thread(self.client.has_collection, collection):
            coll = await asyncio.to_thread(self.client.get_collection, collection, embedding_function=None)
            self._collections[collection] = coll
            return coll

        if vector_size is None:
            vector_size = 384

        config = HNSWConfiguration(dimension=vector_size, distance='cosine')
        self._collection_configs[collection] = config

        coll = await asyncio.to_thread(
            self.client.create_collection, name=collection, configuration=config, embedding_function=None
        )

        self._collections[collection] = coll
        return coll

    async def get_or_create_collection(self, collection):
        return await self._get_or_create_collection_internal(collection)

    async def add_embeddings(self, collection, ids, embeddings_list, metadatas, documents=None):
        if not embeddings_list:
            return

        vector_size = len(embeddings_list[0])
        coll = await self._get_or_create_collection_internal(collection, vector_size)
        await asyncio.to_thread(coll.add, ids=ids, embeddings=embeddings_list, metadatas=metadatas)

    async def search(self, collection, query_embedding, k=5):
        exists = await asyncio.to_thread(self.client.has_collection, collection)
        if not exists:
            return {'ids': [[]], 'metadatas': [[]], 'distances': [[]]}

        if collection not in self._collections:
            coll = await asyncio.to_thread(self.client.get_collection, collection, embedding_function=None)
            self._collections[collection] = coll
        else:
            coll = self._collections[collection]

        results = await asyncio.to_thread(coll.query, query_embeddings=query_embedding, n_results=k)
        return results

    async def delete_by_file_id(self, collection, file_id):
        exists = await asyncio.to_thread(self.client.has_collection, collection)
        if not exists:
            return

        if collection not in self._collections:
            coll = await asyncio.to_thread(self.client.get_collection, collection, embedding_function=None)
            self._collections[collection] = coll
        else:
            coll = self._collections[collection]

        await asyncio.to_thread(coll.delete, where={'file_id': file_id})

    async def delete_collection(self, collection):
        if collection in self._collections:
            del self._collections[collection]
        if collection in self._collection_configs:
            del self._collection_configs[collection]

        exists = await asyncio.to_thread(self.client.has_collection, collection)
        if not exists:
            return

        await asyncio.to_thread(self.client.delete_collection, collection)


@pytest.fixture
def seekdb_adapter():
    """Create a SeekDB adapter with temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'seekdb_test')
        config = {'vdb': {'use': 'seekdb', 'seekdb': {'mode': 'embedded', 'path': db_path, 'database': 'test_db'}}}
        mock_ap = MockApplication(config)
        adapter = SeekDBTestAdapter(mock_ap)
        yield adapter


@pytest.mark.asyncio
async def test_seekdb_create_collection(seekdb_adapter):
    """Test creating a collection in SeekDB."""
    collection_name = 'test_collection'
    await seekdb_adapter.get_or_create_collection(collection_name)

    # Verify collection exists
    exists = await asyncio.to_thread(seekdb_adapter.client.has_collection, collection_name)
    assert exists is True


@pytest.mark.asyncio
async def test_seekdb_add_and_search(seekdb_adapter):
    """Test adding embeddings and searching in SeekDB."""
    collection_name = 'test_search'

    # Add embeddings
    ids = ['doc1', 'doc2', 'doc3']
    embeddings = [[0.1 + i * 0.1 for _ in range(384)] for i in range(3)]
    metadatas = [{'file_id': 'file1', 'text': f'Document {i}'} for i in range(3)]

    await seekdb_adapter.add_embeddings(
        collection=collection_name, ids=ids, embeddings_list=embeddings, metadatas=metadatas
    )

    # Search for similar vectors
    query_vector = [0.1 for _ in range(384)]  # Most similar to doc1
    results = await seekdb_adapter.search(collection=collection_name, query_embedding=query_vector, k=2)

    assert len(results['ids'][0]) == 2
    assert results['ids'][0][0] == 'doc1'  # First result should be most similar


@pytest.mark.asyncio
async def test_seekdb_delete_by_file_id(seekdb_adapter):
    """Test deleting embeddings by file_id."""
    collection_name = 'test_delete'

    # Add embeddings from two files
    ids = ['chunk1', 'chunk2', 'chunk3', 'chunk4']
    embeddings = [[0.1 + i * 0.05 for _ in range(384)] for i in range(4)]
    metadatas = [
        {'file_id': 'file1', 'text': 'Chunk 1'},
        {'file_id': 'file1', 'text': 'Chunk 2'},
        {'file_id': 'file2', 'text': 'Chunk 3'},
        {'file_id': 'file2', 'text': 'Chunk 4'},
    ]

    await seekdb_adapter.add_embeddings(
        collection=collection_name, ids=ids, embeddings_list=embeddings, metadatas=metadatas
    )

    # Delete file1 chunks
    await seekdb_adapter.delete_by_file_id(collection=collection_name, file_id='file1')

    # Verify deletion
    query_vector = [0.1 for _ in range(384)]
    results = await seekdb_adapter.search(collection=collection_name, query_embedding=query_vector, k=10)

    remaining_ids = results['ids'][0]
    assert 'chunk1' not in remaining_ids
    assert 'chunk2' not in remaining_ids
    assert 'chunk3' in remaining_ids
    assert 'chunk4' in remaining_ids


@pytest.mark.asyncio
async def test_seekdb_delete_collection(seekdb_adapter):
    """Test deleting an entire collection."""
    collection_name = 'test_delete_coll'

    # Create and populate collection
    await seekdb_adapter.add_embeddings(
        collection=collection_name,
        ids=['doc1'],
        embeddings_list=[[0.1] * 384],
        metadatas=[{'file_id': 'file1'}],
    )

    # Verify collection exists
    exists = await asyncio.to_thread(seekdb_adapter.client.has_collection, collection_name)
    assert exists is True

    # Delete collection
    await seekdb_adapter.delete_collection(collection_name)

    # Verify collection is deleted
    exists_after = await asyncio.to_thread(seekdb_adapter.client.has_collection, collection_name)
    assert exists_after is False


@pytest.mark.asyncio
async def test_seekdb_search_nonexistent_collection(seekdb_adapter):
    """Test searching in a non-existent collection returns empty results."""
    results = await seekdb_adapter.search(collection='nonexistent', query_embedding=[0.1] * 384, k=1)

    assert results == {'ids': [[]], 'metadatas': [[]], 'distances': [[]]}
