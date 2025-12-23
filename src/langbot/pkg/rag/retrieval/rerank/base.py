from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List
from langbot.pkg.core import app
from langbot_plugin.api.entities.builtin.rag import context as rag_context


class BaseReranker(ABC):
    def __init__(self, ap: app.Application, config: dict = None):
        self.ap = ap
        self.config = config or {}

    @abstractmethod
    async def rerank(
        self, query: str, results: List[rag_context.RetrievalResultEntry], top_k: int
    ) -> List[rag_context.RetrievalResultEntry]:
        """
        Rerank the given results based on the query.
        
        Args:
            query: The user query
            results: List of retrieval results to be reranked
            top_k: Number of top results to return
            
        Returns:
            Reranked and truncated list of results
        """
        pass
