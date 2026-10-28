import unittest

from benchmarks.metrics import dedupe_in_order, metrics_at_k


class BenchmarkMetricsTests(unittest.TestCase):
    def test_dedupe_in_order_keeps_first_occurrence(self):
        self.assertEqual(
            dedupe_in_order(["doc1", "doc2", "doc1", "doc3"]),
            ["doc1", "doc2", "doc3"],
        )

    def test_metrics_at_k_scores_document_relevance(self):
        metrics = metrics_at_k(
            relevant_document_ids=["doc2", "doc4"],
            retrieved_document_ids=["doc1", "doc2", "doc3"],
            k=3,
        )

        self.assertEqual(metrics["hit@3"], 1.0)
        self.assertEqual(metrics["all_relevant@3"], 0.0)
        self.assertAlmostEqual(metrics["precision@3"], 1 / 3)
        self.assertAlmostEqual(metrics["recall@3"], 1 / 2)
        self.assertAlmostEqual(metrics["mrr@3"], 1 / 2)
        self.assertGreater(metrics["ndcg@3"], 0.0)

    def test_metrics_at_k_scores_all_relevant_success(self):
        metrics = metrics_at_k(
            relevant_document_ids=["doc2", "doc4"],
            retrieved_document_ids=["doc4", "doc1", "doc2"],
            k=3,
        )

        self.assertEqual(metrics["hit@3"], 1.0)
        self.assertEqual(metrics["all_relevant@3"], 1.0)
        self.assertEqual(metrics["recall@3"], 1.0)


if __name__ == "__main__":
    unittest.main()
