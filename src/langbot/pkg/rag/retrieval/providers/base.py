from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, TYPE_CHECKING, Dict, Any
from langbot.pkg.core import app
from langbot_plugin.api.entities.builtin.rag import context as rag_context
from langbot_plugin.api.entities.builtin.provider.message import ContentElement

if TYPE_CHECKING:
    from langbot.pkg.vector.vdb import VectorDatabase


class BaseRetrievalProvider(ABC):
    """
    Abstract base class for retrieval providers.

    Each provider represents a specific retrieval strategy (vector, fulltext, hybrid, etc.)
    and retrieves data from VectorDatabase instances via vector_db_mgr.
    """

    def __init__(self, ap: app.Application, kb_id: str, config: dict = None):
        """
        Initialize provider.

        Args:
            ap: Application instance
            kb_id: Knowledge base UUID (used as collection name)
            config: Provider configuration (should include 'vdb' key for VDB reference)
        """
        self.ap = ap
        self.kb_id = kb_id
        self.config = config or {}
        self.vdb_name = self.config.get('vdb', 'default')

    def _get_vdb(self) -> VectorDatabase:
        """
        Get the VectorDatabase instance from vector_db_mgr.

        Returns:
            VectorDatabase instance

        Raises:
            ValueError: If VDB not found
        """
        vdb = self.ap.vector_db_mgr.get_db(self.vdb_name)
        if not vdb:
            # Fallback to default VDB if specific not found
            vdb = self.ap.vector_db_mgr.get_default_db()

        if not vdb:
            raise ValueError(f"VDB '{self.vdb_name}' not found in vector_db_mgr")

        return vdb

    def _check_capability(self, capability: str) -> None:
        """
        Check if the configured VDB supports a required capability.

        Args:
            capability: Required capability ('vector', 'fulltext', 'hybrid')

        Raises:
            ValueError: If VDB doesn't support the capability
        """
        vdb = self._get_vdb()
        capabilities = vdb.get_capabilities()

        if capability not in capabilities:
            raise ValueError(
                f"VDB '{self.vdb_name}' ({vdb.__class__.__name__}) "
                f"does not support '{capability}' search. "
                f"Supported capabilities: {capabilities}"
            )

    def _convert_vdb_results(self, vdb_results: Dict[str, Any]) -> List[rag_context.RetrievalResultEntry]:
        """
        Convert VectorDatabase result format to RetrievalResultEntry list.

        VectorDatabase returns:
        {
            'ids': [[id1, id2, ...]],
            'distances': [[dist1, dist2, ...]],
            'metadatas': [[meta1, meta2, ...]],
            'documents': [[doc1, doc2, ...]]  # optional
        }

        Args:
            vdb_results: Results from VectorDatabase

        Returns:
            List of RetrievalResultEntry for RAG pipeline
        """
        ids = vdb_results.get('ids', [[]])[0]
        distances = vdb_results.get('distances', [[]])[0]
        metadatas = vdb_results.get('metadatas', [[]])[0]
        documents = vdb_results.get('documents', [[]])[0] if 'documents' in vdb_results else None

        entries = []
        for i, chunk_id in enumerate(ids):
            distance = distances[i] if i < len(distances) else 0.0
            metadata = metadatas[i] if i < len(metadatas) else {}
            if metadata is None:
                metadata = {}

            # Get document text from metadata or documents array
            content = ""
            if documents and i < len(documents):
                content = documents[i] or ""
            elif metadata and 'text' in metadata:
                content = metadata.get('text', '')

            entry = rag_context.RetrievalResultEntry(
                id=chunk_id,
                content=[ContentElement.from_text(content)],
                metadata=metadata,
                distance=distance,
            )
            entries.append(entry)

        return entries

    @abstractmethod
    async def retrieve(self, query: str, top_k: int) -> List[rag_context.RetrievalResultEntry]:
        """
        Retrieve relevant context entries for the given query.

        Args:
            query: The user query string
            top_k: Number of results to return

        Returns:
            List of RetrievalResultEntry objects
        """
        pass
