from dataclasses import dataclass
import json
import unittest

from tools.entrypoints.vdb_benchmark_memray_report import summarize


@dataclass
class Record:
    size: int
    n_allocations: int
    stack: list[tuple[str, str, int]]

    def hybrid_stack_trace(self):
        return self.stack


class MemraySummaryTests(unittest.TestCase):
    def test_only_exports_totals_and_specific_stack_categories(self):
        records = [
            Record(11, 2, [('sqlite3_step', 'sqlite.c', 1), ('_pysqlite_query_execute', 'db.c', 2)]),
            Record(7, 1, [('sqlite3_step', 'sqlite.c', 1)]),
            Record(
                5,
                2,
                [
                    ('_io__Buffered_read', '<unknown>', 0),
                    ('read', '/private/tempfile.py', 1),
                    ('run', '/private/langbot/pkg/utils/bounded_executor.py', 2),
                ],
            ),
            Record(3, 1, [('private_symbol', '/private/langbot/pkg/utils/bounded_executor.py', 7)]),
            Record(1, 1, []),
        ]
        result = summarize(records, expected_peak_bytes=27)
        groups = result['groups']
        self.assertEqual(groups['CPython SQLite'], {'bytes': 11, 'allocations': 2, 'largest_stack_bytes': 11})
        self.assertEqual(groups['SQLite other/unresolved caller']['bytes'], 7)
        self.assertEqual(groups['Temporary file reads on Core bounded executor']['bytes'], 5)
        self.assertEqual(groups['Other/unclassified']['bytes'], 4)
        self.assertEqual(groups['Other/unclassified']['largest_stack_bytes'], 3)
        serial = json.dumps(result)
        for private in ('private', 'sqlite3_step', 'tempfile.py'):
            self.assertNotIn(private, serial)
        self.assertEqual(result['metric'], 'tracked_allocation_high_watermark_not_rss')

    def test_rejects_inconsistent_totals(self):
        with self.assertRaises(ValueError):
            summarize([Record(1, 1, [])], expected_peak_bytes=2)
