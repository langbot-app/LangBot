"""Exercise the extracted helper boundaries without a LangBot installation."""

from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest

from tools.regression.http_bot import signed_headers
from tools.regression.resource_cleanup import cleanup
from tools.regression.run_ledger import connect_readonly, high_water_mark, run_event_rows


class RegressionHelpersTest(unittest.TestCase):
    def test_signed_headers_preserve_exact_timestamp_and_body_bytes(self):
        self.assertEqual(
            signed_headers(b'{"a": 1}\n', 'secret', '00123'),
            {
                'Content-Type': 'application/json',
                'X-LB-Timestamp': '00123',
                'X-LB-Signature': 'sha256=4099cb3a7d934c69470793411e37a45207aa866ba505688b718ca9dd6143b9c3',
            },
        )

    def test_cleanup_journals_redacted_failure_without_masking_original_error(self):
        written = {}
        suite = SimpleNamespace(
            variables={'workspace_uuid': 'owned-workspace'},
            secrets=['private-key'],
            write=written.__setitem__,
        )
        for original in (False, True):
            with self.subTest(original=original):
                row = {'owned_resources': [{'uuid': 'owned-id'}]}

                def fail():
                    raise ValueError('private-key cleanup failure')

                if original:
                    with self.assertRaisesRegex(TimeoutError, 'original failure'):
                        try:
                            raise TimeoutError('original failure')
                        finally:
                            cleanup(suite, row, 'delete', fail)
                else:
                    with self.assertRaisesRegex(ValueError, 'cleanup failure'):
                        cleanup(suite, row, 'delete', fail)

                self.assertEqual(row['assertions'], {'delete': 'failed'})
                self.assertEqual(
                    written[row['resource_journal']],
                    {
                        'workspace_uuid': 'owned-workspace',
                        'resources': [{'uuid': 'owned-id'}],
                        'cleanup_errors': ['ValueError: [REDACTED] cleanup failure'],
                    },
                )

    def test_readonly_ledger_never_creates_and_reads_only_requested_ordered_events(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ledger.db'
            with self.assertRaises(sqlite3.OperationalError):
                connect_readonly(path)
            self.assertFalse(path.exists())
            with closing(sqlite3.connect(path)) as db:
                db.executescript(
                    """
                    CREATE TABLE agent_run (id INTEGER PRIMARY KEY);
                    CREATE TABLE agent_run_event (run_id TEXT, type TEXT, data_json TEXT, sequence INTEGER);
                    INSERT INTO agent_run VALUES (19), (7);
                    INSERT INTO agent_run_event VALUES
                      ('run', 'tool.call.completed', '{"index":2}', 2),
                      ('other', 'tool.call.completed', '{}', 1),
                      ('run', 'tool.call.completed', '{"index":1}', 1),
                      ('run', 'run.completed', '{}', 3);
                    """
                )
            with closing(connect_readonly(path)) as db:
                self.assertEqual(high_water_mark(db), 19)
                self.assertEqual(
                    list(run_event_rows(db, 'run', 'tool.call.completed')),
                    [('tool.call.completed', '{"index":1}'), ('tool.call.completed', '{"index":2}')],
                )
                self.assertEqual(
                    [kind for kind, _ in run_event_rows(db, 'run')],
                    ['tool.call.completed', 'tool.call.completed', 'run.completed'],
                )
                with self.assertRaisesRegex(sqlite3.OperationalError, 'readonly'):
                    db.execute('DELETE FROM agent_run')
