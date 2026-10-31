"""Tests for VectorDatabase base class and SearchType enum."""

from __future__ import annotations

import pytest

from langbot.pkg.vector.vdb import (
    SearchType,
    VectorDatabase,
    remember_bounded_mapping,
    remember_bounded_set,
)


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


def test_runtime_cache_helpers_bound_mapping_and_set():
    mapping = {}
    values = set()

    for index in range(100):
        remember_bounded_mapping(mapping, str(index), object(), 8)
        remember_bounded_set(values, str(index), 8)

    assert len(mapping) == 8
    assert len(values) == 8


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

            async def search(
                self,
                collection,
                query_embedding,
                k=5,
                search_type='vector',
                query_text='',
                filter=None,
                vector_weight=None,
            ):
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

    @pytest.mark.asyncio
    async def test_list_by_filter_default_implementation(self):
        """list_by_filter has default implementation returning empty."""

        class MinimalVectorDB(VectorDatabase):
            async def add_embeddings(self, collection, ids, embeddings_list, metadatas, documents=None):
                pass

            async def search(
                self,
                collection,
                query_embedding,
                k=5,
                search_type='vector',
                query_text='',
                filter=None,
                vector_weight=None,
            ):
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
        result = await db.list_by_filter('test_collection')
        assert result == ([], -1)
