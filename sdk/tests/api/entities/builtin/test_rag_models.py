from __future__ import annotations

from langbot_plugin.api.entities.builtin.provider.message import ContentElement
from langbot_plugin.api.entities.builtin.rag.context import (
    RetrievalContext,
    RetrievalResponse,
    RetrievalResultEntry,
)
from langbot_plugin.api.entities.builtin.rag.enums import DocumentStatus
from langbot_plugin.api.entities.builtin.rag.errors import (
    CollectionNotFoundError,
    EmbeddingError,
    FileServiceError,
    ParsingError,
    VectorStoreError,
)
from langbot_plugin.api.entities.builtin.rag.models import (
    FileMetadata,
    FileObject,
    IngestionContext,
    IngestionResult,
    ParseContext,
    ParseResult,
    TextChunk,
    TextSection,
)


def test_rag_file_and_parse_models_keep_metadata_isolated():
    first = FileMetadata(
        filename="a.txt",
        file_size=3,
        mime_type="text/plain",
        document_id="doc-a",
        knowledge_base_id="kb",
    )
    second = FileMetadata(
        filename="b.txt",
        file_size=4,
        mime_type="text/plain",
        document_id="doc-b",
        knowledge_base_id="kb",
    )
    first.extra["source"] = "upload"

    assert second.extra == {}
    assert FileObject(metadata=first, storage_path="files/a.txt").storage_path == (
        "files/a.txt"
    )
    assert (
        ParseContext(
            file_content=b"abc",
            mime_type="text/plain",
            filename="a.txt",
        ).metadata
        == {}
    )


def test_rag_text_models_and_parse_result_defaults():
    chunk = TextChunk(text="hello", chunk_id="c1", document_id="doc")
    section = TextSection(content="hello", heading="Intro", page=1)
    result = ParseResult(text="hello", sections=[section])

    assert chunk.metadata == {}
    assert chunk.embedding is None
    assert result.sections[0].heading == "Intro"
    assert result.metadata == {}


def test_ingestion_context_collection_id_falls_back_to_knowledge_base_id():
    metadata = FileMetadata(
        filename="a.txt",
        file_size=3,
        mime_type="text/plain",
        document_id="doc",
        knowledge_base_id="kb",
    )
    context = IngestionContext(
        file_object=FileObject(metadata=metadata, storage_path="files/a.txt"),
        knowledge_base_id="kb",
    )

    assert context.get_collection_id() == "kb"
    context.collection_id = "collection"
    assert context.get_collection_id() == "collection"


def test_ingestion_result_serializes_document_status_enum():
    result = IngestionResult(
        document_id="doc",
        status=DocumentStatus.COMPLETED,
        chunks_created=2,
    )

    assert result.model_dump()["status"] is DocumentStatus.COMPLETED


def test_retrieval_context_collection_id_fallbacks_and_response_model():
    context = RetrievalContext(query="hello", knowledge_base_id="kb")
    assert context.get_collection_id() == "kb"
    assert RetrievalContext(query="hello").get_collection_id() == ""

    entry = RetrievalResultEntry(
        id="chunk",
        content=[ContentElement.from_text("hello")],
        metadata={"doc": "a"},
        distance=0.1,
        score=0.9,
    )
    response = RetrievalResponse(results=[entry], total_found=1)

    assert response.results[0].content[0].text == "hello"
    assert response.metadata == {}


def test_rag_host_service_errors_preserve_original_error():
    original = RuntimeError("backend unavailable")

    embedding_error = EmbeddingError("embedding failed", original)
    vector_error = VectorStoreError("vector failed", original)
    file_error = FileServiceError("file failed", original)

    assert str(embedding_error) == "embedding failed"
    assert embedding_error.original_error is original
    assert vector_error.original_error is original
    assert file_error.original_error is original


def test_rag_specialized_errors_keep_context_fields():
    collection_error = CollectionNotFoundError("kb-1")
    parsing_error = ParsingError("parse failed", file_path="docs/a.txt")

    assert collection_error.collection_id == "kb-1"
    assert str(collection_error) == "Collection not found or not accessible: kb-1"
    assert parsing_error.file_path == "docs/a.txt"
