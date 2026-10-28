"""Exercise plugin selection, artifact integrity and installation readback."""

from collections import Counter
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

import yaml

import regression_plugins as plugins


def archive(plugin_id, version='1.2.3'):
    author, name = plugin_id.split('/')
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as package:
        package.writestr(
            zipfile.ZipInfo('manifest.yaml'),
            f'kind: Plugin\nmetadata:\n  author: {author}\n  name: {name}\n  version: {version}\n',
        )
        package.writestr(zipfile.ZipInfo('main.py'), '# Published fixture\n')
    return output.getvalue()


class SourcePluginsTests(unittest.TestCase):
    def test_selected_sources_build_in_isolation_and_record_actual_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / 'sources', root / 'packages'
            paths = (*plugins.PLUGIN_PATHS, 'misc/ExtraPlugin')
            for path in paths:
                folder = source / path
                folder.mkdir(parents=True)
                with zipfile.ZipFile(io.BytesIO(archive('test/' + folder.name))) as package:
                    package.extractall(folder)

            def build(args, *, cwd, **kwargs):
                self.assertEqual(args[1:5], ['-m', 'langbot_plugin.cli.__init__', 'build', '--output'])
                self.assertFalse(cwd.is_relative_to(source))
                metadata = yaml.safe_load((cwd / 'manifest.yaml').read_text())['metadata']
                (cwd / 'generated.html').write_text('Generated only in the isolated build copy')
                filename = f'{metadata["author"]}-{metadata["name"]}-{metadata["version"]}.lbpkg'
                (Path(args[-1]) / filename).write_bytes(archive('test/' + metadata['name']))

            with patch.object(plugins.subprocess, 'run', side_effect=build):
                manifest = plugins.prepare_source_plugins(output, source, ['misc/ExtraPlugin'])
            self.assertEqual(manifest['selection'], 'source')
            self.assertEqual([entry['source'] for entry in manifest['plugins']], list(paths))
            for entry in manifest['plugins']:
                self.assertEqual(
                    entry['sha256'], plugins.hashlib.sha256((output / entry['archive']).read_bytes()).hexdigest()
                )
                self.assertFalse((source / entry['source'] / 'generated.html').exists())

    def test_invalid_or_duplicate_selection_is_rejected_before_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for path in plugins.PLUGIN_PATHS:
                (root / path).mkdir(parents=True)
                (root / path / 'manifest.yaml').write_text('kind: Plugin')
            (root / 'misc/escape').symlink_to(root.parent, target_is_directory=True)
            for selected in (['../outside'], ['/tmp/plugin'], ['misc/escape'], [plugins.PLUGIN_PATHS[0]]):
                with self.subTest(selected=selected), patch.object(plugins.subprocess, 'run') as build:
                    with self.assertRaises(ValueError):
                        plugins.prepare_source_plugins(root / 'output', root, selected)
                    build.assert_not_called()

    def test_wrong_built_identity_fails_without_installation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for path in plugins.PLUGIN_PATHS:
                folder = root / path
                folder.mkdir(parents=True)
                with zipfile.ZipFile(io.BytesIO(archive('test/' + folder.name))) as package:
                    package.extractall(folder)

            def build(args, **kwargs):
                (Path(args[-1]) / 'test-LocalAgent-1.2.3.lbpkg').write_bytes(archive('test/WrongPlugin'))

            with patch.object(plugins.subprocess, 'run', side_effect=build):
                with self.assertRaisesRegex(ValueError, 'identity/version differs'):
                    plugins.prepare_source_plugins(root / 'output', root)


class PublishedPluginsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Marketplace(BaseHTTPRequestHandler):
            def do_GET(self):
                cls.requests.append(self.path)
                status, body = cls.responses.get(self.path, (404, b'missing published release'))
                self.send_response(status)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Marketplace)
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.marketplace = patch.object(plugins, 'MARKETPLACE', f'http://127.0.0.1:{self.server.server_port}')
        self.marketplace.start()
        self.addCleanup(self.marketplace.stop)
        type(self).requests = []
        type(self).responses = {}
        for plugin_id in plugins.PLUGIN_IDS:
            author, name = plugin_id.split('/')
            data = {
                'code': 0,
                'data': {
                    'plugin': {
                        'plugin_id': plugin_id,
                        'author': author,
                        'name': name,
                        'latest_version': '1.2.3',
                        'status': 'live',
                    }
                },
            }
            self.responses[f'/api/v1/marketplace/plugins/{plugin_id}'] = (200, json.dumps(data).encode())
            self.responses[f'/api/v1/marketplace/plugins/download/{plugin_id}/1.2.3'] = (200, archive(plugin_id))

    def test_latest_resolved_once_and_replay_uses_same_published_bytes(self):
        directory = self.root / 'latest'
        manifest = plugins.prepare_published_plugins(directory)
        self.assertEqual(Counter(self.requests), {path: 1 for path in self.responses})
        installed = []

        def call(args):
            if args[:3] == ['plugin', 'install', 'local']:
                source = Path(args[4])
                self.assertEqual(source.read_bytes(), archive(plugins.PLUGIN_IDS[len(installed)]))
                author, name = plugins.PLUGIN_IDS[len(installed)].split('/')
                installed.append(
                    {'author': author, 'name': name, 'version': '1.2.3', 'enabled': True, 'status': 'initialized'}
                )
                return {}
            self.assertEqual(args, ['plugin', 'list'])
            return {'plugins': installed}

        plugins.install_plugins(call, directory, manifest)
        recorded = json.loads((directory / 'manifest.json').read_text())
        self.assertTrue(all(entry['installed'][0]['status'] == 'initialized' for entry in recorded['plugins']))
        self.requests.clear()
        replay = plugins.prepare_published_plugins(self.root / 'replay', directory / 'manifest.json')
        self.assertEqual(
            [entry['sha256'] for entry in replay['plugins']], [entry['sha256'] for entry in manifest['plugins']]
        )
        self.assertEqual(len(self.requests), 3)
        self.assertTrue(all('/download/' in path for path in self.requests))

    def test_bad_metadata_and_unpublished_versions_fail_without_download(self):
        url = '/api/v1/marketplace/plugins/langbot-team/LocalAgent'
        valid = json.loads(self.responses[url][1])
        invalid = [[], {'code': 0, 'data': []}, {'code': 1, 'data': valid['data']}]
        for field, value in [
            ('latest_version', ''),
            ('latest_version', '../bad'),
            ('status', 'draft'),
            ('name', 'Other'),
        ]:
            data = copy.deepcopy(valid)
            data['data']['plugin'][field] = value
            invalid.append(data)
        for index, payload in enumerate(invalid):
            with self.subTest(payload=payload):
                self.requests.clear()
                self.responses[url] = (200, json.dumps(payload).encode())
                with self.assertRaises(ValueError):
                    plugins.prepare_published_plugins(self.root / str(index))
                self.assertEqual(self.requests, [url])

    def test_missing_or_wrong_release_does_not_fall_back(self):
        url = '/api/v1/marketplace/plugins/download/langbot-team/LocalAgent/1.2.3'
        self.responses[url] = (404, b'missing')
        with self.assertRaisesRegex(RuntimeError, 'HTTP Error 404'):
            plugins.prepare_published_plugins(self.root / 'missing')
        self.responses[url] = (200, archive('langbot-team/LocalAgent', '0.0.1'))
        with self.assertRaisesRegex(ValueError, 'identity/version differs'):
            plugins.prepare_published_plugins(self.root / 'wrong')

    def test_replay_rejects_changed_packages_and_untrusted_identity(self):
        directory = self.root / 'latest'
        manifest = plugins.prepare_published_plugins(directory)
        replay = directory / 'manifest.json'
        url = '/api/v1/marketplace/plugins/download/langbot-team/LocalAgent/1.2.3'
        self.responses[url] = (200, b'different package')
        with self.assertRaisesRegex(ValueError, 'sha256 changed'):
            plugins.prepare_published_plugins(self.root / 'changed', replay)
        for change in ('identity', 'duplicate', 'origin', 'hash'):
            invalid = copy.deepcopy(manifest)
            if change == 'identity':
                invalid['plugins'][0]['id'] = 'untrusted/Other'
            elif change == 'duplicate':
                invalid['plugins'][1] = invalid['plugins'][0]
            elif change == 'origin':
                invalid['marketplace'] = 'https://untrusted.example'
            else:
                del invalid['plugins'][0]['sha256']
            replay.write_text(json.dumps(invalid))
            with self.subTest(change=change), self.assertRaises(ValueError):
                plugins.prepare_published_plugins(self.root / change, replay)

    def test_readback_records_actual_failed_version_and_stops_installing(self):
        directory = self.root / 'latest'
        manifest = plugins.prepare_published_plugins(directory)
        calls = []

        def call(args):
            calls.append(args)
            return {
                'plugins': [
                    {
                        'author': 'langbot-team',
                        'name': 'LocalAgent',
                        'version': '0.0.1',
                        'enabled': True,
                        'status': 'initialized',
                    }
                ]
            }

        with self.assertRaisesRegex(RuntimeError, 'not ready at the selected version'):
            plugins.install_plugins(call, directory, manifest)
        self.assertEqual(len(calls), 2)
        recorded = json.loads((directory / 'manifest.json').read_text())
        self.assertEqual(recorded['plugins'][0]['installed'][0]['version'], '0.0.1')
        (directory / manifest['plugins'][0]['archive']).write_bytes(b'changed after download')
        with self.assertRaisesRegex(ValueError, 'changed before installation'):
            plugins.install_plugins(call, directory, manifest)
        self.assertEqual(len(calls), 2)


if __name__ == '__main__':
    unittest.main()
