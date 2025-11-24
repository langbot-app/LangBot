"""External knowledge base implementation"""

from __future__ import annotations

import aiohttp

from langbot.pkg.core import app
from langbot.pkg.entity.persistence import rag as persistence_rag
from langbot_plugin.api.entities.rag import context as rag_context
from .base import KnowledgeBaseInterface


class ExternalKnowledgeBase(KnowledgeBaseInterface):
    """External knowledge base that queries via HTTP API"""

    external_kb_entity: persistence_rag.ExternalKnowledgeBase

    def __init__(self, ap: app.Application, external_kb_entity: persistence_rag.ExternalKnowledgeBase):
        super().__init__(ap)
        self.external_kb_entity = external_kb_entity

    async def initialize(self):
        """Initialize the external knowledge base"""
        pass

    async def retrieve(self, query: str, top_k: int) -> list[rag_context.RetrievalResultEntry]:
        """Retrieve documents from external knowledge base via HTTP API

        The API should follow this format:
        POST {api_url}
        Content-Type: application/json
        Authorization: Bearer {api_key} (if api_key is provided)

        Request body:
        {
            "query": "user query text",
            "top_k": 5
        }

        Response format:
        {
            "records": [
                {
                    "content": "document text content",
                    "score": 0.95,
                    "title": "optional document title",
                    "metadata": {}
                }
            ]
        }
        """
        try:
            headers = {'Content-Type': 'application/json'}

            if self.external_kb_entity.api_key:
                headers['Authorization'] = f'Bearer {self.external_kb_entity.api_key}'

            request_data = {'query': query, 'top_k': top_k}

            timeout = aiohttp.ClientTimeout(total=30)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self.external_kb_entity.api_url, json=request_data, headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        self.ap.logger.error(f'External KB API error: status={response.status}, body={error_text}')
                        return []

                    response_data = await response.json()

                    # Parse response
                    records = response_data.get('records', [])
                    results = []

                    for record in records:
                        content = record.get('content', '')
                        score = record.get('score', 0.0)
                        title = record.get('title', '')
                        metadata = record.get('metadata', {})

                        # Build metadata for result
                        result_metadata = {
                            'text': content,
                            'score': score,
                            'source': 'external_kb',
                            'kb_uuid': self.external_kb_entity.uuid,
                            'kb_name': self.external_kb_entity.name,
                        }

                        if title:
                            result_metadata['title'] = title

                        # Merge additional metadata
                        result_metadata.update(metadata)

                        results.append(rag_context.RetrievalResultEntry(score=score, metadata=result_metadata))

                    return results

        except aiohttp.ClientError as e:
            self.ap.logger.error(f'External KB HTTP error: {e}')
            return []
        except Exception as e:
            self.ap.logger.error(f'External KB retrieval error: {e}')
            return []

    def get_uuid(self) -> str:
        """Get the UUID of the external knowledge base"""
        return self.external_kb_entity.uuid

    def get_name(self) -> str:
        """Get the name of the external knowledge base"""
        return self.external_kb_entity.name

    def get_type(self) -> str:
        """Get the type of knowledge base"""
        return 'external'

    async def dispose(self):
        """Clean up resources - no cleanup needed for external KB"""
        pass
