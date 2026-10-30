"""Reranking helpers for retrieval results.

Supports Host-provided rerank models and the legacy LLM listwise reranker.
"""

import logging
import re

from langbot_plugin.api.entities.builtin.provider.message import Message
from components.observability.telemetry import hash_text

logger = logging.getLogger(__name__)

# Maximum characters per candidate passage sent to the LLM.
_PASSAGE_TRUNCATE = 300

RERANK_PROMPT = """\
Given a query and candidate passages, rank the passages by relevance to the query.
Return ONLY the passage numbers in order from most relevant to least relevant.
Format: comma-separated numbers, e.g. "3,1,0,2,4"

Query: {query}

Candidates:
{candidates}

Ranking:"""


def _extract_text(msg: Message) -> str:
    """Extract plain text from an LLM response Message."""
    if isinstance(msg.content, str):
        return msg.content.strip()
    if isinstance(msg.content, list):
        return "".join(e.text for e in msg.content if e.type == "text").strip()
    return ""


def _parse_ranking(text: str, n: int) -> list[int] | None:
    """Parse a comma/space separated list of integers from LLM output.

    Returns a deduplicated list of valid indices (0..n-1), or *None* if
    parsing fails entirely (no valid indices found).
    """
    nums = re.findall(r"\d+", text)
    if not nums:
        return None

    seen: set[int] = set()
    indices: list[int] = []
    for s in nums:
        idx = int(s)
        if 0 <= idx < n and idx not in seen:
            seen.add(idx)
            indices.append(idx)
    return indices if indices else None


def _candidate_text(res: dict) -> str:
    """Extract the display text sent to rerankers."""
    return res.get("metadata", {}).get("text", "") or ""


def _text_log_ref(text: str | None) -> str:
    """Return a privacy-preserving text reference for logs."""
    return f"hash={hash_text(text)}, length={len(text or '')}"


def _apply_ranking(
    results: list[dict],
    ranking: list[int],
    top_k: int,
    scores_by_index: dict[int, float] | None = None,
) -> list[dict]:
    """Apply a candidate index ranking to result dicts."""
    if len(ranking) < len(results):
        remaining = [i for i in range(len(results)) if i not in set(ranking)]
        ranking.extend(remaining)

    reranked = [results[i] for i in ranking[:top_k]]

    # Rewrite distance so downstream sorting stays consistent with reranking.
    for rank, res in enumerate(reranked):
        res["distance"] = 0.01 * (rank + 1)
        if scores_by_index and ranking[rank] in scores_by_index:
            res["score"] = scores_by_index[ranking[rank]]

    return reranked


async def model_rerank(
    plugin,
    rerank_model_uuid: str,
    query: str,
    results: list[dict],
    top_k: int,
) -> list[dict]:
    """Rerank *results* using a Host rerank model.

    The Host returns score entries with candidate indices. On failure or an
    unusable response, retrieval falls back to the original order.
    """
    if not results:
        return results

    n = len(results)
    logger.info(
        f"[Rerank] Model reranking {n} candidates "
        f"for query_ref=({_text_log_ref(query)})"
    )
    documents = [_candidate_text(res) for res in results]

    try:
        scores = await plugin.invoke_rerank(
            rerank_model_uuid,
            query,
            documents,
            top_k=top_k,
        )
    except Exception as e:
        logger.warning(
            f"[Rerank] Model rerank call failed, falling back to original order: {e}"
        )
        return results[:top_k]

    ranking: list[int] = []
    scores_by_index: dict[int, float] = {}
    seen: set[int] = set()

    sorted_scores = sorted(
        scores,
        key=lambda item: item.get("relevance_score", 0),
        reverse=True,
    )
    for item in sorted_scores:
        try:
            idx = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        if 0 <= idx < n and idx not in seen:
            seen.add(idx)
            ranking.append(idx)
            score = item.get("relevance_score")
            if isinstance(score, (int, float)):
                scores_by_index[idx] = float(score)

    if not ranking:
        logger.warning(
            "[Rerank] Model rerank returned no valid indices, "
            "falling back to original order"
        )
        return results[:top_k]

    reranked = _apply_ranking(results, ranking, top_k, scores_by_index)
    logger.info(
        f"[Rerank] Done: {n} candidates -> top {len(reranked)} "
        f"(order: {ranking[:top_k]})"
    )
    return reranked


async def llm_rerank(
    plugin,
    llm_uuid: str,
    query: str,
    results: list[dict],
    top_k: int,
) -> list[dict]:
    """Rerank *results* using an LLM and return the top *top_k* entries.

    On any failure (LLM error, unparseable response) the function falls back
    to returning ``results[:top_k]`` so that retrieval is never blocked.
    """
    if not results:
        return results

    n = len(results)
    logger.info(
        f"[Rerank] LLM reranking {n} candidates "
        f"for query_ref=({_text_log_ref(query)})"
    )

    # Build numbered candidate list
    lines: list[str] = []
    for i, res in enumerate(results):
        text = _candidate_text(res)[:_PASSAGE_TRUNCATE]
        lines.append(f"[{i}] {text}")
    candidates_block = "\n".join(lines)

    prompt = RERANK_PROMPT.format(query=query, candidates=candidates_block)

    try:
        resp = await plugin.invoke_llm(
            llm_uuid, [Message(role="user", content=prompt)]
        )
        raw = _extract_text(resp)
        logger.info(f"[Rerank] LLM response ref: {_text_log_ref(raw)}")
    except Exception as e:
        logger.warning(f"[Rerank] LLM call failed, falling back to original order: {e}")
        return results[:top_k]

    ranking = _parse_ranking(raw, n)
    if ranking is None:
        logger.warning(
            "[Rerank] Failed to parse ranking from LLM response, "
            "falling back to original order"
        )
        return results[:top_k]

    reranked = _apply_ranking(results, ranking, top_k)
    logger.info(
        f"[Rerank] Done: {n} candidates -> top {len(reranked)} "
        f"(order: {ranking[:top_k]})"
    )
    return reranked
