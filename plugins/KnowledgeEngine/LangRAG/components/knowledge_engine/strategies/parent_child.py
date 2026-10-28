"""Parent-Child index strategy.

Uses two-level chunking: large parent chunks for context richness, small child
chunks for precise embedding matches.  Child chunks are embedded, but the
metadata ``text`` field stores the parent chunk so that retrieval automatically
returns full context.

When *sections* are provided, each section naturally maps to a parent chunk.
Sections shorter than *parent_chunk_size* become a single parent; longer ones
are split.  Child chunks are then created from each parent as usual.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from .base import IndexStrategy
from components.offload import BoundedOffload
from ..chunker import (
    chunk_text,
    chunk_sections,
    DEFAULT_CHUNK_OVERLAP,
)

logger = logging.getLogger(__name__)

DEFAULT_PARENT_CHUNK_SIZE = 2048
DEFAULT_CHILD_CHUNK_SIZE = 256


class ParentChildStrategy(IndexStrategy):
    """Two-level parent / child chunking strategy.

    - Parent chunks are large (default 2048 chars), split with no overlap.
    - Each parent is further split into small child chunks (default 256 chars)
      with configurable overlap.
    - Child chunks are the units that get embedded.
    - The ``text`` metadata field on each child stores the **parent** chunk,
      so search results automatically carry richer context.
    - ``postprocess_results`` deduplicates by parent, keeping only the
      highest-scoring child per parent.

    When *sections* are provided, sections are used as natural parent
    boundaries via section-aware chunking at parent_chunk_size, then each
    parent is further split into children.
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
        parent_size = (
            creation_settings.get("parent_chunk_size") or DEFAULT_PARENT_CHUNK_SIZE
        )
        child_size = (
            creation_settings.get("child_chunk_size") or DEFAULT_CHILD_CHUNK_SIZE
        )
        overlap = creation_settings.get("overlap") or DEFAULT_CHUNK_OVERLAP
        doc_fields = self._build_doc_meta_fields(doc_metadata)
        offload = getattr(plugin, "offload", None) or BoundedOffload()

        texts_to_embed: list[str] = []
        ids: list[str] = []
        metadatas: list[dict] = []

        if sections:
            # Section-aware: use sections as parent boundaries
            parent_chunks = await offload.run(chunk_sections, sections, parent_size, 0)

            for p_idx, parent_sc in enumerate(parent_chunks):
                parent_text = parent_sc.text
                child_chunks = await offload.run(chunk_text, parent_text, child_size, overlap)
                for c_idx, child in enumerate(child_chunks):
                    texts_to_embed.append(child)
                    ids.append(f"{doc_id}_p{p_idx}_c{c_idx}")
                    meta = {
                        "file_id": doc_id,
                        "document_id": doc_id,
                        "document_name": filename,
                        "parent_index": p_idx,
                        "child_text": child,
                        "text": parent_text,
                        "index_type": "parent_child",
                        "heading": parent_sc.heading,
                        "level": parent_sc.level,
                        "page": parent_sc.page,
                        "heading_path": parent_sc.heading_path,
                        "has_table": parent_sc.has_table,
                        "section_index": parent_sc.section_index,
                    }
                    meta.update(doc_fields)
                    metadatas.append(meta)
        else:
            # Fallback: flat text chunking (original behaviour)
            parent_chunks_text = await offload.run(chunk_text, text, parent_size, 0)

            for p_idx, parent in enumerate(parent_chunks_text):
                child_chunks = await offload.run(chunk_text, parent, child_size, overlap)
                for c_idx, child in enumerate(child_chunks):
                    texts_to_embed.append(child)
                    ids.append(f"{doc_id}_p{p_idx}_c{c_idx}")
                    meta = {
                        "file_id": doc_id,
                        "document_id": doc_id,
                        "document_name": filename,
                        "parent_index": p_idx,
                        "child_text": child,
                        "text": parent,
                        "index_type": "parent_child",
                    }
                    meta.update(doc_fields)
                    metadatas.append(meta)

        yield texts_to_embed, ids, metadatas

    def postprocess_results(self, results: list[dict], top_k: int) -> list[dict]:
        """Deduplicate by parent chunk, keeping the highest-scoring child."""

        def _metric(res: dict) -> tuple[int, float]:
            distance = res.get("distance")
            if isinstance(distance, (int, float)):
                return (0, float(distance))

            score = res.get("score")
            if isinstance(score, (int, float)):
                return (1, float(score))

            return (2, float("inf"))

        seen: dict[str, dict] = {}  # key → best result
        for res in results:
            meta = res.get("metadata", {})
            doc_id = meta.get("document_id", "")
            parent_idx = meta.get("parent_index", "")
            key = f"{doc_id}:{parent_idx}"

            if key not in seen:
                seen[key] = res
            else:
                if _metric(res) < _metric(seen[key]):
                    seen[key] = res

        deduped = list(seen.values())
        return deduped[:top_k]
