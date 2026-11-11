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


ROOT = Path(__file__).resolve().parents[2]
JOBS = yaml.safe_load((ROOT / '.github/workflows/run-tests.yml').read_text())['jobs']


class CoverageWorkflowTests(unittest.TestCase):
    def test_each_python_version_runs_tests_once_with_coverage_only_on_312(self):
        command = next(step['run'] for step in JOBS['test']['steps'] if step.get('name') == 'Run unit + smoke tests')
        for version in ('3.11', '3.12', '3.13'):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                # Capture only the invocation; actual test execution belongs to the matrix job.
                capture = 'uv() { printf "%s\\n" "$*" >> commands.txt; }\n'
                subprocess.run(
                    ['bash', '-e', '-c', capture + command.replace('${{ matrix.python-version }}', version)],
                    cwd=directory,
                    check=True,
                )
                commands = (Path(directory) / 'commands.txt').read_text().splitlines()
                self.assertEqual(len(commands), 1)
                args = shlex.split(commands[0])
                self.assertEqual(args[:4], ['run', 'pytest', 'tests/unit_tests/', 'tests/smoke/'])
                self.assertEqual('--cov=langbot' in args, version == '3.12')
                if version == '3.12':
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

    def test_summary_gate_rejects_unsuccessful_prerequisites(self):
        command = next(
            step['run'] for step in JOBS['coverage']['steps'] if step.get('name') == 'Verify required test jobs'
        )
        cases = [(None, 'success')]
        cases.extend(
            (job, status) for job in JOBS['coverage']['needs'] for status in ('failure', 'skipped', 'cancelled')
        )
        for unsuccessful, status in cases:
            with self.subTest(job=unsuccessful, status=status):
                rendered = command
                for job in JOBS['coverage']['needs']:
                    rendered = rendered.replace(
                        '${{ needs.' + job + '.result }}', status if job == unsuccessful else 'success'
                    )
                result = subprocess.run(['bash', '-e', '-c', rendered], capture_output=True)
                self.assertEqual(result.returncode, 0 if unsuccessful is None else 1)


if __name__ == '__main__':
    unittest.main()
