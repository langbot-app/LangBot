"""RAG data models."""

from __future__ import annotations

from typing import Any
import pydantic
from pydantic import Field

from .enums import DocumentStatus


class FileMetadata(pydantic.BaseModel):
    """Metadata for uploaded files."""

    filename: str
    """Original filename."""

    file_size: int
    """File size in bytes."""

    mime_type: str
    """MIME type of the file."""

    document_id: str
    """Unique document identifier."""

    knowledge_base_id: str
    """Knowledge base this document belongs to."""

    upload_time: str | None = None
    """ISO 8601 timestamp of upload."""

    extra: dict[str, Any] = Field(default_factory=dict)
    """Additional metadata."""


class FileObject(pydantic.BaseModel):
    """Represents a file ready for ingestion."""

    metadata: FileMetadata
    """File metadata."""

    storage_path: str
    """Path to the file in storage system."""


class TextChunk(pydantic.BaseModel):
    """A text chunk extracted from a document."""

    text: str
    """Chunk content."""

    chunk_id: str
    """Unique chunk identifier."""

    document_id: str
    """Parent document identifier."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    """Chunk metadata (e.g., page number, section, position)."""

    embedding: list[float] | None = None
    """Embedding vector (populated by host)."""


class TextSection(pydantic.BaseModel):
    """A section of text extracted from a document by a parser."""

    content: str
    """Section text content."""

    heading: str | None = None
    """Section heading."""

    level: int = 0
    """Nesting level."""

    page: int | None = None
    """Source page number (for PDF, etc.)."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    """Additional section metadata."""


class ParseContext(pydantic.BaseModel):
    """Context passed to Parser.parse()."""

    file_content: bytes
    """Raw file bytes (read by LangBot from storage)."""

    mime_type: str
    """Detected MIME type of the file."""

    filename: str
    """Original filename."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    """Extra metadata from FileObject."""


class ParseResult(pydantic.BaseModel):
    """Result returned by a parser after extracting text from a file."""

    text: str
    """Full extracted plain text."""

    sections: list[TextSection] = Field(default_factory=list)
    """Structured sections (optional)."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    """Parsing metadata (page_count, language, etc.)."""


class IngestionContext(pydantic.BaseModel):
    """Context for document ingestion operations."""

    file_object: FileObject
    """File to be ingested."""

    knowledge_base_id: str
    """Target knowledge base ID."""

    collection_id: str | None = None
    """Target vector collection ID. Defaults to knowledge_base_id if not set."""

    creation_settings: dict[str, Any] = Field(default_factory=dict)
    """Plugin-specific ingestion settings (from knowledge base creation_settings)."""

    parsed_content: ParseResult | None = None
    """Pre-parsed content from an external Parser plugin. If present, KnowledgeEngine can skip its own parsing."""

    def get_collection_id(self) -> str:
        """Get the collection ID, falling back to knowledge_base_id."""
        return self.collection_id or self.knowledge_base_id


class IngestionResult(pydantic.BaseModel):
    """Result of document ingestion."""

    document_id: str
    """Ingested document identifier."""

    status: DocumentStatus
    """Processing status."""

    chunks_created: int = 0
    """Number of chunks created."""

    error_message: str | None = None
    """Error message if status is FAILED."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    """Additional result metadata."""
