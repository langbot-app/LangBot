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
import re
import string
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


SCHEMA = 'langbot.public-memory-eval.v2'
DEFAULT_K_VALUES = (1, 3, 5, 10)
_LOCOMO_ID = re.compile(r'D:?(\d+)(?::(\d+))?')
_FAILED_STATUSES = {'error', 'failed', 'timeout', 'cancelled', 'canceled'}


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


def normalize_evidence_id(value: Any, *, granularity: str = 'session') -> str:
    """Normalize one LoCoMo ID, preserving generic IDs containing colons."""

    text = '' if value is None else str(value).strip()
    if text == 'D':
        return ''
    match = _LOCOMO_ID.fullmatch(text)
    if match is None:
        return text
    session, turn = match.groups()
    session_id = f'D{int(session)}'
    if granularity == 'session' or turn is None:
        return session_id
    return f'{session_id}:{int(turn)}'


def normalize_evidence_ids(value: Any, *, granularity: str = 'session') -> list[str]:
    """Expand compound LoCoMo annotations while retaining generic source IDs."""

    values = value if isinstance(value, (list, tuple)) else [value]
    result: list[str] = []
    for item in values:
        text = '' if item is None else str(item).strip()
        matches = list(_LOCOMO_ID.finditer(text))
        remainder = _LOCOMO_ID.sub('', text)
        if matches and not remainder.strip(' ;,\t\r\n'):
            result.extend(normalize_evidence_id(match.group(0), granularity=granularity) for match in matches)
        else:
            result.append(normalize_evidence_id(item, granularity=granularity))
    return dedupe_in_order(result)


def _ranked_ids(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return dedupe_in_order(str(item).strip() for item in value if item is not None)
    return [str(value).strip()] if value is not None and str(value).strip() else []


def metrics_at_k(
    relevant_ids: Iterable[str],
    retrieved_ids: Iterable[Any],
    k: int,
    *,
    relevance: Mapping[str, float] | None = None,
) -> dict[str, float]:
    """Score the first ``k`` original retrieval items.

    One item may cite multiple sources at one rank. Recall credits all newly
    covered gold sources. Precision and nDCG credit at most one newly relevant
    item per rank. Repeated and unresolved evidence retains its rank.
    """

    if k <= 0:
        raise ValueError('k must be positive')

    relevant = set(dedupe_in_order(relevant_ids))
    ranked = list(retrieved_ids)[:k]
    covered: set[str] = set()
    first_rank: int | None = None
    credited_items = 0
    dcg = 0.0
    gains = relevance or {}
    for rank, value in enumerate(ranked, 1):
        new_relevant = (set(_ranked_ids(value)) & relevant) - covered
        if not new_relevant:
            continue
        if first_rank is None:
            first_rank = rank
        credited_items += 1
        covered.update(new_relevant)
        gain = max(float(gains.get(item_id, 1.0)) for item_id in new_relevant)
        dcg += gain / math.log2(rank + 1)
    ideal_gains = sorted(
        (float(gains.get(item_id, 1.0)) for item_id in relevant),
        reverse=True,
    )[:k]
    idcg = sum(gain / math.log2(rank + 1) for rank, gain in enumerate(ideal_gains, 1))

    return {
        f'hit@{k}': 1.0 if first_rank is not None else 0.0,
        f'precision@{k}': credited_items / k,
        f'recall@{k}': len(covered) / len(relevant) if relevant else 0.0,
        f'mrr@{k}': 1.0 / first_rank if first_rank else 0.0,
        f'ndcg@{k}': dcg / idcg if idcg else 0.0,
    }


def evaluate_query(
    relevant_ids: Iterable[str],
    retrieved_ids: Iterable[Any],
    k_values: Iterable[int] = DEFAULT_K_VALUES,
    *,
    relevance: Mapping[str, float] | None = None,
) -> dict[str, float]:
    relevant, retrieved = list(relevant_ids), list(retrieved_ids)
    result: dict[str, float] = {}
    for k in k_values:
        result.update(metrics_at_k(relevant, retrieved, k, relevance=relevance))
    return result


def mean_metrics(rows: Sequence[Mapping[str, float]]) -> dict[str, float]:
    if not rows:
        return {}
    keys = sorted({key for row in rows for key in row})
    return {key: sum(float(row.get(key, 0.0)) for row in rows) / len(rows) for key in keys}


def normalize_answer(value: Any) -> str:
    """Normalize a short answer for deterministic EM and token F1."""

    text = ('' if value is None else str(value)).lower()
    text = text.translate(str.maketrans('', '', string.punctuation))
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def token_f1(prediction: Any, reference: Any) -> float:
    prediction_tokens = normalize_answer(prediction).split()
    reference_tokens = normalize_answer(reference).split()
    if not prediction_tokens or not reference_tokens:
        return 1.0 if prediction_tokens == reference_tokens else 0.0
    common = sum((Counter(prediction_tokens) & Counter(reference_tokens)).values())
    if not common:
        return 0.0
    precision = common / len(prediction_tokens)
    recall = common / len(reference_tokens)
    return 2 * precision * recall / (precision + recall)


def _answer_references(row: Mapping[str, Any]) -> list[Any]:
    value = _first_value(row, ('reference_answers', 'gold_answers', 'reference_answer', 'gold_answer'))
    if isinstance(value, list):
        return [reference for reference in value if reference is not None]
    return [value] if value is not None else []


def _failed(row: Mapping[str, Any]) -> bool:
    return bool(row.get('error')) or str(row.get('status', '')).lower() in _FAILED_STATUSES


def _judge_label(row: Mapping[str, Any]) -> bool | None:
    judge = row.get('judge')
    if not isinstance(judge, Mapping):
        return None
    label = judge.get('correct', judge.get('label'))
    if isinstance(label, bool):
        return label
    if isinstance(label, str):
        normalized = label.strip().lower()
        if normalized in {'true', 'correct', 'pass'}:
            return True
        if normalized in {'false', 'wrong', 'fail'}:
            return False
    return None


def answer_metrics(row: Mapping[str, Any]) -> dict[str, float] | None:
    """Keep missing and failed predictions in the gold-bearing denominator."""

    prediction = _first_value(row, ('answer', 'generated_answer', 'prediction'))
    references = _answer_references(row)
    if not references:
        return None
    if _failed(row) or prediction is None or not str(prediction).strip():
        return {'exact_match': 0.0, 'token_f1': 0.0, 'judge_correct': 0.0}
    normalized_prediction = normalize_answer(prediction)
    exact = max(float(normalized_prediction == normalize_answer(reference)) for reference in references)
    f1 = max(token_f1(prediction, reference) for reference in references)
    return {'exact_match': exact, 'token_f1': f1, 'judge_correct': float(_judge_label(row) is True)}


def _first_value(row: Mapping[str, Any], names: Sequence[str]) -> Any:
    for name in names:
        value = row.get(name)
        if value is not None:
            return value
    return None


def _hit_ids(hit: Any, *, granularity: str) -> list[str]:
    if not isinstance(hit, Mapping):
        return normalize_evidence_ids(hit, granularity=granularity)
    citation = hit.get('citation')
    metadata = hit.get('metadata')
    for source in (hit, citation, metadata):
        if not isinstance(source, Mapping):
            continue
        for key in ('source_ids', 'source_id', 'source'):
            if key in source:
                return normalize_evidence_ids(source[key], granularity=granularity)
    for source in (hit, metadata):
        if not isinstance(source, Mapping):
            continue
        for key in ('document_id', 'file_id', 'id', 'artifact_id'):
            if key in source:
                return normalize_evidence_ids(source[key], granularity=granularity)
    return []


def _hit_id(hit: Any, *, granularity: str) -> str:
    """Retain the legacy single-ID helper for existing callers."""

    ids = _hit_ids(hit, granularity=granularity)
    return ids[0] if ids else ''


def _row_relevant_ids(row: Mapping[str, Any], *, granularity: str) -> list[str]:
    value = _first_value(
        row,
        ('gold_evidence_ids', 'gold_evidence', 'relevant_document_ids', 'relevant_source_ids', 'evidence'),
    )
    return normalize_evidence_ids(value, granularity=granularity)


def _row_retrieved_ids(row: Mapping[str, Any], *, granularity: str) -> list[Any]:
    value = _first_value(
        row,
        ('retrieved_ids', 'retrieved_document_ids', 'retrieved_source_ids'),
    )
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        value = _first_value(row, ('retrieved_hits', 'hits', 'results'))
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    result: list[Any] = []
    for hit in value:
        ids = _hit_ids(hit, granularity=granularity)
        result.append(ids[0] if len(ids) == 1 else ids)
    return result


def _rows_from_payload(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, Mapping):
        rows = _first_value(payload, ('queries', 'results', 'observations', 'rows'))
        if rows is None and isinstance(payload.get('retrieval'), Mapping):
            rows = payload['retrieval'].get('rows')
    else:
        raise ValueError('input JSON must be an object or an array')
    if not isinstance(rows, list):
        raise ValueError('input JSON has no query rows')
    if any(not isinstance(row, Mapping) for row in rows):
        raise ValueError('every query row must be an object')
    return rows


def evaluate_payload(
    payload: Any,
    *,
    k_values: Iterable[int] = DEFAULT_K_VALUES,
    granularity: str = 'session',
) -> dict[str, Any]:
    """Compute metrics with explicit evidence and judge coverage counts."""

    k_values = tuple(int(k) for k in k_values)
    if not k_values or any(k <= 0 for k in k_values):
        raise ValueError('k_values must contain positive integers')
    if granularity not in {'exact', 'session'}:
        raise ValueError('granularity must be exact or session')

    rows = _rows_from_payload(payload)
    per_query: list[dict[str, Any]] = []
    metric_rows: list[dict[str, float]] = []
    answer_rows: list[dict[str, float]] = []
    judge_count = 0
    answer_missing_count = 0
    answer_error_count = 0
    for index, row in enumerate(rows, 1):
        relevant = _row_relevant_ids(row, granularity=granularity)
        retrieved = _row_retrieved_ids(row, granularity=granularity)
        metrics = evaluate_query(relevant, [] if _failed(row) else retrieved, k_values)
        retrieval_scorable = bool(relevant) and row.get('retrieval_trace_available') is not False
        if retrieval_scorable:
            metric_rows.append(metrics)
        answer_row = answer_metrics(row)
        if answer_row is not None:
            answer_rows.append(answer_row)
            prediction = _first_value(row, ('answer', 'generated_answer', 'prediction'))
            answer_missing_count += int(prediction is None or not str(prediction).strip())
            answer_error_count += int(_failed(row))
            judge_count += int(_judge_label(row) is not None)
        per_query.append(
            {
                'id': row.get('id', row.get('index', index)),
                'sample_id': row.get('sample_id'),
                'question': row.get('question', row.get('query', '')),
                'gold_evidence_ids': relevant,
                'retrieved_ids': retrieved,
                'retrieval_scorable': retrieval_scorable,
                'metrics': metrics,
                **({'answer_metrics': answer_row} if answer_row is not None else {}),
            }
        )

    result = {
        'schema': SCHEMA,
        'metric_granularity': granularity,
        'rank_unit': 'original_retrieval_item',
        'k_values': list(k_values),
        'query_count': len(per_query),
        'retrieval_count': len(metric_rows),
        'retrieval_unscorable_count': len(rows) - len(metric_rows),
        'queries': per_query,
        'summary': mean_metrics(metric_rows),
    }
    if answer_rows:
        result['answer_count'] = len(answer_rows)
        result['answer_missing_count'] = answer_missing_count
        result['answer_error_count'] = answer_error_count
        result['judge_count'] = judge_count
        result['judge_missing_count'] = len(answer_rows) - judge_count
        result['judge_coverage'] = judge_count / len(answer_rows)
        result['answer_summary'] = mean_metrics(answer_rows)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--k', nargs='+', type=int, default=list(DEFAULT_K_VALUES))
    parser.add_argument('--granularity', choices=('exact', 'session'), default='session')
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = json.loads(args.input.read_text(encoding='utf-8'))
    result = evaluate_payload(payload, k_values=args.k, granularity=args.granularity)
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(serialized, encoding='utf-8')
    else:
        print(serialized, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
