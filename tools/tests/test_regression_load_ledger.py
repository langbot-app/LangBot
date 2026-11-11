"""Check delayed duplicate runs and separate ledger setup from request latency."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch, Mock
from uuid import uuid4

from tools.entrypoints.regression_traffic import main, reconcile_runs, sample_containers


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

    def test_cli_request_limit_is_exact_and_stops_unused_workers(self):
        cases = self.root / 'cases.json'
        cases.write_text(json.dumps([{'name': name, 'args': [name], 'expect': 'OK'} for name in ('first', 'second')]))
        for limit, rps, shared in ((1, 1, True), (41, 1000, True), (17, 1000, False)):
            calls = []
            lock = threading.Lock()

            def response(command, **_kwargs):
                with lock:
                    calls.append(command[-1])
                time.sleep(0.01)
                return SimpleNamespace(returncode=0, stdout='{"data":{"reply":"OK"}}', stderr='')

            output = self.root / f'limited-{limit}'
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
                '20',
                '--rps',
                str(rps),
                '--workers',
                '8',
                '--cooldown',
                '0',
                '--max-requests',
                str(limit),
            ]
            if shared:
                argv.append('--shared-case-sequence')
            with (
                self.subTest(limit=limit, shared=shared),
                patch.object(sys, 'argv', argv),
                patch('tools.entrypoints.regression_traffic.subprocess.run', side_effect=response),
                redirect_stdout(io.StringIO()),
            ):
                main()
            summary = json.loads((output / 'summary.json').read_text())
            self.assertEqual(len(calls), limit)
            if shared:
                self.assertEqual(calls.count('first'), (limit + 1) // 2)
            self.assertEqual(summary['requests'], limit)
            self.assertEqual(summary['request_limit'], limit)
            self.assertEqual(summary['planned_requests'], limit)
            self.assertEqual(summary['delivery_ratio'], 1)
            self.assertLess(summary['load_elapsed_seconds'], 3)

    def test_cli_request_limit_fails_on_shortfall_or_unknown_outcome(self):
        cases = self.root / 'cases.json'
        cases.write_text(json.dumps([{'name': 'chat', 'args': ['chat'], 'expect': 'OK'}]))
        for unknown in (False, True):
            output = self.root / f'incomplete-{unknown}'
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
                '0.05' if not unknown else '2',
                '--rps',
                '1' if not unknown else '1000',
                '--workers',
                '1',
                '--cooldown',
                '0',
                '--max-requests',
                '3',
            ]
            result = SimpleNamespace(
                returncode=int(unknown),
                stdout='{"error":{"type":"result_unknown"}}' if unknown else '{"data":{"reply":"OK"}}',
                stderr='',
            )
            with (
                self.subTest(unknown=unknown),
                patch.object(sys, 'argv', argv),
                patch('tools.entrypoints.regression_traffic.subprocess.run', return_value=result) as run,
                redirect_stdout(io.StringIO()),
                self.assertRaises(SystemExit) as caught,
            ):
                main()
            self.assertEqual(caught.exception.code, 1)
            summary = json.loads((output / 'summary.json').read_text())
            self.assertEqual(summary['requests'], 3 if unknown else 1)
            self.assertEqual(run.call_count, summary['requests'])
            self.assertEqual(summary['status'], {'unknown': 3} if unknown else {'ok': 1})

    def test_completed_request_past_fixed_count_deadline_is_still_failure(self):
        cases = self.root / 'cases.json'
        cases.write_text(json.dumps([{'name': 'chat', 'args': ['chat'], 'expect': 'OK'}]))
        output = self.root / 'late'
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
            '0.05',
            '--rps',
            '1',
            '--workers',
            '1',
            '--cooldown',
            '0',
            '--max-requests',
            '1',
        ]

        def late_response(*_args, **_kwargs):
            time.sleep(0.12)
            return SimpleNamespace(returncode=0, stdout='{"data":{"reply":"OK"}}', stderr='')

        with (
            patch.object(sys, 'argv', argv),
            patch('tools.entrypoints.regression_traffic.subprocess.run', side_effect=late_response),
            redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit) as caught,
        ):
            main()
        self.assertEqual(caught.exception.code, 1)
        summary = json.loads((output / 'summary.json').read_text())
        self.assertEqual(summary['requests'], 1)
        self.assertEqual(summary['status'], {'ok': 1})
        self.assertGreater(summary['drain_seconds'], 0)

    def test_container_churn_recovers_once_but_other_collection_errors_fail(self):
        failed = SimpleNamespace(returncode=1, stdout='', stderr='Error response from daemon: No such container: old')
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
            patch('tools.entrypoints.regression_traffic.sqlite3.connect', side_effect=slow_connect),
            patch('tools.entrypoints.regression_traffic.group_request', side_effect=response),
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
