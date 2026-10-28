"""Minimal SDK stubs for offline tests and benchmarks.

These stubs let repository-local tooling import LangRAG without installing or
starting LangBot. Runtime plugin deployments still use the real SDK.
"""

from __future__ import annotations

import enum
import importlib
import sys
import types


class SimpleModel:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class DocumentStatus(str, enum.Enum):
    COMPLETED = "completed"
    FAILED = "failed"


class SearchType(str, enum.Enum):
    VECTOR = "vector"
    FULL_TEXT = "full_text"
    HYBRID = "hybrid"


class FileMetadata(SimpleModel):
    pass


class FileObject(SimpleModel):
    pass


class TextSection(SimpleModel):
    def __init__(
        self,
        content,
        heading=None,
        level=0,
        page=None,
        metadata=None,
    ):
        super().__init__(
            content=content,
            heading=heading,
            level=level,
            page=page,
            metadata=metadata or {},
        )


class ParseResult(SimpleModel):
    def __init__(self, text="", sections=None, metadata=None):
        super().__init__(
            text=text,
            sections=sections or [],
            metadata=metadata or {},
        )


class IngestionContext(SimpleModel):
    def __init__(
        self,
        file_object,
        knowledge_base_id,
        creation_settings=None,
        parsed_content=None,
        collection_id=None,
    ):
        super().__init__(
            file_object=file_object,
            knowledge_base_id=knowledge_base_id,
            collection_id=collection_id,
            creation_settings=creation_settings or {},
            parsed_content=parsed_content,
        )

    def get_collection_id(self):
        return self.collection_id or self.knowledge_base_id


class IngestionResult(SimpleModel):
    def __init__(
        self,
        document_id,
        status,
        chunks_created=0,
        error_message=None,
        metadata=None,
    ):
        super().__init__(
            document_id=document_id,
            status=status,
            chunks_created=chunks_created,
            error_message=error_message,
            metadata=metadata or {},
        )


class RetrievalContext(SimpleModel):
    def __init__(
        self,
        query,
        knowledge_base_id=None,
        collection_id=None,
        retrieval_settings=None,
        creation_settings=None,
        filters=None,
    ):
        super().__init__(
            query=query,
            knowledge_base_id=knowledge_base_id,
            collection_id=collection_id,
            retrieval_settings=retrieval_settings or {},
            creation_settings=creation_settings or {},
            filters=filters or {},
        )

    def get_collection_id(self):
        return self.collection_id or self.knowledge_base_id or ""


class RetrievalResultEntry(SimpleModel):
    pass


class ParseContext(SimpleModel):
    def __init__(
        self,
        file_content,
        filename,
        mime_type=None,
        metadata=None,
    ):
        super().__init__(
            file_content=file_content,
            filename=filename,
            mime_type=mime_type,
            metadata=metadata or {},
        )


class RetrievalResponse(SimpleModel):
    def __init__(self, results, total_found, metadata=None):
        super().__init__(
            results=results,
            total_found=total_found,
            metadata=metadata or {},
        )


class KnowledgeEngineCapability:
    DOC_INGESTION = "doc_ingestion"
    DOC_PARSING = "doc_parsing"


class KnowledgeEngine:
    pass


class Parser:
    pass


class PageRequest(SimpleModel):
    def __init__(self, endpoint, method, body=None, caller=None, headers=None):
        super().__init__(
            endpoint=endpoint,
            method=method,
            body=body,
            caller=caller,
            headers=headers or {},
        )


class PageResponse(SimpleModel):
    def __init__(self, data=None, error=None):
        super().__init__(data=data, error=error)

    @classmethod
    def ok(cls, data=None):
        return cls(data=data)

    @classmethod
    def fail(cls, error):
        return cls(error=error)


class Page:
    async def handle_api(self, request):
        return PageResponse.fail("Not implemented")


class Message(SimpleModel):
    pass


def _set_module(name: str, **attrs) -> None:
    module = types.ModuleType(name)
    for attr_name, value in attrs.items():
        setattr(module, attr_name, value)
    sys.modules[name] = module


def _ensure_optional_parser_deps() -> None:
    for module_name in ("PyPDF2", "markdown", "fitz"):
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError:
            sys.modules[module_name] = types.ModuleType(module_name)

    if not hasattr(sys.modules["markdown"], "markdown"):
        sys.modules["markdown"].markdown = lambda text, extensions=None: text

    if not hasattr(sys.modules["PyPDF2"], "PdfReader"):
        sys.modules["PyPDF2"].PdfReader = object

    if not hasattr(sys.modules["fitz"], "TEXT_PRESERVE_WHITESPACE"):
        sys.modules["fitz"].TEXT_PRESERVE_WHITESPACE = 0


def install_stubs() -> None:
    _ensure_optional_parser_deps()

    package_names = [
        "langbot_plugin",
        "langbot_plugin.api",
        "langbot_plugin.api.definition",
        "langbot_plugin.api.definition.components",
        "langbot_plugin.api.definition.components.parser",
        "langbot_plugin.api.definition.components.page",
        "langbot_plugin.api.entities",
        "langbot_plugin.api.entities.builtin",
        "langbot_plugin.api.entities.builtin.provider",
    ]
    for name in package_names:
        sys.modules.setdefault(name, types.ModuleType(name))

    _set_module(
        "langbot_plugin.api.definition.components.knowledge_engine",
        KnowledgeEngine=KnowledgeEngine,
        KnowledgeEngineCapability=KnowledgeEngineCapability,
    )
    _set_module(
        "langbot_plugin.api.definition.components.parser.parser",
        Parser=Parser,
    )
    _set_module(
        "langbot_plugin.api.definition.components.page",
        Page=Page,
        PageRequest=PageRequest,
        PageResponse=PageResponse,
    )
    _set_module(
        "langbot_plugin.api.entities.builtin.rag",
        DocumentStatus=DocumentStatus,
        SearchType=SearchType,
        FileMetadata=FileMetadata,
        FileObject=FileObject,
        TextSection=TextSection,
        ParseContext=ParseContext,
        ParseResult=ParseResult,
        IngestionContext=IngestionContext,
        IngestionResult=IngestionResult,
        RetrievalContext=RetrievalContext,
        RetrievalResultEntry=RetrievalResultEntry,
        RetrievalResponse=RetrievalResponse,
    )
    _set_module(
        "langbot_plugin.api.entities.builtin.rag.models",
        FileMetadata=FileMetadata,
        FileObject=FileObject,
        TextSection=TextSection,
        ParseContext=ParseContext,
        ParseResult=ParseResult,
        IngestionContext=IngestionContext,
        IngestionResult=IngestionResult,
    )
    _set_module(
        "langbot_plugin.api.entities.builtin.provider.message",
        Message=Message,
    )
