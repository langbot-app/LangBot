"""Exercise the real finite runner with a controlled clock and an independent SQLite ledger."""

import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from regression_scenarios import ExecutionWindow, expanded_profile
from regression_smoke import run_smoke
from regression_suite import Suite, validate


class ScenarioExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        with sqlite3.connect(self.root / 'ledger.db') as connection:
            connection.executescript("""
                CREATE TABLE agent_run (id INTEGER, run_id TEXT, workspace_id TEXT,
                    conversation_id TEXT, status TEXT, status_reason TEXT, finished_at TEXT);
                CREATE TABLE agent_run_event (run_id TEXT, sequence INTEGER, type TEXT, data_json TEXT);
            """)
        self.profile = {
            'version': 1,
            'cli': {'config': 'context.yaml'},
            'smoke': {'ledger_db': 'ledger.db'},
            'cases': [{'name': name, 'args': ['provider', 'list'], 'expect': 'OK'} for name in ('a', 'b', 'c')],
            'observe': {'health': {'core': 'http://unused.invalid/healthz'}},
            'execution': {'total_seconds': 100, 'drain_seconds': 10, 'cooldown_seconds': 10},
        }
        self.suite = Suite(self.profile, self.root / 'profile.json', self.root)
        self.suite.variables['workspace_uuid'] = 'test'
        self.now = 0
        self.clock = patch('time.monotonic', side_effect=lambda: self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.suite.execution = ExecutionWindow(self.suite)

    def execute(self, outputs):
        calls = []

        def call(args, body=None):
            calls.append(list(args))
            self.now += 20
            value = next(outputs)
            if isinstance(value, Exception):
                raise value
            return value

        self.suite.call = call
        with patch('regression_smoke.read_endpoint_snapshot', return_value={'http.ok': 1}):
            result = run_smoke(self.suite)
        return result, calls

    def test_required_first_pass_then_partial_optional_cycle_preserves_evidence(self):
        result, calls = self.execute(iter(['OK'] * 4))
        self.assertEqual(len(calls), 4)
        self.assertTrue(result['first_pass_complete'])
        self.assertEqual(result['errors'], [])
        self.assertEqual(
            [(row['case'], row['cycle']) for row in result['cases']], [('a', 1), ('b', 1), ('c', 1), ('a', 2)]
        )
        self.assertEqual([cycle['complete'] for cycle in result['cycles']], [True, False])
        self.assertEqual(json.loads((self.root / 'cases.json').read_text()), result['cases'])

    def test_first_pass_shortfall_is_incomplete(self):
        self.profile['execution']['total_seconds'] = 50
        self.suite.execution = ExecutionWindow(self.suite)
        result, calls = self.execute(iter(['OK'] * 2))
        self.assertEqual(len(calls), 2)
        self.assertFalse(result['first_pass_complete'])
        self.assertIn('Required first pass', result['incomplete'][0])
        self.assertTrue(result['errors'])

    def test_later_success_does_not_erase_failure_and_unknown_stops_repetition(self):
        result, _ = self.execute(iter(['wrong', 'OK', 'OK', 'OK']))
        self.assertEqual(result['status'], {'failed': 1, 'passed': 3})
        self.assertEqual(result['cases'][0]['assertions']['response'], 'failed')
        self.assertTrue(result['errors'])
        self.now = 0
        result, calls = self.execute(iter([RuntimeError('outcome unknown'), 'OK', 'OK']))
        self.assertEqual(len(calls), 3)
        self.assertEqual(result['status'], {'unknown': 1, 'passed': 2})
        self.assertTrue(result['incomplete'])
        self.assertEqual(len(result['cycles']), 1)

    def test_connection_reset_is_unknown_and_does_not_start_another_cycle(self):
        self.profile['cases'][0] = {
            'name': 'transport',
            'http_probe': {'url': 'http://unused.invalid', 'auth': 'missing'},
            'expect': '401',
        }
        with patch('regression_smoke.api_probe', side_effect=ConnectionResetError('peer reset')) as probe:
            result, calls = self.execute(iter(['OK'] * 4))
        self.assertEqual(probe.call_count, 1)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result['status'], {'unknown': 1, 'passed': 2})
        self.assertEqual(len(result['cycles']), 1)
        self.assertTrue(result['first_pass_complete'])
        self.assertEqual(result['errors'], result['incomplete'])

    def test_cooldown_reconciles_late_runs_against_original_scope(self):
        self.profile['cases'] = [{'name': 'chat', 'args': ['pipeline', 'run', 'owned'], 'expect': 'OK'}]
        self.profile['execution']['total_seconds'] = 50
        path = self.root / 'ledger.db'

        def call(args, body=None):
            self.now = 30
            with sqlite3.connect(path) as connection:
                connection.execute("INSERT INTO agent_run VALUES (1,'expected','test','session','completed','','now')")
                connection.execute("INSERT INTO agent_run_event VALUES ('expected',1,'run.completed','{}')")
            return {'session_id': 'session', 'reply': 'OK'}

        self.suite.call = call
        for late_status in (None, 'completed', 'running'):
            with self.subTest(late_status=late_status):
                self.now = 0
                with sqlite3.connect(path) as connection:
                    connection.execute('DELETE FROM agent_run')
                    connection.execute('DELETE FROM agent_run_event')
                window = self.suite.execution = ExecutionWindow(self.suite)
                with patch('regression_smoke.read_endpoint_snapshot', return_value={'http.ok': 1}):
                    result = run_smoke(self.suite)
                self.assertTrue(result['ledger']['matched'])
                self.assertEqual(result['errors'], [])

                def cooldown(_seconds):
                    self.assertEqual(window.stage, 'cooldown')
                    with sqlite3.connect(path) as connection:
                        connection.execute(
                            "INSERT INTO agent_run VALUES (2,'other-ws','other','session','running','',NULL)"
                        )
                        connection.execute(
                            "INSERT INTO agent_run VALUES (3,'other-session','test','other','running','',NULL)"
                        )
                        if late_status:
                            connection.execute(
                                "INSERT INTO agent_run VALUES (4,'late','test','session',?,'',?)",
                                (late_status, 'now' if late_status == 'completed' else None),
                            )
                    self.now = window.deadline - 1

                with (
                    patch.object(window.stop, 'wait', side_effect=cooldown),
                    patch.object(window.thread, 'join'),
                    patch.object(window.thread, 'is_alive', return_value=False),
                ):
                    window.finish(result)
                self.assertTrue(result['ledger']['matched'])
                self.assertEqual(result['ledger_closeout']['matched'], late_status is None)
                self.assertEqual(result['ledger_closeout']['extra'], ['late'] if late_status else [])
                self.assertEqual(
                    result['ledger_closeout']['not_completed'], ['late'] if late_status == 'running' else []
                )
                self.assertEqual(bool(result['errors']), late_status is not None)

    def test_early_abort_waits_only_for_configured_cooldown(self):
        window = self.suite.execution
        self.now = 5
        result = {'errors': ['Preparation failed']}

        def cooldown(seconds):
            self.assertEqual(seconds, 10)
            self.now += seconds

        with (
            patch.object(window.stop, 'wait', side_effect=cooldown),
            patch.object(window.thread, 'join'),
            patch.object(window.thread, 'is_alive', return_value=False),
        ):
            window.finish(result)
        self.assertEqual(result['errors'], ['Preparation failed'])
        self.assertEqual(result['execution']['elapsed_seconds'], 15)
        self.assertLess(self.now, window.deadline)

    def test_request_timeout_is_unknown_but_remains_a_failure(self):
        result, _ = self.execute(iter([TimeoutError('request timed out'), 'OK', 'OK']))
        self.assertEqual(result['cases'][0]['status'], 'unknown')
        self.assertTrue(result['cases'][0]['timed_out'])
        self.assertTrue(set(result['errors']) - set(result['incomplete']))

    def test_cli_timeout_shrinks_to_shared_deadline_and_cleanup_reuses_it(self):
        self.now = 87
        value = subprocess.CompletedProcess([], 0, '{"data": {}}', '')
        with patch('regression_suite.subprocess.run', return_value=value) as run:
            self.suite.call(['provider', 'list'])
            self.assertEqual(run.call_args.kwargs['timeout'], 3)
            self.now = 90
            with self.assertRaises(TimeoutError):
                self.suite.call(['provider', 'list'])
            self.assertEqual(run.call_count, 1)
        (self.root / 'owned.json').write_text(json.dumps({'workspace_uuid': 'test', 'resources': []}))
        with self.assertRaises(TimeoutError):
            self.suite.cleanup()
        self.assertEqual(self.suite.execution.stage, 'cleanup')

    def test_unavailable_process_fails_observation_mode_and_retains_sample(self):
        self.clock.stop()
        self.profile['performance_mode'] = 'observe'
        self.profile['execution'] = {'total_seconds': 0.15, 'drain_seconds': 0.02, 'cooldown_seconds': 0.02}
        self.profile['observe']['pids'] = {'missing': 999999999}
        window = ExecutionWindow(self.suite)
        result = {'errors': []}
        with patch('regression_traffic.read_endpoint_snapshot', return_value={'http.ok': 1}):
            window.start()
            window.finish(result)
        self.assertTrue(any('process sample failed' in error for error in result['errors']))
        self.assertFalse(window.thread.is_alive())
        rows = [json.loads(line) for line in (self.root / 'resources.jsonl').read_text().splitlines()]
        self.assertIn('error', rows[0]['targets']['missing'])
        self.assertEqual(
            [phase['stage'] for phase in result['execution']['phases']], ['prepare', 'cooldown', 'finished']
        )

    def test_expanded_profile_and_budget_validation(self):
        expanded = expanded_profile()
        self.assertEqual(len(expanded['cases']), 46)
        validate(expanded)
        validate(self.profile)
        for execution in (
            {},
            {**self.profile['execution'], 'total_seconds': 20},
            {**self.profile['execution'], 'drain_seconds': float('nan')},
        ):
            with self.subTest(execution=execution), self.assertRaises(ValueError):
                validate({**self.profile, 'execution': execution})


if __name__ == '__main__':
    unittest.main()
