"""Base classes and interfaces for knowledge bases"""

from __future__ import annotations

import abc

from langbot.pkg.core import app
from langbot_plugin.api.entities.builtin.rag import context as rag_context


class KnowledgeBaseInterface(metaclass=abc.ABCMeta):
    """Abstract interface for all knowledge base types"""

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    @abc.abstractmethod
    async def initialize(self):
        """Initialize the knowledge base"""
        pass

    @abc.abstractmethod
    async def retrieve(
        self, query: str, top_k: int, settings: dict | None = None
    ) -> list[rag_context.RetrievalResultEntry]:
        """Retrieve relevant documents from the knowledge base

        Args:
            query: The query string
            top_k: Number of top results to return
            settings: Optional retrieval settings/configuration

        Returns:
            List of retrieve result entries
        """
        pass

    @abc.abstractmethod
    def get_uuid(self) -> str:
        """Get the UUID of the knowledge base"""
        pass

    @abc.abstractmethod
    def get_name(self) -> str:
        """Get the name of the knowledge base"""
        pass

    @abc.abstractmethod
    def get_rag_engine_plugin_id(self) -> str:
        """Get the RAG engine plugin ID"""
        pass

    @abc.abstractmethod
    async def dispose(self):
        """Clean up resources"""
        pass
