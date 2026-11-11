"""RAG-related error definitions."""

from __future__ import annotations


class RAGError(Exception):
    """Base exception for all RAG-related errors."""

    pass


class HostServiceError(RAGError):
    """Base exception for host service errors."""

    pass


class EmbeddingError(HostServiceError):
    """Error occurred during embedding generation."""

    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error


class VectorStoreError(HostServiceError):
    """Error occurred during vector store operations."""

    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error


class CollectionNotFoundError(VectorStoreError):
    """Requested collection does not exist or is not accessible."""

    def __init__(self, collection_id: str):
        super().__init__(f"Collection not found or not accessible: {collection_id}")
        self.collection_id = collection_id


class FileServiceError(HostServiceError):
    """Error occurred during file service operations."""

    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error


class IngestionError(RAGError):
    """Error occurred during document ingestion."""

    pass


class RetrievalError(RAGError):
    """Error occurred during retrieval."""

    pass


class ParsingError(IngestionError):
    """Error occurred during document parsing."""

    def __init__(self, message: str, file_path: str | None = None):
        super().__init__(message)
        self.file_path = file_path


class ChunkingError(IngestionError):
    """Error occurred during text chunking."""

    pass
