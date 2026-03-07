from __future__ import annotations
import abc
import enum
from typing import Any, Dict
import numpy as np


class SearchType(str, enum.Enum):
    """Supported search types for vector databases."""

    VECTOR = 'vector'
    FULL_TEXT = 'full_text'
    HYBRID = 'hybrid'


class VectorDatabase(abc.ABC):
    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        """Return the search types supported by this VDB backend.

        Default: vector search only. Override in subclasses that support
        full-text or hybrid search.
        """
        return [SearchType.VECTOR]

    @abc.abstractmethod
    async def add_embeddings(
        self,
        collection: str,
        ids: list[str],
        embeddings_list: list[list[float]],
        metadatas: list[dict[str, Any]],
        documents: list[str] | None = None,
    ) -> None:
        """Add vector data to the specified collection.

        Args:
            collection: Collection name.
            ids: Unique IDs for each vector.
            embeddings_list: List of embedding vectors.
            metadatas: List of metadata dicts.
            documents: Optional raw text documents. Required for full-text
                and hybrid search in backends that support them.
        """
        pass

    @abc.abstractmethod
    async def search(
        self,
        collection: str,
        query_embedding: np.ndarray,
        k: int = 5,
        search_type: str = 'vector',
        query_text: str = '',
        filter: dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Search for the most similar vectors in the specified collection.

        Args:
            collection: Collection name.
            query_embedding: Query vector for similarity search.
            k: Number of results to return.
            search_type: One of 'vector', 'full_text', 'hybrid'.
            query_text: Raw query text, used for full_text and hybrid search.
            filter: Optional metadata filters using Chroma-style ``where``
                syntax.  Multiple top-level keys are AND-ed.  Supported
                operators: ``$eq``, ``$ne``, ``$gt``, ``$gte``, ``$lt``,
                ``$lte``, ``$in``, ``$nin``.  Example::

                    {"file_id": "abc"}
                    {"created_at": {"$gte": 1700000000}}
                    {"file_type": {"$in": ["pdf", "docx"]}}
        """
        pass

    @abc.abstractmethod
    async def delete_by_file_id(self, collection: str, file_id: str) -> None:
        """Delete vectors from the specified collection by file_id."""
        pass

    @abc.abstractmethod
    async def delete_by_filter(self, collection: str, filter: dict[str, Any]) -> int:
        """Delete vectors matching the given metadata filter.

        Args:
            collection: Collection name.
            filter: Metadata filter dict in canonical format (see ``search``).

        Returns:
            Number of deleted vectors (best-effort; backends that cannot
            report an exact count may return 0).
        """
        pass

    @abc.abstractmethod
    async def get_or_create_collection(self, collection: str):
        """Get or create collection."""
        pass

    @abc.abstractmethod
    async def delete_collection(self, collection: str):
        """Delete collection."""
        pass
