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
            config = kb.creation_settings or {}
            logger.info(
                f"Calling RAG plugin {plugin_id}: on_knowledge_base_create(kb_id={kb.uuid})"
            )
            await self.ap.plugin_connector.rag_on_kb_create(plugin_id, kb.uuid, config)
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
            await self.ap.plugin_connector.rag_on_kb_delete(plugin_id, kb.uuid)
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
            "collection_id": kb.collection_id or kb.uuid,  # Use collection_id if set, otherwise kb.uuid
            "chunking_strategy": kb.creation_settings.get("chunking_strategy", "fixed_size") if kb.creation_settings else "fixed_size",
            "custom_settings": kb.creation_settings or {},
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

        plugin_author, plugin_name = plugin_id.split('/', 1)

        # For the new RAGEngine design, retriever_name comes from the plugin's component.
        # We use the instance_id (kb.uuid) to identify the KB instance.
        # The runtime/plugin will look up the correct RAGEngine component automatically.
        # Using empty string for retriever_name to let the runtime find the default RAGEngine component.
        retriever_name = ""  # Runtime will find the RAGEngine component automatically

        retrieval_context = {
            "query": query,
            "knowledge_base_id": kb.uuid,
            "collection_id": kb.collection_id or kb.uuid,
            "top_k": settings.get("top_k", kb.top_k or 5),
            "config": settings,
        }

        try:
            result = await self.ap.plugin_connector.retrieve_knowledge(
                plugin_author,
                plugin_name,
                retriever_name,
                kb.uuid,  # instance_id
                retrieval_context
            )
            return result
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
        try:
            return await self.ap.plugin_connector.get_rag_creation_schema(plugin_id)
        except Exception as e:
            logger.error(f"Failed to get creation schema from plugin {plugin_id}: {e}")
            return {}

    async def get_retrieval_schema(self, plugin_id: str) -> Dict[str, Any]:
        """Get retrieval settings schema from plugin."""
        try:
            return await self.ap.plugin_connector.get_rag_retrieval_schema(plugin_id)
        except Exception as e:
            logger.error(f"Failed to get retrieval schema from plugin {plugin_id}: {e}")
            return {}
