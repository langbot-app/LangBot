from __future__ import annotations

import posixpath
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

import sqlalchemy

from langbot.pkg.api.http.authz import WorkspaceRequiredError
from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.entity.persistence import rag as persistence_rag
from langbot.pkg.workspace.errors import WorkspaceNotFoundError

if TYPE_CHECKING:
    from langbot.pkg.core import app


class RAGRuntimeService:
    """Service to handle RAG-related requests from plugins (Runtime).

    This service acts as the bridge between plugin RPC requests and
    LangBot's infrastructure (embedding models, vector databases, file storage).
    """

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def _validate_execution_context(self, execution_context: ExecutionContext) -> None:
        if not isinstance(execution_context, ExecutionContext):
            raise WorkspaceRequiredError('ExecutionContext is required for RAG runtime access')
        if (
            not execution_context.instance_uuid.strip()
            or not execution_context.workspace_uuid.strip()
            or execution_context.placement_generation <= 0
        ):
            raise WorkspaceRequiredError('A complete active ExecutionContext is required')
        workspace_service = getattr(self.ap, 'workspace_service', None)
        if workspace_service is None:
            raise WorkspaceRequiredError('Workspace execution service is unavailable')
        binding = await workspace_service.get_execution_binding(
            execution_context.workspace_uuid,
            expected_generation=execution_context.placement_generation,
        )
        if binding.instance_uuid != execution_context.instance_uuid:
            raise WorkspaceRequiredError('ExecutionContext belongs to another LangBot instance')

    async def _resolve_knowledge_base_uuid(
        self,
        execution_context: ExecutionContext,
        collection_id: str,
    ) -> str:
        """Resolve a plugin logical handle to a Workspace-owned KB UUID."""

        await self._validate_execution_context(execution_context)
        if not isinstance(collection_id, str) or not collection_id.strip():
            raise WorkspaceNotFoundError('Knowledge base not found')
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_rag.KnowledgeBase.uuid)
            .where(persistence_rag.KnowledgeBase.workspace_uuid == execution_context.workspace_uuid)
            .where(
                sqlalchemy.or_(
                    persistence_rag.KnowledgeBase.uuid == collection_id,
                    persistence_rag.KnowledgeBase.collection_id == collection_id,
                )
            )
            .limit(1)
        )
        kb_uuid = result.scalar_one_or_none()
        if kb_uuid is None:
            raise WorkspaceNotFoundError('Knowledge base not found')
        return kb_uuid

    async def vector_upsert(
        self,
        execution_context: ExecutionContext,
        collection_id: str,
        vectors: list[list[float]],
        ids: list[str],
        metadata: list[dict[str, Any]] | None = None,
        documents: list[str] | None = None,
    ) -> None:
        """Handle VECTOR_UPSERT action."""
        knowledge_base_uuid = await self._resolve_knowledge_base_uuid(execution_context, collection_id)
        if len(vectors) != len(ids):
            raise ValueError('vectors and ids must have the same length')
        if metadata is not None and len(metadata) != len(vectors):
            raise ValueError('metadata must have the same length as vectors')
        if documents is not None and len(documents) != len(vectors):
            raise ValueError('documents must have the same length as vectors')
        metadatas = metadata if metadata else [{} for _ in vectors]
        await self.ap.vector_db_mgr.upsert(
            execution_context=execution_context,
            knowledge_base_uuid=knowledge_base_uuid,
            vectors=vectors,
            ids=ids,
            metadata=metadatas,
            documents=documents,
        )

    async def vector_search(
        self,
        execution_context: ExecutionContext,
        collection_id: str,
        query_vector: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
        search_type: str = 'vector',
        query_text: str = '',
        vector_weight: float | None = None,
    ) -> list[dict[str, Any]]:
        """Handle VECTOR_SEARCH action."""
        knowledge_base_uuid = await self._resolve_knowledge_base_uuid(execution_context, collection_id)
        return await self.ap.vector_db_mgr.search(
            execution_context=execution_context,
            knowledge_base_uuid=knowledge_base_uuid,
            query_vector=query_vector,
            limit=top_k,
            filter=filters,
            search_type=search_type,
            query_text=query_text,
            vector_weight=vector_weight,
        )

    async def vector_delete(
        self,
        execution_context: ExecutionContext,
        collection_id: str,
        file_ids: list[str] | None = None,
        filters: dict[str, Any] | None = None,
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
        knowledge_base_uuid = await self._resolve_knowledge_base_uuid(execution_context, collection_id)
        count = 0
        if file_ids:
            await self.ap.vector_db_mgr.delete_by_file_id(
                execution_context=execution_context,
                knowledge_base_uuid=knowledge_base_uuid,
                file_ids=file_ids,
            )
            count = len(file_ids)
        elif filters:
            count = await self.ap.vector_db_mgr.delete_by_filter(
                execution_context=execution_context,
                knowledge_base_uuid=knowledge_base_uuid,
                filter=filters,
            )
        return count

    async def vector_list(
        self,
        execution_context: ExecutionContext,
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
        knowledge_base_uuid = await self._resolve_knowledge_base_uuid(execution_context, collection_id)
        return await self.ap.vector_db_mgr.list_by_filter(
            execution_context=execution_context,
            knowledge_base_uuid=knowledge_base_uuid,
            filter=filters,
            limit=limit,
            offset=offset,
        )

    async def get_file_stream(
        self,
        execution_context: ExecutionContext,
        storage_path: str,
    ) -> bytes:
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
        await self._validate_execution_context(execution_context)
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_rag.File.uuid)
            .where(persistence_rag.File.workspace_uuid == execution_context.workspace_uuid)
            .where(persistence_rag.File.file_name == normalized)
            .limit(1)
        )
        if result.first() is None:
            raise WorkspaceNotFoundError('Knowledge file not found')
        content_bytes = await self.ap.storage_mgr.load_scoped_object_key(
            execution_context,
            normalized,
            expected_owner_type='upload_document',
        )
        return content_bytes if content_bytes else b''
