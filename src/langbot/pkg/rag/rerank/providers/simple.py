from __future__ import annotations
from typing import List
from langbot.pkg.core import app
from langbot_plugin.api.entities.builtin.rag import context as rag_context
from .base import BaseReranker


class SimpleReranker(BaseReranker):
    """
    A simple pass-through reranker that truncates results.
    Assuming the input results are already roughly sorted or we don't change order logic here.
    """

    async def rerank(
        self, query: str, results: List[rag_context.RetrievalResultEntry], top_k: int
    ) -> List[rag_context.RetrievalResultEntry]:
        # Basic deduplication based on ID if not already done
        seen = set()
        unique_results = []
        for r in results:
            if r.id not in seen:
                seen.add(r.id)
                unique_results.append(r)
                
        # Return top_k
        return unique_results[:top_k]
