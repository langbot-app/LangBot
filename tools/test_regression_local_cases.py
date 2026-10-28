"""Keep optional cases and expected failures from turning incomplete evidence green."""

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from regression_local_cases import GROUPS, ScenarioUnavailable
from regression_scenarios import expanded_profile
from regression_smoke import run_smoke
from regression_suite import Suite, validate
from regression_traffic import reconcile_runs


class LocalScenarioTests(unittest.TestCase):
    def test_group_switches_keep_base_cases_and_reject_unknown_handlers(self):
        base = expanded_profile()
        for group in GROUPS:
            profile = expanded_profile([group])
            validate(profile)
            self.assertEqual(profile['scenario_groups'], [group])
            self.assertGreater(len(profile['cases']), len(base['cases']))
            self.assertEqual(profile['cases'][: len(base['cases'])], base['cases'])
        for groups in (['unknown'], ['resources', 'resources']):
            with self.assertRaises(ValueError):
                expanded_profile(groups)
        profile = expanded_profile(['resources'])
        profile['scenario_groups'] = []
        with self.assertRaises(ValueError):
            validate(profile)
        profile['scenario_groups'] = ['resources']
        profile['cases'][-1]['scenario'] = 'not-a-real-handler'
        with self.assertRaises(ValueError):
            validate(profile)

    def test_missing_prerequisite_is_skipped_and_incomplete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with sqlite3.connect(root / 'ledger.db') as connection:
                connection.execute('CREATE TABLE agent_run (id INTEGER)')
            profile = {
                'version': 1,
                'cli': {'config': 'context.yaml'},
                'smoke': {'ledger_db': 'ledger.db'},
                'cases': [{'name': 'auth_revocation', 'scenario': 'auth_revocation', 'expect': 'OK'}],
                'observe': {'health': {}},
            }
            suite = Suite(profile, root / 'profile.json', root)
            with patch('regression_local_cases.run_case', side_effect=ScenarioUnavailable('Missing user credential')):
                result = run_smoke(suite)
            self.assertEqual(result['status'], {'skipped': 1})
            self.assertEqual(result['errors'], result['incomplete'])
            self.assertIn('Missing user credential', result['incomplete'][0])
            self.assertFalse(result['cases'][0].get('assertions'))
            self.assertEqual(json.loads((root / 'cases.json').read_text())[0]['status'], 'skipped')

    def test_cleanup_failure_remains_fail_after_unknown_request(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with sqlite3.connect(root / 'ledger.db') as connection:
                connection.execute('CREATE TABLE agent_run (id INTEGER)')
            profile = {
                'version': 1,
                'cli': {'config': 'context.yaml'},
                'smoke': {'ledger_db': 'ledger.db'},
                'cases': [{'name': 'agent_direct_execution', 'scenario': 'agent_direct_execution', 'expect': 'OK'}],
                'observe': {'health': {}},
            }
            suite = Suite(profile, root / 'profile.json', root)

            def fail(suite, case, row):
                row['cleanup_errors'] = ['Agent deletion returned HTTP 500']
                raise RuntimeError('Request outcome unknown')

            with patch('regression_local_cases.run_case', side_effect=fail):
                result = run_smoke(suite)
            suite.finish(result)
            self.assertEqual(result['outcome'], 'FAIL')
            self.assertEqual(result['cases'][0]['status'], 'unknown')
            self.assertTrue(any('cleanup failed' in message for message in result['errors']))

    def test_expected_failure_does_not_allow_extra_or_running_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ledger.db'
            with sqlite3.connect(path) as connection:
                connection.execute(
                    'CREATE TABLE agent_run (id INTEGER, run_id TEXT, workspace_id TEXT, conversation_id TEXT, status TEXT)'
                )
                connection.execute("INSERT INTO agent_run VALUES (1, 'owned', 'ws', 'session', 'failed')")
            args = (path, 'ws', 0, {'session'}, {'owned'})
            self.assertFalse(reconcile_runs(*args)['matched'])
            expected = {'owned': 'failed'}
            self.assertTrue(reconcile_runs(*args, expected_statuses=expected)['matched'])
            with sqlite3.connect(path) as connection:
                connection.execute("UPDATE agent_run SET status='running'")
            self.assertFalse(reconcile_runs(*args, expected_statuses=expected)['matched'])
            with sqlite3.connect(path) as connection:
                connection.execute("UPDATE agent_run SET status='failed'")
                connection.execute("INSERT INTO agent_run VALUES (2, 'extra', 'ws', 'session', 'completed')")
            result = reconcile_runs(*args, expected_statuses=expected)
            self.assertFalse(result['matched'])
            self.assertEqual(result['extra'], ['extra'])
            with self.assertRaises(ValueError):
                reconcile_runs(*args, expected_statuses={'owned': 'running'})


if __name__ == '__main__':
    unittest.main()
