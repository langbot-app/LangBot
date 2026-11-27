"""Compare complete paired public-evaluation runs under one declared protocol."""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .locomo import digest
from .public_memory_metrics import answer_metrics, evaluate_payload
from .traces import validate_model_traces


SCHEMA = 'langbot.public-memory-comparison.v1'
PROTOCOL_FIELDS = (
    'protocol_id',
    'dataset_sha256',
    'question_set_sha256',
    'embedding_model',
    'answer_model',
    'answer_policy',
    'answer_temperature',
    'answer_max_tokens',
    'judge_model',
    'judge_policy',
    'context_budget_bytes',
    'execution_layer',
)
FAILED_STATUSES = {'error', 'failed', 'timeout', 'cancelled', 'canceled'}
# Dataset adapters use these exact fields when hashing their fixed question plan.
QUESTION_PLAN_FIELDS = ('id', 'sample_id', 'question', 'category', 'category_name', 'reference_answer', 'gold_evidence')
JUDGE_OUTPUT_FIELDS = {'judge_source_sha256', 'judge_instruction', 'judge_identity'}


def _validate_judge_provenance(payload: Mapping[str, Any], protocol: Mapping[str, Any]) -> None:
    identity = payload.get('judge_identity')
    if not isinstance(identity, Mapping):
        raise ValueError('Run lacks frozen judge_identity. Apply the current judge command before comparison')
    if (
        identity.get('model') != protocol['judge_model']
        or not isinstance(identity.get('instruction'), str)
        or not identity['instruction']
        or payload.get('judge_instruction') != identity['instruction']
        or identity.get('temperature') != 0
        or identity.get('max_tokens') != 256
        or identity.get('extra') != protocol.get('judge_request_settings', {})
    ):
        raise ValueError('Frozen judge identity differs from the declared protocol or recorded instruction')
    endpoint = urlsplit(identity.get('base_url', ''))
    if (
        endpoint.scheme not in {'http', 'https'}
        or not endpoint.hostname
        or endpoint.username
        or endpoint.password
        or endpoint.query
        or endpoint.fragment
    ):
        raise ValueError('Frozen judge identity has an invalid endpoint')
    original = {key: value for key, value in payload.items() if key not in JUDGE_OUTPUT_FIELDS}
    row_key = 'results' if 'results' in payload else 'rows'
    original[row_key] = [
        {key: value for key, value in row.items() if key not in {'judge', 'judge_usage'}} for row in payload[row_key]
    ]
    if payload.get('judge_source_sha256') != digest(original):
        raise ValueError('Judge source hash differs from the recorded raw answers or traces')
    if protocol['execution_layer'] == 'langbot.pipeline':
        untraced = {
            key: value
            for key, value in original.items()
            if key not in {'model_trace_coverage', 'untraced_result_sha256'}
        }
        untraced[row_key] = [
            {
                key: value
                for key, value in row.items()
                if key not in {'model_trace_status', 'model_traces', 'retrieval_trace_available'}
            }
            for row in original[row_key]
        ]
        if original.get('untraced_result_sha256') != digest(untraced):
            raise ValueError('Model-trace source hash differs from the original Pipeline answers')


def _references(row: Mapping[str, Any]) -> list[Any]:
    for key in ('reference_answers', 'gold_answers', 'reference_answer', 'gold_answer'):
        if key in row and row[key] is not None:
            value = row[key]
            return value if isinstance(value, list) else [value]
    raise ValueError('every paired question requires a reference answer')


def _row_id(row: Mapping[str, Any]) -> str:
    if row.get('id') is not None:
        return str(row['id'])
    if row.get('index') is not None and row.get('sample_id'):
        return f'{row["sample_id"]}/{row["index"]}'
    raise ValueError('every result requires a stable id and sample_id')


def _validate(payload: Mapping[str, Any]) -> tuple[dict[str, Any], list[str], dict[str, Mapping[str, Any]]]:
    protocol = payload.get('protocol')
    if not isinstance(protocol, Mapping):
        raise ValueError('run is missing the declared protocol manifest')
    missing = [key for key in PROTOCOL_FIELDS if protocol.get(key) is None or protocol[key] == '']
    if missing:
        raise ValueError(f'protocol is missing required fields: {", ".join(missing)}')
    budget = protocol['context_budget_bytes']
    if isinstance(budget, bool) or not isinstance(budget, int) or budget <= 0:
        raise ValueError('protocol context_budget_bytes must be a positive integer')
    planned = payload.get('planned_question_ids')
    if not isinstance(planned, list) or not planned or any(not isinstance(item, str) or not item for item in planned):
        raise ValueError('run requires a non-empty planned_question_ids list')
    if len(set(planned)) != len(planned):
        raise ValueError('planned_question_ids contains duplicate question IDs')
    raw_rows = payload.get('results', payload.get('rows'))
    if not isinstance(raw_rows, list):
        raise ValueError('run requires a results array')
    rows: dict[str, Mapping[str, Any]] = {}
    request_ids = set()
    for row in raw_rows:
        if not isinstance(row, Mapping) or not row.get('sample_id'):
            raise ValueError('every result requires an object with sample_id')
        key = _row_id(row)
        if key in rows:
            raise ValueError(f'duplicate result question ID: {key}')
        _references(row)
        if row.get('status') == 'unknown':
            raise ValueError('unknown executions require reconciliation before comparison')
        if (
            protocol['execution_layer'] == 'langbot.pipeline'
            and row.get('status') not in FAILED_STATUSES
            and not row.get('error')
        ):
            trace_status = validate_model_traces(row, protocol)
            if trace_status != 'verified':
                raise ValueError(f'Question {key} lacks valid raw model/context-budget traces: {trace_status}')
            for trace in row['model_traces']:
                request_id = trace['request']['request_id']
                if request_id in request_ids:
                    raise ValueError('One model request was attributed to multiple questions')
                request_ids.add(request_id)
        rows[key] = row
    if set(rows) != set(planned):
        missing_count = len(set(planned) - set(rows))
        extra_count = len(set(rows) - set(planned))
        raise ValueError(f'run does not cover the complete question plan: missing={missing_count}, extra={extra_count}')
    try:
        questions = [{field: rows[key][field] for field in QUESTION_PLAN_FIELDS} for key in planned]
    except KeyError as exc:
        raise ValueError(
            f'Result lacks canonical question-plan field {exc.args[0]}. Use current fixed-plan outputs'
        ) from None
    if digest(questions) != protocol['question_set_sha256']:
        raise ValueError('Question plan hash differs from the actual questions, references, categories or evidence')
    _validate_judge_provenance(payload, protocol)
    return dict(protocol), planned, rows


def _judge_score(row: Mapping[str, Any]) -> int:
    if row.get('error') or str(row.get('status', '')).lower() in FAILED_STATUSES:
        return 0
    judge = row.get('judge')
    if not isinstance(judge, Mapping):
        raise ValueError(f'question {_row_id(row)} is missing a completed judge')
    label = judge.get('correct', judge.get('label'))
    valid = isinstance(label, bool) or (
        isinstance(label, str) and label.strip().lower() in {'true', 'false', 'correct', 'wrong', 'pass', 'fail'}
    )
    if not valid:
        raise ValueError(f'question {_row_id(row)} has an invalid or incomplete judge')
    metrics = answer_metrics(row)
    if metrics is None:
        raise ValueError(f'question {_row_id(row)} has no reference answer')
    return int(metrics['judge_correct'])


def _percentile(sorted_values: Sequence[float], fraction: float) -> float:
    position = (len(sorted_values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (position - lower)


def compare_payloads(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    seed: int = 0,
    bootstrap_samples: int = 2000,
) -> dict[str, Any]:
    """Return paired judge outcomes and a conversation-cluster bootstrap CI.

    The interval resamples whole conversations, preserving within-conversation
    dependence. LoCoMo has only ten conversations, which limits the precision
    of this interval and its generalization to other datasets.
    """

    if bootstrap_samples <= 0:
        raise ValueError('bootstrap_samples must be positive')
    left_protocol, left_plan, left_rows = _validate(left)
    right_protocol, right_plan, right_rows = _validate(right)
    changed = [
        key
        for key in sorted(set(left_protocol) | set(right_protocol))
        if left_protocol.get(key) != right_protocol.get(key)
    ]
    if changed:
        raise ValueError(f'incompatible declared protocols: {", ".join(changed)}')
    if left['judge_identity'] != right['judge_identity']:
        raise ValueError('Runs used different frozen judge instructions, endpoints or decoding settings')
    if left_plan != right_plan:
        raise ValueError('runs declare different question plans or order')
    outcomes = {'both_correct': 0, 'left_only_correct': 0, 'right_only_correct': 0, 'both_wrong': 0}
    clusters: dict[str, list[int]] = defaultdict(list)
    pairs = []
    for key in left_plan:
        left_row, right_row = left_rows[key], right_rows[key]
        if (
            left_row['sample_id'] != right_row['sample_id']
            or left_row.get('question') != right_row.get('question')
            or _references(left_row) != _references(right_row)
        ):
            raise ValueError(f'question, reference answer or conversation differs for {key}')
        left_score, right_score = _judge_score(left_row), _judge_score(right_row)
        if left_score and right_score:
            outcome = 'both_correct'
        elif left_score:
            outcome = 'left_only_correct'
        elif right_score:
            outcome = 'right_only_correct'
        else:
            outcome = 'both_wrong'
        outcomes[outcome] += 1
        delta = right_score - left_score
        clusters[str(left_row['sample_id'])].append(delta)
        pairs.append({'id': key, 'sample_id': left_row['sample_id'], 'left': left_score, 'right': right_score})
    cluster_values = list(clusters.values())
    rng = random.Random(seed)
    samples = []
    for _ in range(bootstrap_samples):
        selected = rng.choices(cluster_values, k=len(cluster_values))
        samples.append(sum(sum(cluster) for cluster in selected) / sum(len(cluster) for cluster in selected))
    samples.sort()
    count = len(left_plan)
    left_correct = outcomes['both_correct'] + outcomes['left_only_correct']
    right_correct = outcomes['both_correct'] + outcomes['right_only_correct']
    return {
        'schema': SCHEMA,
        'protocol': left_protocol,
        'question_count': count,
        'conversation_count': len(clusters),
        'left_correct': left_correct,
        'right_correct': right_correct,
        'left_accuracy': left_correct / count,
        'right_accuracy': right_correct / count,
        'right_minus_left': (right_correct - left_correct) / count,
        'paired_outcomes': outcomes,
        'confidence_interval': {
            'method': 'conversation-cluster-bootstrap-percentile',
            'confidence': 0.95,
            'seed': seed,
            'bootstrap_samples': bootstrap_samples,
            'lower': _percentile(samples, 0.025) if len(clusters) > 1 else None,
            'upper': _percentile(samples, 0.975) if len(clusters) > 1 else None,
            'limitations': (
                'At least two independent conversation clusters are needed for an interval.'
                if len(clusters) < 2
                else 'Few conversation clusters limit interval precision and generalization.'
            ),
        },
        'left_metrics': evaluate_payload(left),
        'right_metrics': evaluate_payload(right),
        'pairs': pairs,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--bootstrap-samples', type=int, default=2000)
    args = parser.parse_args(argv)
    result = compare_payloads(
        json.loads(args.left.read_text(encoding='utf-8')),
        json.loads(args.right.read_text(encoding='utf-8')),
        seed=args.seed,
        bootstrap_samples=args.bootstrap_samples,
    )
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(serialized, encoding='utf-8')
    else:
        print(serialized, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
