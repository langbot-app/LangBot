"""Focused checks for bounded upload-memory fixtures."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.entrypoints import vdb_benchmark_upload as runner


class UploadMemoryTests(unittest.TestCase):
    def test_peak_inflight_does_not_double_count_adjacent_intervals(self):
        rows = [{'began_ns': a, 'ended_ns': b} for a, b in [(10, 20), (20, 30), (16, 25)]]
        self.assertEqual(runner.peak_inflight(rows), 2)

    def test_rejects_unproven_size_or_memory_headroom_before_upload(self):
        with TemporaryDirectory() as working:
            p = Path(working)
            (p / 'profile.json').write_text(
                json.dumps(
                    {
                        'version': 1,
                        'idle_seconds': 4,
                        'chunk_size': 2048,
                        'cases': [
                            {'id': 'too-large', 'file_bytes': 8 * runner.MIB, 'files': 1, 'workers': 1, 'attach': True}
                        ],
                    }
                )
            )
            with self.assertRaisesRegex(ValueError, 'file_bytes'):
                runner.load_profile(p / 'profile.json')
            (p / 'meminfo').write_text('MemAvailable: 999 kB\n')
            with self.assertRaisesRegex(ValueError, 'admission floor'):
                runner.check_headroom(p / 'meminfo')
            (p / 'meminfo').write_text('MemTotal: 999 kB\n')
            with self.assertRaisesRegex(ValueError, 'unavailable'):
                runner.check_headroom(p / 'meminfo')
