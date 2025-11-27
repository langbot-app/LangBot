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
        # Use KB UUID as instance ID
        # Instance creation is now handled by the unified sync mechanism
        # when LangBot connects to runtime
        self.retriever_instance_id = self.external_kb_entity.uuid

        self.ap.logger.info(
            f'Initialized external KB {self.external_kb_entity.uuid}, instance will be created by sync mechanism'
        )

    async def retrieve(self, query: str, top_k: int = 5) -> list[rag_context.RetrievalResultEntry]:
        """Retrieve documents from external knowledge base via plugin retriever"""
        if not self.retriever_instance_id:
            self.ap.logger.error(f'No retriever instance for KB {self.external_kb_entity.uuid}')
            return []

        try:
            results = await self.ap.plugin_connector.retrieve_knowledge(
                self.external_kb_entity.plugin_author,
                self.external_kb_entity.plugin_name,
                self.external_kb_entity.retriever_name,
                self.retriever_instance_id,
                {'query': query},
            )

            # Convert plugin results to RetrievalResultEntry
            retrieval_entries = []
            for result in results:
                retrieval_entries.append(rag_context.RetrievalResultEntry(**result))

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
        # Trigger sync to immediately delete the instance from plugin process
        # This ensures instance is cleaned up without waiting for next LangBot restart
        try:
            await self.ap.plugin_connector.sync_polymorphic_component_instances()
            self.ap.logger.info(
                f'Disposed external KB {self.external_kb_entity.uuid}, triggered sync to delete instance'
            )
        except Exception as e:
            self.ap.logger.error(f'Failed to sync after disposing KB: {e}')
