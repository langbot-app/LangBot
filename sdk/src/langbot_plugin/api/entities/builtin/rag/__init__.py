"""RAG-related entities and protocols."""

from __future__ import annotations

# Enumerations
from .enums import (
    DocumentStatus,
    SearchType,
)

# Data models
from .models import (
    FileMetadata,
    FileObject,
    TextChunk,
    TextSection,
    ParseContext,
    ParseResult,
    IngestionContext,
    IngestionResult,
)

# Error types
from .errors import (
    RAGError,
    HostServiceError,
    EmbeddingError,
    VectorStoreError,
    CollectionNotFoundError,
    FileServiceError,
    IngestionError,
    RetrievalError,
    ParsingError,
    ChunkingError,
)


# Context and retrieval types
from .context import (
    RetrievalResultEntry,
    RetrievalContext,
    RetrievalResponse,
)

__all__ = [
    # Enums
    "DocumentStatus",
    "SearchType",
    # Models
    "FileMetadata",
    "FileObject",
    "TextChunk",
    "TextSection",
    "ParseContext",
    "ParseResult",
    "IngestionContext",
    "IngestionResult",
    # Errors
    "RAGError",
    "HostServiceError",
    "EmbeddingError",
    "VectorStoreError",
    "CollectionNotFoundError",
    "FileServiceError",
    "IngestionError",
    "RetrievalError",
    "ParsingError",
    "ChunkingError",
    # Context
    "RetrievalResultEntry",
    "RetrievalContext",
    "RetrievalResponse",
]
