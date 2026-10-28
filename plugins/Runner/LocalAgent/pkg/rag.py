"""Knowledge retrieval utilities for local-agent runner."""

from __future__ import annotations

import json
import logging
import typing
from dataclasses import dataclass, field, replace

from langbot_plugin.api.proxies.runner import PermissionDeniedError, RunnerAPIProxy

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RagChunk:
    """Structured retrieval chunk kept by the runner before prompt rendering."""

    kb_id: str
    content: str
    source_index: int
    chunk_id: str | None = None
    score: float | None = None
    rerank_score: float | None = None
    metadata: dict[str, typing.Any] = field(default_factory=dict)


async def retrieve_from_knowledge_bases(
    api: RunnerAPIProxy,
    kb_ids: list[str],
    query_text: str,
    top_k: int = 5,
    rerank_model_id: str | None = None,
    rerank_top_k: int = 5,
) -> str:
    """Retrieve context from authorized knowledge bases with optional reranking.

    This compatibility wrapper returns only the stable model-facing text. Use
    retrieve_rag_chunks() when the caller needs source metadata.
    """
    return format_rag_chunks(
        await retrieve_rag_chunks(
            api=api,
            kb_ids=kb_ids,
            query_text=query_text,
            top_k=top_k,
            rerank_model_id=rerank_model_id,
            rerank_top_k=rerank_top_k,
        )
    )


async def retrieve_rag_chunks(
    api: RunnerAPIProxy,
    kb_ids: list[str],
    query_text: str,
    top_k: int = 5,
    rerank_model_id: str | None = None,
    rerank_top_k: int = 5,
) -> list[RagChunk]:
    """Retrieve authorized knowledge chunks while preserving source metadata."""
    if not kb_ids or not query_text:
        return []

    chunks: list[RagChunk] = []

    for kb_id in kb_ids:
        try:
            results = await api.retrieve_knowledge(
                kb_id=kb_id,
                query_text=query_text,
                top_k=top_k,
            )
            if results:
                for entry in results:
                    chunk = _chunk_from_result(kb_id, len(chunks), entry)
                    if chunk is not None:
                        chunks.append(chunk)
        except PermissionDeniedError:
            logger.debug("Knowledge base is not authorized for this run: %s", kb_id)
            continue
        except Exception:
            logger.warning("Knowledge base retrieval failed: %s", kb_id, exc_info=True)
            continue

    if not chunks:
        return []

    if rerank_model_id:
        try:
            scores = await api.invoke_rerank(
                rerank_model_uuid=rerank_model_id,
                query=query_text,
                documents=[chunk.content for chunk in chunks],
                top_k=rerank_top_k,
            )
            if scores:
                reranked = _reranked_chunks(chunks, scores)
                if reranked:
                    chunks = reranked
        except PermissionDeniedError:
            logger.debug("Rerank model is not authorized for this run: %s", rerank_model_id)
        except Exception:
            logger.warning("Knowledge rerank failed: %s", rerank_model_id, exc_info=True)

    max_chunks = rerank_top_k if rerank_model_id else top_k
    return chunks[: max(1, max_chunks)]


def format_rag_chunks(chunks: list[RagChunk]) -> str:
    """Render retrieval chunks for the model without volatile source metadata."""
    if not chunks:
        return ""

    return json.dumps(
        {
            "chunks": [
                {
                    "index": index,
                    "content": chunk.content,
                }
                for index, chunk in enumerate(chunks, start=1)
            ]
        },
        ensure_ascii=False,
    )


def _chunk_from_result(kb_id: str, source_index: int, entry: typing.Any) -> RagChunk | None:
    content = _extract_text_content(_model_or_mapping_get(entry, "content", ""))
    if not content:
        return None

    metadata = _model_or_mapping_get(entry, "metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    return RagChunk(
        kb_id=kb_id,
        content=content,
        source_index=source_index,
        chunk_id=_optional_str(
            _model_or_mapping_get(
                entry,
                "chunk_id",
                _model_or_mapping_get(entry, "id", _model_or_mapping_get(entry, "document_id")),
            )
        ),
        score=_optional_float(_model_or_mapping_get(entry, "score", _model_or_mapping_get(entry, "similarity"))),
        metadata=dict(metadata),
    )


def _reranked_chunks(chunks: list[RagChunk], scores: typing.Any) -> list[RagChunk]:
    reranked: list[RagChunk] = []
    seen: set[int] = set()

    for score_item in scores:
        index = _model_or_mapping_get(score_item, "index")
        if isinstance(index, bool) or not isinstance(index, int):
            continue
        if index < 0 or index >= len(chunks) or index in seen:
            continue
        seen.add(index)
        reranked.append(
            replace(
                chunks[index],
                rerank_score=_optional_float(
                    _model_or_mapping_get(
                        score_item,
                        "score",
                        _model_or_mapping_get(score_item, "relevance_score"),
                    )
                ),
            )
        )

    return reranked


def _extract_text_content(content: typing.Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text" and isinstance(part.get("text"), str):
                    text_parts.append(part["text"])
            elif isinstance(part, str):
                text_parts.append(part)
            elif getattr(part, "type", None) == "text" and isinstance(getattr(part, "text", None), str):
                text_parts.append(part.text)
        return " ".join(part for part in text_parts if part)
    return ""


def _model_or_mapping_get(value: typing.Any, key: str, default: typing.Any = None) -> typing.Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _optional_str(value: typing.Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _optional_float(value: typing.Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None
