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
        documents: list[str],
    ) -> None:
        """Add vector data to the specified collection."""
        pass

    @abc.abstractmethod
    async def search(self, collection: str, query_embedding: np.ndarray, k: int = 5) -> Dict[str, Any]:
        """Search for the most similar vectors in the specified collection."""
        pass

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
