from __future__ import annotations
import httpx
from typing import List
from langbot.pkg.core import app
from langbot_plugin.api.entities.builtin.rag import context as rag_context
from .base import BaseReranker


class QwenReranker(BaseReranker):
    """
    Qwen reranker using DashScope API.

    This reranker uses Alibaba Cloud's DashScope service with Qwen models
    to rerank retrieved documents based on their relevance to the query.
    """

    def __init__(self, ap: app.Application, config: dict = None):
        super().__init__(ap, config)
        self.api_key = self.config.get('key', '')
        self.api_url = "https://dashscope.aliyuncs.com/compatible-api/v1/reranks"
        self.model = self.config.get('model', 'qwen3-rerank')
        # Default instruction for reranking - can be overridden in config if needed
        self.instruct = self.config.get('instruct', 'Given a web search query, retrieve relevant passages that answer the query.')

        if not self.api_key:
            raise ValueError("Qwen reranker requires 'key' configuration for DashScope API")

    async def rerank(
        self, query: str, results: List[rag_context.RetrievalResultEntry], top_k: int
    ) -> List[rag_context.RetrievalResultEntry]:
        """
        Rerank results using Qwen model via DashScope API.

        Args:
            query: The user query
            results: List of retrieval results to be reranked
            top_k: Number of top results to return

        Returns:
            Reranked and truncated list of results
        """
        if not results:
            return []

        try:
            # Extract documents from results
            documents = []
            for result in results:
                content = result.content[0].text if result.content else ""
                documents.append(content)

            # Prepare API request
            request_data = {
                "model": self.model,
                "documents": documents,
                "query": query,
                "top_n": min(top_k, len(documents)),  # Don't request more than available
                "instruct": self.instruct
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # Make API request
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url,
                    json=request_data,
                    headers=headers
                )
                response.raise_for_status()

                api_response = response.json()

            # Parse response and rerank results
            reranked_results = self._parse_and_rerank(api_response, results, top_k)

            self.ap.logger.info(f"Qwen reranker processed {len(results)} results, returned top {len(reranked_results)}")
            return reranked_results

        except Exception as e:
            self.ap.logger.error(f"Qwen reranker failed: {e}")
            # Fallback to original order
            return results[:top_k]

    def _parse_and_rerank(
        self, api_response: dict, original_results: List[rag_context.RetrievalResultEntry], top_k: int
    ) -> List[rag_context.RetrievalResultEntry]:
        """
        Parse DashScope API response and rerank original results.

        Args:
            api_response: Response from DashScope API
            original_results: Original retrieval results
            top_k: Number of top results to return

        Returns:
            Reranked results
        """
        # DashScope rerank API returns results with indices and relevance_scores
        # Response structure:
        # {
        #     "object": "list",
        #     "results": [
        #         {"index": 1, "relevance_score": 0.6171875690986707},
        #         {"index": 0, "relevance_score": 0.6073028761000254},
        #         ...
        #     ],
        #     "model": "qwen3-rerank",
        #     "id": "...",
        #     "usage": {"total_tokens": 2064}
        # }

        results_data = api_response.get('results', [])

        # Create reranked results based on API response order
        reranked_results = []
        for result_item in results_data:
            index = result_item.get('index')
            relevance_score = result_item.get('relevance_score', 0.0)

            if index is not None and 0 <= index < len(original_results):
                # Create a new result entry with rerank score as distance
                original_entry = original_results[index]
                new_entry = rag_context.RetrievalResultEntry(
                    id=original_entry.id,
                    content=original_entry.content,
                    metadata=original_entry.metadata.copy() if original_entry.metadata else {},
                    distance=relevance_score  # Use relevance_score as distance (higher is better)
                )

                # Add rerank score to metadata for debugging
                new_entry.metadata['rerank_score'] = relevance_score

                reranked_results.append(new_entry)

                if len(reranked_results) >= top_k:
                    break

        # If API didn't return enough results, fill with remaining original results
        if len(reranked_results) < top_k:
            used_indices = {result_item.get('index') for result_item in results_data}
            for i, result in enumerate(original_results):
                if i not in used_indices and len(reranked_results) < top_k:
                    reranked_results.append(result)

        return reranked_results[:top_k]
