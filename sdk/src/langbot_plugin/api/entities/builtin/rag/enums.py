"""RAG-related enumerations."""

from __future__ import annotations

import enum


class DocumentStatus(str, enum.Enum):
    """Document processing status."""

    PENDING = "pending"
    """Document is queued for processing."""

    PROCESSING = "processing"
    """Document is being processed."""

    COMPLETED = "completed"
    """Document has been successfully processed."""

    FAILED = "failed"
    """Document processing failed."""

    DELETED = "deleted"
    """Document has been deleted."""


class SearchType(str, enum.Enum):
    """Supported search types for vector databases."""

    VECTOR = "vector"
    """Semantic similarity search using embedding vectors."""

    FULL_TEXT = "full_text"
    """Keyword-based full-text search."""

    HYBRID = "hybrid"
    """Combined vector and full-text search."""
