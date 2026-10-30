"""Retrieval metrics used by the offline benchmark runner."""

from __future__ import annotations

import math
from collections.abc import Iterable


def dedupe_in_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def metrics_at_k(
    relevant_document_ids: Iterable[str],
    retrieved_document_ids: Iterable[str],
    k: int,
) -> dict[str, float]:
    """Compute binary document-level retrieval metrics at *k*."""
    relevant = set(relevant_document_ids)
    ranked = dedupe_in_order(retrieved_document_ids)[:k]

    if not relevant:
        return {
            f"hit@{k}": 0.0,
            f"precision@{k}": 0.0,
            f"recall@{k}": 0.0,
            f"mrr@{k}": 0.0,
            f"ndcg@{k}": 0.0,
        }

    hits = [doc_id for doc_id in ranked if doc_id in relevant]
    first_hit_rank = next(
        (rank for rank, doc_id in enumerate(ranked, start=1) if doc_id in relevant),
        None,
    )

    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, doc_id in enumerate(ranked, start=1)
        if doc_id in relevant
    )
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))

    return {
        f"hit@{k}": 1.0 if hits else 0.0,
        f"all_relevant@{k}": 1.0 if relevant.issubset(set(ranked)) else 0.0,
        f"precision@{k}": len(hits) / k if k else 0.0,
        f"recall@{k}": len(hits) / len(relevant),
        f"mrr@{k}": (1.0 / first_hit_rank) if first_hit_rank else 0.0,
        f"ndcg@{k}": (dcg / idcg) if idcg else 0.0,
    }


def evaluate_query(
    relevant_document_ids: Iterable[str],
    retrieved_document_ids: Iterable[str],
    k_values: Iterable[int],
) -> dict[str, float]:
    result: dict[str, float] = {}
    for k in k_values:
        result.update(metrics_at_k(relevant_document_ids, retrieved_document_ids, k))
    return result


def mean_metrics(rows: list[dict[str, float]]) -> dict[str, float]:
    if not rows:
        return {}

    keys = sorted({key for row in rows for key in row})
    return {
        key: sum(row.get(key, 0.0) for row in rows) / len(rows)
        for key in keys
    }
