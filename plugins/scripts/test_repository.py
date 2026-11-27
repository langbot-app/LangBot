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

SDK_RUNTIME_FILES = (
    'sdk/pyproject.toml',
    'sdk/README.md',
    'sdk/LICENSE',
    'sdk/src/langbot_plugin/__init__.py',
    'sdk/src/langbot_plugin/box/client.py',
    'sdk/src/langbot_plugin/runtime/app.py',
    'sdk/src/langbot_plugin/assets/templates/.github/workflows/release.yml.example',
    'sdk/src/langbot_plugin/assets/templates/.vscode/launch.json.example',
    'sdk/src/langbot_plugin/assets/templates/.gitignore.example',
    'sdk/src/langbot_plugin/assets/templates/.env.example.example',
)
SDK_EXCLUDED_FILES = (
    'sdk/tests/test_example.py',
    'sdk/examples/example.py',
    'sdk/docs/internal.md',
    'sdk/scripts/helper.py',
    'sdk/local_e2e/test_example.py',
    'sdk/data/private.txt',
    'sdk/.venv/bin/python',
    'sdk/__pycache__/example.pyc',
    'sdk/.pytest_cache/state',
    'sdk/.mypy_cache/state',
    'sdk/.ruff_cache/state',
)


def write_sdk_fixture(root: Path) -> None:
    for relative in (*SDK_RUNTIME_FILES, *SDK_EXCLUDED_FILES):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'fixture: {relative}')


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
            write_sdk_fixture(source)
            subprocess.run(
                ['bash', '-c', command],
                cwd=source,
                env={**os.environ, 'RUNNER_TEMP': directory},
                check=True,
                capture_output=True,
            )
            artifact = root / 'langbot-test-all.zip'
            core_artifacts.check_artifact(artifact, source=True)
            with zipfile.ZipFile(artifact) as archive:
                self.assertIn('main.py', archive.namelist())
                for relative in SDK_RUNTIME_FILES:
                    self.assertEqual(archive.read(relative).decode(), f'fixture: {relative}')
                for relative in SDK_EXCLUDED_FILES:
                    self.assertNotIn(relative, archive.namelist())

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
            write_sdk_fixture(source)
            (destination / 'app/langbot').mkdir(parents=True)
            subprocess.run(
                ['bash', '-c', command],
                cwd=source,
                env={**os.environ, 'FPK_DIR': str(destination)},
                check=True,
                capture_output=True,
            )
            core_artifacts.check_artifact(destination / 'app/langbot', source=True)
            self.assertTrue((destination / 'app/langbot/main.py').is_file())
            for relative in SDK_RUNTIME_FILES:
                self.assertEqual((destination / 'app/langbot' / relative).read_text(), f'fixture: {relative}')
            for relative in SDK_EXCLUDED_FILES:
                self.assertFalse((destination / 'app/langbot' / relative).exists())

    def test_catalog_and_readme_cover_all_plugins(self):
        catalog = check_catalog()
        self.assertEqual(json.loads((ROOT / 'catalog.json').read_text()), catalog)
        readme = (ROOT / 'README.md').read_text()
        for entry in catalog:
            self.assertIn(f'({entry["path"]}/README.md)', readme)

    def test_pipeline_bridge_with_event_runner_remains_misc(self):
        entry = next(item for item in check_catalog() if item['id'] == 'langbot-team/HandoffBridge')
        self.assertEqual(entry['category'], 'misc')
        self.assertEqual(entry['path'], 'misc/HandoffBridge')
        manifest = yaml.safe_load((ROOT / entry['path'] / 'manifest.yaml').read_text())
        self.assertEqual(set(manifest['spec']['components']), {'EventListener', 'Runner'})

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
            # Released and candidate SDK plugin consumers need their actual
            # Core-side integration surface, not all unrelated Core modules.
            consumer_paths = {
                'plugins-runner-tests.yml': {
                    'src/langbot/pkg/agent/**',
                    'src/langbot/pkg/box/**',
                    'src/langbot/pkg/pipeline/**',
                    'src/langbot/pkg/storage/**',
                },
                'plugins-knowledgeengine-shared-tests.yml': {
                    'src/langbot/pkg/rag/**',
                    'src/langbot/pkg/vector/**',
                },
            }.get(path.name, set())
            if consumer_paths:
                consumer_paths |= {
                    'sdk/**',
                    'src/langbot/pkg/api/application/**',
                    'src/langbot/pkg/core/stages/**',
                    'src/langbot/pkg/entity/**',
                    'src/langbot/pkg/plugin/**',
                    'src/langbot/pkg/workspace/**',
                    'scripts/generate_plugin_workspace_api.py',
                    'pyproject.toml',
                    'uv.lock',
                }
                self.assertIn('pull_request', events, path.name)
            for event in ('push', 'pull_request'):
                if event in events:
                    paths = set(events[event]['paths'])
                    self.assertNotIn('src/langbot/**', paths, path.name)
                    self.assertTrue(
                        all(
                            pattern.startswith(('plugins/', '.github/workflows/plugins-')) or pattern in consumer_paths
                            for pattern in paths
                        ),
                        path.name,
                    )
                    self.assertTrue(consumer_paths <= paths, path.name)
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
        if lock.get('revision') == 'in-tree':
            for key in ('files', 'local_agent_files'):
                for relative in lock[key]:
                    self.assertTrue((ROOT / relative).is_file(), relative)
            return
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
