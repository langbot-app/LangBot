from __future__ import annotations

import abc

from langbot_plugin.api.definition.components.base import BaseComponent
from langbot_plugin.api.entities.builtin.rag.context import (
    RetrievalContext,
    RetrievalResponse,
)
from langbot_plugin.api.entities.builtin.rag.models import (
    IngestionContext,
    IngestionResult,
)


class KnowledgeEngineCapability:
    """Standard Knowledge Engine capabilities.

    These capabilities inform the frontend which UI elements to render.
    For example, declaring DOC_INGESTION enables the document upload interface.

    Retrieval behavior (reranking, hybrid search, etc.) is controlled by the
    plugin's retrieval_schema and does not need a capability flag.
    """

    DOC_INGESTION = "doc_ingestion"
    """Supports document upload and processing."""

    DOC_PARSING = "doc_parsing"
    """Supports native document parsing (file-to-text extraction).

    This is a coarse-grained flag: the engine either handles parsing or it
    does not.  A finer per-MIME-type declaration was considered but would
    require coordinated changes across the SDK manifest, the backend KB info
    pipeline, and the frontend prop chain, so a simple capability flag is
    used instead.
    """


class KnowledgeEngine(BaseComponent):
    """Complete Knowledge Engine component with full lifecycle management.

    This component provides comprehensive Knowledge Engine operations including document ingestion,
    deletion, and retrieval.

    Plugins implementing this component should use `self.plugin.knowledge_*` methods
    to access Host capabilities.
    """

    __kind__ = "KnowledgeEngine"

    # ========== Capabilities ==========

    @classmethod
    def get_capabilities(cls) -> list[str]:
        """Declare Knowledge Engine capabilities.

        Override this method to declare what capabilities your Knowledge Engine supports.
        The frontend will use these to determine which UI elements to show.

        Available capabilities (see KnowledgeEngineCapability):
        - 'doc_ingestion': Supports document upload and processing

        Returns:
            List of capability strings.
        """
        return [KnowledgeEngineCapability.DOC_INGESTION]

    # ========== Lifecycle Hooks ==========

    async def on_knowledge_base_create(self, kb_id: str, config: dict) -> None:
        """Called when a knowledge base using this engine is created.

        Args:
            kb_id: The knowledge base identifier.
            config: Creation settings provided by the user.
        """
        pass

    async def on_knowledge_base_delete(self, kb_id: str) -> None:
        """Called when a knowledge base using this engine is deleted.

        Args:
            kb_id: The knowledge base identifier.
        """
        pass

    # ========== Core Methods ==========

    @abc.abstractmethod
    async def ingest(self, context: IngestionContext) -> IngestionResult:
        """Ingest a document into the knowledge base.

        This method should:
        1. Read the file using `await self.plugin.get_knowledge_file_stream(context.file_object.storage_path)`
        2. Parse and chunk the content
        3. Embed using `await self.plugin.invoke_embedding(embedding_model_uuid, [chunk.text for chunk in chunks])`
        4. Store using `await self.plugin.vector_upsert(collection_id=context.get_collection_id(), ...)`

        Args:
            context: Ingestion context containing file info and settings.

        Returns:
            Ingestion result with status and metadata.
        """
        pass

    @abc.abstractmethod
    async def delete_document(self, kb_id: str, document_id: str) -> bool:
        """Delete a document and its associated data from the knowledge base.

        Use `await self.plugin.vector_delete(...)` to clean up vectors.

        Args:
            kb_id: Knowledge base identifier.
            document_id: Document identifier to delete.

        Returns:
            True if deletion was successful.
        """
        pass

    @abc.abstractmethod
    async def retrieve(self, context: RetrievalContext) -> RetrievalResponse:
        """Retrieve relevant content from the knowledge base.

        This method should:
        1. Embed query using `await self.plugin.invoke_embedding(embedding_model_uuid, [query])`
        2. Search using `await self.plugin.vector_search(kb_id, ...)`
        3. Return structured response

        Args:
            context: Retrieval context with query and settings.

        Returns:
            Structured retrieval response.
        """
        pass
