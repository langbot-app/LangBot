"""Exercise Job ownership and lifecycle with controlled CLI/Docker responses."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import yaml

from regression_job import Job, load_profile, main
from regression_scenarios import ExecutionWindow
from regression_suite import Suite
from test_regression_suite import FAKE_CLI, profile


class ControlledJob(Job):
    def __init__(self, manifest, suite, path, output, health, fail_install=False):
        super().__init__(manifest, suite, path, output)
        self.health = health
        self.fail_install = fail_install
        self.calls = []
        self.env['LBCTL_TEST_ROOT'] = str(output.parent)

    def command(self, args, timeout=900):
        self.calls.append(args)
        if args[: len(self.cli)] == self.cli:
            operation = args[len(self.cli) :]
            if operation[0] == 'install':
                self.deploy.mkdir()
                (self.deploy / 'data').mkdir()
                (self.deploy / 'compose.yaml').write_text('services: {}')
                (self.deploy / '.env').write_text(
                    'LANGBOT_PLUGIN_RUNTIME_CONTROL_TOKEN=' + 't' * 32 + '\nLANGBOT_BOX_ENABLED=true\n'
                )
                record = {
                    'deployment_id': 'owned-deployment',
                    'compose_project': 'test-project',
                    'compose_file': str(self.deploy / 'compose.yaml'),
                    'data_dir': str(self.deploy / 'data'),
                    'env_file': str(self.deploy / '.env'),
                    'endpoint': self.health,
                }
                (self.deploy / 'deployment.yaml').write_text(yaml.safe_dump(record))
                # Simulate a timeout/failed final probe with no returned record.
                return (
                    (1, json.dumps({'data': {}}), 'install failed')
                    if self.fail_install
                    else (0, json.dumps({'data': {'record': record}}), '')
                )
            if operation[0] == '--endpoint':
                return 0, json.dumps({'data': {'workspace_uuid': 'test-workspace'}}), ''
            if operation[0] == 'uninstall':
                shutil.rmtree(self.deploy / 'data')
            return 0, json.dumps({'data': {}}), ''
        if args[:2] == ['docker', 'ps']:
            if 'label=langbot.box=true' in args:
                return 0, '', ''
            return (
                0,
                '\n'.join(
                    f'id-{name} {name}'
                    for name in ('langbot', 'langbot_plugin_runtime', 'langbot_box', 'regression_mock')
                ),
                '',
            )
        if args[:2] == ['docker', 'inspect']:
            if '{{.State.Pid}}' in args:
                return 0, str(os.getpid()), ''
            return 0, json.dumps({'network': {'IPAddress': '127.0.0.1'}}), ''
        if args[:2] == ['docker', 'compose']:
            if 'logs' in args:
                return 0, self.redact(self.env.get('LANGBOT_QA_API_KEY', '') + '\n' + 't' * 32), ''
            return 0, '', ''
        raise AssertionError(args)

    @staticmethod
    def ready(url):
        pass

    def prepare(self):
        suite = super().prepare()
        # Real traffic driver and HTTP health probe; infrastructure calls are controlled above.
        suite.profile['observe'] = {'health': {'core': self.health}}
        return suite


class JobTests(unittest.TestCase):
    def test_published_resolution_failure_is_preparation_failure_without_deployment(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            job = ControlledJob({}, profile(), root / 'profile.json', root / 'run', 'unused')
            with patch('regression_job.prepare_published_plugins', side_effect=RuntimeError('release unavailable')):
                result = job.run()
            self.assertFalse(result['passed'])
            self.assertFalse(result['completed'])
            self.assertEqual(result['phase'], 'plugins')
            self.assertEqual(result['errors'], ['release unavailable'])
            self.assertEqual(job.calls, [])

    def test_job_defaults_to_published_plugins_and_keeps_explicit_profile_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            suite = profile()
            suite['plugins'] = [{'source': 'local', 'file': 'developer.zip'}]
            (root / 'suite.json').write_text(json.dumps(suite))
            path = root / 'job.json'
            manifest = {'version': 1, 'suite': 'suite.json', 'deployment': {'version': 'v4.11.0'}}
            path.write_text(json.dumps(manifest))
            self.assertEqual(load_profile(path)[1]['plugins'], [])
            manifest['plugin_mode'] = 'profile'
            path.write_text(json.dumps(manifest))
            self.assertEqual(load_profile(path)[1]['plugins'], suite['plugins'])
            manifest['plugin_manifest'] = 'previous/manifest.json'
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'requires published'):
                load_profile(path)

    def test_lifecycle_success_and_partial_install_recovery(self):
        class Health(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"code":0}')

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Health)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                cli = root / 'lbctl-test'
                cli.write_text(f'#!{sys.executable}\n' + FAKE_CLI)
                cli.chmod(0o700)
                manifest = {
                    'lbctl': str(cli),
                    'deployment': {'version': 'v4.11.0', 'port': 15351},
                    'plugin_mode': 'profile',
                }
                suite = profile()
                suite['coverage_suite'] = 'smoke'
                suite['resources'] = [{'id': 'chat', 'kind': 'pipeline', 'body': {'name': 'QA', 'config': {'ai': {}}}}]
                suite['cases'][0].update(args=['pipeline', 'run', '${chat}'], expect='TEST_OK')
                suite['phases'][0].update(duration_seconds=0.5, rps=4, workers=2)
                health = f'http://127.0.0.1:{server.server_port}'
                job = ControlledJob(manifest, suite, root / 'profile.json', root / 'success', health)
                result = job.run()
                self.assertTrue(result['passed'], result)
                self.assertTrue((job.output / 'suite/coverage.json').exists())
                self.assertEqual(result['phase'], 'cleaned')
                self.assertFalse((job.deploy / 'data').exists())
                self.assertFalse((job.private / 'api-key').exists())
                self.assertIn('--purge-data', job.calls[-1])
                self.assertNotIn('t' * 32, (job.output / 'services.log').read_text())

                job = ControlledJob(manifest, suite, root / 'profile.json', root / 'failed', health, fail_install=True)
                result = job.run()
                self.assertFalse(result['passed'])
                self.assertEqual(job.state['record']['deployment_id'], 'owned-deployment')
                self.assertTrue((job.deploy / 'data').exists())
                self.assertFalse(any('uninstall' in call for call in job.calls))
                with (
                    patch.object(sys, 'argv', ['regression_job.py', 'cleanup', '--output', str(job.output)]),
                    patch('regression_job.Job', return_value=job),
                ):
                    main()
                self.assertFalse((job.deploy / 'data').exists())
                self.assertEqual(job.state['phase'], 'cleaned')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_shared_finish_cleans_owned_resources_before_environment_teardown(self):
        for failure in ('prepare', 'finish-error', 'finish-raises'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                current = profile()
                current.pop('phases')
                current.update(
                    smoke={'ledger_db': 'unused.db'},
                    cleanup='always',
                    execution={'total_seconds': 1, 'drain_seconds': 0.1, 'cooldown_seconds': 0.01},
                )
                job = Job({'cleanup': 'always'}, current, root / 'profile.json', root / 'job')
                events, visible = [], ['owned']

                def prepare():
                    destination = job.output / 'suite'
                    destination.mkdir()
                    suite = job.suite = Suite(current, root / 'profile.json', destination)
                    suite.variables['workspace_uuid'] = 'workspace'
                    suite.owned = [{'kind': 'provider', 'uuid': 'owned'}]
                    suite.journal()

                    def call(args, body=None):
                        if args == ['whoami']:
                            return {'workspace_uuid': 'workspace'}
                        if args == ['provider', 'delete', 'owned', '--yes']:
                            events.append('delete-owned')
                            visible.remove('owned')
                            return {}
                        if args == ['provider', 'list']:
                            return {'providers': [{'uuid': item} for item in visible]}
                        raise AssertionError(args)

                    suite.call = call
                    suite.run = lambda: {'errors': [], 'phases': []}
                    suite.execution = ExecutionWindow(suite)
                    suite.execution.start()
                    if failure == 'prepare':
                        raise RuntimeError('prepare failed after creating resource')
                    finish = suite.finish

                    def failing_finish(summary):
                        if failure == 'finish-error':
                            suite.execution.errors.append('health failed during execution')
                        finish(summary)
                        if failure == 'finish-raises':
                            raise TypeError('finalization defect')

                    suite.finish = failing_finish
                    return suite

                with (
                    patch.object(job, 'prepare', side_effect=prepare),
                    patch.object(job, 'collect', side_effect=lambda: events.append('collect')),
                    patch.object(job, 'cleanup', side_effect=lambda: events.append('teardown')),
                    patch('regression_traffic.read_endpoint_snapshot', return_value={'http.ok': 1}),
                ):
                    result = job.run()
                self.assertFalse(result['passed'])
                self.assertFalse(result['suite']['passed'])
                self.assertEqual(result['suite']['outcome'], 'FAIL')
                self.assertFalse(job.suite.execution.thread.is_alive())
                self.assertEqual(events, ['delete-owned', 'collect', 'teardown'])
                self.assertEqual(json.loads((job.output / 'suite/owned.json').read_text())['resources'], [])
                self.assertIn('cleanup', [phase['stage'] for phase in result['suite']['execution']['phases']])
                self.assertEqual(result['errors'], result['suite']['errors'])
                self.assertEqual(result['completed'], failure != 'prepare')

    def test_finished_state_save_failure_does_not_skip_collection_or_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            job = Job({'cleanup': 'always'}, profile(), root / 'profile.json', root / 'job')
            suite = SimpleNamespace(run=lambda: {'errors': []}, finish=lambda summary: None)
            events = []
            save = job.save

            def failing_save():
                if job.state['phase'] == 'finished':
                    raise OSError('state disk unavailable')
                save()

            with (
                patch.object(job, 'prepare', return_value=suite),
                patch.object(job, 'save', side_effect=failing_save),
                patch.object(job, 'collect', side_effect=lambda: events.append('collect')),
                patch.object(job, 'cleanup', side_effect=lambda: events.append('cleanup')),
            ):
                result = job.run()
            self.assertEqual(events, ['collect', 'cleanup'])
            self.assertTrue(result['completed'])
            self.assertFalse(result['passed'])
            self.assertEqual(result['errors'], ['state persistence: state disk unavailable'])
            self.assertEqual(json.loads((job.output / 'summary.json').read_text()), result)

    def test_cleanup_refuses_changed_deployment(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            job = Job({}, profile(), root / 'profile.json', root)
            job.private.mkdir()
            job.deploy.mkdir()
            (job.private / 'job-id').write_text(job.state['job_id'])
            record = {
                'deployment_id': 'old',
                'compose_file': str(job.deploy / 'compose.yaml'),
                'data_dir': str(job.deploy / 'data'),
                'env_file': str(job.deploy / '.env'),
            }
            job.state['record'] = record
            (job.deploy / 'deployment.yaml').write_text(yaml.safe_dump({**record, 'deployment_id': 'new'}))
            with self.assertRaisesRegex(RuntimeError, 'identity changed'):
                job.cleanup()

    def test_sandbox_cleanup_uses_owned_mount_roots(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            job = Job({}, profile(), root / 'profile.json', root)
            job.state['record'] = {'data_dir': str(job.deploy / 'data')}
            containers = ['ours', 'other']

            def checked(args, timeout=900):
                if args[1] == 'ps':
                    return '\n'.join(containers)
                return '\n'.join(
                    json.dumps(
                        {
                            'Id': container,
                            'Mounts': [
                                {
                                    'Source': str(job.deploy / 'data/box/tenant')
                                    if container != 'other'
                                    else '/unrelated/box/tenant'
                                }
                            ],
                        }
                    )
                    for container in args[4:]
                )

            job.checked = checked
            self.assertEqual(job.owned_sandboxes(), ['ours'])
            containers.append('later')
            self.assertEqual(job.owned_sandboxes(), ['ours', 'later'])


if __name__ == '__main__':
    unittest.main()
