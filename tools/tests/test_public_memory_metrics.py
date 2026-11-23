from __future__ import annotations

import unittest

from tools.evaluation.public_memory_metrics import (
    answer_metrics,
    evaluate_payload,
    metrics_at_k,
    normalize_evidence_id,
    normalize_evidence_ids,
    token_f1,
)


class PublicMemoryMetricsTests(unittest.TestCase):
    def test_binary_metrics_preserve_original_item_ranks(self) -> None:
        metrics = metrics_at_k(['D1', 'D2'], ['D3', 'D1', 'D1', 'D2'], 3)
        self.assertEqual(metrics['hit@3'], 1.0)
        self.assertEqual(metrics['recall@3'], 0.5)
        self.assertEqual(metrics['precision@3'], 1 / 3)
        self.assertEqual(metrics['mrr@3'], 0.5)

    def test_duplicate_and_unknown_hits_do_not_promote_later_evidence(self) -> None:
        result = evaluate_payload(
            {
                'rows': [
                    {
                        'gold_evidence': ['D2:3'],
                        'retrieved_hits': [
                            {'source_id': 'D1'},
                            {'source_id': 'D1'},
                            {},
                            {'source_id': 'D2'},
                        ],
                    }
                ]
            },
            k_values=(3, 4),
        )
        self.assertEqual(result['summary']['hit@3'], 0.0)
        self.assertEqual(result['summary']['mrr@4'], 0.25)
        self.assertEqual(result['queries'][0]['retrieved_ids'], ['D1', 'D1', [], 'D2'])

    def test_multiple_sources_share_one_original_rank(self) -> None:
        result = evaluate_payload(
            {
                'rows': [
                    {
                        'gold_evidence_ids': ['D2', 'D3'],
                        'retrieved_hits': [
                            {'source_ids': ['D1', 'D2', 'D3']},
                        ],
                    }
                ]
            },
            k_values=(1,),
        )
        self.assertEqual(result['summary']['recall@1'], 1.0)
        self.assertEqual(result['summary']['precision@1'], 1.0)
        self.assertEqual(result['queries'][0]['retrieved_ids'], [['D1', 'D2', 'D3']])

    def test_compound_locomo_evidence_and_typo_are_canonicalized(self) -> None:
        self.assertEqual(
            normalize_evidence_ids(['D8:6; D9:17', 'D:11:26', 'D', 'D09:01 D4:4 D4:6']),
            ['D8', 'D9', 'D11', 'D4'],
        )
        self.assertEqual(normalize_evidence_ids('D:11:26', granularity='exact'), ['D11:26'])
        self.assertEqual(normalize_evidence_id('corpus:document:42'), 'corpus:document:42')

    def test_source_citation_takes_precedence_over_internal_entry_id(self) -> None:
        result = evaluate_payload(
            {
                'rows': [
                    {
                        'gold_evidence_ids': ['D1'],
                        'hits': [
                            {'id': 'internal-entry-1', 'citation': {'source_id': 'D1'}},
                        ],
                    }
                ]
            },
            k_values=(1,),
        )
        self.assertEqual(result['summary']['hit@1'], 1.0)

    def test_missing_gold_evidence_is_counted_as_unscorable(self) -> None:
        result = evaluate_payload(
            {
                'rows': [
                    {'gold_evidence_ids': ['D1'], 'retrieved_ids': ['D1']},
                    {'gold_evidence_ids': [], 'retrieved_ids': ['D2']},
                ]
            },
            k_values=(1,),
        )
        self.assertEqual(result['query_count'], 2)
        self.assertEqual(result['retrieval_count'], 1)
        self.assertEqual(result['retrieval_unscorable_count'], 1)
        self.assertEqual(result['summary']['hit@1'], 1.0)

    def test_token_f1_counts_repeated_tokens(self) -> None:
        self.assertEqual(token_f1('very very happy', 'very very happy'), 1.0)
        self.assertAlmostEqual(token_f1('very happy', 'very very happy'), 0.8)
        self.assertEqual(token_f1(0, '0'), 1.0)

    def test_prediction_cannot_supply_its_own_gold(self) -> None:
        self.assertIsNone(answer_metrics({'answer': 'invented'}))

    def test_missing_failed_answers_and_judges_remain_in_denominator(self) -> None:
        result = evaluate_payload(
            {
                'rows': [
                    {'reference_answer': 'yes', 'answer': 'yes', 'judge': {'correct': True}},
                    {'reference_answer': 'yes'},
                    {'reference_answer': 'yes', 'answer': 'yes', 'status': 'error', 'judge': {'correct': True}},
                    {'reference_answer': 'yes', 'answer': 'yes', 'judge': {'correct': None}},
                ]
            }
        )
        self.assertEqual(result['answer_count'], 4)
        self.assertEqual(result['answer_missing_count'], 1)
        self.assertEqual(result['answer_error_count'], 1)
        self.assertEqual(result['judge_missing_count'], 2)
        self.assertEqual(result['judge_coverage'], 0.5)
        self.assertEqual(result['answer_summary']['judge_correct'], 0.25)
        self.assertEqual(result['answer_summary']['exact_match'], 0.5)

    def test_error_rows_cannot_keep_retrieval_credit(self) -> None:
        result = evaluate_payload(
            {'rows': [{'gold_evidence_ids': ['D1'], 'retrieved_ids': ['D1'], 'error': 'timeout'}]},
            k_values=(1,),
        )
        self.assertEqual(result['summary']['hit@1'], 0.0)

    def test_non_object_rows_raise_instead_of_shrinking_denominator(self) -> None:
        with self.assertRaises(ValueError):
            evaluate_payload({'rows': [{}, None]})

    def test_graded_ndcg_uses_all_relevant_gains_for_ideal_order(self) -> None:
        metrics = metrics_at_k(['low', 'high'], ['high'], 1, relevance={'low': 1, 'high': 3})
        self.assertEqual(metrics['ndcg@1'], 1.0)

    def test_session_granularity_normalizes_locomo_turn_ids(self) -> None:
        result = evaluate_payload(
            {
                'results': [
                    {
                        'id': 'q1',
                        'question': 'q',
                        'evidence': ['D1:3'],
                        'retrieved_hits': [{'source_id': 'D2'}, {'source_id': 'D1'}],
                    }
                ]
            },
            k_values=(1, 2),
            granularity='session',
        )
        self.assertEqual(result['queries'][0]['gold_evidence_ids'], ['D1'])
        self.assertEqual(result['queries'][0]['retrieved_ids'], ['D2', 'D1'])
        self.assertEqual(result['summary']['recall@2'], 1.0)

    def test_empty_retrieval_counts_as_zero(self) -> None:
        result = evaluate_payload(
            {'queries': [{'id': 'q1', 'gold_evidence_ids': ['D1'], 'retrieved_ids': []}]},
            k_values=(1,),
        )
        self.assertEqual(result['summary']['hit@1'], 0.0)
        self.assertEqual(result['summary']['mrr@1'], 0.0)

    def test_answer_em_f1_and_judge_are_reported(self) -> None:
        row = {
            'reference_answer': '7 May 2023',
            'answer': 'May 7, 2023',
            'judge': {'correct': True},
        }
        metrics = answer_metrics(row)
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics['exact_match'], 0.0)
        self.assertEqual(metrics['token_f1'], 1.0)
        self.assertEqual(metrics['judge_correct'], 1.0)

        result = evaluate_payload(
            {'results': [{'id': 'q1', 'gold_evidence_ids': ['D1'], 'retrieved_ids': ['D1'], **row}]},
            k_values=(1,),
        )
        self.assertEqual(result['answer_count'], 1)
        self.assertEqual(result['answer_summary']['judge_correct'], 1.0)


if __name__ == '__main__':
    unittest.main()
