import tempfile
import unittest
from pathlib import Path

from benchmarks.run import DEFAULT_CONFIG, DEFAULT_DATASET, run_benchmark


class BenchmarkRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_benchmark_writes_traceable_results(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = await run_benchmark(
                dataset_path=DEFAULT_DATASET,
                config_path=DEFAULT_CONFIG,
                out_dir=Path(tmpdir),
                run_id="unit",
            )

            output_path = Path(result["run"]["output_path"])
            self.assertTrue(output_path.exists())
            self.assertEqual(result["run"]["run_id"], "unit")
            self.assertEqual(result["dataset"]["id"], "mini_zh_v1")
            self.assertGreaterEqual(len(result["experiments"]), 1)
            self.assertIn("dataset_sha256", result["run"])
            self.assertIn("config_sha256", result["run"])


if __name__ == "__main__":
    unittest.main()
