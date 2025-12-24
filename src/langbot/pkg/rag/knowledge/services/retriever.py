"""
DEPRECATED: This simple retriever service is no longer used.

This file contains the old Retriever class that only supports basic vector search.
It has been replaced by the new retrieval system located in src/langbot/pkg/rag/retrieval/

New Usage:
==========

The new retrieval system consists of:

1. Retriever (src/langbot/pkg/rag/retrieval/retrieval.py):
   - Orchestrator that manages multiple retrieval providers
   - Supports RRF (Reciprocal Rank Fusion) for combining results from different providers
   - Supports vector, fulltext, and hybrid search strategies

2. Retrieval Providers (src/langbot/pkg/rag/retrieval/providers/):
   - VectorSearchProvider: Pure vector similarity search
   - FullTextSearchProvider: Keyword/fulltext search
   - HybridSearchProvider: Native VDB-level hybrid search

3. Usage in KnowledgeBaseManager:
   ```python
   from langbot.pkg.rag.retrieval.retrieval import Retriever

   self.retriever = Retriever(
       ap=self.ap,
       kb_id=self.knowledge_base_entity.uuid,
       embedding_model_uuid=self.knowledge_base_entity.embedding_model_uuid,
       config=retrieval_config
   )

   # Retrieve with RRF fusion
   results = await self.retriever.retrieve(query, top_k)
   ```

Migration Reason:
================
- The old retriever only supported vector search
- New system supports multiple search strategies with fusion
- Better separation of concerns (retrieval vs. reranking)
- More flexible configuration and extensibility

This file is kept for reference and potential migration purposes.
"""

from __future__ import annotations

from . import base_service
from ....core import app
from ....provider.modelmgr.requester import RuntimeEmbeddingModel
from langbot_plugin.api.entities.builtin.rag import context as rag_context
from langbot_plugin.api.entities.builtin.provider.message import ContentElement


class Retriever(base_service.BaseService):
    """
    DEPRECATED: This class is no longer used.

    See module docstring above for migration information.
    Use src/langbot/pkg/rag/retrieval/retrieval.py instead.
    """
    def __init__(self, ap: app.Application):
        super().__init__()
        self.ap = ap

    async def retrieve(
        self, kb_id: str, query: str, embedding_model: RuntimeEmbeddingModel, k: int = 5
    ) -> list[rag_context.RetrievalResultEntry]:
        self.ap.logger.info(
            f"Retrieving for query: '{query[:10]}' with k={k} using {embedding_model.model_entity.uuid}"
        )

        query_embedding: list[float] = await embedding_model.requester.invoke_embedding(
            model=embedding_model,
            input_text=[query],
            extra_args={},  # TODO: add extra args
        )

        vector_results = await self.ap.vector_db_mgr.get_default_db().search(kb_id, query_embedding[0], k)

        # 'ids' shape mirrors the Chroma-style response contract for compatibility
        matched_vector_ids = vector_results.get('ids', [[]])[0]
        distances = vector_results.get('distances', [[]])[0]
        vector_metadatas = vector_results.get('metadatas', [[]])[0]

        if not matched_vector_ids:
            self.ap.logger.info('No relevant chunks found in vector database.')
            return []

        result: list[rag_context.RetrievalResultEntry] = []

        for i, id in enumerate(matched_vector_ids):
            entry = rag_context.RetrievalResultEntry(
                id=id,
                content=[ContentElement.from_text(vector_metadatas[i].get('text', ''))],
                metadata=vector_metadatas[i],
                distance=distances[i],
            )
            result.append(entry)

        return result
