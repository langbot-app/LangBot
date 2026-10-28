"""Focused checks for profile validation, ownership and the CLI preparation sequence."""

import copy
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from regression_suite import Suite, main, merge, resolve, validate


FAKE_CLI = r"""
import json, os, sys
from pathlib import Path
args = sys.argv[5:]
root = Path(os.environ['LBCTL_TEST_ROOT'])
state_path = root / 'cli-state.json'
state = json.loads(state_path.read_text()) if state_path.exists() else {}
body = json.loads(Path(args[args.index('--file') + 1]).read_text()) if '--file' in args else {}
with (root / 'cli-calls.jsonl').open('a') as log:
    log.write(json.dumps({'args': args, 'body': body}) + '\n')
if args == ['whoami']:
    data = {'workspace_uuid': 'test-workspace'}
elif args[:2] == ['pipeline', 'run']:
    assert args[2] in state
    data = {'status': 'completed', 'reply': 'TEST_OK'}
elif args[1] == 'delete':
    del state[args[2]]
    state_path.write_text(json.dumps(state))
    data = {}
elif args[:2] == ['pipeline', 'get']:
    data = state[args[2]]
elif args[1] in ['create', 'apply']:
    uuid = body.get('uuid', f'created-{len(state)}')
    data = {'uuid': uuid, 'name': body.get('name', 'test'), 'description': '', 'config': body.get('config', {'ai': {'default': True}})}
    state[uuid] = data
    state_path.write_text(json.dumps(state))
else:
    raise RuntimeError(args)
print(json.dumps({'ok': True, 'data': data}))
"""


def profile():
    return {
        'version': 1,
        'cli': {'config': 'lbctl.yaml'},
        'cases': [{'name': 'chat', 'args': ['pipeline', 'run', 'existing'], 'expect': 'OK'}],
        'phases': [{'name': 'normal', 'duration_seconds': 1, 'rps': 2, 'workers': 4}],
        'observe': {'health': {'core': 'http://127.0.0.1:5300/healthz'}},
    }


class ProfileTests(unittest.TestCase):
    def test_created_bot_verification_failure_can_only_defer_bot_readback(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            suite = Suite(profile(), root / 'profile.json', root)
            response = {
                'data': {'operation': 'bot.create', 'uuid': 'owned-bot', 'bot': {'uuid': 'owned-bot'}},
                'error': {'type': 'verification_failed'},
            }
            result = subprocess.CompletedProcess([], 1, json.dumps(response), '')
            with patch('regression_suite.subprocess.run', return_value=result):
                with self.assertRaises(RuntimeError):
                    suite.call(['bot', 'create'], {'name': 'QA'})
                self.assertEqual(
                    suite.call(['bot', 'create'], {'name': 'QA'}, defer_bot_readback=True)['uuid'], 'owned-bot'
                )
                with self.assertRaises(RuntimeError):
                    suite.call(['pipeline', 'apply'], {}, defer_bot_readback=True)

    def test_group_bot_is_owned_before_raw_readback_and_warmed_before_load(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            current = profile()
            current['resources'] = [
                {
                    'id': 'chat_bot',
                    'kind': 'bot',
                    'body': {
                        'name': 'QA',
                        'adapter': 'http_bot',
                        'enable': True,
                        'adapter_config': {'inbound_secret': '${group_secret}'},
                        'event_bindings': [{'target_type': 'pipeline', 'target_uuid': 'pipeline-a'}],
                    },
                }
            ]
            current['cases'] = [
                {
                    'name': 'chat',
                    'expect': 'OK',
                    'http_group': {
                        'url': 'http://localhost/bots/${chat_bot}/sync',
                        'message': 'ai Test',
                        'secret_env': 'LANGBOT_QA_GROUP_SECRET',
                    },
                }
            ]
            current['phases'][0]['groups'] = 1
            validate(current)
            for correct_route in (False, True):
                suite = Suite(current, root / 'profile.json', root)

                def call(args, body=None, **kwargs):
                    if args == ['whoami']:
                        return {'workspace_uuid': 'workspace-a'}
                    if args == ['bot', 'create']:
                        self.assertTrue(kwargs['defer_bot_readback'])
                        return {'uuid': 'owned-bot'}
                    raise AssertionError(args)

                suite.call = call
                actual = copy.deepcopy(current['resources'][0]['body'])
                actual['adapter_config']['inbound_secret'] = '***'
                if not correct_route:
                    actual['event_bindings'][0]['target_uuid'] = 'wrong-pipeline'
                with (
                    patch.object(suite, 'read_bot', return_value=actual),
                    patch('regression_suite.group_request', return_value={'code': 0}) as warmup,
                ):
                    if correct_route:
                        suite.prepare()
                        warmup.assert_called_once()
                        self.assertNotIn(suite.variables['group_secret'], (root / 'resources.json').read_text())
                    else:
                        with self.assertRaisesRegex(RuntimeError, 'Bot readback differs'):
                            suite.prepare()
                        warmup.assert_not_called()
                    self.assertEqual(
                        json.loads((root / 'owned.json').read_text())['resources'],
                        [{'kind': 'bot', 'uuid': 'owned-bot'}],
                    )

    def test_normal_profile_and_overrides_contract(self):
        validate(json.loads(Path(__file__).with_name('regression_profiles').joinpath('normal.json').read_text()))
        bad = profile()
        for field, value in [('rps', float('nan')), ('workers', 33), ('duration_seconds', -1)]:
            with self.subTest(field=field):
                current = copy.deepcopy(bad)
                current['phases'][0][field] = value
                with self.assertRaises(ValueError):
                    validate(current)

    def test_missing_refs_and_existing_resource_overwrite_are_rejected(self):
        current = profile()
        current['cases'][0]['args'][-1] = '${missing}'
        with self.assertRaises(KeyError):
            validate(current)
        current = profile()
        current['resources'] = [{'id': 'pipeline', 'kind': 'pipeline', 'body': {'uuid': 'existing'}}]
        with self.assertRaisesRegex(ValueError, 'uuid is forbidden'):
            validate(current)

    def test_merge_keeps_defaults_but_replaces_lists(self):
        base = {'ai': {'enabled': True, 'models': ['old']}, 'output': {'x': 1}}
        actual = merge(base, {'ai': {'models': ['new']}})
        self.assertEqual(actual, {'ai': {'enabled': True, 'models': ['new']}, 'output': {'x': 1}})
        self.assertEqual(base['ai']['models'], ['old'])
        self.assertEqual(resolve(['${id}', {'id': '${id}'}], {'id': 'created'}), ['created', {'id': 'created'}])

    def test_ownership_recorded_before_configuration_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            current = profile()
            current['resources'] = [{'id': 'chat', 'kind': 'pipeline', 'body': {'name': 'QA', 'config': {'ai': {}}}}]
            suite = Suite(current, root / 'profile.json', root)
            calls = []

            def call(args, body=None):
                calls.append((args, body))
                if args == ['whoami']:
                    return {'workspace_uuid': 'workspace-a'}
                if args == ['pipeline', 'apply'] and 'uuid' not in body:
                    return {'uuid': 'owned-pipeline'}
                if args[:2] == ['pipeline', 'get']:
                    return {'uuid': 'owned-pipeline', 'name': 'QA', 'description': '', 'config': {'ai': {'old': 1}}}
                if args == ['pipeline', 'apply']:
                    raise RuntimeError('configuration failed')
                return {}

            suite.call = call
            with self.assertRaisesRegex(RuntimeError, 'configuration failed'):
                suite.prepare()
            self.assertEqual(
                json.loads((root / 'owned.json').read_text())['resources'],
                [{'kind': 'pipeline', 'uuid': 'owned-pipeline'}],
            )
            self.assertEqual(suite.cleanup(), [])
            self.assertEqual(calls[-1][0], ['pipeline', 'delete', 'owned-pipeline', '--yes'])
            self.assertEqual(json.loads((root / 'owned.json').read_text())['resources'], [])

    def test_cleanup_refuses_another_workspace(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'owned.json').write_text(json.dumps({'workspace_uuid': 'other', 'resources': []}))
            suite = Suite(profile(), root / 'profile.json', root)
            suite.call = lambda args: {'workspace_uuid': 'current'}
            with self.assertRaisesRegex(RuntimeError, 'Workspace differs'):
                suite.cleanup()

    def test_aborted_run_is_not_treated_as_successful_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = root / 'profile.json'
            config.write_text(json.dumps(profile()))
            for error_type in (KeyboardInterrupt, TypeError):
                output = root / error_type.__name__

                def interrupt(suite):
                    suite.variables['workspace_uuid'] = 'test-workspace'
                    suite.journal()
                    raise error_type

                argv = ['regression_suite.py', 'run', '--profile', str(config), '--output', str(output)]
                with (
                    patch.object(sys, 'argv', argv),
                    patch.object(Suite, 'prepare', interrupt),
                    patch.object(Suite, 'cleanup') as cleanup,
                    redirect_stdout(io.StringIO()),
                ):
                    with self.assertRaises(SystemExit if error_type is KeyboardInterrupt else TypeError):
                        main()
                    cleanup.assert_not_called()
                self.assertFalse(json.loads((output / 'summary.json').read_text())['passed'])

    def test_subprocess_phases_and_cleanup_with_controlled_cli(self):
        class Health(BaseHTTPRequestHandler):
            def do_GET(self):
                payload = b'{"code":0}'
                self.send_response(200)
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

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
                current = profile()
                current['cli']['executable'] = str(cli)
                current['resources'] = [
                    {'id': 'provider', 'kind': 'provider', 'body': {'name': 'test'}},
                    {
                        'id': 'pipeline',
                        'kind': 'pipeline',
                        'body': {'name': 'test', 'config': {'ai': {'model': '${provider}'}}},
                    },
                ]
                current['cases'] = [
                    {'name': 'chat', 'args': ['pipeline', 'run', '${pipeline}'], 'expect': 'TEST_OK', 'weight': 2},
                    {'name': 'box', 'args': ['pipeline', 'run', '${pipeline}'], 'expect': 'TEST_OK', 'weight': 1},
                ]
                current['phases'] = [
                    {'name': name, 'duration_seconds': 0.5, 'rps': 12, 'workers': 3} for name in ('low', 'high')
                ]
                current['observe'] = {'health': {'core': f'http://127.0.0.1:{server.server_port}/healthz'}}
                current['cleanup'] = 'always'
                config = root / 'profile.json'
                command = [
                    sys.executable,
                    str(Path(__file__).with_name('regression_suite.py')),
                    'run',
                    '--profile',
                    str(config),
                ]
                environment = {**os.environ, 'LBCTL_TEST_ROOT': folder}
                for enforce_latency, mode, wrong_reply in (
                    (False, 'gate', False),
                    (True, 'gate', False),
                    (True, 'observe', False),
                    (True, 'observe', True),
                ):
                    current['performance_mode'] = mode
                    current['cases'][0]['expect'] = 'WRONG_RESULT' if wrong_reply else 'TEST_OK'
                    expected_failure = wrong_reply or (enforce_latency and mode == 'gate')
                    current['thresholds'] = {'max_p95_seconds': {'chat': 0.001}} if enforce_latency else {}
                    config.write_text(json.dumps(current))
                    output = root / f'{enforce_latency}-{mode}-{wrong_reply}'
                    result = subprocess.run(
                        [*command, '--output', str(output)], env=environment, capture_output=True, text=True, timeout=30
                    )
                    summary = json.loads((output / 'summary.json').read_text())
                    self.assertEqual(result.returncode, int(expected_failure), result.stdout + result.stderr)
                    self.assertEqual(summary['passed'], not expected_failure)
                    self.assertEqual(len(summary['phases']), 2)
                    for phase in summary['phases']:
                        self.assertGreater(phase['achieved_rps'], 0)
                        self.assertEqual(phase['health_failures'], 0)
                        self.assertGreaterEqual(phase['cases']['chat']['requests'], phase['cases']['box']['requests'])
                    self.assertEqual(json.loads((output / 'owned.json').read_text())['resources'], [])
                    self.assertEqual(json.loads((root / 'cli-state.json').read_text()), {})
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
