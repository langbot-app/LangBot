from __future__ import annotations

import base64
import os
import json
import logging
import sqlalchemy
from typing import Any, List, Dict, Optional
from langbot.pkg.core import app

from langbot.pkg.entity.persistence import rag as persistence_rag
from langbot.pkg.storage.providers.localstorage import LocalStorageProvider, LOCAL_STORAGE_PATH



class RAGRuntimeService:
    """Service to handle RAG-related requests from plugins (Runtime)."""

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def _get_kb_entity(self, kb_id: str) -> persistence_rag.KnowledgeBase:
        stmt = sqlalchemy.select(persistence_rag.KnowledgeBase).where(persistence_rag.KnowledgeBase.uuid == kb_id)
        result = await self.ap.persistence_mgr.execute_async(stmt)
        row = result.first()
        if not row:
             raise ValueError(f"Knowledge Base {kb_id} not found")
        # Convert Row to KnowledgeBase entity
        kb = persistence_rag.KnowledgeBase(**row._mapping)
        return kb

    def _get_embedding_model_uuid(self, kb: persistence_rag.KnowledgeBase) -> str | None:
        """Get embedding model UUID from creation_settings (preferred) or KB field (fallback)."""
        # First check creation_settings (new approach - plugin defines via creation_schema)
        if kb.creation_settings and isinstance(kb.creation_settings, dict):
            embed_uuid = kb.creation_settings.get('embedding_model_uuid')
            if embed_uuid:
                return embed_uuid
        # Fallback to KB field (backward compatibility)
        return kb.embedding_model_uuid

    async def embed_documents(self, kb_id: str, texts: List[str]) -> List[List[float]]:
        """Handle RAG_EMBED_DOCUMENTS action."""
        # 1. Get KB config to find embedding model
        kb = await self._get_kb_entity(kb_id)
        embed_model_uuid = self._get_embedding_model_uuid(kb)

        if not embed_model_uuid:
             raise ValueError(f"Embedding model not configured for this Knowledge Base (kb_id: {kb_id})")

        # 2. Get embedder instance
        embedder_model = await self.ap.model_mgr.get_embedding_model_by_uuid(embed_model_uuid)

        if not embedder_model:
             raise ValueError(f"Embedding model {embed_model_uuid} not found")

        # 3. Generate embeddings
        return await embedder_model.embed_documents(texts)

    async def embed_query(self, kb_id: str, text: str) -> List[float]:
        """Handle RAG_EMBED_QUERY action."""
        kb = await self._get_kb_entity(kb_id)
        embed_model_uuid = self._get_embedding_model_uuid(kb)

        if not embed_model_uuid:
             raise ValueError(f"Embedding model not configured (kb_id: {kb_id})")

        embedder_model = await self.ap.model_mgr.get_embedding_model_by_uuid(embed_model_uuid)
        if not embedder_model:
             raise ValueError(f"Embedding model {embed_model_uuid} not found")

        return await embedder_model.embed_query(text)

    async def vector_upsert(
        self, 
        collection_id: str, 
        vectors: List[List[float]], 
        ids: List[str], 
        metadata: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """Handle RAG_VECTOR_UPSERT action."""
        metadatas = metadata if metadata else [{} for _ in vectors]
        await self.ap.vector_db_mgr.upsert(
            collection_name=collection_id,
            vectors=vectors,
            ids=ids,
            metadata=metadatas
        )

    async def vector_search(
        self, 
        collection_id: str, 
        query_vector: List[float], 
        top_k: int, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Handle RAG_VECTOR_SEARCH action."""
        return await self.ap.vector_db_mgr.search(
            collection_name=collection_id,
            query_vector=query_vector,
            limit=top_k,
            filter=filters
        )

    async def vector_delete(
        self, 
        collection_id: str, 
        ids: Optional[List[str]] = None, 
        filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """Handle RAG_VECTOR_DELETE action."""
        count = 0
        if ids:
            await self.ap.vector_db_mgr.delete(collection_name=collection_id, ids=ids)
            count = len(ids)
        elif filters:
             await self.ap.vector_db_mgr.delete_by_filter(collection_name=collection_id, filter=filters)
        return count

    async def get_file_stream(self, storage_path: str) -> bytes:
        """Handle RAG_GET_FILE_STREAM action."""
        provider = self.ap.storage_mgr.storage_provider
        content_bytes = b""

        if isinstance(provider, LocalStorageProvider):
            real_path = os.path.join(LOCAL_STORAGE_PATH, storage_path)
            if os.path.exists(real_path):
                 with open(real_path, "rb") as f:
                     content_bytes = f.read()
            else:
                content_bytes = await self.ap.storage_mgr.load(storage_path)
        else:
            content_bytes = await self.ap.storage_mgr.load(storage_path)
        
        return content_bytes
