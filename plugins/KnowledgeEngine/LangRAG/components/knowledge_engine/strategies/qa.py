"""QA Index strategy — generates question-answer pairs from document chunks.

Instead of embedding raw chunk text, this strategy uses an LLM to generate
question-answer pairs from each chunk.  The *questions* are embedded and stored
as vectors, while the *answers* are stored in metadata.  At retrieval time the
user's query (naturally phrased as a question) matches against generated
questions, yielding better semantic alignment than raw-chunk matching.

This strategy yields Q&A pairs incrementally (per chunk) so that the ingest
pipeline can embed and upsert concurrently with ongoing LLM generation.

When *sections* are provided, section-aware chunks are used instead of flat
text chunks, preserving heading/page metadata in each Q&A pair's metadata.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncGenerator

from langbot_plugin.api.entities.builtin.provider.message import Message

from .base import IndexStrategy
from components.offload import BoundedOffload
from ..chunker import (
    chunk_text,
    chunk_sections,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNK_OVERLAP,
)

logger = logging.getLogger(__name__)

DEFAULT_QUESTIONS_PER_CHUNK = 1

QA_GENERATION_PROMPT = """\
Based on the following text, generate {n} question-answer pairs.
Each question should be directly answerable from the text.
Each answer should be concise and grounded in the text.

Text:
{chunk_text}

Output exactly {n} pairs in this JSON format (no other text):
[
  {{"q": "question", "a": "answer"}},
  ...
]"""


def _parse_qa_pairs(text: str) -> list[tuple[str, str]]:
    """Parse Q&A pairs from LLM response.

    Tries JSON first, falls back to ``Q:/A:`` text format.
    """
    # --- Try JSON ---
    try:
        # Extract JSON array even if surrounded by markdown fences
        json_match = re.search(r"\[.*?\]", text, re.DOTALL)
        if json_match:
            items = json.loads(json_match.group())
            pairs = []
            for item in items:
                q = str(item.get("q", "")).strip()
                a = str(item.get("a", "")).strip()
                if q and a:
                    pairs.append((q, a))
            if pairs:
                return pairs
    except (json.JSONDecodeError, AttributeError):
        pass

    # --- Fallback: Q:/A: text format ---
    pairs: list[tuple[str, str]] = []
    blocks = re.split(r"\nQ:\s*", "\n" + text)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        parts = re.split(r"\nA:\s*", block, maxsplit=1)
        if len(parts) == 2:
            q, a = parts[0].strip(), parts[1].strip()
            if q and a:
                pairs.append((q, a))
    return pairs


def _extract_text(msg: Message) -> str:
    """Extract plain text from an LLM response Message."""
    if isinstance(msg.content, str):
        return msg.content.strip()
    if isinstance(msg.content, list):
        return "".join(e.text for e in msg.content if e.type == "text").strip()
    return ""


class QAStrategy(IndexStrategy):
    """QA Index strategy.

    During ingestion each chunk is sent to an LLM which generates N
    question-answer pairs.  The **questions** become the texts that get
    embedded.  The **answers** are stored in the ``text`` metadata field so
    they are returned as retrieval results.  The original chunk is kept in
    ``source_chunk`` for additional context.

    Yields Q&A pairs per chunk so the ingest pipeline can start embedding
    while the next chunk's LLM call is in flight.

    When *sections* are provided, section-aware chunks are used, and each
    Q&A pair inherits the chunk's heading/page/heading_path metadata.
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
        if plugin is None:
            raise RuntimeError("QAStrategy requires a plugin reference for LLM calls")

        chunk_size = creation_settings.get("chunk_size") or DEFAULT_CHUNK_SIZE
        overlap = creation_settings.get("overlap") or DEFAULT_CHUNK_OVERLAP
        qa_llm_uuid = creation_settings.get("qa_llm_model_uuid", "")
        n_questions = (
            creation_settings.get("questions_per_chunk") or DEFAULT_QUESTIONS_PER_CHUNK
        )
        doc_fields = self._build_doc_meta_fields(doc_metadata)
        offload = getattr(plugin, "offload", None) or BoundedOffload()

        if not qa_llm_uuid:
            raise ValueError(
                "QA Index requires 'qa_llm_model_uuid' in creation settings"
            )

        # Build chunk list — section-aware or flat
        if sections:
            s_chunks = await offload.run(chunk_sections, sections, chunk_size, overlap)
            # Wrap into a uniform structure for the loop below
            chunk_items = [
                {
                    "text": sc.text,
                    "heading": sc.heading,
                    "level": sc.level,
                    "page": sc.page,
                    "heading_path": sc.heading_path,
                    "has_table": sc.has_table,
                    "section_index": sc.section_index,
                }
                for sc in s_chunks
            ]
        else:
            flat_chunks = await offload.run(chunk_text, text, chunk_size, overlap)
            chunk_items = [{"text": c} for c in flat_chunks]

        logger.info(
            f"[QA] Generating Q&A pairs: {len(chunk_items)} chunks × "
            f"{n_questions} questions, LLM={qa_llm_uuid}"
        )

        total_qa = 0

        for chunk_idx, chunk_info in enumerate(chunk_items):
            chunk = chunk_info["text"]
            prompt = QA_GENERATION_PROMPT.format(n=n_questions, chunk_text=chunk)
            messages = [Message(role="user", content=prompt)]

            try:
                response = await plugin.invoke_llm(qa_llm_uuid, messages)
                response_text = _extract_text(response)
            except Exception as e:
                logger.warning(
                    f"[QA] LLM call failed for chunk {chunk_idx}: {e}, skipping"
                )
                continue

            qa_pairs = _parse_qa_pairs(response_text)
            if not qa_pairs:
                logger.warning(
                    f"[QA] No Q&A pairs parsed from chunk {chunk_idx}, "
                    f"raw response: {response_text[:200]!r}"
                )
                continue

            logger.info(
                f"[QA] Chunk {chunk_idx}/{len(chunk_items) - 1}: "
                f"generated {len(qa_pairs)} Q&A pairs"
            )

            questions: list[str] = []
            ids: list[str] = []
            metadatas: list[dict] = []

            for qa_idx, (question, answer) in enumerate(qa_pairs):
                vec_id = f"{doc_id}_{chunk_idx}_qa{qa_idx}"
                questions.append(question)
                ids.append(vec_id)
                meta = {
                    "file_id": doc_id,
                    "document_id": doc_id,
                    "document_name": filename,
                    "chunk_index": chunk_idx,
                    "qa_index": qa_idx,
                    "question": question,
                    "answer": answer,
                    "text": answer,
                    "source_chunk": chunk,
                    "index_type": "qa",
                }
                # Add section metadata if available
                if "heading" in chunk_info:
                    meta["heading"] = chunk_info["heading"]
                    meta["level"] = chunk_info["level"]
                    meta["page"] = chunk_info["page"]
                    meta["heading_path"] = chunk_info["heading_path"]
                    meta["has_table"] = chunk_info["has_table"]
                    meta["section_index"] = chunk_info["section_index"]
                meta.update(doc_fields)
                metadatas.append(meta)

            total_qa += len(questions)
            yield questions, ids, metadatas

        logger.info(f"[QA] Total: {total_qa} Q&A pairs from {len(chunk_items)} chunks")

    def postprocess_results(self, results: list[dict], top_k: int) -> list[dict]:
        """Deduplicate by source chunk, keeping the highest-scoring QA per chunk."""

        def _metric(res: dict) -> tuple[int, float]:
            distance = res.get("distance")
            if isinstance(distance, (int, float)):
                return (0, float(distance))

            score = res.get("score")
            if isinstance(score, (int, float)):
                return (1, float(score))

            return (2, float("inf"))

        seen: dict[str, dict] = {}
        for res in results:
            meta = res.get("metadata", {})
            doc_id = meta.get("document_id", "")
            chunk_idx = meta.get("chunk_index", "")
            key = f"{doc_id}:{chunk_idx}"

            if key not in seen:
                seen[key] = res
            else:
                if _metric(res) < _metric(seen[key]):
                    seen[key] = res

        return list(seen.values())[:top_k]
