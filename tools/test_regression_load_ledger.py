"""Check delayed duplicate runs and separate ledger setup from request latency."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch, Mock
from uuid import uuid4

from regression_traffic import main, reconcile_runs, sample_containers


class LoadLedgerTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.db = self.root / 'ledger.db'
        with sqlite3.connect(self.db) as db:
            db.executescript("""
                CREATE TABLE agent_run (id INTEGER PRIMARY KEY, run_id TEXT, workspace_id TEXT,
                    conversation_id TEXT, status TEXT, status_reason TEXT, finished_at TEXT);
                CREATE TABLE agent_run_event (run_id TEXT, sequence INTEGER, type TEXT, data_json TEXT);
            """)

    def test_phase_closeout_catches_delayed_extra_and_unfinished_runs(self):
        with sqlite3.connect(self.db) as db:
            db.execute("INSERT INTO agent_run VALUES (1,'expected','ws','group','completed','','now')")
            db.execute("INSERT INTO agent_run VALUES (2,'unrelated','other','group','completed','','now')")
        self.assertTrue(reconcile_runs(self.db, 'ws', 0, {'group'}, {'expected'})['matched'])
        with sqlite3.connect(self.db) as db:
            db.execute("INSERT INTO agent_run VALUES (3,'late','ws','group','running','',NULL)")
        result = reconcile_runs(self.db, 'ws', 0, {'group'}, {'expected'})
        self.assertFalse(result['matched'])
        self.assertEqual(result['extra'], ['late'])
        self.assertEqual(result['not_completed'], ['late'])

    def test_container_churn_recovers_once_but_other_collection_errors_fail(self):
        failed = SimpleNamespace(returncode=1, stdout='', stderr='No such container: old')
        success = SimpleNamespace(returncode=0, stdout='{"MemUsage":"1MiB / 1GiB","PIDs":"1"}\n', stderr='')
        run = Mock(side_effect=[failed, success])
        result = sample_containers([], '/owned', run, Mock(side_effect=[['old', 'live'], ['live']]))
        self.assertNotIn('container_error', result)
        self.assertEqual(result['container_churn']['removed'], ['old'])
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args.args[0][-1], 'live')
        run = Mock(return_value=failed)
        result = sample_containers([], '/owned', run, Mock(return_value=['live']))
        self.assertIn('container_error', result)
        self.assertEqual(run.call_count, 1)
        run = Mock(return_value=failed)
        result = sample_containers([], '/owned', run, Mock(side_effect=[['old', 'live'], ['live']]))
        self.assertIn('container_error', result)
        self.assertEqual(run.call_count, 2)

    def test_slow_ledger_snapshot_does_not_inflate_response_latency(self):
        connect = sqlite3.connect
        cases = self.root / 'cases.json'
        cases.write_text(
            json.dumps(
                [
                    {
                        'name': 'chat',
                        'expect': 'OK',
                        'http_group': {
                            'url': 'http://127.0.0.1:1/unused',
                            'message': 'hello',
                            'secret_env': 'TEST_GROUP_SECRET',
                        },
                    }
                ]
            )
        )

        def slow_connect(*args, **kwargs):
            time.sleep(0.12)
            return connect(*args, **kwargs)

        def response(case, group, *_args):
            run_id = uuid4().hex
            with connect(self.db) as db:
                db.execute(
                    'INSERT INTO agent_run VALUES (NULL,?,?,?,?,?,?)',
                    (run_id, 'ws', 'group_' + group, 'completed', '', 'now'),
                )
                db.execute('INSERT INTO agent_run_event VALUES (?,1,?,?)', (run_id, 'run.completed', '{}'))
            return {'data': {'session_id': group}}

        output = self.root / 'run'
        argv = [
            'traffic',
            '--lbctl',
            'unused',
            '--config',
            'unused',
            '--cases',
            str(cases),
            '--output',
            str(output),
            '--duration',
            '0.4',
            '--cooldown',
            '0',
            '--rps',
            '8',
            '--workers',
            '1',
            '--groups',
            '1',
            '--ledger-db',
            str(self.db),
            '--workspace',
            'ws',
        ]
        with (
            patch.object(sys, 'argv', argv),
            patch.dict('os.environ', {'TEST_GROUP_SECRET': 'test'}),
            patch('regression_traffic.sqlite3.connect', side_effect=slow_connect),
            patch('regression_traffic.group_request', side_effect=response),
            redirect_stdout(io.StringIO()),
        ):
            main()
        rows = [json.loads(line) for line in (output / 'requests.jsonl').read_text().splitlines()]
        self.assertGreaterEqual(len(rows), 2)
        self.assertTrue(all(row['ledger_setup_seconds'] >= 0.12 for row in rows))
        self.assertTrue(all(row['seconds'] < row['ledger_setup_seconds'] for row in rows))
        self.assertTrue(json.loads((output / 'summary.json').read_text())['ledger_closeout']['matched'])


if __name__ == '__main__':
    unittest.main()
