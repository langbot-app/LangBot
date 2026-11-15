"""Compute shared retrieval metrics for public memory benchmark outputs.

The evaluator is intentionally dependency-free.  Adapters for LangRAG,
PowerContext and LongTermMemory should write one result row per question and
include the gold evidence IDs and the ranked evidence IDs they actually
delivered to the answer stage.  This module then computes the same metrics for
all three systems without changing their runtime implementations.
"""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


SCHEMA = "langbot.public-memory-eval.v1"
DEFAULT_K_VALUES = (1, 3, 5, 10)


def dedupe_in_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def normalize_evidence_id(value: Any, *, granularity: str = "session") -> str:
    """Normalize LoCoMo-style evidence IDs while preserving generic IDs."""

    text = str(value or "").strip()
    if granularity == "session" and ":" in text:
        return text.split(":", 1)[0]
    return text


def metrics_at_k(
    relevant_ids: Iterable[str],
    retrieved_ids: Iterable[str],
    k: int,
    *,
    relevance: Mapping[str, float] | None = None,
) -> dict[str, float]:
    """Return binary retrieval metrics at one cutoff.

    ``relevance`` may provide graded gains for retrieved IDs.  When omitted,
    every relevant ID has gain one, which matches the public LoCoMo session-
    evidence protocol and the LangRAG benchmark's binary metrics.
    """

    if k <= 0:
        raise ValueError("k must be positive")

    relevant = set(dedupe_in_order(relevant_ids))
    ranked = dedupe_in_order(retrieved_ids)[:k]
    if not relevant:
        return {
            f"hit@{k}": 0.0,
            f"precision@{k}": 0.0,
            f"recall@{k}": 0.0,
            f"mrr@{k}": 0.0,
            f"ndcg@{k}": 0.0,
        }

    first_rank = next(
        (rank for rank, item_id in enumerate(ranked, 1) if item_id in relevant),
        None,
    )
    gains = relevance or {}
    dcg = sum(
        (float(gains.get(item_id, 1.0)) if item_id in relevant else 0.0)
        / math.log2(rank + 1)
        for rank, item_id in enumerate(ranked, 1)
    )
    ideal_ids = list(relevant)[:k]
    ideal_gains = sorted(
        (float(gains.get(item_id, 1.0)) for item_id in ideal_ids),
        reverse=True,
    )
    idcg = sum(gain / math.log2(rank + 1) for rank, gain in enumerate(ideal_gains, 1))
    hits = sum(item_id in relevant for item_id in ranked)

    return {
        f"hit@{k}": 1.0 if first_rank is not None else 0.0,
        f"precision@{k}": hits / k,
        f"recall@{k}": hits / len(relevant),
        f"mrr@{k}": 1.0 / first_rank if first_rank else 0.0,
        f"ndcg@{k}": dcg / idcg if idcg else 0.0,
    }


def evaluate_query(
    relevant_ids: Iterable[str],
    retrieved_ids: Iterable[str],
    k_values: Iterable[int] = DEFAULT_K_VALUES,
    *,
    relevance: Mapping[str, float] | None = None,
) -> dict[str, float]:
    result: dict[str, float] = {}
    for k in k_values:
        result.update(metrics_at_k(relevant_ids, retrieved_ids, k, relevance=relevance))
    return result


def mean_metrics(rows: Sequence[Mapping[str, float]]) -> dict[str, float]:
    if not rows:
        return {}
    keys = sorted({key for row in rows for key in row})
    return {
        key: sum(float(row.get(key, 0.0)) for row in rows) / len(rows)
        for key in keys
    }


def _first_value(row: Mapping[str, Any], names: Sequence[str]) -> Any:
    for name in names:
        value = row.get(name)
        if value is not None:
            return value
    return None


def _hit_id(hit: Any, *, granularity: str) -> str:
    if isinstance(hit, str):
        return normalize_evidence_id(hit, granularity=granularity)
    if not isinstance(hit, Mapping):
        return ""
    metadata = hit.get("metadata")
    if not isinstance(metadata, Mapping):
        metadata = {}
    citation = hit.get("citation")
    if isinstance(citation, Mapping):
        source = citation.get("source_id") or citation.get("source")
        if source:
            return normalize_evidence_id(source, granularity=granularity)
    value = _first_value(
        hit,
        ("source_id", "document_id", "file_id", "id", "artifact_id"),
    )
    if value is None:
        value = _first_value(metadata, ("source_id", "document_id", "file_id", "id"))
    return normalize_evidence_id(value, granularity=granularity)


def _row_relevant_ids(row: Mapping[str, Any], *, granularity: str) -> list[str]:
    value = _first_value(
        row,
        ("gold_evidence_ids", "relevant_document_ids", "relevant_source_ids", "evidence"),
    )
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray)):
        return []
    return dedupe_in_order(
        normalize_evidence_id(item, granularity=granularity) for item in value
    )


def _row_retrieved_ids(row: Mapping[str, Any], *, granularity: str) -> list[str]:
    value = _first_value(
        row,
        ("retrieved_ids", "retrieved_document_ids", "retrieved_source_ids"),
    )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return dedupe_in_order(
            normalize_evidence_id(item, granularity=granularity) for item in value
        )

    hits = _first_value(row, ("retrieved_hits", "hits", "results"))
    if not isinstance(hits, Sequence) or isinstance(hits, (str, bytes, bytearray)):
        return []
    return dedupe_in_order(_hit_id(hit, granularity=granularity) for hit in hits)


def _rows_from_payload(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, Mapping)]
    if not isinstance(payload, Mapping):
        raise ValueError("input JSON must be an object or an array")
    for key in ("queries", "results", "observations", "rows"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, Mapping)]
    retrieval = payload.get("retrieval")
    if isinstance(retrieval, Mapping):
        value = retrieval.get("rows")
        if isinstance(value, list):
            return [row for row in value if isinstance(row, Mapping)]
    raise ValueError("input JSON has no query rows")


def evaluate_payload(
    payload: Any,
    *,
    k_values: Iterable[int] = DEFAULT_K_VALUES,
    granularity: str = "session",
) -> dict[str, Any]:
    """Normalize an adapter output and compute per-query plus mean metrics."""

    k_values = tuple(int(k) for k in k_values)
    if not k_values or any(k <= 0 for k in k_values):
        raise ValueError("k_values must contain positive integers")
    if granularity not in {"exact", "session"}:
        raise ValueError("granularity must be exact or session")

    rows = _rows_from_payload(payload)
    per_query: list[dict[str, Any]] = []
    metric_rows: list[dict[str, float]] = []
    for index, row in enumerate(rows, 1):
        relevant = _row_relevant_ids(row, granularity=granularity)
        retrieved = _row_retrieved_ids(row, granularity=granularity)
        metrics = evaluate_query(relevant, retrieved, k_values)
        metric_rows.append(metrics)
        per_query.append(
            {
                "id": row.get("id", row.get("index", index)),
                "question": row.get("question", row.get("query", "")),
                "gold_evidence_ids": relevant,
                "retrieved_ids": retrieved,
                "metrics": metrics,
            }
        )

    return {
        "schema": SCHEMA,
        "metric_granularity": granularity,
        "k_values": list(k_values),
        "query_count": len(per_query),
        "queries": per_query,
        "summary": mean_metrics(metric_rows),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--k", nargs="+", type=int, default=list(DEFAULT_K_VALUES))
    parser.add_argument("--granularity", choices=("exact", "session"), default="session")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    result = evaluate_payload(payload, k_values=args.k, granularity=args.granularity)
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

