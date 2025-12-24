from __future__ import annotations
from typing import List
from langbot.pkg.core import app
from langbot_plugin.api.entities.builtin.rag import context as rag_context
from .base import BaseRetrievalProvider


class VectorSearchProvider(BaseRetrievalProvider):
    """
    Pure vector similarity search provider.

    Uses embeddings to find semantically similar documents.
    Requires a VDB with 'vector' capability.
    """

    def __init__(self, ap: app.Application, kb_id: str, embedding_model_uuid: str, config: dict = None):
        """
        Initialize vector search provider.

        Args:
            ap: Application instance
            kb_id: Knowledge base UUID
            embedding_model_uuid: UUID of the embedding model to use
            config: Provider configuration (must include 'vdb' key for VDB reference)
        """
        super().__init__(ap, kb_id, config)
        self.embedding_model_uuid = embedding_model_uuid

    async def retrieve(self, query: str, top_k: int) -> List[rag_context.RetrievalResultEntry]:
        """
        Retrieve documents using vector similarity search.

        Args:
            query: Query text
            top_k: Number of results to return

        Returns:
            List of retrieval results
        """
        # Check VDB capability
        self._check_capability('vector')

        # Get embedding model
        embedding_model = await self.ap.model_mgr.get_embedding_model_by_uuid(self.embedding_model_uuid)
        if not embedding_model:
            self.ap.logger.error(f"Embedding model {self.embedding_model_uuid} not found for KB {self.kb_id}")
            return []

        self.ap.logger.info(
            f"Vector search for '{query[:30]}...' with k={top_k} "
            f"(model: {embedding_model.model_entity.uuid}, vdb: {self.vdb_name})"
        )

        # Generate query embedding
        query_embeddings = await embedding_model.requester.invoke_embedding(
            model=embedding_model,
            input_text=[query],
            extra_args={},
        )
        query_embedding = query_embeddings[0]

        # Get VDB and perform vector search
        vdb = self._get_vdb()
        results = await vdb.search(
            collection=self.kb_id,
            query_embedding=query_embedding,
            k=top_k
        )

        # Convert to RetrievalResultEntry
        return self._convert_vdb_results(results)
