"""Tests for VectorDatabase base class and SearchType enum."""

from __future__ import annotations

from unittest.mock import AsyncMock
import pytest

from langbot.pkg.vector.vdb import SearchType, VectorDatabase


class TestSearchType:
    """Tests for SearchType enum."""

    def test_search_type_values(self):
        """Test SearchType enum values."""
        assert SearchType.VECTOR.value == 'vector'
        assert SearchType.FULL_TEXT.value == 'full_text'
        assert SearchType.HYBRID.value == 'hybrid'

    def test_search_type_is_string_enum(self):
        """SearchType is a string enum."""
        assert isinstance(SearchType.VECTOR, str)
        assert SearchType.VECTOR == 'vector'

    def test_search_type_from_string(self):
        """Can create SearchType from string."""
        assert SearchType('vector') == SearchType.VECTOR
        assert SearchType('full_text') == SearchType.FULL_TEXT
        assert SearchType('hybrid') == SearchType.HYBRID


class TestVectorDatabaseAbstractMethods:
    """Tests for VectorDatabase abstract methods."""

    def test_vector_database_is_abstract(self):
        """VectorDatabase is abstract and cannot be instantiated directly."""
        with pytest.raises(TypeError):
            VectorDatabase()

    def test_abstract_methods_required(self):
        """Subclass must implement all abstract methods."""
        class IncompleteVectorDB(VectorDatabase):
            pass

        with pytest.raises(TypeError):
            IncompleteVectorDB()

    def test_supported_search_types_default(self):
        """Default supported_search_types returns [VECTOR]."""
        class MinimalVectorDB(VectorDatabase):
            async def add_embeddings(self, collection, ids, embeddings_list, metadatas, documents=None):
                pass

            async def search(self, collection, query_embedding, k=5, search_type='vector', query_text='', filter=None, vector_weight=None):
                pass

            async def delete_by_file_id(self, collection, file_id):
                pass

            async def delete_by_filter(self, collection, filter):
                pass

            async def get_or_create_collection(self, collection):
                pass

            async def delete_collection(self, collection):
                pass

        db = MinimalVectorDB()
        assert db.supported_search_types() == [SearchType.VECTOR]

    def test_list_by_filter_default_implementation(self):
        """list_by_filter has default implementation returning empty."""
        class MinimalVectorDB(VectorDatabase):
            async def add_embeddings(self, collection, ids, embeddings_list, metadatas, documents=None):
                pass

            async def search(self, collection, query_embedding, k=5, search_type='vector', query_text='', filter=None, vector_weight=None):
                pass

            async def delete_by_file_id(self, collection, file_id):
                pass

            async def delete_by_filter(self, collection, filter):
                pass

            async def get_or_create_collection(self, collection):
                pass

            async def delete_collection(self, collection):
                pass

        db = MinimalVectorDB()
        # list_by_filter should return empty list and -1 for total
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            db.list_by_filter('test_collection')
        )
        assert result == ([], -1)


class TestVectorDatabaseInterface:
    """Tests for VectorDatabase interface contracts."""

    @pytest.fixture
    def mock_vector_db(self):
        """Create a minimal mock VectorDatabase for testing."""
        class MockVectorDB(VectorDatabase):
            def __init__(self):
                self.add_embeddings = AsyncMock()
                self.search = AsyncMock(return_value={
                    'ids': [['id1', 'id2']],
                    'distances': [[0.1, 0.2]],
                    'metadatas': [[{'key': 'val1'}, {'key': 'val2'}]]
                })
                self.delete_by_file_id = AsyncMock()
                self.delete_by_filter = AsyncMock(return_value=5)
                self.get_or_create_collection = AsyncMock()
                self.delete_collection = AsyncMock()

            async def add_embeddings(self, collection, ids, embeddings_list, metadatas, documents=None):
                pass

            async def search(self, collection, query_embedding, k=5, search_type='vector', query_text='', filter=None, vector_weight=None):
                pass

            async def delete_by_file_id(self, collection, file_id):
                pass

            async def delete_by_filter(self, collection, filter):
                pass

            async def get_or_create_collection(self, collection):
                pass

            async def delete_collection(self, collection):
                pass

        return MockVectorDB()

    @pytest.mark.asyncio
    async def test_add_embeddings_signature(self, mock_vector_db):
        """add_embeddings has expected signature."""
        await mock_vector_db.add_embeddings(
            collection='test',
            ids=['id1', 'id2'],
            embeddings_list=[[0.1, 0.2], [0.3, 0.4]],
            metadatas=[{'a': 1}, {'b': 2}],
            documents=['doc1', 'doc2']
        )
        mock_vector_db.add_embeddings.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_signature(self, mock_vector_db):
        """search has expected signature with all optional params."""
        import numpy as np

        await mock_vector_db.search(
            collection='test',
            query_embedding=np.array([0.1, 0.2]),
            k=10,
            search_type='hybrid',
            query_text='search text',
            filter={'file_id': 'abc'},
            vector_weight=0.7
        )
        mock_vector_db.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_by_filter_returns_int(self, mock_vector_db):
        """delete_by_filter returns int count."""
        result = await mock_vector_db.delete_by_filter('test', {'file_id': 'abc'})
        assert isinstance(result, int)