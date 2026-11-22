"""Exercise the daily workflow's published verdict, including incomplete runs."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

from tools.entrypoints.regression_ci import SUITE_BUDGETS, main, mixed_scenarios, suite_profile
from tools.entrypoints.regression_suite import validate


class PipelinePermissionProfileTests(unittest.TestCase):
    def test_smoke_explicitly_preserves_empty_workspace_operation_grants(self):
        profile, _ = suite_profile('smoke', 'permissions-test')
        pipelines = [resource for resource in profile['resources'] if resource['kind'] == 'pipeline']
        self.assertTrue(pipelines)
        for pipeline in pipelines:
            preferences = pipeline['body']['extensions_preferences']
            self.assertEqual(preferences['workspace_operations'], [])
            self.assertFalse(preferences['enable_all_plugins'])


class CIProfileTest(unittest.TestCase):
    def test_endurance_load_settings_preserve_business_resources_and_oracles(self):
        original, _ = suite_profile('endurance', 'original')
        settings = {
            'phases': [{**original['phases'][0], 'name': 'soak', 'duration_seconds': 1200, 'rps': 3}],
            'thresholds': {'min_rps_ratio': 0.8, 'max_p95_seconds': {'chat': 8}},
            'performance_mode': 'gate',
        }
        profile, _ = suite_profile('endurance', 'custom', load_settings=settings)
        self.assertEqual(profile['phases'], settings['phases'])
        self.assertEqual(profile['thresholds'], settings['thresholds'])
        self.assertEqual(profile['performance_mode'], 'gate')
        for field in ('resources', 'cases', 'plugins', 'verification', 'coverage_suite', 'resource_limits'):
            self.assertEqual(profile[field], original[field])
        self.assertEqual(profile['cleanup'], 'always')
        with self.assertRaisesRegex(ValueError, 'requires --suite endurance'):
            suite_profile('smoke', 'invalid', load_settings=settings)

    def test_load_settings_reuse_validation_and_reject_unrelated_overrides(self):
        for settings, message in [
            ([], 'non-empty object'),
            ({}, 'non-empty object'),
            ({'vars': {'api_key': 'replacement'}}, 'Unsupported load profile fields'),
            ({'cases': []}, 'Unsupported load profile fields'),
            ({'phases': []}, 'phases must be a non-empty array'),
            ({'thresholds': {'min_rps_ratio': 2}}, 'min_rps_ratio must be <= 1'),
            ({'performance_mode': 'ignored'}, 'performance_mode must be gate or observe'),
            ({'box_command_delay_seconds': True}, 'box_command_delay_seconds must be a finite number'),
            ({'box_command_delay_seconds': []}, 'box_command_delay_seconds must be a finite number'),
            ({'box_command_delay_seconds': float('inf')}, 'box_command_delay_seconds must be a finite number'),
            ({'box_command_delay_seconds': float('nan')}, 'box_command_delay_seconds must be a finite number'),
            ({'box_command_delay_seconds': -1}, 'box_command_delay_seconds must be >= 0'),
        ]:
            with self.subTest(settings=settings), self.assertRaisesRegex(ValueError, message):
                suite_profile('endurance', 'invalid', load_settings=settings)

    def test_mixed_box_duration_is_applied_without_changing_suite_schema(self):
        original, _ = suite_profile('endurance', 'original')
        for delay in (0, 4, 0.25):
            with self.subTest(delay=delay):
                profile, _ = suite_profile('endurance', 'custom', load_settings={'box_command_delay_seconds': delay})
                self.assertEqual(profile, original)
                scenarios = mixed_scenarios(delay)
                commands = [
                    call['arguments']['command']
                    for step in scenarios['mock-smoke-box']['steps']
                    for call in step.get('tool_calls', [])
                ]
                self.assertEqual(len(commands), 2)
                self.assertTrue(all(f'; sleep {delay}; ' in command for command in commands))
                self.assertTrue(all('LB_BOX_HOST=' in command for command in commands))
                self.assertEqual(scenarios['mock-chat']['delay_seconds'], 0.6)
        default = mixed_scenarios()
        self.assertEqual(default, mixed_scenarios(1))
        self.assertNotEqual(default, mixed_scenarios(4))

    def test_cli_load_settings_and_budget_are_validated_before_environment_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings_path = root / 'load.json'
            settings = {'performance_mode': 'gate'}
            settings_path.write_text(json.dumps(settings))
            base = ['regression_ci', '--lbctl', 'unused', '--output', str(root / 'run')]
            with (
                patch(
                    'sys.argv',
                    [*base, '--suite', 'endurance', '--load-profile', str(settings_path), '--budget-seconds', '1800'],
                ),
                patch('tools.entrypoints.regression_ci.run', return_value={'passed': True}) as run,
                patch('builtins.print'),
                self.assertRaises(SystemExit) as result,
            ):
                main()
            self.assertEqual(result.exception.code, 0)
            self.assertEqual(run.call_args.args[0].load_settings, settings)
            self.assertEqual(run.call_args.args[0].budget_seconds, 1800)
            for extra in (
                ['--suite', 'smoke', '--load-profile', str(settings_path)],
                ['--suite', 'smoke', '--budget-seconds', '1800'],
                ['--suite', 'endurance', '--budget-seconds', '0'],
                ['--suite', 'endurance', '--load-profile', str(settings_path), '--mixload-profile', str(settings_path)],
                ['--suite', 'endurance', '--load-profile', str(root / 'missing.json')],
            ):
                with (
                    self.subTest(extra=extra),
                    patch('sys.argv', [*base, *extra]),
                    patch('tools.entrypoints.regression_ci.run') as run,
                    patch('sys.stderr'),
                    self.assertRaises(SystemExit) as result,
                ):
                    main()
                self.assertEqual(result.exception.code, 2)
                run.assert_not_called()
            self.assertFalse((root / 'run').exists())

    def test_local_groups_are_explicit_and_smoke_rejects_them(self):
        profile, _ = suite_profile('daily', 'test-run', ['resources'])
        self.assertEqual(profile['scenario_groups'], ['resources'])
        self.assertIn('auth_revocation', {case['name'] for case in profile['cases']})
        with tempfile.TemporaryDirectory() as directory:
            process = subprocess.run(
                [
                    sys.executable,
                    '-m',
                    'tools.entrypoints.regression_ci',
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
                    self.assertEqual([phase['groups'] for phase in profile['phases']], [8, 16])
                    self.assertEqual(
                        sum(phase['duration_seconds'] + phase['cooldown_seconds'] for phase in profile['phases']), 570
                    )
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


def run_report(mode, directory, *options):
    return subprocess.run(
        [sys.executable, '-m', 'tools.entrypoints.regression_report', mode, str(directory), *options],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
    )


class DailySummaryTest(unittest.TestCase):
    def test_summary_reports_observations_without_hiding_outer_failures(self):
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
                result = run_report('daily', target, '--sha', 'core-revision')
                self.assertEqual(result.returncode, 0 if gate and gate.get('passed') else 1)
                text = result.stdout
                self.assertIn(expected, text)
                self.assertIn('langbot-team/LocalAgent@1.2.3', text)
                self.assertIn('not confirmed', text)
                if gate and gate.get('passed'):
                    self.assertIn('Final ledger reconciliation: True', text)
                    self.assertIn('1.000 RPS', text)
                else:
                    self.assertNotIn('Daily regression: PASS', text)

    def test_api_summary_reports_both_modes_and_keeps_failures_visible(self):
        suite = {'passed': True, 'requests': 14, 'status': {'passed': 14}, 'elapsed_seconds': 7.3}
        daily = {'passed': True, 'api_fixed_only': False, 'api_seed': 123}
        cases = [
            (False, daily, suite, 'success', True, 'Daily API contracts: PASS'),
            (
                False,
                {'passed': True, 'api_seed': 123, 'case_order': ['fixed_api_skills', 'shuffled_api_skills']},
                suite,
                'success',
                True,
                'Daily API contracts: PASS',
            ),
            (False, {'passed': True}, suite, 'success', False, 'verdict does not match'),
            (True, {'passed': True, 'api_fixed_only': True}, suite, 'success', True, 'PR API contracts: PASS'),
            (True, daily, suite, 'success', False, 'verdict does not match the requested run mode'),
            (False, daily, suite, 'failure', False, 'API runner step: failure'),
            (False, daily, None, 'success', False, 'Missing verdict'),
            (
                False,
                {'passed': False, 'infrastructure_error': 'plugin installation failed'},
                None,
                'failure',
                False,
                'plugin installation failed',
            ),
            (False, {'passed': False, 'timed_out': True}, suite, 'failure', False, '600-second outer process guard'),
            (
                False,
                {'passed': False, 'resource_errors': ['sampling failed']},
                suite,
                'failure',
                False,
                'sampling failed',
            ),
            (
                False,
                {'passed': False, 'coverage_errors': ['missing evidence']},
                suite,
                'failure',
                False,
                'missing evidence',
            ),
            (
                False,
                {'passed': False},
                {'passed': False, 'errors': ['MCP mode persisted']},
                'failure',
                False,
                'MCP mode persisted',
            ),
            (False, None, None, 'skipped', False, 'Missing verdict'),
        ]
        for fixed_only, gate, actual_suite, outcome, passed, expected in cases:
            with (
                self.subTest(fixed_only=fixed_only, gate=gate, outcome=outcome),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                target = root / '.qa/api/gate/suite'
                target.mkdir(parents=True)
                if gate is not None:
                    (target.parent / 'gate.json').write_text(json.dumps(gate))
                if actual_suite is not None:
                    (target / 'summary.json').write_text(json.dumps(actual_suite))
                result = run_report(
                    'api-fixed' if fixed_only else 'api-daily', target.parent.parent, '--step-outcome', outcome
                )
                self.assertEqual(result.returncode, 0 if passed else 1, result.stderr)
                text = result.stdout
                self.assertIn(expected, text)
                self.assertIn('not reported', text)
                if fixed_only:
                    self.assertNotIn('Shuffle seed', text)
                else:
                    seed = (gate or {}).get('api_seed', 'not reported')
                    self.assertIn(f'Shuffle seed: `{seed}`', text)
                if not passed:
                    self.assertIn('FAIL / incomplete', text)

    def test_report_rejects_a_different_recorded_suite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'gate/suite').mkdir(parents=True)
            (root / 'gate/gate.json').write_text(json.dumps({'passed': True, 'api_fixed_only': True}))
            (root / 'gate/suite/summary.json').write_text(json.dumps({'passed': True}))
            for mode in ('daily', 'core-smoke'):
                with self.subTest(mode=mode):
                    result = run_report(mode, root)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn('does not match report mode', result.stdout)

    def test_old_core_smoke_is_not_a_legacy_daily_run(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'gate/suite').mkdir(parents=True)
            (root / 'gate/gate.json').write_text(json.dumps({'passed': True, 'budget_seconds': 300}))
            (root / 'gate/suite/summary.json').write_text(json.dumps({'passed': True}))
            result = run_report('daily', root)
            self.assertEqual(result.returncode, 1)
            self.assertIn('Recorded execution budget 300s', result.stdout)

    def test_core_summary_records_preparation_failure_and_selected_plugins(self):
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
            result = run_report('core-smoke', target)
            self.assertEqual(result.returncode, 1)
            text = result.stdout
            self.assertIn('Core smoke: FAIL', text)
            self.assertIn('Preparation or teardown failed', text)
            self.assertIn('langbot-team/LocalAgent@1.2.3', text)
            self.assertIn('not confirmed', text)


class MixedScheduleTest(unittest.TestCase):
    def commands(self):
        path = Path(__file__).resolve().parents[2] / '.github/workflows/daily-endurance.yml'
        steps = yaml.safe_load(path.read_text())['jobs']['endurance']['steps']
        return {step.get('name'): step.get('run') for step in steps}

    def test_one_owned_deployment_selects_mixed_or_finite_contracts(self):
        command = self.commands()['Run daily mixed load or explicit manual contracts']
        for event, requested, suite in [
            ('schedule', 'mixed', 'endurance'),
            ('workflow_dispatch', 'mixed', 'endurance'),
            ('workflow_dispatch', 'contracts', 'scenarios'),
        ]:
            with self.subTest(event=event, requested=requested), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                bindir = root / 'bin'
                bindir.mkdir()
                path = bindir / 'uv'
                path.write_text('#!/bin/sh\nprintf "%s\\n" "$@" >> "$TEST_ARGS"\n')
                path.chmod(0o700)
                subprocess.run(
                    ['bash', '-e', '-c', command],
                    cwd=root,
                    check=True,
                    capture_output=True,
                    env={
                        **os.environ,
                        'PATH': str(bindir) + os.pathsep + os.environ['PATH'],
                        'GITHUB_EVENT_NAME': event,
                        'WORKLOAD': requested,
                        'TEST_ARGS': str(root / 'args'),
                        'SCENARIO_GROUPS': 'faults lifecycle',
                        'EXTRA_PLUGINS': 'misc/EssentialCommands',
                        'RESTART_SERVICES': 'true',
                    },
                )
                args = (root / 'args').read_text().splitlines()
                self.assertEqual(args.count('tools.entrypoints.regression_ci'), 1)
                self.assertEqual(args[args.index('--suite') + 1], suite)
                self.assertEqual('--scenario-groups' in args, suite == 'scenarios')
                self.assertEqual('--restart-services' in args, suite == 'scenarios')
                self.assertEqual(
                    (root / '.qa/daily-workload.txt').read_text().strip(),
                    'mixed' if suite == 'endurance' else 'contracts',
                )

    def test_mixed_summary_requires_its_independent_execution_evidence(self):
        for mixed in (None, {'passed': False, 'outcome': 'INCOMPLETE'}, {'passed': True, 'outcome': 'PASS'}):
            with self.subTest(mixed=mixed), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                target = root / '.qa/daily/gate/suite'
                target.mkdir(parents=True)
                (root / '.qa/daily-workload.txt').write_text('mixed\n')
                (target / 'summary.json').write_text(json.dumps({'passed': True, 'phases': []}))
                (target.parent / 'gate.json').write_text(json.dumps({'passed': True}))
                if mixed is not None:
                    (target.parent / 'mixed.json').write_text(json.dumps(mixed))
                result = run_report('daily', target.parent.parent)
                passed = bool(mixed and mixed['passed'])
                self.assertEqual(result.returncode, 0 if passed else 1)
                self.assertEqual('Daily regression: PASS' in result.stdout, passed)

    def test_mixed_timeout_report_uses_the_recorded_execution_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'gate/suite').mkdir(parents=True)
            (root / 'gate/suite/profile.json').write_text(json.dumps({'coverage_suite': 'endurance'}))
            (root / 'gate/suite/summary.json').write_text(json.dumps({'passed': False}))
            (root / 'gate/gate.json').write_text(
                json.dumps({'passed': False, 'timed_out': True, 'budget_seconds': 1200.0})
            )
            (root / 'gate/mixed.json').write_text(json.dumps({'passed': True}))
            report = run_report('daily', root)
            self.assertEqual(report.returncode, 1)
            self.assertIn('Configured execution guard: 1200 seconds', report.stdout)
            self.assertIn('1200-second outer process guard', report.stdout)

    def test_workload_marker_cannot_hide_missing_mixed_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'daily'
            (root / 'gate/suite').mkdir(parents=True)
            (root.parent / 'daily-workload.txt').write_text('contracts\n')
            (root / 'gate/gate.json').write_text(json.dumps({'passed': True, 'mixed': {'passed': True}}))
            (root / 'gate/suite/summary.json').write_text(json.dumps({'passed': True}))
            result = run_report('daily', root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("conflicts with recorded 'mixed' run", result.stdout)

    def test_required_daily_jobs_fail_for_cancel_skip_missing_and_failure(self):
        path = Path(__file__).resolve().parents[2] / '.github/workflows/daily-endurance.yml'
        jobs = yaml.safe_load(path.read_text())['jobs']
        verdict = jobs['verdict']
        self.assertEqual(set(verdict['needs']), jobs.keys() - {'verdict'})
        daily = dict.fromkeys(verdict['needs'], 'success')
        manual = {**daily, 'dify-cloud': 'skipped'}
        persistence = jobs['persistence-runtime']
        self.assertEqual(persistence['uses'], './.github/workflows/persistence-acceptance.yml')
        self.assertNotIn('if', persistence)
        matrix = {name for name, job in jobs.items() if "inputs.validation_scope == 'full'" in job.get('if', '')}
        workload_only = {**manual, **dict.fromkeys(matrix, 'skipped')}
        commands = [
            (True, True, daily, 0),
            (True, False, manual, 0),
            (False, False, workload_only, 0),
            (False, False, {**workload_only, 'persistence-runtime': 'skipped'}, 1),
            (True, True, {name: state for name, state in daily.items() if name != 'migrations'}, 1),
            *[(True, True, {**daily, 'migrations': state}, 1) for state in ('failure', 'skipped', 'cancelled')],
        ]
        for full, dify, results, expected in commands:
            with self.subTest(full=full, dify=dify, migrations=results.get('migrations')):
                with tempfile.TemporaryDirectory() as folder:
                    summary = Path(folder) / 'summary.md'
                    result = subprocess.run(
                        ['bash', '-e', '-c', verdict['steps'][0]['run']],
                        capture_output=True,
                        env={
                            **os.environ,
                            'PATH': str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH'],
                            'FULL_MATRIX': str(full).lower(),
                            'LIVE_DIFY': str(dify).lower(),
                            'JOB_RESULTS': json.dumps({name: {'result': value} for name, value in results.items()}),
                            'GITHUB_STEP_SUMMARY': str(summary),
                            'GITHUB_SHA': 'candidate',
                        },
                    )
                    self.assertEqual(result.returncode, expected, result.stderr)
                    self.assertIn('migrations', summary.read_text())


if __name__ == '__main__':
    unittest.main()
