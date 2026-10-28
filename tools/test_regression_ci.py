"""Exercise the daily workflow's published verdict, including incomplete runs."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml

from regression_ci import SUITE_BUDGETS, suite_profile
from regression_suite import validate


class CIProfileTest(unittest.TestCase):
    def test_local_groups_are_explicit_and_smoke_rejects_them(self):
        profile, _ = suite_profile('daily', 'test-run', ['resources'])
        self.assertEqual(profile['scenario_groups'], ['resources'])
        self.assertIn('auth_revocation', {case['name'] for case in profile['cases']})
        with tempfile.TemporaryDirectory() as directory:
            process = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).with_name('regression_ci.py')),
                    '--suite',
                    'smoke',
                    '--scenario-groups',
                    'resources',
                    '--lbctl',
                    'unused',
                    '--output',
                    str(Path(directory) / 'not-created'),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(process.returncode, 2)
            self.assertIn('require --suite scenarios or --suite daily', process.stderr)
            self.assertFalse((Path(directory) / 'not-created').exists())

    def test_suite_selection_uses_shared_cases_and_one_daily_budget(self):
        for name in ('smoke', 'scenarios', 'daily', 'endurance'):
            with self.subTest(suite=name):
                profile, path = suite_profile(name, 'test-run')
                profile['observe'] = {
                    'health': {'core': 'http://localhost/healthz'},
                    'pids': {'core': 1, 'runtime': 2, 'box': 3},
                    'box_data_root': '/tmp/test-box',
                }
                validate(profile)
                self.assertTrue(path.exists())
                self.assertEqual(profile['cleanup'], 'always')
                self.assertEqual(profile['performance_mode'], 'observe')
                if name == 'smoke':
                    self.assertEqual(profile['smoke']['group_turns'], 2)
                    self.assertEqual(SUITE_BUDGETS[name], 60)
                elif name in ('scenarios', 'daily'):
                    self.assertEqual(len(profile['cases']), 46)
                    self.assertEqual(profile['coverage_suite'], 'scenarios')
                    self.assertEqual(profile['smoke']['group_turns'], 3)
                else:
                    self.assertEqual(profile['phases'][0]['duration_seconds'], 540)
                self.assertEqual('execution' in profile, name == 'daily')
        daily, _ = suite_profile('daily', 'test-run')
        self.assertEqual(daily['execution'], {'total_seconds': 1800, 'drain_seconds': 120, 'cooldown_seconds': 60})
        endurance, _ = suite_profile('endurance', 'test-run')
        self.assertEqual(daily['resource_limits']['warmup_seconds'], 180)
        self.assertEqual(daily['resource_limits']['targets'], endurance['resource_limits']['targets'])
        self.assertEqual(daily['resource_limits']['containers'], endurance['resource_limits']['containers'])

    def test_daily_reuses_boxes_per_pipeline_and_separates_runs(self):
        def keys(name, run_id):
            profile, _ = suite_profile(name, run_id)
            return {
                resource['id']: runner['box-session-id-template']
                for resource in profile['resources']
                if resource['kind'] == 'pipeline'
                for runner in resource['body']['config']['ai']['runner_config'].values()
                if runner.get('box-enabled')
            }

        first, second = keys('daily', 'run-a'), keys('daily', 'run-b')
        self.assertTrue(first)
        self.assertEqual(len(set(first.values())), len(first))
        self.assertFalse(set(first.values()) & set(second.values()))
        self.assertEqual(first, keys('daily', 'run-a'))
        self.assertTrue(all(value == '{launcher_type}_{launcher_id}' for value in keys('scenarios', 'run-a').values()))


class DailySummaryTest(unittest.TestCase):
    def test_summary_reports_observations_without_hiding_outer_failures(self):
        workflow = Path(__file__).resolve().parents[1] / '.github/workflows/daily-endurance.yml'
        steps = yaml.safe_load(workflow.read_text())['jobs']['endurance']['steps']
        command = next(step['run'] for step in steps if step.get('name') == 'Publish observations')
        suite = {
            'passed': True,
            'outcome': 'PASS',
            'errors': [],
            'first_pass_complete': True,
            'cycles': [{'complete': True}],
            'requests': 86,
            'ledger_closeout': {'matched': True},
            'observations': {'successful_requests_per_second': 1.0, 'step_p95_seconds': {'chat': 0.5}},
        }
        for gate, actual_suite, expected in [
            ({'passed': True}, suite, 'Daily regression: PASS'),
            ({'passed': False, 'infrastructure_error': 'teardown failed'}, suite, 'teardown failed'),
            ({'passed': False, 'infrastructure_error': 'published plugin install failed'}, None, 'not confirmed'),
            ({'passed': False, 'timed_out': True}, suite, '1860-second outer process guard'),
            ({'passed': False, 'coverage_errors': ['missing access records']}, suite, 'missing access records'),
            ({'passed': False}, {**suite, 'passed': False, 'outcome': 'INCOMPLETE'}, 'Daily regression: INCOMPLETE'),
            (None, None, 'Missing verdict'),
        ]:
            with self.subTest(gate=gate), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / '.qa/daily'
                (target / 'plugins').mkdir(parents=True)
                (target / 'plugins/manifest.json').write_text(
                    json.dumps({'plugins': [{'id': 'langbot-team/LocalAgent', 'version': '1.2.3'}]})
                )
                if gate is not None:
                    (target / 'gate/suite').mkdir(parents=True)
                    (target / 'gate/gate.json').write_text(json.dumps(gate))
                    if actual_suite is not None:
                        (target / 'gate/suite/summary.json').write_text(json.dumps(actual_suite))
                summary = root / 'summary.md'
                env = {
                    **os.environ,
                    'PATH': str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH'],
                    'GITHUB_STEP_SUMMARY': str(summary),
                    'GITHUB_SHA': 'core-revision',
                }
                subprocess.run(['bash', '-e', '-c', command], cwd=root, env=env, check=True, capture_output=True)
                text = summary.read_text()
                self.assertIn(expected, text)
                self.assertIn('langbot-team/LocalAgent@1.2.3', text)
                self.assertIn('not confirmed', text)
                if gate and gate.get('passed'):
                    self.assertIn('Final ledger reconciliation: True', text)
                    self.assertIn('1.000 RPS', text)
                else:
                    self.assertNotIn('Daily regression: PASS', text)

    def test_core_summary_records_preparation_failure_and_selected_plugins(self):
        workflow = Path(__file__).resolve().parents[1] / '.github/workflows/core-smoke.yml'
        steps = yaml.safe_load(workflow.read_text())['jobs']['smoke']['steps']
        command = next(step['run'] for step in steps if step.get('name') == 'Publish gate result')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / '.qa/core-smoke'
            (target / 'plugins').mkdir(parents=True)
            (target / 'gate').mkdir()
            (target / 'plugins/manifest.json').write_text(
                json.dumps({'plugins': [{'id': 'langbot-team/LocalAgent', 'version': '1.2.3'}]})
            )
            (target / 'gate/gate.json').write_text(
                json.dumps({'passed': False, 'infrastructure_error': 'incompatible'})
            )
            summary = root / 'summary.md'
            subprocess.run(
                ['bash', '-e', '-c', command],
                cwd=root,
                check=True,
                capture_output=True,
                env={
                    **os.environ,
                    'PATH': str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH'],
                    'GITHUB_STEP_SUMMARY': str(summary),
                },
            )
            text = summary.read_text()
            self.assertIn('Core smoke: FAIL', text)
            self.assertIn('Preparation or teardown failed', text)
            self.assertIn('langbot-team/LocalAgent@1.2.3', text)
            self.assertIn('not confirmed', text)


if __name__ == '__main__':
    unittest.main()
