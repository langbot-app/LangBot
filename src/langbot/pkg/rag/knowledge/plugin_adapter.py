from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from langbot.pkg.core import app
from langbot.pkg.entity.persistence import rag as persistence_rag

logger = logging.getLogger(__name__)


class RAGPluginAdapter:
    """Adapter for interacting with RAG plugins."""

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def on_kb_create(self, kb: persistence_rag.KnowledgeBase) -> None:
        """Notify plugin about KB creation."""
        plugin_id = kb.rag_engine_plugin_id
        if not plugin_id:
            return

        try:
            # TODO: RPC Call to plugin
            logger.info(
                f"Calling RAG plugin {plugin_id}: on_knowledge_base_create(kb_id={kb.uuid})"
            )
        except Exception as e:
            logger.error(f"Failed to notify plugin {plugin_id} on KB create: {e}")

    async def on_kb_delete(self, kb: persistence_rag.KnowledgeBase) -> None:
        """Notify plugin about KB deletion."""
        plugin_id = kb.rag_engine_plugin_id
        if not plugin_id:
            return

        try:
            logger.info(
                f"Calling RAG plugin {plugin_id}: on_knowledge_base_delete(kb_id={kb.uuid})"
            )
        except Exception as e:
            logger.error(f"Failed to notify plugin {plugin_id} on KB delete: {e}")

    async def ingest_document(
        self,
        kb: persistence_rag.KnowledgeBase,
        file_metadata: Dict[str, Any],
        storage_path: str,
    ) -> Dict[str, Any]:
        """Call plugin to ingest document."""
        plugin_id = kb.rag_engine_plugin_id
        if not plugin_id:
            logger.error(f"No RAG plugin ID configured for KB {kb.uuid}. Ingestion failed.")
            raise ValueError("RAG Plugin ID required")

        logger.info(f"Calling RAG plugin {plugin_id}: ingest(doc={file_metadata.get('filename')})")
        
        context_data = {
            "file_object": {
                "metadata": file_metadata,
                "storage_path": storage_path,
            },
            "knowledge_base_id": kb.uuid,
            "chunking_strategy": "fixed_size", 
            # "custom_settings": kb.creation_settings # Pass settings if needed
        }

        try:
            result = await self.ap.plugin_connector.call_rag_ingest(plugin_id, context_data)
            return result
        except Exception as e:
            logger.error(f"Plugin ingestion failed: {e}")
            raise

    async def retrieve(
        self,
        kb: persistence_rag.KnowledgeBase,
        query: str,
        settings: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Call plugin to retrieve documents."""
        plugin_id = kb.rag_engine_plugin_id
        if not plugin_id:
            logger.error(f"No RAG plugin ID configured for KB {kb.uuid}. Retrieval failed.")
            return {"results": [], "total_found": 0}

        # Uses reused RETRIEVE_KNOWLEDGE action which might already exist in connector
        # But we need to ensure it uses the new RAGEngine interface on plugin side.
        # For now, let's assume standard retrieval_knowledge route handles it if plugin implements KnowledgeRetriever component
        # OR we add a specific call_rag_retrieve if RAGEngine is distinct from KnowledgeRetriever actions.
        
        # Current connector.retrieve_knowledge:
        # return await self.handler.retrieve_knowledge(plugin_author, plugin_name, retriever_name, instance_id, retrieval_context)
        
        plugin_author, plugin_name = plugin_id.split('/', 1)
        
        # Assumption: retriever_name is "default" or derived? 
        # In the new design, RAGEngine IS the KnowledgeRetriever component.
        # So we need to know the component name. 
        # Currently KB entity might not store component name (only plugin_id).
        # We might need to assume 'rag_engine' or look it up.
        # Let's assume the component name is 'langrag-engine' or similar from manifest.
        # For this refactor, let's assume we invoke the first available KnowledgeRetriever/RAGEngine component.
        
        retriever_name = "default" # Placeholder, logic to find component name needed
        
        try:
            return await self.ap.plugin_connector.retrieve_knowledge(
                plugin_author,
                plugin_name, 
                retriever_name, 
                kb.uuid, # instance_id
                { "query": query, "config": settings }
            )
        except Exception as e:
             logger.error(f"Plugin retrieval failed: {e}")
             return {"results": [], "total_found": 0}

    async def delete_document(
        self, kb: persistence_rag.KnowledgeBase, document_id: str
    ) -> bool:
        """Call plugin to delete document."""
        plugin_id = kb.rag_engine_plugin_id
        if not plugin_id:
            return False

        logger.info(f"Calling RAG plugin {plugin_id}: delete_document(doc_id={document_id})")
        
        try:
            return await self.ap.plugin_connector.call_rag_delete_document(plugin_id, document_id, kb.uuid)
        except Exception as e:
            logger.error(f"Plugin document deletion failed: {e}")
            return False

    async def get_creation_schema(self, plugin_id: str) -> Dict[str, Any]:
        """Get creation settings schema from plugin."""
        return await self.ap.plugin_connector.get_rag_creation_schema(plugin_id)

    async def get_retrieval_schema(self, plugin_id: str) -> Dict[str, Any]:
        """Get retrieval settings schema from plugin."""
        return await self.ap.plugin_connector.get_rag_retrieval_schema(plugin_id)
