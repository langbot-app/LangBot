from __future__ import annotations

import unittest

from tools.evaluation.public_memory_metrics import evaluate_payload, metrics_at_k


class PublicMemoryMetricsTests(unittest.TestCase):
    def test_binary_metrics_dedupe_ranked_ids(self) -> None:
        metrics = metrics_at_k(["D1", "D2"], ["D3", "D1", "D1", "D2"], 3)
        self.assertEqual(metrics["hit@3"], 1.0)
        self.assertEqual(metrics["recall@3"], 1.0)
        self.assertEqual(metrics["mrr@3"], 0.5)

    def test_session_granularity_normalizes_locomo_turn_ids(self) -> None:
        result = evaluate_payload(
            {
                "results": [
                    {
                        "id": "q1",
                        "question": "q",
                        "evidence": ["D1:3"],
                        "retrieved_hits": [{"source_id": "D2"}, {"source_id": "D1"}],
                    }
                ]
            },
            k_values=(1, 2),
            granularity="session",
        )
        self.assertEqual(result["queries"][0]["gold_evidence_ids"], ["D1"])
        self.assertEqual(result["queries"][0]["retrieved_ids"], ["D2", "D1"])
        self.assertEqual(result["summary"]["recall@2"], 1.0)

    def test_empty_retrieval_counts_as_zero(self) -> None:
        result = evaluate_payload(
            {"queries": [{"id": "q1", "gold_evidence_ids": ["D1"], "retrieved_ids": []}]},
            k_values=(1,),
        )
        self.assertEqual(result["summary"]["hit@1"], 0.0)
        self.assertEqual(result["summary"]["mrr@1"], 0.0)


if __name__ == "__main__":
    unittest.main()

