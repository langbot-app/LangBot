"""Execute the CI shell commands that select and enforce source coverage."""

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

import yaml

from tools.ci_core_tests import FULL, select_core_tests


ROOT = Path(__file__).resolve().parents[2]
JOBS = yaml.safe_load((ROOT / '.github/workflows/run-tests.yml').read_text())['jobs']


class CoverageWorkflowTests(unittest.TestCase):
    def test_each_python_version_runs_tests_once_with_coverage_only_on_full_312(self):
        command = next(step['run'] for step in JOBS['test']['steps'] if step.get('name') == 'Run unit + smoke tests')
        cases = [
            ('3.11', True, ['tests/unit_tests', 'tests/smoke']),
            ('3.12', True, ['tests/unit_tests', 'tests/smoke']),
            ('3.13', True, ['tests/unit_tests', 'tests/smoke']),
            ('3.12', False, ['tests/smoke', 'tests/unit_tests/platform']),
        ]
        for version, full, targets in cases:
            with self.subTest(version=version, full=full), tempfile.TemporaryDirectory() as directory:
                capture = 'uv() { printf "%s\\n" "$*" >> commands.txt; }\n'
                subprocess.run(
                    ['bash', '-eo', 'pipefail', '-c', capture + command],
                    cwd=directory,
                    env={
                        **os.environ,
                        'PATH': str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH'],
                        'UNIT_TARGETS': json.dumps(targets),
                        'FULL_UNIT': json.dumps(full),
                        'PYTHON_VERSION': version,
                    },
                    check=True,
                )
                commands = (Path(directory) / 'commands.txt').read_text().splitlines()
                self.assertEqual(len(commands), 1)
                args = shlex.split(commands[0])
                self.assertEqual(args[: 3 + len(targets)], ['run', '--no-sync', 'pytest', *targets])
                self.assertEqual('--cov=langbot' in args, full and version == '3.12')
                if full and version == '3.12':
                    self.assertTrue({'--cov-branch', '--cov-report=json', '--cov-report=xml'} <= set(args))

    def test_threshold_uses_line_coverage_and_rejects_missing_reports(self):
        command = next(
            step['run'] for step in JOBS['test']['steps'] if step.get('name') == 'Check line coverage threshold'
        )
        for covered, expected in ((18, 0), (17, 1), (None, 1)):
            with self.subTest(covered=covered), tempfile.TemporaryDirectory() as directory:
                if covered is not None:
                    # Combined branch percentage must not replace the 18% line threshold.
                    report = {'totals': {'covered_lines': covered, 'num_statements': 100, 'percent_covered': 0}}
                    (Path(directory) / 'coverage.json').write_text(json.dumps(report))
                result = subprocess.run(
                    ['bash', '-e', '-c', command],
                    cwd=directory,
                    env={**os.environ, 'PATH': str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH']},
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, expected, result.stderr)

    def test_focused_routes_and_broad_fallback(self):
        targets, integration = select_core_tests(['src/langbot/pkg/command/callback.py'], False, ROOT)
        self.assertEqual(targets, ['tests/smoke', 'tests/unit_tests/command', 'tests/unit_tests/pipeline'])
        self.assertEqual(integration, ['tests/integration/pipeline'])
        self.assertEqual(
            select_core_tests(['tests/integration/persistence/test_migrations_postgres.py'], False, ROOT),
            (['tests/smoke'], ['tests/integration/persistence']),
        )
        for paths in ([], ['src/langbot/new_boundary.py'], ['tests/integration/persistence/test_removed.py']):
            with self.subTest(paths=paths):
                self.assertEqual(select_core_tests(paths, False, ROOT), FULL)

    def test_runtime_contracts_only_run_for_the_affected_or_full_lane(self):
        flags = ('CORE', 'CORE_FULL', 'SDK', 'COMPATIBILITY', 'PERSISTENCE', 'PERMISSIONS', 'BOX', 'FRONTEND')
        routine = ['src/langbot/pkg/discover/discover.py']
        cases = [
            (routine, {'CORE'}, False),
            *[(routine, {'CORE', flag}, True) for flag in ('SDK', 'PERSISTENCE', 'PERMISSIONS', 'BOX')],
            (['.github/workflows/run-tests.yml'], set(flags), True),
            ([], set(flags), True),
        ]
        for paths, selected, expected in cases:
            with self.subTest(paths=paths, flags=selected), tempfile.NamedTemporaryFile() as output:
                subprocess.run(
                    [sys.executable, 'tools/ci_core_tests.py', 'plan'],
                    cwd=ROOT,
                    env={
                        **os.environ,
                        **{flag: json.dumps(flag in selected) for flag in flags},
                        'CHANGED_PATHS': json.dumps(paths),
                        'GITHUB_OUTPUT': output.name,
                    },
                    check=True,
                    capture_output=True,
                )
                results = dict(line.split('=', 1) for line in Path(output.name).read_text().splitlines())
                self.assertEqual(json.loads(results['runtime_contracts']), expected)
        for name in ('Run required Core and SDK protocol contracts', 'Run Runtime artifact transport'):
            with self.subTest(step=name):
                guard = next(step['if'] for step in JOBS['test']['steps'] if step.get('name') == name)
                self.assertIn("matrix.python-version == '3.12'", guard)
                self.assertIn("needs.plan.outputs.runtime_contracts == 'true'", guard)

    def test_summary_gate_matches_selected_jobs_and_fails_closed(self):
        command = next(
            step['run'] for step in JOBS['coverage']['steps'] if step.get('name') == 'Verify required test jobs'
        )
        jobs = set(JOBS['coverage']['needs']) - {'plan'}
        selection = {job: job in ('test', 'integration') for job in jobs}
        cases = [(None, 'success', True)]
        cases.extend((job, status, False) for job in ('plan', 'test') for status in ('failure', 'skipped', 'cancelled'))
        cases.extend(('postgres-contracts', status, False) for status in ('success', 'failure', 'cancelled'))
        for unsuccessful, status, expected in cases:
            with self.subTest(job=unsuccessful, status=status):
                needs = {job: {'result': 'success' if selection[job] else 'skipped'} for job in jobs}
                needs['plan'] = {'result': 'success', 'outputs': {'selection': json.dumps(selection)}}
                if unsuccessful:
                    needs[unsuccessful]['result'] = status
                with tempfile.NamedTemporaryFile() as summary:
                    result = subprocess.run(
                        ['bash', '-eo', 'pipefail', '-c', command],
                        cwd=ROOT,
                        env={**os.environ, 'NEEDS_JSON': json.dumps(needs), 'GITHUB_STEP_SUMMARY': summary.name},
                        capture_output=True,
                        text=True,
                    )
                self.assertEqual(result.returncode, 0 if expected else 1, result.stderr)


if __name__ == '__main__':
    unittest.main()
