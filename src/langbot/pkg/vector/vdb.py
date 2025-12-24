from __future__ import annotations
import abc
from typing import Any, Dict
import numpy as np


class VectorDatabase(abc.ABC):
    @abc.abstractmethod
    async def add_embeddings(
        self,
        collection: str,
        ids: list[str],
        embeddings_list: list[list[float]],
        metadatas: list[dict[str, Any]],
        documents: list[str] = None,
    ) -> None:
        """Add vector data to the specified collection."""
        pass

    @abc.abstractmethod
    async def search(self, collection: str, query_embedding: np.ndarray, k: int = 5) -> Dict[str, Any]:
        """Search for the most similar vectors in the specified collection."""
        pass

    async def search_fulltext(self, collection: str, query: str, k: int = 5) -> Dict[str, Any]:
        """Search for documents matching the keyword query using full-text/keyword search."""
        raise NotImplementedError(f"Full-text search is not supported by {self.__class__.__name__}")

    async def search_hybrid(
        self, collection: str, query_embedding: np.ndarray, query: str, k: int = 5, **kwargs
    ) -> Dict[str, Any]:
        """Search using both vector similarity and keyword matching (Hybrid Search)."""
        raise NotImplementedError(f"Hybrid search is not supported by {self.__class__.__name__}")

    def get_capabilities(self) -> set[str]:
        """
        Return the set of capabilities this VDB supports.

        All VDBs support 'vector' search by default.
        Subclasses SHOULD override this method to declare additional capabilities.

        Returns:
            Set of capability names: {'vector', 'fulltext', 'hybrid'}

        Example:
            # In SeekDB with fulltext enabled:
            return {'vector', 'fulltext', 'hybrid'}

            # In basic Chroma (only vector):
            return {'vector'}

        Note:
            The base implementation only returns {'vector'}. If your VDB supports
            fulltext or hybrid search, you MUST override this method.
        """
        # Base implementation: only vector search is guaranteed
        # Subclasses should explicitly declare their capabilities
        return {'vector'}

    @abc.abstractmethod
    async def delete_by_file_id(self, collection: str, file_id: str) -> None:
        """Delete vectors from the specified collection by file_id."""
        pass

    @abc.abstractmethod
    async def get_or_create_collection(self, collection: str):
        """Get or create collection."""
        pass

    @abc.abstractmethod
    async def delete_collection(self, collection: str):
        """Delete collection."""
        pass
