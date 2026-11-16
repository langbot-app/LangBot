from __future__ import annotations

import copy
import unittest

from tools.evaluation.compare import compare_payloads


def run_payload(labels: list[bool]) -> dict:
    ids = [f'conv-{index // 2}/q{index}' for index in range(len(labels))]
    return {
        'protocol': {
            'protocol_id': 'public-memory-v2',
            'dataset_sha256': 'a' * 64,
            'question_set_sha256': 'b' * 64,
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
        'results': [
            {
                'id': ids[index],
                'sample_id': f'conv-{index // 2}',
                'question': f'question {index}',
                'reference_answer': 'yes',
                'answer': 'yes' if label else 'no',
                'judge': {'correct': label},
                'model_trace_status': 'verified',
            }
            for index, label in enumerate(labels)
        ],
    }


class PublicMemoryCompareTests(unittest.TestCase):
    def test_pipeline_without_observed_protocol_trace_is_rejected(self) -> None:
        left = run_payload([True])
        right = copy.deepcopy(left)
        right['results'][0]['model_trace_status'] = 'budget_exceeded'
        with self.assertRaises(ValueError):
            compare_payloads(left, right)
        right['results'][0]['model_trace_status'] = 'verified'
        right['results'][0]['status'] = 'unknown'
        with self.assertRaises(ValueError):
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
        result = compare_payloads(left, right, bootstrap_samples=10)
        self.assertEqual(result['right_correct'], 0)


if __name__ == '__main__':
    unittest.main()
