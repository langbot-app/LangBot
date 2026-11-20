import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from tools.entrypoints.vdb_benchmark_public import latency
from tools.regression import vdb_benchmark_public as bench


class PublicBenchmarkTest(TestCase):
    def test_document_metrics_deduplicate_chunks_without_refilling(self):
        file_ids = {'x': 'not-relevant', 'y': 'relevant-1', 'z': 'relevant-2'}
        result = bench.score_chunks(['x', 'y', 'y'], file_ids, {'relevant-1': 1, 'relevant-2': 1})
        self.assertEqual(result['returned_document_ids'], ['not-relevant', 'relevant-1'])
        self.assertEqual(result['recall_at_10'], 0.5)
        self.assertAlmostEqual(result['ndcg_at_10'], 0.38685280723454163)
        with self.assertRaisesRegex(ValueError, 'unowned'):
            bench.score_chunks(['unexpected'], file_ids, {'relevant-1': 1})

    def test_subset_keeps_all_selected_qrels_and_is_deterministic(self):
        docs = {str(i): {} for i in range(24)}
        queries = {f'q{i}': {} for i in range(12)}
        qrels = {'q9': {'21': 1, '22': 1}, 'q8': {'23': 1}}
        src = Path(__file__).resolve().parents[1] / 'profiles' / 'vdb-public-scifact-smoke.json'
        profile = json.loads(src.read_text())
        profile.update(documents=10, test_queries=2)
        with (
            TemporaryDirectory() as directory,
            mock.patch.object(bench, 'read_data', return_value=(docs, queries, qrels)),
        ):
            root = Path(directory)
            path = root / 'profile.json'
            path.write_text(json.dumps(profile))
            manifest, *_ = bench.plan(path, root, verify=False)
            self.assertIn('not a standard BEIR score', manifest['population'])
            self.assertEqual(len(set(manifest['documents'])), 10)
            self.assertTrue({'21', '22', '23'}.issubset(manifest['documents']))
            self.assertTrue(set(manifest['warmup_query_ids']).isdisjoint(manifest['scored_query_ids']))
            self.assertEqual(bench.plan(path, root, verify=False)[0], manifest)

    def test_assets_are_hashed_before_parsing(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'scifact.zip').write_bytes(b'corrupted asset')
            with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                bench.assets_verified(root, ('scifact.zip',))

    def test_latency_interpolates_and_records_denominator(self):
        self.assertIsNone(latency([]))
        self.assertEqual(latency([5, 1]), {'samples': 2, 'p50': 3.0, 'p95': 4.8, 'p99': 4.96, 'max': 5})
