from __future__ import annotations

import pydantic
from typing import Any
from pydantic import Field

from langbot_plugin.api.entities.builtin.provider.message import ContentElement


class RetrievalResultEntry(pydantic.BaseModel):
    """A single retrieval result entry."""

    id: str
    """Unique identifier for this result."""

    content: list[ContentElement]
    """Content elements of the result."""

    metadata: dict[str, Any]
    """Metadata associated with this result."""

    distance: float
    """Distance/dissimilarity score (lower is more similar)."""

    score: float | None = None
    """Optional similarity score (higher is more similar)."""


class RetrievalContext(pydantic.BaseModel):
    """The retrieval context."""

    query: str
    """The query."""

    knowledge_base_id: str | None = None
    """Knowledge base to search in."""

    collection_id: str | None = None
    """Target vector collection ID. Defaults to knowledge_base_id if not set."""

    retrieval_settings: dict[str, Any] = Field(default_factory=dict)
    """Plugin-specific retrieval settings."""

    creation_settings: dict[str, Any] = Field(default_factory=dict)
    """Creation settings of the knowledge base (e.g. API keys)."""

    filters: dict[str, Any] = Field(default_factory=dict)
    """Metadata filters for retrieval."""

    def get_collection_id(self) -> str:
        """Get the collection ID, falling back to knowledge_base_id.

        Returns:
            The collection_id if set, otherwise knowledge_base_id.
        """
        return self.collection_id or self.knowledge_base_id or ""


class RetrievalResponse(pydantic.BaseModel):
    """Response from a retrieval operation."""

    results: list[RetrievalResultEntry]
    """Retrieved results."""

    total_found: int
    """Total number of results found before top_k filtering."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    """Additional response metadata (e.g., query rewriting info, timing)."""
