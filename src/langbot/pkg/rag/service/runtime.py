from __future__ import annotations

import posixpath
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

if TYPE_CHECKING:
    from langbot.pkg.core import app


class RAGRuntimeService:
    """Service to handle RAG-related requests from plugins (Runtime).

    This service acts as the bridge between plugin RPC requests and
    LangBot's infrastructure (embedding models, vector databases, file storage).
    """

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def vector_upsert(
        self,
        collection_id: str,
        vectors: list[list[float]],
        ids: list[str],
        metadata: list[dict[str, Any]] | None = None,
        documents: list[str] | None = None,
    ) -> None:
        """Handle VECTOR_UPSERT action."""
        metadatas = metadata if metadata else [{} for _ in vectors]
        await self.ap.vector_db_mgr.upsert(
            collection_name=collection_id,
            vectors=vectors,
            ids=ids,
            metadata=metadatas,
            documents=documents,
        )

    async def vector_search(
        self,
        collection_id: str,
        query_vector: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
        search_type: str = 'vector',
        query_text: str = '',
        vector_weight: float | None = None,
    ) -> list[dict[str, Any]]:
        """Handle VECTOR_SEARCH action."""
        return await self.ap.vector_db_mgr.search(
            collection_name=collection_id,
            query_vector=query_vector,
            limit=top_k,
            filter=filters,
            search_type=search_type,
            query_text=query_text,
            vector_weight=vector_weight,
        )

    async def vector_delete(
        self, collection_id: str, file_ids: list[str] | None = None, filters: dict[str, Any] | None = None
    ) -> int:
        """Handle VECTOR_DELETE action.

        Deletes vectors associated with the given file IDs from the collection.
        Each file_id corresponds to a document whose vectors will be removed.

        Args:
            collection_id: The collection to delete from.
            file_ids: File IDs whose associated vectors should be deleted.
                Each file_id maps to a set of vectors stored with that file_id
                in their metadata.
            filters: Filter-based deletion (not yet supported, will raise).
        """
        count = 0
        if file_ids:
            await self.ap.vector_db_mgr.delete_by_file_id(collection_name=collection_id, file_ids=file_ids)
            count = len(file_ids)
        elif filters:
            count = await self.ap.vector_db_mgr.delete_by_filter(collection_name=collection_id, filter=filters)
        return count

    async def vector_list(
        self,
        collection_id: str,
        filters: dict[str, Any] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Handle VECTOR_LIST action.

        Args:
            collection_id: The collection to list from.
            filters: Optional metadata filters.
            limit: Maximum number of items to return.
            offset: Number of items to skip.

        Returns:
            Tuple of (items, total).
        """
        return await self.ap.vector_db_mgr.list_by_filter(
            collection_name=collection_id,
            filter=filters,
            limit=limit,
            offset=offset,
        )

    async def get_file_stream(self, storage_path: str) -> bytes:
        """Handle GET_KNOWLEDEGE_FILE_STREAM action.

        Uses the storage manager abstraction to load file content,
        regardless of the underlying storage provider.
        """
        # Validate storage_path to prevent path traversal
        decoded_path = unquote(storage_path).replace('\\', '/')
        decoded_segments = decoded_path.split('/')
        normalized = posixpath.normpath(decoded_path)
        if (
            not storage_path
            or '\x00' in decoded_path
            or normalized.startswith('/')
            or '..' in decoded_segments
            or '..' in normalized.split('/')
            or re.match(r'^[A-Za-z]:/', normalized)
        ):
            raise ValueError('Invalid storage path')
        content_bytes = await self.ap.storage_mgr.storage_provider.load(normalized)
        return content_bytes if content_bytes else b''
