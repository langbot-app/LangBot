from __future__ import annotations
from typing import List
from langbot.pkg.core import app
from langbot_plugin.api.entities.builtin.rag import context as rag_context
from .base import BaseRetrievalProvider


class FullTextSearchProvider(BaseRetrievalProvider):
    """
    Pure keyword/fulltext search provider.

    Uses keyword matching (BM25, fulltext index, etc.) to find relevant documents.
    Requires a VDB with 'fulltext' capability.
    """

    def __init__(self, ap: app.Application, kb_id: str, config: dict = None):
        """
        Initialize fulltext search provider.

        Args:
            ap: Application instance
            kb_id: Knowledge base UUID
            config: Provider configuration (must include 'vdb' key for VDB reference)
        """
        super().__init__(ap, kb_id, config)

    async def retrieve(self, query: str, top_k: int) -> List[rag_context.RetrievalResultEntry]:
        """
        Retrieve documents using fulltext/keyword search.

        Args:
            query: Query text
            top_k: Number of results to return

        Returns:
            List of retrieval results
        """
        # Check VDB capability
        self._check_capability('fulltext')

        self.ap.logger.info(
            f"Fulltext search for '{query[:30]}...' with k={top_k} (vdb: {self.vdb_name})"
        )

        # Get VDB and perform fulltext search
        vdb = self._get_vdb()
        results = await vdb.search_fulltext(
            collection=self.kb_id,
            query=query,
            k=top_k
        )

        # Convert to RetrievalResultEntry
        return self._convert_vdb_results(results)
