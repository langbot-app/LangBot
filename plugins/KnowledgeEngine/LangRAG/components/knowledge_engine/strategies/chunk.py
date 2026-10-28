"""Default flat chunking strategy — preserves the original LangRAG behavior."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from .base import IndexStrategy
from components.offload import BoundedOffload
from ..chunker import chunk_text, chunk_sections, DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP


class ChunkStrategy(IndexStrategy):
    """Simple fixed-size chunking with overlap.

    Each chunk is independently embedded and stored.  This is the original
    behaviour of LangRAG prior to strategy modularisation.

    When *sections* are provided (from an external parser), uses
    section-aware chunking that preserves heading/page metadata.
    """

    async def build_chunks_and_metadata(
        self,
        text: str,
        doc_id: str,
        filename: str,
        creation_settings: dict,
        plugin=None,
        *,
        sections: list | None = None,
        doc_metadata: dict | None = None,
    ) -> AsyncGenerator[tuple[list[str], list[str], list[dict]], None]:
        chunk_size = creation_settings.get("chunk_size") or DEFAULT_CHUNK_SIZE
        overlap = creation_settings.get("overlap") or DEFAULT_CHUNK_OVERLAP
        doc_fields = self._build_doc_meta_fields(doc_metadata)
        offload = getattr(plugin, "offload", None) or BoundedOffload()

        if sections:
            # Section-aware path
            s_chunks = await offload.run(chunk_sections, sections, chunk_size, overlap)
            chunks_text: list[str] = []
            ids: list[str] = []
            metadatas: list[dict] = []
            for i, sc in enumerate(s_chunks):
                chunks_text.append(sc.text)
                ids.append(f"{doc_id}_{i}")
                meta = {
                    "file_id": doc_id,
                    "document_id": doc_id,
                    "document_name": filename,
                    "chunk_index": i,
                    "text": sc.text,
                    "index_type": "chunk",
                    "heading": sc.heading,
                    "level": sc.level,
                    "page": sc.page,
                    "heading_path": sc.heading_path,
                    "has_table": sc.has_table,
                    "section_index": sc.section_index,
                }
                meta.update(doc_fields)
                metadatas.append(meta)

            yield chunks_text, ids, metadatas
        else:
            # Fallback: flat text chunking (original behaviour)
            chunks = await offload.run(chunk_text, text, chunk_size, overlap)

            ids = []
            metadatas = []
            for i, chunk in enumerate(chunks):
                ids.append(f"{doc_id}_{i}")
                meta = {
                    "file_id": doc_id,
                    "document_id": doc_id,
                    "document_name": filename,
                    "chunk_index": i,
                    "text": chunk,
                    "index_type": "chunk",
                }
                meta.update(doc_fields)
                metadatas.append(meta)

            yield chunks, ids, metadatas
