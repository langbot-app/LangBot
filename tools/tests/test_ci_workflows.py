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
            ('3.14', True, ['tests/unit_tests', 'tests/smoke']),
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
        root_tests = {test.relative_to(ROOT).as_posix() for test in (ROOT / 'tests/unit_tests').glob('test_*.py')}
        self.assertEqual(
            set(targets), root_tests | {'tests/smoke', 'tests/unit_tests/command', 'tests/unit_tests/pipeline'}
        )
        self.assertEqual(integration, ['tests/integration/pipeline'])
        self.assertEqual(
            select_core_tests(['tests/integration/persistence/test_migrations_postgres.py'], False, ROOT),
            (['tests/smoke'], ['tests/integration/persistence']),
        )
        for paths in ([], ['src/langbot/new_boundary.py'], ['tests/integration/persistence/test_removed.py']):
            with self.subTest(paths=paths):
                self.assertEqual(select_core_tests(paths, False, ROOT), FULL)

    def test_source_changes_include_existing_root_level_regressions(self):
        for source, regression in (
            ('src/langbot/pkg/platform/sources/matrix.py', 'tests/unit_tests/test_matrix_relogin.py'),
            (
                'src/langbot/pkg/provider/modelmgr/requesters/litellmchat.py',
                'tests/unit_tests/test_speech_models_api.py',
            ),
            ('src/langbot/pkg/pipeline/preproc/preproc.py', 'tests/unit_tests/test_preproc.py'),
        ):
            with self.subTest(source=source):
                targets, _ = select_core_tests([source], False, ROOT)
                self.assertIn(regression, targets)
                self.assertNotEqual(targets, FULL[0])

    def test_image_build_and_lightweight_packaging_have_separate_selection(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/core-packaging.yml').read_text())
        triggers = workflow[True]
        jobs = workflow['jobs']
        self.assertFalse(triggers['workflow_call']['inputs']['production_acceptance']['default'])
        self.assertTrue(triggers['workflow_dispatch']['inputs']['production_acceptance']['default'])
        self.assertIn("needs.changes.outputs.packaging == 'true'", jobs['artifacts']['if'])
        self.assertIn('!inputs.production_acceptance', jobs['artifacts']['if'])
        image = jobs['production-image']
        self.assertNotIn('needs', image)
        self.assertIn('inputs.production_acceptance', image['if'])
        self.assertIn("github.event_name == 'schedule'", image['if'])
        self.assertIn("github.event_name == 'workflow_dispatch'", image['if'])
        self.assertNotIn("'pull_request'", image['if'])
        steps = {step.get('name'): step for step in image['steps']}
        upgrade = steps['Run production image upgrade and replacement acceptance']
        self.assertEqual(upgrade['if'], 'inputs.production_acceptance')
        self.assertEqual(upgrade['env']['LANGBOT_IMAGE_PREVIOUS'], 'rockchin/langbot:v4.11.7')
        self.assertIn('--required-suite p0_image', upgrade['run'])
        self.assertIn('inputs.export_image', steps['Upload the production image for Linux acceptance']['if'])
        self.assertNotIn('if', steps['Upload image verification metadata'])

    def test_p0_image_covers_image_inputs_without_enabling_other_suites(self):
        import runpy

        select = runpy.run_path(str(ROOT / 'scripts/p0_acceptance_scope.py'))['select']
        for path in (
            'web/package.json',
            'web/pnpm-lock.yaml',
            '.github/actions/classify-test-changes/action.yml',
            '.github/actions/classify-test-changes/classify.py',
            'scripts/stamp_build_revision.py',
            'scripts/check_core_artifacts.py',
            'Dockerfile',
        ):
            with self.subTest(path=path):
                self.assertEqual(select([path]), {'image': True, 'permissions': False, 'persistence': False})
        for path in ('web/src/app/page.tsx', 'docs/index.mdx'):
            with self.subTest(path=path):
                self.assertEqual(select([path]), {'image': False, 'permissions': False, 'persistence': False})

    def test_generic_startup_e2e_leaves_opt_in_cases_to_separate_lanes(self):
        startup = next(step['run'] for step in JOBS['e2e']['steps'] if step.get('name') == 'Run E2E startup tests')
        command = shlex.split(startup)
        self.assertEqual(command[command.index('-m') + 1], 'not local_agent and not p0_image')

        for module in (
            'test_artifact_mixed_acceptance.py',
            'test_artifact_lifecycle_soak.py',
            'test_artifact_persistence.py',
        ):
            with self.subTest(module=module):
                self.assertIn(f'--ignore=tests/e2e/{module}', command)
        self.assertIn('python tools/verify_junit.py e2e-results.xml', startup)

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

    def test_pr_api_contracts_use_core_selection_and_skip_daily_matrix(self):
        flags = ('CORE', 'CORE_FULL', 'SDK', 'COMPATIBILITY', 'PERSISTENCE', 'PERMISSIONS', 'BOX', 'FRONTEND')
        cases = [
            ('pull_request', ['src/langbot/pkg/api/http/controller/groups/skills.py'], {'CORE'}, True),
            ('pull_request', ['tools/regression/regression_api_resources.py'], set(flags), True),
            ('pull_request', [], set(flags), True),
            ('pull_request', ['docs/index.mdx'], set(), False),
            ('schedule', [], set(flags), False),
            ('workflow_dispatch', [], set(flags), False),
        ]
        for event, paths, selected, expected in cases:
            with self.subTest(event=event, paths=paths), tempfile.NamedTemporaryFile() as output:
                subprocess.run(
                    [sys.executable, 'tools/ci_core_tests.py', 'plan'],
                    cwd=ROOT,
                    env={
                        **os.environ,
                        **{flag: json.dumps(flag in selected) for flag in flags},
                        'CHANGED_PATHS': json.dumps(paths),
                        'GITHUB_EVENT_NAME': event,
                        'GITHUB_OUTPUT': output.name,
                    },
                    check=True,
                    capture_output=True,
                )
                results = dict(line.split('=', 1) for line in Path(output.name).read_text().splitlines())
                self.assertEqual(json.loads(results['selection'])['api-contracts'], expected)

    def test_pr_and_daily_use_the_same_api_command_with_different_modes(self):
        daily_jobs = yaml.safe_load((ROOT / '.github/workflows/daily-endurance.yml').read_text())['jobs']
        pr = JOBS['api-contracts']
        self.assertEqual(pr['needs'], 'plan')
        self.assertIn("fromJSON(needs.plan.outputs.selection)['api-contracts']", pr['if'])
        pr_step = pr['steps'][-1]
        daily_step = daily_jobs['api-contracts']['steps'][-1]
        self.assertEqual(pr_step['uses'], daily_step['uses'])
        action = yaml.safe_load((ROOT / pr_step['uses'] / 'action.yml').read_text())
        command = next(step['run'] for step in action['runs']['steps'] if step.get('id') == 'execute')
        for caller, expected in ((pr_step, ['--api-fixed-only']), (daily_step, ['--api-seed', '1234'])):
            mode = caller.get('with', {}).get('fixed-only', action['inputs']['fixed-only']['default'])
            with self.subTest(mode=mode):
                result = subprocess.run(
                    ['bash', '-eo', 'pipefail', '-c', 'uv() { printf \'%s\\n\' "$@"; }\n' + command],
                    env={**os.environ, 'API_FIXED_ONLY': mode, 'GITHUB_RUN_ID': '1234'},
                    check=True,
                    capture_output=True,
                    text=True,
                )
                args = result.stdout.splitlines()
                suite = args.index('--suite')
                self.assertIn('tools.entrypoints.regression_ci', args)
                self.assertEqual(args[suite + 1 : args.index('--lbctl')], ['api', *expected])

    def test_summary_gate_matches_selected_jobs_and_fails_closed(self):
        command = next(
            step['run'] for step in JOBS['coverage']['steps'] if step.get('name') == 'Verify required test jobs'
        )
        jobs = set(JOBS['coverage']['needs']) - {'plan'}
        selection = {job: job in ('test', 'integration', 'api-contracts') for job in jobs}
        cases = [(None, 'success', True)]
        cases.extend(
            (job, status, False)
            for job in ('plan', 'test', 'api-contracts')
            for status in ('failure', 'skipped', 'cancelled')
        )
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
