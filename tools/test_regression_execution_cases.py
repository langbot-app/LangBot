"""Challenge fault oracles and their cleanup; exercise NDJSON over real HTTP."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import regression_execution_cases as cases
from mock_llm import MockServer


class ExecutionCasesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ledger = self.root / 'ledger.db'
        with sqlite3.connect(self.ledger) as db:
            db.execute(
                'CREATE TABLE agent_run(id INTEGER, run_id TEXT, conversation_id TEXT, status TEXT, finished_at TEXT, workspace_id TEXT)'
            )
        self.suite = SimpleNamespace(
            output=self.root,
            variables={
                **{f'fault_{name}_model': name for name in cases.MODELS},
                'chat_model': 'chat',
                'error503_model': '503',
                'error429_model': '429',
                'workspace_uuid': 'workspace',
                'mock_base_url': 'http://unused.invalid/v1',
            },
            profile={'smoke': {'ledger_db': str(self.ledger), 'mock_records': str(self.root / 'mock.jsonl')}},
            path=lambda value: value,
            timeout=lambda maximum: maximum,
            secrets=[],
            connection={'endpoint': 'http://unused.invalid', 'credential_source': 'env:TEST_KEY'},
            env={'TEST_KEY': 'test-only'},
        )

    def run_fixture(
        self,
        scenario,
        *,
        tool_ok=True,
        fault=True,
        primary_status=None,
        recovery_status='completed',
        delete_ok=True,
        recycled=False,
    ):
        expected = {
            'execution.cancel_cleanup': 'cancelled',
            'execution.timeout_cleanup': 'timeout',
            'execution.retry_side_effects': 'completed',
            'tools.path_escape': 'completed',
            'model.stream_disconnect': 'failed',
            'model.exhausted_fallback': 'failed',
        }[scenario]
        row = {'case': scenario, 'after_id': 0}
        self.row = row
        self.deleted = False
        runs, events = [], {}
        statuses = {
            'execution.retry_side_effects': [503, 200, 200, 200],
            'model.stream_disconnect': [200],
            'model.exhausted_fallback': [503, 429],
        }.get(scenario, [200, 200])
        models = {
            'execution.retry_side_effects': ['mock-local-retry-side-effect'] * 4,
            'model.stream_disconnect': ['mock-stream-disconnect'],
            'model.exhausted_fallback': ['mock-503', 'mock-429'],
        }.get(scenario, ['fixture'] * 2)
        requests = [
            {
                'scope': 'qa-fault-fixture',
                'status': status if fault else 200,
                'request': {'model': model},
                'injected_disconnect': fault,
                'response_complete': not fault,
            }
            for status, model in zip(statuses, models)
        ]
        (self.root / 'mock.jsonl').write_text(''.join(json.dumps(item) + '\n' for item in requests))
        box_key = 'qa-fault-' + hashlib.sha256((str(self.root.resolve()) + scenario).encode()).hexdigest()[:24]
        box_session_id = 'runner-' + hashlib.sha256(box_key.encode()).hexdigest()

        def api(_suite, method, path, body=None):
            if method == 'DELETE':
                self.deleted = True
                return (200, {'code': 0}) if delete_ok else (500, {'code': 'delete_failed'})
            if method == 'GET' and path == '/api/v1/agents/agent':
                return 404, {'code': -1}
            if path == '/api/v1/box/sessions':
                if recycled and len(runs) == 1:
                    return 200, {'code': 0, 'data': []}
                return 200, {'code': 0, 'data': [{'session_id': box_session_id, 'status': 'idle'}]}
            if path.endswith('/events'):
                run_id = path.split('/')[-2]
                return 200, {'code': 0, 'data': {'items': events[run_id], 'has_more': False}}
            if path.endswith('/runs'):
                return 200, {'code': 0, 'data': {'items': list(runs)}}
            return 200, {'code': 0, 'data': {'uuid': 'agent'}}

        def stream(_suite, _agent, scope, _row, **kwargs):
            index = len(runs) + 1
            run_id = f'run-{index}'
            status = (primary_status or expected) if index == 1 else recovery_status
            run = {'run_id': run_id, 'conversation_id': scope, 'status': status, 'finished_at': 'now'}
            runs.append(run)
            with sqlite3.connect(self.ledger) as db:
                db.execute(
                    'INSERT INTO agent_run VALUES(?,?,?,?,?,?)', (index, run_id, scope, status, 'now', 'workspace')
                )
            tool = 'read' if scenario == 'tools.path_escape' else 'exec'
            stdout = 'INTERRUPT_CLEANUP_OK' if index > 1 else 'SIDE_EFFECT_ONCE'
            result = {'exit_code': 0 if tool_ok else 1, 'stdout': stdout if tool_ok else 'DUPLICATE_OR_LEAK'}
            if not tool_ok and index > 1:
                result = {'exit_code': 42, 'stdout': 'INTERRUPT_LATE_SIDE_EFFECT', 'stderr': ''}
            events[run_id] = [
                {
                    'type': 'tool.call.completed',
                    'data': {
                        'tool_name': tool,
                        'result': result,
                        'error': 'Path escapes the workspace boundary.' if tool == 'read' else None,
                    },
                }
            ]
            if scenario == 'execution.retry_side_effects':
                events[run_id].insert(
                    0,
                    {
                        'type': 'tool.call.completed',
                        'data': {
                            'tool_name': 'exec',
                            'result': {'exit_code': 0, 'stdout': 'SIDE_EFFECT_WRITTEN'},
                        },
                    },
                )
            if kwargs.get('interrupt'):
                row['box_session_id'] = box_session_id
            return [
                *[{'kind': 'result', 'data': event} for event in events[run_id]],
                {'kind': 'result', 'data': {'type': 'message.delta', 'data': {'chunk': {'content': 'LANGBOT_'}}}},
                {'kind': 'completed', 'data': {'final_text': 'LANGBOT_CHAT_OK'}},
            ]

        class Released:
            status = 200

            def __enter__(self):
                from io import BytesIO

                self.read = BytesIO(b'{"scope":"qa-fault-fixture","released":1}').read
                return self

            def __exit__(self, *_):
                pass

        with (
            patch.object(cases, 'api', side_effect=api),
            patch.object(cases, '_stream', side_effect=stream),
            patch.object(cases, 'uuid4', return_value=SimpleNamespace(hex='fixture')),
            patch.object(cases.urllib.request.OpenerDirector, 'open', return_value=Released()),
        ):
            return cases.run_case(self.suite, {'scenario': scenario}, row)

    def test_fault_cases_preserve_expected_terminal_runs_and_delete_agent(self):
        for scenario in sorted(cases.CASE_NAMES):
            with self.subTest(scenario=scenario):
                with sqlite3.connect(self.ledger) as db:
                    db.execute('DELETE FROM agent_run')
                result = self.run_fixture(scenario)
                self.assertEqual(result['result'], 'FAULT_CASE_OK')
                self.assertTrue(self.deleted)
                self.assertTrue(self.row['scenario_runs'])
                self.assertEqual(self.row['assertions']['run_status'], 'passed')
                self.assertEqual(self.row['cleanup_errors'], [])

    def test_duplicate_side_effect_and_untriggered_fault_fail_without_replay(self):
        for tool_ok, fault, assertion in ((False, True, 'side_effect_once'), (True, False, 'fault_injected')):
            with self.subTest(assertion=assertion):
                with sqlite3.connect(self.ledger) as db:
                    db.execute('DELETE FROM agent_run')
                with self.assertRaises(ValueError):
                    self.run_fixture('execution.retry_side_effects', tool_ok=tool_ok, fault=fault)
                self.assertEqual(self.row['assertions'][assertion], 'failed')
                self.assertTrue(self.deleted)
                self.assertEqual(len(self.row['scenario_runs']), 1)

    def test_late_side_effect_is_a_failure_even_when_run_is_cancelled(self):
        with self.assertRaisesRegex(ValueError, 'INTERRUPT_LATE_SIDE_EFFECT'):
            self.run_fixture('execution.cancel_cleanup', tool_ok=False, recovery_status='failed')
        self.assertEqual(self.row['assertions']['no_late_side_effect'], 'failed')
        self.assertEqual([run['status'] for run in self.row['scenario_runs']], ['cancelled', 'failed'])
        self.assertEqual(self.row['recovery_exec_results'][0]['result']['exit_code'], 42)
        self.assertTrue(self.deleted)

    def test_recycled_box_requires_the_same_persistent_file_check(self):
        for scenario in ('execution.cancel_cleanup', 'execution.timeout_cleanup'):
            with self.subTest(scenario=scenario):
                with sqlite3.connect(self.ledger) as db:
                    db.execute('DELETE FROM agent_run')
                result = self.run_fixture(scenario, recycled=True)
                self.assertEqual(result['result'], 'FAULT_CASE_OK')
                self.assertIsNone(self.row['box_after_interrupt'])
                self.assertEqual(self.row['assertions']['no_late_side_effect'], 'passed')
                with sqlite3.connect(self.ledger) as db:
                    db.execute('DELETE FROM agent_run')
                with self.assertRaisesRegex(ValueError, 'INTERRUPT_LATE_SIDE_EFFECT'):
                    self.run_fixture(scenario, recycled=True, tool_ok=False, recovery_status='failed')
                self.assertEqual(self.row['assertions']['no_late_side_effect'], 'failed')

    def test_recovery_command_distinguishes_missing_setup_and_late_side_effect(self):
        scenarios = json.loads(Path(cases.__file__).with_name('mock_llm_scenarios.json').read_text())
        command = scenarios['mock-local-interrupt-check']['steps'][0]['tool_calls'][0]['arguments']['command']
        command = command.removeprefix('sleep 9; ').replace(
            '/workspace/langbot-{mock_scope}', str(self.root / 'fixture')
        )
        ready, leaked = self.root / 'fixture-ready', self.root / 'fixture-leak'
        for setup, leak, status, output in (
            (False, False, 41, 'INTERRUPT_SETUP_MISSING'),
            (True, True, 42, 'INTERRUPT_LATE_SIDE_EFFECT'),
            (True, False, 0, 'INTERRUPT_CLEANUP_OK'),
        ):
            with self.subTest(setup=setup, leak=leak):
                if setup:
                    ready.write_text('SETUP_READY')
                if leak:
                    leaked.write_text('LATE_SIDE_EFFECT')
                else:
                    leaked.unlink(missing_ok=True)
                result = subprocess.run(['sh', '-c', command], capture_output=True, text=True, timeout=2)
                self.assertEqual((result.returncode, result.stdout), (status, output))
                self.assertEqual(ready.exists(), setup and status != 0)

    def test_unexpected_run_status_is_recorded_and_cleanup_failure_keeps_original(self):
        with self.assertRaisesRegex(RuntimeError, 'Run ended as completed.*Agent cleanup'):
            self.run_fixture('model.exhausted_fallback', primary_status='completed', delete_ok=False)
        self.assertEqual(self.row['scenario_runs'][0]['status'], 'completed')
        self.assertEqual(self.row['scenario_runs'][0]['expected_status'], 'failed')
        self.assertTrue(self.deleted)

    def test_real_ndjson_transport_and_cancel_close(self):
        requests = []
        frames = [
            {
                'kind': 'result',
                'data': {'type': 'tool.call.started', 'data': {'parameters': {'command': 'sleep 8; printf late'}}},
            },
            {'kind': 'completed', 'data': {'final_text': 'done'}},
        ]

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(200)
                self.send_header('Content-Type', 'application/x-ndjson')
                self.end_headers()
                for frame in frames:
                    self.wfile.write(json.dumps(frame).encode() + b'\n')
                self.wfile.flush()

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        self.suite.connection['endpoint'] = f'http://127.0.0.1:{server.server_port}'
        try:
            self.assertEqual(cases._stream(self.suite, 'agent', 'scope', {})[-1]['kind'], 'completed')
            row = {}
            with (
                patch.object(cases, '_running_box', return_value='box'),
                patch.object(cases, '_sessions', return_value={'box': {'status': 'running'}}),
            ):
                cancelled = cases._stream(self.suite, 'agent', 'scope', row, interrupt='cancel')
            self.assertEqual(len(cancelled), 1)
            self.assertEqual(row['box_session_id'], 'box')
            frames.pop()
            with self.assertRaisesRegex(RuntimeError, 'outcome unknown'):
                cases._stream(self.suite, 'agent', 'scope', {})
            self.assertEqual(len(requests), 3)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_real_mock_http_scopes_isolate_tool_paths_and_reject_unsafe_substitution(self):
        scenarios = json.loads(Path(cases.__file__).with_name('mock_llm_scenarios.json').read_text())
        with MockServer(('127.0.0.1', 0), scenarios) as server:
            thread = threading.Thread(target=server.serve_forever)
            thread.start()

            def request(scope):
                body = {
                    'model': 'mock-local-interrupt',
                    'mock_scope': scope,
                    'messages': [{'role': 'user', 'content': 'test'}],
                    'tools': [{'type': 'function', 'function': {'name': 'exec'}}],
                }
                with urlopen(
                    Request(
                        f'http://127.0.0.1:{server.server_port}/v1/chat/completions', data=json.dumps(body).encode()
                    ),
                    timeout=5,
                ) as response:
                    return json.load(response)

            try:
                commands = []
                for scope in ('run-a', 'run-b'):
                    call = request(scope)['choices'][0]['message']['tool_calls'][0]
                    command = json.loads(call['function']['arguments'])['command']
                    self.assertIn(f'/workspace/langbot-{scope}-ready', command)
                    self.assertNotIn('{mock_scope}', command)
                    commands.append(command)
                self.assertNotEqual(commands[0], commands[1])
                for invalid in (None, 'unsafe;echo', '../../escape'):
                    with self.subTest(scope=invalid), self.assertRaises(HTTPError) as caught:
                        request(invalid)
                    self.assertEqual(caught.exception.code, 400)
            finally:
                server.shutdown()
                thread.join()


if __name__ == '__main__':
    unittest.main()
