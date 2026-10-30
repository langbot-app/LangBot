"""Abstract base class for index strategies."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator


class IndexStrategy(ABC):
    """Base class for RAG index strategies.

    Each strategy defines how documents are chunked/indexed during ingestion
    and how search results are post-processed during retrieval.
    """

    @abstractmethod
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
        """Build chunks, IDs, and metadata for a parsed document.

        Yields batches of ``(texts_to_embed, ids, metadatas)``.  Most
        strategies yield a single batch; streaming strategies (e.g. QA)
        may yield incrementally to enable pipelined embedding.


        Args:
            text: Full parsed text of the document.
            doc_id: Unique document identifier.
            filename: Original filename.
            creation_settings: Knowledge base creation settings dict.
            plugin: Optional plugin reference for strategies that need
                Host API access (e.g. LLM calls during ingestion).
            sections: Optional list of TextSection objects from an external
                parser.  When provided, strategies should use section-aware
                chunking instead of flat text splitting.
            doc_metadata: Optional document-level metadata from the parser
                (e.g. page_count, has_tables).  Fields (except ``images``)
                are merged into each chunk's metadata with a ``doc_`` prefix.

        Yields:
            A tuple of (texts_to_embed, ids, metadatas).
            - texts_to_embed: text chunks to be embedded.
            - ids: unique ID for each chunk.
            - metadatas: metadata dict for each chunk.
        """
        yield  # abstract – subclasses must override

    @staticmethod
    def _build_doc_meta_fields(doc_metadata: dict | None) -> dict:
        """Extract document-level metadata fields with ``doc_`` prefix.

        Excludes heavy fields like ``images`` to keep chunk metadata lean.

        TODO: Chroma 1.5.0+ supports array metadata types (list of str/int/float/bool)
        with $contains/$not_contains operators. LangBot currently uses Chroma 1.4.1
        which only accepts scalar types (str, int, float, bool, None). This function
        converts non-scalar values to JSON strings for compatibility. Once LangBot
        upgrades to Chroma 1.5.0+, this conversion layer can be removed to enable
        native array filtering. See: https://www.trychroma.com/changelog/metadata-arrays
        """
        if not doc_metadata:
            return {}
        skip = {"images"}
        result = {}
        for k, v in doc_metadata.items():
            if k in skip:
                continue
            # Chroma 1.4.1 only accepts scalar types; convert list/dict to JSON string
            if isinstance(v, (str, int, float, bool)) or v is None:
                result[f"doc_{k}"] = v
            else:
                result[f"doc_{k}"] = json.dumps(v, ensure_ascii=False)
        return result

    def postprocess_results(self, results: list[dict], top_k: int) -> list[dict]:
        """Post-process search results before returning to the caller.

        Default implementation is a no-op passthrough.

        Args:
            results: Raw search results from the vector store.
            top_k: Desired number of results.

        Returns:
            Processed results list.
        """
        return results[:top_k]
