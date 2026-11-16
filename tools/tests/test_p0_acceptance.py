import unittest
from pathlib import Path
import subprocess

import yaml

from scripts.p0_acceptance_scope import select


class TestP0Scope(unittest.TestCase):
    def test_required_smoke_reports_a_failure_instead_of_skipping(self):
        workflow = yaml.safe_load(
            (Path(__file__).resolve().parents[2] / '.github/workflows/core-smoke.yml').read_text()
        )
        smoke = workflow['jobs']['smoke']
        self.assertEqual(smoke['needs'], 'p0')
        self.assertEqual(smoke['if'], 'always()')
        gate = smoke['steps'][0]
        self.assertEqual(gate['env']['P0_RESULT'], '${{ needs.p0.result }}')
        for state in ('success', 'failure', 'cancelled', 'skipped', ''):
            with self.subTest(state=state):
                result = subprocess.run(['bash', '-c', gate['run']], env={'P0_RESULT': state})
                self.assertEqual(result.returncode == 0, state == 'success')

    def test_backend_changes_never_escape_acceptance(self):
        for path in (
            'src/langbot/pkg/unknown/new.py',
            'sdk/src/langbot_plugin/box/runtime.py',
            '.github/workflows/persistence-acceptance.yml',
            'uv.lock',
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
