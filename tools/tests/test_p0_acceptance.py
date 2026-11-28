import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml

from scripts.p0_acceptance_scope import select


class TestP0Scope(unittest.TestCase):
    def test_required_smoke_reports_a_failure_instead_of_skipping(self):
        workflow = yaml.safe_load(
            (Path(__file__).resolve().parents[2] / '.github/workflows/core-smoke.yml').read_text()
        )
        jobs = workflow['jobs']
        self.assertNotIn('needs', jobs['smoke'])
        verdict = jobs['verdict']
        self.assertEqual(verdict['name'], 'Core smoke (60s)')
        self.assertEqual(set(verdict['needs']), {'p0', 'smoke'})
        self.assertEqual(verdict['if'], 'always()')
        gate = verdict['steps'][0]
        self.assertEqual(gate['env']['P0_RESULT'], '${{ needs.p0.result }}')
        self.assertEqual(gate['env']['SMOKE_RESULT'], '${{ needs.smoke.result }}')
        for key in gate['env']:
            for state in ('success', 'failure', 'cancelled', 'skipped', ''):
                with self.subTest(job=key, state=state):
                    env = dict.fromkeys(gate['env'], 'success')
                    env[key] = state
                    result = subprocess.run(['bash', '-c', gate['run']], env=env)
                    self.assertEqual(result.returncode == 0, state == 'success')

    def test_backend_changes_never_escape_acceptance(self):
        for path in (
            'src/langbot/pkg/unknown/new.py',
            'sdk/src/langbot_plugin/box/runtime.py',
            '.github/workflows/persistence-acceptance.yml',
            'uv.lock',
            'main.py',
            'pytest.ini',
            'tests/conftest.py',
        ):
            with self.subTest(path=path):
                self.assertEqual(select([path]), dict(persistence=True, permissions=True, image=True))

    def test_existing_consumer_paths_select_their_real_boundaries(self):
        self.assertEqual(
            select(['src/langbot/pkg/storage/content.py']), dict(persistence=True, permissions=True, image=True)
        )
        self.assertEqual(
            select(['src/langbot/pkg/api/application/plugin_permissions.py']),
            dict(persistence=True, permissions=True, image=True),
        )
        self.assertEqual(
            select(['tests/e2e/test_image_upgrade.py']), dict(persistence=True, permissions=True, image=True)
        )
        self.assertEqual(
            select(['docs/en/develop/dev-config.mdx', 'web/app/root.tsx']),
            dict(persistence=False, permissions=False, image=False),
        )

    def test_rename_to_docs_keeps_the_backend_source(self):
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory:
            base_dir = Path(directory)
            repo = base_dir / 'repo'
            repo.mkdir()

            def git(*args):
                return subprocess.check_output(
                    [
                        'git',
                        '-c',
                        'user.name=P0 Test',
                        '-c',
                        'user.email=p0@example.invalid',
                        '-c',
                        'diff.renames=true',
                        *args,
                    ],
                    cwd=repo,
                    text=True,
                ).strip()

            git('init', '-q')
            source = repo / 'src/langbot/pkg/discover/module.py'
            source.parent.mkdir(parents=True)
            source.write_text('def discover():\n    return 1\n')
            git('add', '.')
            git('commit', '-qm', 'base')
            base = git('rev-parse', 'HEAD')

            target = repo / 'docs/en/module.mdx'
            target.parent.mkdir(parents=True)
            git('mv', str(source), str(target))
            git('commit', '-qm', 'move backend out of src')
            output = repo / 'changes'
            subprocess.run(
                [sys.executable, str(root / 'scripts/p0_acceptance_scope.py')],
                cwd=repo,
                env={
                    **os.environ,
                    'BASE_SHA': base,
                    'HEAD_SHA': git('rev-parse', 'HEAD'),
                    'GITHUB_OUTPUT': str(output),
                },
                capture_output=True,
                check=True,
            )
            self.assertEqual(
                set(output.read_text().splitlines()),
                {'persistence=true', 'permissions=true', 'image=true'},
            )

    def test_p0_verdict_requires_explicit_booleans_and_expected_results(self):
        path = Path(__file__).resolve().parents[2] / '.github/workflows/p0-acceptance.yml'
        verdict = yaml.safe_load(path.read_text())['jobs']['verdict']['steps'][0]['run']
        lanes = ('persistence', 'permissions', 'image')
        cases = [
            ({}, {}, True),
            ({'image': 'true'}, {'image': 'success'}, True),
            ({'image': 'true'}, {'image': 'failure'}, False),
            ({'image': 'true'}, {'image': 'cancelled'}, False),
            ({'image': 'true'}, {}, False),
            ({'image': ''}, {}, False),
            ({'image': 'FALSE'}, {}, False),
            ({'image': False}, {}, False),
            ({'image': None}, {}, False),
        ]
        for overrides, statuses, expected in cases:
            with self.subTest(outputs=overrides, statuses=statuses):
                outputs = dict.fromkeys(lanes, 'false') | overrides
                state = {
                    'changes': {'result': 'success', 'outputs': outputs},
                    **{name: {'result': statuses.get(name, 'skipped')} for name in lanes},
                }
                if outputs['image'] is None:
                    del outputs['image']
                result = subprocess.run(
                    ['bash', '-e', '-c', verdict],
                    env={**os.environ, 'NEEDS': json.dumps(state)},
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode == 0, expected, result.stderr)

    def test_synthetic_pr_merge_ignores_stale_base_commits_on_target_branch(self):
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory:
            base_dir = Path(directory)
            repo = base_dir / 'repo'
            repo.mkdir()

            def git(*args):
                return subprocess.check_output(
                    [
                        'git',
                        '-c',
                        'user.name=P0 Test',
                        '-c',
                        'user.email=p0@example.invalid',
                        *args,
                    ],
                    cwd=repo,
                    text=True,
                ).strip()

            git('init', '-q')
            git('commit', '--allow-empty', '-qm', 'old base')
            old_base = git('rev-parse', 'HEAD')

            git('checkout', '-qb', 'pr-branch', old_base)
            doc = repo / 'docs/en/guide.mdx'
            doc.parent.mkdir(parents=True)
            doc.write_text('# guide\n')
            git('add', '.')
            git('commit', '-qm', 'docs only')
            pr_head = git('rev-parse', 'HEAD')

            git('checkout', '-qb', 'target-branch', old_base)
            src = repo / 'src/langbot/pkg/core/app.py'
            src.parent.mkdir(parents=True)
            src.write_text('APP = 1\n')
            git('add', '.')
            git('commit', '-qm', 'unrelated target commit')
            git('merge', '--no-ff', '-m', 'Merge PR into current target', pr_head)
            merge_head = git('rev-parse', 'HEAD')

            output = base_dir / 'changes'
            subprocess.run(
                [sys.executable, str(root / 'scripts/p0_acceptance_scope.py')],
                cwd=repo,
                env={
                    **os.environ,
                    'EVENT_NAME': 'pull_request',
                    'BASE_SHA': old_base,
                    'HEAD_SHA': merge_head,
                    'PR_HEAD_SHA': pr_head,
                    'GITHUB_OUTPUT': str(output),
                },
                capture_output=True,
                check=True,
            )
            self.assertEqual(
                set(output.read_text().splitlines()),
                {'persistence=false', 'permissions=false', 'image=false'},
            )

            # Target branch force-push: BASE_SHA is not an ancestor of p1, so
            # P0 falls back to BASE_SHA..HEAD instead of narrowing.
            git('checkout', '--orphan', 'rewritten-target')
            git('rm', '-rfq', '.')
            dockerfile = repo / 'Dockerfile'
            dockerfile.write_text('FROM scratch\n')
            git('add', '.')
            git('commit', '-qm', 'rewritten base')
            rewritten_base = git('rev-parse', 'HEAD')
            git('checkout', '-q', 'target-branch')

            output.unlink()
            subprocess.run(
                [sys.executable, str(root / 'scripts/p0_acceptance_scope.py')],
                cwd=repo,
                env={
                    **os.environ,
                    'EVENT_NAME': 'pull_request',
                    'BASE_SHA': rewritten_base,
                    'HEAD_SHA': merge_head,
                    'PR_HEAD_SHA': pr_head,
                    'GITHUB_OUTPUT': str(output),
                },
                capture_output=True,
                check=True,
            )
            self.assertEqual(
                set(output.read_text().splitlines()),
                {'persistence=true', 'permissions=true', 'image=true'},
            )

            # Shallow clone / unavailable base commit fails open to all P0 suites.
            shallow = base_dir / 'shallow'
            subprocess.check_output(['git', 'clone', '--depth', '1', f'file://{repo}', str(shallow)], text=True)
            shallow_output = base_dir / 'shallow-changes'
            subprocess.run(
                [sys.executable, str(root / 'scripts/p0_acceptance_scope.py')],
                cwd=shallow,
                env={
                    **os.environ,
                    'EVENT_NAME': 'pull_request',
                    'BASE_SHA': old_base,
                    'HEAD_SHA': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=shallow, text=True).strip(),
                    'PR_HEAD_SHA': pr_head,
                    'GITHUB_OUTPUT': str(shallow_output),
                },
                capture_output=True,
                check=True,
            )
            self.assertEqual(
                set(shallow_output.read_text().splitlines()),
                {'persistence=true', 'permissions=true', 'image=true'},
            )
