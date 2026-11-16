import unittest

from scripts.p0_acceptance_scope import select


class TestP0Scope(unittest.TestCase):
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
