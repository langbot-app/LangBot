"""Exercise signed group traffic, member rotation, phase continuity and fail-closed history."""

import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from regression_suite import Suite, validate


class GroupTests(unittest.TestCase):
    def test_bot_readback_uses_the_cli_confirmed_endpoint_and_workspace(self):
        received = []

        class Readback(BaseHTTPRequestHandler):
            def do_GET(self):
                received.append((self.path, self.headers.get('Authorization'), self.headers.get('X-Workspace-Id')))
                body = json.dumps({'code': 0, 'data': {'bot': {'uuid': 'owned-bot', 'event_bindings': []}}}).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Readback)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as folder:
                current = json.loads((Path(__file__).with_name('regression_profiles') / 'groups.json').read_text())
                suite = Suite(current, Path(folder) / 'profile.json', Path(folder), env={'TEST_API_KEY': 'test-key'})
                suite.variables['workspace_uuid'] = 'bound-workspace'
                suite.connection = {
                    'endpoint': f'http://127.0.0.1:{server.server_port}',
                    'credential_source': 'env:TEST_API_KEY',
                }
                self.assertEqual(suite.read_bot('owned-bot')['uuid'], 'owned-bot')
                self.assertEqual(received, [('/api/v1/platform/bots/owned-bot', 'Bearer test-key', 'bound-workspace')])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_groups_profile_and_invalid_modes(self):
        path = Path(__file__).with_name('regression_profiles') / 'groups.json'
        profile = json.loads(path.read_text())
        validate(profile)
        for field, value in [('groups', 3), ('members_per_group', 0), ('groups', 4097)]:
            current = json.loads(path.read_text())
            current['phases'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate(current)

    def test_signed_groups_continue_across_phases_and_stop_after_bad_reply(self):
        secret = 'test-group-signing-key'
        histories = {}
        failures = []
        active = set()
        lock = threading.Lock()
        bad_reply = False

        class Ingress(BaseHTTPRequestHandler):
            def do_GET(self):
                self.respond({'code': 0})

            def respond(self, payload, status=200):
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                raw = self.rfile.read(int(self.headers['Content-Length']))
                stamp = self.headers['X-LB-Timestamp']
                expected = (
                    'sha256=' + hmac.new(secret.encode(), stamp.encode() + b'.' + raw, hashlib.sha256).hexdigest()
                )
                payload = json.loads(raw)
                group = payload['session_id']
                fields = dict(re.findall(r'LB_(GROUP|TURN|TOKEN|PREVIOUS)=(\S+)', payload['message'][0]['text']))
                with lock:
                    prior = histories.get(group, [])
                    if (
                        self.headers['X-LB-Signature'] != expected
                        or group in active
                        or payload['session_type'] != 'group'
                        or fields['GROUP'] != group
                        or int(fields['TURN']) != len(prior) + 1
                        or fields['PREVIOUS'] != (prior[-1]['token'] if prior else 'none')
                    ):
                        failures.append(payload)
                    active.add(group)
                time.sleep(0.01)
                with lock:
                    histories.setdefault(group, []).append(
                        {'token': fields['TOKEN'], 'member': payload['sender']['id']}
                    )
                    active.remove(group)
                ack = 'missing' if bad_reply and group.endswith('g0000') else fields['TOKEN']
                self.respond(
                    {
                        'code': 0,
                        'data': {
                            'session_id': group,
                            'reply_to': 'incoming-' + fields['TOKEN'],
                            'message': [
                                {'type': 'Plain', 'text': 'TEST_OK GROUP_'},
                                {'type': 'Plain', 'text': 'ACK=' + ack},
                            ],
                        },
                    },
                    status=500 if bad_reply == 'unknown' and group.endswith('g0000') else 200,
                )

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Ingress)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                cases = root / 'cases.json'
                cases.write_text(
                    json.dumps(
                        [
                            {
                                'name': 'group',
                                'expect': 'TEST_OK',
                                'http_group': {
                                    'url': f'http://127.0.0.1:{server.server_port}/bots/test/sync',
                                    'secret_env': 'LANGBOT_QA_GROUP_SECRET',
                                    'message': 'ai Test group history',
                                },
                            }
                        ]
                    )
                )
                state = root / 'group-state.json'
                command = [
                    sys.executable,
                    str(Path(__file__).with_name('regression_traffic.py')),
                    '--lbctl',
                    'unused',
                    '--config',
                    'unused',
                    '--cases',
                    str(cases),
                    '--duration',
                    '0.8',
                    '--rps',
                    '40',
                    '--workers',
                    '3',
                    '--cooldown',
                    '0',
                    '--members-per-group',
                    '2',
                    '--health',
                    f'core=http://127.0.0.1:{server.server_port}/healthz',
                ]
                env = {**os.environ, 'LANGBOT_QA_GROUP_SECRET': secret}
                summaries = []
                for groups in (4, 8):
                    output = root / f'phase-{groups}'
                    result = subprocess.run(
                        [*command, '--groups', str(groups), '--group-state', str(state), '--output', str(output)],
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    summaries.append(json.loads((output / 'summary.json').read_text()))
                first = summaries[0]['groups']['sessions']
                second = summaries[1]['groups']['sessions']
                self.assertEqual(len(first), 4)
                self.assertEqual(len(second), 8)
                for group in first:
                    self.assertGreater(second[group]['successful_turns_total'], first[group]['successful_turns_total'])
                    self.assertEqual(len(second[group]['members_this_phase']), 2)
                self.assertFalse(failures)
                self.assertNotIn(secret, state.read_text())
                bad_reply = True
                output = root / 'failed'
                result = subprocess.run(
                    [*command, '--groups', '4', '--output', str(output)],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                summary = json.loads((output / 'summary.json').read_text())
                failed = next(item for group, item in summary['groups']['sessions'].items() if group.endswith('g0000'))
                self.assertTrue(failed['failed'])
                self.assertEqual(failed['requests_this_phase'], 1)
                bad_reply = 'unknown'
                result = subprocess.run(
                    [*command, '--groups', '4', '--output', str(root / 'unknown')],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                unknown = json.loads((root / 'unknown/summary.json').read_text())
                self.assertEqual(unknown['status'].get('unknown'), 1)
                interrupted = json.loads(state.read_text())
                interrupted['in_progress'] = True
                state.write_text(json.dumps(interrupted))
                result = subprocess.run(
                    [*command, '--groups', '4', '--group-state', str(state), '--output', str(root / 'interrupted')],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('interrupted', result.stderr)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
