"""External knowledge base implementation"""

from __future__ import annotations

from langbot.pkg.core import app
from langbot.pkg.entity.persistence import rag as persistence_rag
from langbot_plugin.api.entities.builtin.rag import context as rag_context
from .base import KnowledgeBaseInterface


class ExternalKnowledgeBase(KnowledgeBaseInterface):
    """External knowledge base that queries via HTTP API or plugin retriever"""

    external_kb_entity: persistence_rag.ExternalKnowledgeBase

    # Plugin retriever instance ID
    retriever_instance_id: str | None

    def __init__(self, ap: app.Application, external_kb_entity: persistence_rag.ExternalKnowledgeBase):
        super().__init__(ap)
        self.external_kb_entity = external_kb_entity
        self.retriever_instance_id = None

    async def initialize(self):
        """Initialize the external knowledge base"""
        # Create a retriever instance for this KB
        # Use plugin_author, plugin_name, retriever_name directly from entity
        plugin_author = self.external_kb_entity.plugin_author
        plugin_name = self.external_kb_entity.plugin_name
        retriever_name = self.external_kb_entity.retriever_name

        # Use KB UUID as instance ID
        self.retriever_instance_id = self.external_kb_entity.uuid

        # Create retriever instance
        await self.ap.plugin_connector.create_knowledge_retriever_instance(
            self.retriever_instance_id,
            plugin_author,
            plugin_name,
            retriever_name,
            self.external_kb_entity.retriever_config or {},
        )

        self.ap.logger.info(
            f'Created retriever instance {self.retriever_instance_id} for KB {self.external_kb_entity.uuid}'
        )

    async def retrieve(self, query: str, top_k: int) -> list[rag_context.RetrievalResultEntry]:
        """Retrieve documents from external knowledge base via plugin retriever"""
        if not self.retriever_instance_id:
            self.ap.logger.error(f'No retriever instance for KB {self.external_kb_entity.uuid}')
            return []

        try:
            results = await self.ap.plugin_connector.retrieve_knowledge(self.retriever_instance_id, query, top_k)

            # Convert plugin results to RetrievalResultEntry
            retrieval_entries = []
            for result in results:
                # result is a dict with keys: id, metadata, distance
                score = 1.0 - result.get('distance', 0.0)  # Convert distance to score
                metadata = result.get('metadata', {})

                # Add KB metadata
                metadata['source'] = 'plugin_retriever'
                metadata['kb_uuid'] = self.external_kb_entity.uuid
                metadata['kb_name'] = self.external_kb_entity.name

                retrieval_entries.append(rag_context.RetrievalResultEntry(score=score, metadata=metadata))

            return retrieval_entries
        except Exception as e:
            self.ap.logger.error(f'Plugin retriever error: {e}')
            import traceback

            traceback.print_exc()
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
        """Clean up resources"""
        # Delete retriever instance if exists
        if self.retriever_instance_id:
            try:
                await self.ap.plugin_connector.delete_knowledge_retriever_instance(self.retriever_instance_id)
                self.ap.logger.info(f'Deleted retriever instance {self.retriever_instance_id}')
            except Exception as e:
                self.ap.logger.error(f'Failed to delete retriever instance: {e}')
