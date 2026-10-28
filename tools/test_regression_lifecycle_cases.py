"""Challenge callback evidence and cleanup with real loopback HTTP receipts."""

import json
from pathlib import Path
import socket
import sqlite3
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

import regression_lifecycle_cases as lifecycle


class LifecycleTest(unittest.TestCase):
    def exercise(self, corruption=None):
        suite = SimpleNamespace(
            variables={'chat_pipeline': 'fixture-pipeline'}, secrets=[], timeout=lambda limit: limit
        )
        case = {'scenario': 'callback_retry_identity'}
        row, settings, workers, receivers, errors = {'after_id': 0}, {}, [], [], []
        calls = []
        receiver_class = lifecycle.CallbackReceiver

        def receiver(secret):
            result = receiver_class(secret)
            receivers.append(result)
            return result

        def callback(body, message_id):
            payload = {
                'session_id': body['session_id'],
                'reply_to': message_id,
                'sequence': 1,
                'is_final': True,
                'message': [{'type': 'Plain', 'text': 'LANGBOT_CHAT_OK'}],
            }
            secret = settings['outbound_secret'] + ('wrong' if corruption == 'signature' else '')
            try:
                for attempt in range(2):
                    if corruption == 'body' and attempt:
                        payload['timestamp'] = 'changed by retry'
                    raw = json.dumps(payload).encode()
                    stamp = str(int(time.time()))
                    request = urllib.request.Request(
                        settings['callback_url'],
                        data=raw,
                        headers={
                            'Content-Type': 'application/json',
                            'X-LB-Timestamp': stamp,
                            'X-LB-Signature': lifecycle.signature(secret, raw, stamp),
                        },
                    )
                    try:
                        with urllib.request.urlopen(request, timeout=2) as response:
                            response.read()
                            return
                    except urllib.error.HTTPError as exc:
                        if exc.code != 503:
                            return
                errors.append('Callback was never accepted')
            except Exception as exc:
                errors.append(str(exc))

        def api(_suite, method, path, body=None, headers=None):
            calls.append((method, path))
            if method == 'POST' and path == '/api/v1/platform/bots':
                settings.update(body['adapter_config'])
                self.assertEqual(body['event_bindings'][0]['target_uuid'], 'fixture-pipeline')
                return 200, {'code': 0, 'data': {'uuid': 'temporary-bot'}}
            if method == 'POST' and path == '/bots/temporary-bot':
                self.assertEqual(
                    headers['X-LB-Signature'],
                    lifecycle.signature(
                        settings['inbound_secret'], json.dumps(body).encode(), headers['X-LB-Timestamp']
                    ),
                )
                message_id = 'in-' + str(len(workers))
                worker = threading.Thread(target=callback, args=(body, message_id))
                workers.append(worker)
                worker.start()
                return 202, {'code': 0, 'data': {'accepted_message_id': message_id}}
            if method == 'DELETE' and path == '/api/v1/platform/bots/temporary-bot':
                return 200, {'code': 0}
            if method == 'GET' and path == '/api/v1/platform/bots/temporary-bot':
                return 404, {'code': -1}
            raise AssertionError((method, path))

        with (
            patch.object(lifecycle, 'api', side_effect=api),
            patch.object(lifecycle, 'CallbackReceiver', side_effect=receiver),
            patch.object(lifecycle, 'completed'),
        ):
            if corruption is None:
                result = lifecycle.run_case(suite, case, row)
                self.assertEqual(result['result'], 'LANGBOT_CALLBACK_RETRY_OK')
                self.assertEqual([item['finals'] for item in result['deliveries']], [1, 1])
                self.assertEqual(
                    row['assertions'],
                    {'callback_retry': 'passed', 'callback_followup': 'passed', 'callback_cleanup': 'passed'},
                )
            else:
                with self.assertRaisesRegex(ValueError, 'signature|Retry changed'):
                    lifecycle.run_case(suite, case, row)
                self.assertEqual(row['assertions']['callback_retry'], 'failed')
                self.assertEqual(row['assertions']['callback_cleanup'], 'passed')
        for worker in workers:
            worker.join(timeout=2)
            self.assertFalse(worker.is_alive())
        self.assertFalse(errors, errors)
        self.assertIn(('DELETE', '/api/v1/platform/bots/temporary-bot'), calls)
        self.assertFalse(receivers[0].thread.is_alive())
        with socket.socket() as client:
            self.assertNotEqual(client.connect_ex(receivers[0].server.server_address), 0)
        return receivers[0].records

    def test_retry_followup_and_cleanup_use_actual_http_receipts(self):
        receipts = self.exercise()
        self.assertEqual([item['status'] for item in receipts], [503, 200, 200])
        self.assertEqual(receipts[0]['body'], receipts[1]['body'])

    def test_modified_retry_cannot_pass_and_still_cleans_up(self):
        self.exercise('body')

    def test_invalid_callback_signature_cannot_pass_and_still_cleans_up(self):
        self.exercise('signature')

    def test_duplicate_final_is_not_a_successful_delivery(self):
        payload = {'session_id': 'session', 'sequence': 1, 'is_final': True, 'message': []}
        records = [{'status': 200, 'payload': payload, 'body': b'{}'}] * 2
        with self.assertRaisesRegex(ValueError, 'order changed'):
            lifecycle.verify_delivery(records, 'session', retried=False)

    def test_unknown_callback_result_survives_cleanup_failure(self):
        class NoDelivery:
            url = 'http://127.0.0.1:9/test-only'

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def wait_final(self, *args):
                raise TimeoutError('callback outcome unknown')

        suite = SimpleNamespace(variables={'chat_pipeline': 'fixture'}, secrets=[], timeout=lambda limit: limit)
        row = {'after_id': 0}
        responses = [
            (200, {'code': 0, 'data': {'uuid': 'temporary-bot'}}),
            (202, {'code': 0, 'data': {'accepted_message_id': 'accepted'}}),
            (500, {'code': -1}),
        ]
        with (
            patch.object(lifecycle, 'CallbackReceiver', return_value=NoDelivery()),
            patch.object(lifecycle, 'api', side_effect=responses),
        ):
            with self.assertRaisesRegex(TimeoutError, 'callback outcome unknown'):
                lifecycle.run_case(suite, {'scenario': 'callback_retry_identity'}, row)
        self.assertEqual(row['assertions']['callback_cleanup'], 'failed')
        self.assertTrue(any('deletion failed' in error for error in row['cleanup_errors']))
        self.assertNotIn('callback_retry', row['assertions'])

    def test_restart_profile_reuses_fixture_resources_without_mutating_input(self):
        path = Path(__file__).with_name('regression_profiles') / 'smoke.json'
        original = json.loads(path.read_text())
        original['execution'] = {'total_seconds': 1800, 'drain_seconds': 120, 'cooldown_seconds': 60}
        snapshot = json.dumps(original, sort_keys=True)
        profile = lifecycle.restart_profile(original)
        self.assertEqual(json.dumps(original, sort_keys=True), snapshot)
        self.assertNotIn('execution', profile)
        self.assertEqual(profile['coverage_suite'], 'scenarios')
        self.assertEqual(
            [case['name'] for case in profile['cases']], ['core_restart_history', 'runtime_restart_recovery']
        )
        self.assertEqual(len(profile['resources']), 7)

    def test_restart_preflight_records_real_ledger_rows_and_preserves_failed_history(self):
        from regression_suite import Suite

        for fail_history in (False, True):
            with self.subTest(fail_history=fail_history), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path = root / 'runs.db'
                with sqlite3.connect(path) as connection:
                    connection.execute(
                        'CREATE TABLE agent_run (id INTEGER PRIMARY KEY, run_id TEXT, workspace_id TEXT, '
                        'conversation_id TEXT, status TEXT, finished_at TEXT, status_reason TEXT)'
                    )
                profile_path = Path(__file__).with_name('regression_profiles') / 'smoke.json'
                profile = json.loads(profile_path.read_text())
                profile['smoke']['ledger_db'] = str(path)
                release = threading.Event()
                restarts = []

                def prepare(suite):
                    suite.variables.update(workspace_uuid='workspace', chat_bot='chat-bot', restart_slow_bot='slow-bot')
                    suite.journal()

                def group_request(case, session_id, _member, turn, _token, previous, _env, *, timeout):
                    is_slow = 'slow-bot' in case['http_group']['url']
                    with sqlite3.connect(path) as connection:
                        count = connection.execute('SELECT COUNT(*) FROM agent_run').fetchone()[0]
                        run_id = f'run-{count}'
                        connection.execute(
                            'INSERT INTO agent_run(run_id,workspace_id,conversation_id,status,finished_at) VALUES(?,?,?,?,?)',
                            (
                                run_id,
                                'workspace',
                                'group_' + session_id,
                                'running' if is_slow else 'completed',
                                None if is_slow else 'done',
                            ),
                        )
                    if is_slow:
                        if not release.wait(2):
                            raise TimeoutError('Runtime restart was never invoked')
                        with sqlite3.connect(path) as connection:
                            connection.execute(
                                "UPDATE agent_run SET status='failed',finished_at='done' WHERE run_id=?", (run_id,)
                            )
                        raise RuntimeError('Runtime disconnected')
                    if turn == 2:
                        self.assertNotEqual(previous, 'none')
                        if fail_history:
                            raise ValueError('history rejected after restart')
                    return {'data': {'session_id': session_id}}

                def restart(name, *, timeout):
                    self.assertGreater(timeout, 0)
                    self.assertLessEqual(timeout, 60)
                    restarts.append(name)
                    if name == 'runtime':
                        release.set()
                    return {'old_pid': 10, 'new_pid': 20}

                def public_api(_suite, method, resource, *, headers):
                    self.assertEqual(method, 'GET')
                    self.assertEqual(headers, {'Authorization': 'Bearer test-only-user-token'})
                    run_id = resource.split('/')[-1].split('?')[0]
                    with sqlite3.connect(path) as connection:
                        status = connection.execute(
                            'SELECT status FROM agent_run WHERE run_id=?', (run_id,)
                        ).fetchone()[0]
                    return 200, {'code': 0, 'data': {'run': {'run_id': run_id, 'status': status}}}

                with (
                    patch.object(Suite, 'prepare', prepare),
                    patch.object(Suite, 'call', return_value={'workspace_uuid': 'workspace'}),
                    patch('regression_traffic.group_request', side_effect=group_request),
                    patch.object(lifecycle, 'api', side_effect=public_api),
                ):
                    result = lifecycle.run_restart_checks(
                        profile,
                        profile_path,
                        root / 'preflight',
                        {'LANGBOT_QA_USER_TOKEN': 'test-only-user-token'},
                        restart,
                    )
                self.assertEqual(result['passed'], not fail_history, result)
                self.assertEqual(
                    json.loads((root / 'preflight/profile.json').read_text()), lifecycle.restart_profile(profile)
                )
                self.assertEqual(restarts, ['core'] if fail_history else ['core', 'runtime'])
                self.assertEqual(json.loads((root / 'preflight/owned.json').read_text())['resources'], [])
                if fail_history:
                    self.assertTrue(any('history rejected' in message for message in result['errors']))
                    self.assertEqual(result['cases'][0]['assertions']['history_after_restart'], 'failed')
                else:
                    self.assertEqual(result['cases'][1]['scenario_runs'][0]['expected_status'], 'failed')
                    self.assertTrue(result['ledger_closeout']['matched'])
                    self.assertEqual(sum(len(row['scenario_runs']) for row in result['cases']), 4)

    def test_restart_missing_user_token_is_incomplete_before_preparation(self):
        from regression_suite import Suite

        path = Path(__file__).with_name('regression_profiles') / 'smoke.json'
        profile = json.loads(path.read_text())
        with tempfile.TemporaryDirectory() as directory, patch.object(Suite, 'prepare') as prepare:
            result = lifecycle.run_restart_checks(profile, path, Path(directory) / 'preflight', {}, None)
        prepare.assert_not_called()
        self.assertFalse(result['passed'])
        self.assertEqual(result['outcome'], 'INCOMPLETE')
        self.assertTrue(any('LANGBOT_QA_USER_TOKEN' in error for error in result['errors']))


if __name__ == '__main__':
    unittest.main()
