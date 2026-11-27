from __future__ import annotations

import copy
import unittest

from tools.evaluation.compare import compare_payloads
from tools.evaluation.locomo import digest
from tools.evaluation.traces import attach


def refresh_judge_source(payload: dict) -> None:
    untraced = {
        key: value
        for key, value in payload.items()
        if key
        not in {
            'model_trace_coverage',
            'untraced_result_sha256',
            'judge_source_sha256',
            'judge_instruction',
            'judge_identity',
        }
    }
    untraced['results'] = [
        {
            key: value
            for key, value in row.items()
            if key not in {'model_trace_status', 'model_traces', 'retrieval_trace_available', 'judge', 'judge_usage'}
        }
        for row in payload['results']
    ]
    payload['untraced_result_sha256'] = digest(untraced)
    original = {
        key: value
        for key, value in payload.items()
        if key not in {'judge_source_sha256', 'judge_instruction', 'judge_identity'}
    }
    original['results'] = [
        {key: value for key, value in row.items() if key not in {'judge', 'judge_usage'}} for row in payload['results']
    ]
    payload['judge_source_sha256'] = digest(original)


def run_payload(labels: list[bool]) -> dict:
    ids = [f'conv-{index // 2}/q{index}' for index in range(len(labels))]
    questions = [
        {
            'id': ids[index],
            'sample_id': f'conv-{index // 2}',
            'question': f'question {index}',
            'reference_answer': 'yes',
            'category': 4,
            'category_name': 'single_hop',
            'gold_evidence': ['D1:1'],
        }
        for index in range(len(labels))
    ]
    payload = {
        'protocol': {
            'protocol_id': 'public-memory-v2',
            'dataset_sha256': 'a' * 64,
            'question_set_sha256': digest(questions),
            'embedding_model': 'minilm384',
            'answer_model': 'flash',
            'answer_policy': 'source-only-v1',
            'answer_temperature': 0,
            'answer_max_tokens': 256,
            'judge_model': 'flash',
            'judge_policy': 'strict-v1',
            'context_budget_bytes': 12000,
            'execution_layer': 'langbot.pipeline',
        },
        'planned_question_ids': ids,
        'complete': True,
        'results': [
            {
                **questions[index],
                'answer': 'yes' if label else 'no',
                'status': 'completed',
                'started_at': f'2026-01-01T00:{index:02d}:00+00:00',
                'finished_at': f'2026-01-01T00:{index:02d}:30+00:00',
            }
            for index, label in enumerate(labels)
        ],
    }
    records = []
    for index, row in enumerate(payload['results']):
        request_id = f'request-{index}'
        records.extend(
            [
                {
                    'event': 'request_start',
                    'request_id': request_id,
                    'timestamp': f'2026-01-01T00:{index:02d}:05+00:00',
                    'request_body': {
                        'model': 'flash',
                        'temperature': 0,
                        'max_tokens': 256,
                        'messages': [{'role': 'user', 'content': row['question']}],
                    },
                },
                {
                    'event': 'request_complete',
                    'request_id': request_id,
                    'timestamp': f'2026-01-01T00:{index:02d}:10+00:00',
                    'outcome': 'ok',
                    'upstream_status': 200,
                },
            ]
        )
    payload = attach(payload, records)
    payload['judge_instruction'] = 'Frozen fixture correctness instruction'
    payload['judge_identity'] = {
        'instruction': payload['judge_instruction'],
        'base_url': 'https://example.org/v1',
        'model': 'flash',
        'temperature': 0,
        'max_tokens': 256,
        'extra': {},
    }
    for row, label in zip(payload['results'], labels):
        row['judge'] = {'correct': label}
    refresh_judge_source(payload)
    return payload


class PublicMemoryCompareTests(unittest.TestCase):
    def test_one_conversation_does_not_produce_a_degenerate_confidence_interval(self) -> None:
        result = compare_payloads(run_payload([True]), run_payload([False]), bootstrap_samples=10)
        self.assertIsNone(result['confidence_interval']['lower'])
        self.assertIsNone(result['confidence_interval']['upper'])

    def test_raw_receipts_override_stale_cached_flags_and_unknown_is_rejected(self) -> None:
        left = run_payload([True])
        right = copy.deepcopy(left)
        right['results'][0]['model_trace_status'] = 'budget_exceeded'
        refresh_judge_source(right)
        result = compare_payloads(left, right, bootstrap_samples=10)
        self.assertEqual(result['right_correct'], 1)
        right['results'][0]['model_trace_status'] = 'verified'
        right['results'][0]['status'] = 'unknown'
        refresh_judge_source(right)
        with self.assertRaisesRegex(ValueError, 'unknown executions'):
            compare_payloads(left, right)

    def test_paired_outcomes_and_seeded_cluster_interval(self) -> None:
        left = run_payload([True, False, True, False])
        right = run_payload([True, True, False, False])
        result = compare_payloads(left, right, seed=7, bootstrap_samples=100)
        self.assertEqual(
            result['paired_outcomes'],
            {
                'both_correct': 1,
                'left_only_correct': 1,
                'right_only_correct': 1,
                'both_wrong': 1,
            },
        )
        self.assertEqual(result['conversation_count'], 2)
        self.assertEqual(result['right_minus_left'], 0.0)
        self.assertEqual(result, compare_payloads(left, right, seed=7, bootstrap_samples=100))

    def test_partial_and_duplicate_results_are_rejected(self) -> None:
        left = run_payload([True, False])
        for mutation in ('partial', 'duplicate', 'extra'):
            with self.subTest(mutation=mutation):
                right = copy.deepcopy(left)
                if mutation == 'partial':
                    right['results'].pop()
                elif mutation == 'duplicate':
                    right['results'].append(copy.deepcopy(right['results'][0]))
                else:
                    extra = copy.deepcopy(right['results'][0])
                    extra['id'] = 'extra'
                    right['results'].append(extra)
                with self.assertRaises(ValueError):
                    compare_payloads(left, right)

    def test_protocol_drift_and_missing_manifest_are_rejected(self) -> None:
        left = run_payload([True])
        for field in left['protocol']:
            with self.subTest(field=field):
                right = copy.deepcopy(left)
                right['protocol'][field] = 4096 if field == 'context_budget_bytes' else 'different'
                with self.assertRaises(ValueError):
                    compare_payloads(left, right)
        with self.assertRaises(ValueError):
            compare_payloads(left, {'results': left['results']})

    def test_reference_question_and_conversation_drift_are_rejected(self) -> None:
        left = run_payload([True])
        for field in ('question', 'reference_answer', 'sample_id'):
            right = copy.deepcopy(left)
            right['results'][0][field] = 'changed'
            with self.subTest(field=field), self.assertRaises(ValueError):
                compare_payloads(left, right)

    def test_explicit_errors_remain_zero_scored_in_complete_plan(self) -> None:
        left = run_payload([True, True])
        right = copy.deepcopy(left)
        right['results'][0].update(status='error', answer='', error='transport failure')
        right['results'][0].pop('judge')
        refresh_judge_source(right)
        result = compare_payloads(left, right, bootstrap_samples=10)
        self.assertEqual(result['question_count'], 2)
        self.assertEqual(result['right_accuracy'], 0.5)
        self.assertEqual(result['right_metrics']['answer_count'], 2)

    def test_successful_rows_require_a_completed_judge(self) -> None:
        left = run_payload([True])
        right = copy.deepcopy(left)
        right['results'][0]['judge']['correct'] = None
        with self.assertRaises(ValueError):
            compare_payloads(left, right)

    def test_missing_answer_cannot_receive_true_judge_credit(self) -> None:
        left = run_payload([True])
        right = copy.deepcopy(left)
        right['results'][0].pop('answer')
        refresh_judge_source(right)
        result = compare_payloads(left, right, bootstrap_samples=10)
        self.assertEqual(result['right_correct'], 0)

    def test_cached_verified_flag_cannot_replace_raw_delivery_receipts(self) -> None:
        left = run_payload([True])
        right = copy.deepcopy(left)
        right['results'][0].pop('model_traces')
        refresh_judge_source(right)
        with self.assertRaisesRegex(ValueError, 'raw model/context-budget traces: missing'):
            compare_payloads(left, right)

    def test_raw_trace_settings_and_outcome_are_revalidated(self) -> None:
        left = run_payload([True])
        for field, value in [('model', 'wrong'), ('temperature', 1), ('max_tokens', 1024)]:
            right = copy.deepcopy(left)
            right['results'][0]['model_traces'][0]['request']['request_body'][field] = value
            refresh_judge_source(right)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'raw model/context-budget traces'):
                compare_payloads(left, right)
        right = copy.deepcopy(left)
        right['results'][0]['model_traces'][0]['response']['upstream_status'] = 500
        refresh_judge_source(right)
        with self.assertRaisesRegex(ValueError, 'raw model/context-budget traces: incomplete'):
            compare_payloads(left, right)

    def test_declared_budget_is_checked_against_actual_serialized_messages(self) -> None:
        left = run_payload([True])
        right = copy.deepcopy(left)
        left['protocol']['context_budget_bytes'] = right['protocol']['context_budget_bytes'] = 1
        for payload in (left, right):
            payload['results'][0]['model_traces'][0]['request']['serialized_messages_bytes'] = 0
            refresh_judge_source(payload)
        with self.assertRaisesRegex(ValueError, 'budget_exceeded'):
            compare_payloads(left, right)

    def test_judge_source_hash_rejects_changed_answer(self) -> None:
        left = run_payload([True])
        right = copy.deepcopy(left)
        right['results'][0]['answer'] = 'changed after judging'
        with self.assertRaisesRegex(ValueError, 'Judge source hash'):
            compare_payloads(left, right)

    def test_model_trace_source_hash_is_revalidated(self) -> None:
        left = run_payload([True])
        right = copy.deepcopy(left)
        right['untraced_result_sha256'] = 'wrong'
        original = {
            key: value
            for key, value in right.items()
            if key not in {'judge_source_sha256', 'judge_instruction', 'judge_identity'}
        }
        original['results'] = [
            {key: value for key, value in row.items() if key not in {'judge', 'judge_usage'}}
            for row in right['results']
        ]
        right['judge_source_sha256'] = digest(original)
        with self.assertRaisesRegex(ValueError, 'Model-trace source hash'):
            compare_payloads(left, right)

    def test_actual_judge_instructions_endpoints_and_decoding_must_match(self) -> None:
        left = run_payload([True])
        for field, value in [('instruction', 'another prompt'), ('base_url', 'https://other.org/v1')]:
            right = copy.deepcopy(left)
            right['judge_identity'][field] = value
            if field == 'instruction':
                right['judge_instruction'] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'different frozen judge'):
                compare_payloads(left, right)
        right = copy.deepcopy(left)
        right['judge_identity']['model'] = 'other'
        with self.assertRaisesRegex(ValueError, 'Frozen judge identity differs'):
            compare_payloads(left, right)

    def test_plan_hash_binds_actual_evidence_and_categories(self) -> None:
        left = run_payload([True])
        right = copy.deepcopy(left)
        right['results'][0]['gold_evidence'] = ['D2:1']
        refresh_judge_source(right)
        with self.assertRaisesRegex(ValueError, 'Question plan hash differs'):
            compare_payloads(left, right)


if __name__ == '__main__':
    unittest.main()
