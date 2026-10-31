"""Base classes and interfaces for knowledge bases"""

from __future__ import annotations

import abc

from langbot.pkg.core import app
from langbot.pkg.api.http.context import ExecutionContext
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
        self,
        execution_context: ExecutionContext,
        query: str,
        settings: dict | None = None,
    ) -> list[rag_context.RetrievalResultEntry]:
        """Retrieve relevant documents from the knowledge base

        Args:
            execution_context: Trusted active Workspace placement.
            query: The query string
            settings: Optional per-request retrieval settings overrides

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
    def get_knowledge_engine_plugin_id(self) -> str:
        """Get the Knowledge Engine plugin ID"""
        pass

    @abc.abstractmethod
    async def dispose(self, execution_context: ExecutionContext):
        """Clean up resources"""
        pass
