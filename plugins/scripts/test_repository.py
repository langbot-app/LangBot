from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import yaml

from check_catalog import ROOT, check_catalog
from package_plugin import package_plugin

CORE = ROOT.parent
spec = importlib.util.spec_from_file_location('core_artifacts', CORE / 'scripts/check_core_artifacts.py')
core_artifacts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core_artifacts)


def workflow(name):
    return yaml.safe_load((CORE / '.github/workflows' / name).read_text())


class RepositoryTests(unittest.TestCase):
    def test_imported_debug_configuration_is_not_lost(self):
        relative = 'misc/AgenticRAG/.vscode/launch.json'
        self.assertTrue((ROOT / relative).is_file())
        self.assertIn('!misc/AgenticRAG/.vscode/', (ROOT / '.gitignore').read_text())

    def test_release_zip_excludes_sources_and_packages(self):
        data = workflow('build-release-artifacts.yaml')
        steps = data['jobs']['build-artifacts']['steps']
        script = next(step['run'] for step in steps if step.get('name') == 'Upload To Release')
        command = next(line for line in script.splitlines() if line.strip().startswith('zip -r '))
        command = command.replace('${{ steps.check_version.outputs.version }}', 'test')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            (source / 'plugins/misc/HelloPlugin').mkdir(parents=True)
            (source / 'plugins/misc/HelloPlugin/main.py').write_text('plugin')
            (source / 'unexpected.lbpkg').write_text('package')
            (source / 'main.py').write_text('core')
            subprocess.run(
                ['bash', '-c', command],
                cwd=source,
                env={**os.environ, 'RUNNER_TEMP': directory},
                check=True,
                capture_output=True,
            )
            artifact = root / 'langbot-test-all.zip'
            core_artifacts.check_artifact(artifact)
            with zipfile.ZipFile(artifact) as archive:
                self.assertIn('main.py', archive.namelist())

    def test_fnos_real_staging_command_excludes_sources_and_packages(self):
        script = (CORE / 'packaging/fnos/build.sh').read_text()
        command = 'rsync -a ' + script.split('rsync -a ', 1)[1].split('\n\n', 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            destination = root / 'fnos'
            (source / 'plugins/Runner/LocalAgent').mkdir(parents=True)
            (source / 'plugins/Runner/LocalAgent/main.py').write_text('plugin')
            (source / 'unexpected.lbpkg').write_text('package')
            (source / 'main.py').write_text('core')
            (destination / 'app/langbot').mkdir(parents=True)
            subprocess.run(
                ['bash', '-c', command],
                cwd=source,
                env={**os.environ, 'FPK_DIR': str(destination)},
                check=True,
                capture_output=True,
            )
            core_artifacts.check_artifact(destination / 'app/langbot')
            self.assertTrue((destination / 'app/langbot/main.py').is_file())

    def test_catalog_and_readme_cover_all_plugins(self):
        catalog = check_catalog()
        self.assertEqual(json.loads((ROOT / 'catalog.json').read_text()), catalog)
        readme = (ROOT / 'README.md').read_text()
        for entry in catalog:
            self.assertIn(f'({entry["path"]}/README.md)', readme)

    def test_original_identities_are_preserved(self):
        imported = json.loads((ROOT / 'SOURCE.json').read_text())
        current = {entry['id']: entry['path'] for entry in check_catalog()}
        for identity, relative in imported['plugins'].items():
            self.assertEqual(current[identity], relative)

    def test_plugin_workflows_do_not_release_core_or_checkout_old_repo(self):
        for path in (CORE / '.github/workflows').glob('plugins-*.yml'):
            text = path.read_text()
            data = workflow(path.name)
            events = data.get('on', data.get(True))
            self.assertNotIn('release', events)
            self.assertNotIn('langbot-app/langbot-plugins', text)
            self.assertNotIn('secrets.', text)
            for event in ('push', 'pull_request'):
                if event in events:
                    self.assertTrue(
                        all(
                            pattern.startswith(('plugins/', '.github/workflows/plugins-'))
                            for pattern in events[event]['paths']
                        )
                    )
            for job in data['jobs'].values():
                default = job.get('defaults', {}).get('run', {}).get('working-directory', '.')
                self.assertTrue((CORE / default).is_dir())
                for step in job['steps']:
                    directory = step.get('working-directory', default)
                    self.assertTrue((CORE / directory).is_dir(), directory)
                    self.assertNotIn('uv publish', step.get('run', ''))

    def test_every_plugin_category_has_independent_ci(self):
        for name in ('runner', 'local-agent', 'langrag', 'misc', 'knowledgeengine-shared'):
            data = workflow(f'plugins-{name}-tests.yml')
            self.assertIn('workflow_dispatch', data.get('on', data.get(True)))
            self.assertEqual(data['permissions'], {'contents': 'read'})

    def test_core_release_jobs_reject_plugin_tags(self):
        for filename, job in (
            ('build-release-artifacts.yaml', 'build-artifacts'),
            ('build-fnos-fpk.yaml', 'build-fnos-fpk'),
            ('build-docker-image.yml', 'publish-docker-image'),
            ('publish-to-pypi.yml', 'build-and-publish'),
            ('discord-release.yml', 'announce'),
        ):
            condition = workflow(filename)['jobs'][job]['if']
            self.assertIn("!startsWith(github.event.release.tag_name, 'plugins/')", condition)

    def test_core_consumer_hashes_match_in_tree_sources(self):
        lock = json.loads((CORE / 'tests/fixtures/legacy_plugin_identity_sources.json').read_text())
        self.assertEqual(lock['root'], 'plugins')
        self.assertEqual(lock['repository'], 'langbot-app/LangBot')
        for key in ('files', 'local_agent_files'):
            for relative, expected in lock[key].items():
                self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), expected, relative)

    def test_packaging_exclusions_are_present(self):
        self.assertIn('prune plugins', (CORE / 'MANIFEST.in').read_text())
        self.assertIn('plugins/', (CORE / '.dockerignore').read_text().splitlines())
        self.assertIn('/plugins export-ignore', (CORE / '.gitattributes').read_text())
        self.assertIn("--exclude='/plugins/'", (CORE / 'packaging/fnos/build.sh').read_text())
        release = (CORE / '.github/workflows/build-release-artifacts.yaml').read_text()
        self.assertIn('!plugins/**', release)
        self.assertIn("-x 'plugins/*' '*.lbpkg'", release)

    def test_core_artifact_checker_rejects_plugin_content(self):
        with tempfile.TemporaryDirectory() as directory:
            for member in (
                'plugins/misc/HelloPlugin/main.py',
                'langbot-1/plugins/catalog.json',
                'nested/HelloPlugin.lbpkg',
            ):
                artifact = Path(directory) / 'core.zip'
                with zipfile.ZipFile(artifact, 'w') as archive:
                    archive.writestr(member, 'unexpected')
                with self.assertRaises(ValueError):
                    core_artifacts.check_artifact(artifact)

    def test_core_artifact_checker_accepts_host_plugin_bridge(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / 'core.zip'
            with zipfile.ZipFile(artifact, 'w') as archive:
                archive.writestr('langbot/pkg/plugin/connector.py', 'host')
            core_artifacts.check_artifact(artifact)

    def test_package_selection_rejects_traversal_and_root(self):
        with tempfile.TemporaryDirectory() as directory, patch('package_plugin.subprocess.run') as build:
            for selected in ('..', '.', 'Runner', 'Runner/LocalAgent/../LocalAgent', '/tmp/plugin'):
                with self.assertRaises(ValueError):
                    package_plugin(selected, Path(directory))
            build.assert_not_called()

    def test_no_plugin_build_output_inside_sources(self):
        with patch('package_plugin.subprocess.run') as build:
            with self.assertRaises(ValueError):
                package_plugin('Runner/LocalAgent', ROOT / 'dist')
            build.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
