"""Exercise the change selector against real Git commits and CI evidence policies."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.verify_junit import verify_report


ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER = ROOT / '.github/actions/classify-test-changes/classify.py'


class ChangeSelectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / 'repo'
        self.root.mkdir()
        self.output = self.root.parent / 'outputs'
        self.git('init', '-q')
        self.git('config', 'user.name', 'CI')
        self.git('config', 'user.email', 'ci@example.invalid')
        self.git('commit', '--allow-empty', '-qm', 'base')
        self.base = self.git('rev-parse', 'HEAD').strip()

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, text=True)

    def write(self, path):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('test\n')

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '-qm', 'change')

    def run_selector(self, event='pull_request', base=None):
        self.output.unlink(missing_ok=True)
        subprocess.run(
            [sys.executable, str(CLASSIFIER)],
            cwd=self.root,
            env={
                **os.environ,
                'EVENT_NAME': event,
                'BASE_SHA': self.base if base is None else base,
                'GITHUB_OUTPUT': str(self.output),
                'GITHUB_STEP_SUMMARY': '',
            },
            check=True,
        )
        outputs = dict(line.split('=', 1) for line in self.output.read_text().splitlines())
        paths = json.loads(outputs.pop('changed_paths'))
        return {name for name, value in outputs.items() if value == 'true'}, paths

    def test_representative_changes_select_and_omit_expected_boundaries(self):
        cases = [
            ('docs/en/dev.mdx', {'docs'}, {'core', 'frontend', 'sdk', 'packaging', 'persistence'}),
            ('web/src/components/widget.tsx', {'frontend'}, {'core', 'sdk', 'persistence', 'packaging'}),
            ('src/langbot/pkg/i18n/messages.py', {'core'}, {'core_full', 'frontend', 'sdk', 'persistence'}),
            (
                'sdk/src/langbot_plugin/runtime/file.py',
                {'sdk', 'compatibility', 'box', 'core_full', 'plugins'},
                {'docs'},
            ),
            (
                'src/langbot/pkg/persistence/alembic/versions/new.py',
                {'permissions', 'persistence', 'core'},
                {'compatibility', 'frontend'},
            ),
            (
                '.github/workflows/run-tests.yml',
                {
                    'workflows',
                    'core_full',
                    'compatibility',
                    'persistence',
                    'permissions',
                    'frontend',
                    'docs',
                    'box',
                    'packaging',
                },
                set(),
            ),
            ('uv.lock', {'core_full', 'compatibility', 'persistence', 'frontend', 'box', 'packaging'}, {'docs'}),
            ('src/langbot/pkg/api/application/operation.py', {'sdk', 'permissions', 'compiled_cli'}, {'packaging'}),
            ('src/langbot/pkg/vector/seekdb.py', {'core', 'seekdb'}, {'box', 'packaging'}),
        ]
        for path, expected, excluded in cases:
            with self.subTest(path=path):
                self.git('reset', '--hard', self.base)
                self.write(path)
                self.commit()
                lanes, changed = self.run_selector()
                self.assertEqual(changed, [path])
                self.assertTrue(expected <= lanes, expected - lanes)
                self.assertFalse(excluded & lanes, excluded & lanes)

    def test_large_diff_keeps_tail_and_checks_both_sides_of_rename(self):
        original = 'src/langbot/pkg/persistence/old.py'
        self.write(original)
        self.commit()
        self.base = self.git('rev-parse', 'HEAD').strip()
        docs = {f'docs/en/{index:03d}.md' for index in range(320)}
        for path in sorted(docs):
            self.write(path)
        self.git('mv', original, 'docs/en/renamed.md')
        self.commit()
        lanes, changed = self.run_selector()
        self.assertCountEqual(changed, docs | {original, 'docs/en/renamed.md'})
        self.assertEqual(lanes, {'core', 'docs', 'permissions', 'persistence'})

    def test_production_images_only_follow_image_inputs(self):
        for path, expected in (
            ('plugins/Runner/README.md', False),
            ('plugins/Runner/LocalAgent/pkg/context_pipeline.py', False),
            ('tools/README.md', False),
            ('tools/entrypoints/regression_traffic.py', False),
            ('.github/workflows/run-tests.yml', False),
            ('src/langbot/pkg/platform/sources/matrix.py', False),
            ('Dockerfile', True),
            ('.dockerignore', True),
            ('uv.lock', True),
            ('sdk/src/langbot_plugin/box/client.py', True),
            ('packaging/entrypoint.sh', True),
            ('.github/workflows/core-packaging.yml', True),
            ('.github/actions/classify-test-changes/classify.py', True),
            ('web/pnpm-lock.yaml', True),
        ):
            with self.subTest(path=path):
                self.git('reset', '--hard', self.base)
                self.write(path)
                self.commit()
                lanes, changed = self.run_selector()
                self.assertEqual(changed, [path])
                self.assertEqual('production_image' in lanes, expected)
                if path.startswith(('plugins/', 'tools/')):
                    self.assertIn('packaging', lanes)

    def test_missing_base_fails_open_and_full_entries_do_not_use_event_diff(self):
        missing, paths = self.run_selector(base='f' * 40)
        self.assertEqual(paths, [])
        self.assertIn('compatibility', missing)
        self.assertIn('workflows', missing)
        self.assertEqual(self.run_selector('schedule')[0], missing)
        self.assertEqual(self.run_selector('workflow_dispatch')[0], missing)


class MandatoryEvidenceTests(unittest.TestCase):
    def test_junit_requires_nonempty_success_and_rejects_a_skipped_or_failed_case(self):
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / 'report.xml'
            with self.assertRaises(FileNotFoundError):
                verify_report(report)
            for xml in (
                '<testsuites/>',
                '<broken',
                '<testcase name="x"><failure/></testcase>',
                '<testcase name="x"><error/></testcase>',
                '<testcase name="x"><skipped type="pytest.xfail"/></testcase>',
            ):
                with self.subTest(xml=xml):
                    report.write_text(xml)
                    with self.assertRaises((ValueError, SyntaxError)):
                        verify_report(report)
            report.write_text('<testsuite><testcase name="x"/></testsuite>')
            self.assertEqual(verify_report(report), 1)


if __name__ == '__main__':
    unittest.main()
