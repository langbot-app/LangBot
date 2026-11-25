"""Fixed arrivals remain accounted for under queue saturation and group failure."""

from collections import Counter
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from tools.entrypoints.regression_traffic import main
from tools.regression.arrival_schedule import run_open_loop


class ArrivalScheduleTests(unittest.TestCase):
    def test_slow_worker_preserves_fixed_arrivals_and_drains_only_dispatched_work(self):
        settled, calls = [], []
        started = time.monotonic()

        def execute(item):
            calls.append((item['arrival_id'], time.monotonic() - started))
            time.sleep(0.11)
            return {'status': 'ok'}

        summary = run_open_loop(
            started=started,
            duration=0.2,
            rps=100,
            workers=1,
            queue_capacity=1,
            execute=execute,
            key_for=lambda index: None,
            blocked=lambda key: False,
            settle=lambda item, outcome, row: settled.append({**item, 'outcome': outcome}),
            stop=threading.Event(),
        )
        self.assertEqual(sorted(item['arrival_id'] for item in settled), list(range(20)))
        self.assertTrue(all(item['scheduled_elapsed'] == item['arrival_id'] / 100 for item in settled))
        self.assertEqual(summary['scheduled'], 20)
        self.assertEqual(summary['dispatched'], len(calls))
        self.assertGreater(summary['dropped'], 0)
        self.assertGreater(summary['expired'], 0)
        self.assertEqual(summary['queue_peak'], 1)
        self.assertTrue(all(begin < 0.2 for _, begin in calls))
        self.assertTrue(summary['conserved'])
        self.assertEqual(sum(Counter(item['outcome'] for item in settled).values()), 20)

    def test_observer_abort_settles_all_remaining_planned_arrivals(self):
        stop = threading.Event()
        stop.set()
        settled, calls = [], []
        summary = run_open_loop(
            started=time.monotonic(),
            duration=0.07,
            rps=100,
            workers=2,
            queue_capacity=2,
            execute=lambda item: calls.append(item),
            key_for=lambda index: None,
            blocked=lambda key: False,
            settle=lambda item, outcome, row: settled.append((item['arrival_id'], outcome)),
            stop=stop,
        )
        self.assertEqual(calls, [])
        self.assertEqual(settled, [(index, 'expired') for index in range(7)])
        self.assertEqual(summary['expired'], 7)
        self.assertTrue(summary['conserved'])


class CliTrafficArrivalTests(unittest.TestCase):
    def test_slow_independent_cli_accounts_for_wire_calls_queue_full_and_deadline(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            calls = root / 'cli-calls.jsonl'
            cli = root / 'lbctl-test'
            script = r"""
import json
from pathlib import Path
import sys
import time

started = time.monotonic()
time.sleep(0.6)
with Path(sys.argv[-1]).open('a') as stream:
    stream.write(json.dumps({'args': sys.argv[1:], 'started': started, 'completed': time.monotonic()}) + '\n')
print(json.dumps({'ok': True, 'data': {'status': 'completed', 'reply': 'CLI_OK'}}))
"""
            cli.write_text(f'#!{sys.executable}\n{script}')
            cli.chmod(0o700)
            cases = root / 'cases.json'
            cases.write_text(
                json.dumps(
                    [
                        {
                            'name': 'chat',
                            'args': ['pipeline', 'run', 'existing-pipeline', '--message', str(calls)],
                            'expect': 'CLI_OK',
                        }
                    ]
                )
            )
            output = root / 'output'
            argv = [
                'regression_traffic',
                '--lbctl',
                str(cli),
                '--config',
                'unused',
                '--cases',
                str(cases),
                '--output',
                str(output),
                '--duration',
                '0.4',
                '--rps',
                '100',
                '--workers',
                '1',
                '--cooldown',
                '0',
                '--arrival-mode',
                'open-loop',
                '--queue-capacity',
                '1',
            ]
            with patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    main()
            self.assertEqual(raised.exception.code, 1)
            summary = json.loads((output / 'summary.json').read_text())
            rows = [json.loads(line) for line in (output / 'requests.jsonl').read_text().splitlines()]
            arrivals = [json.loads(line) for line in (output / 'arrivals.jsonl').read_text().splitlines()]
            actual = [json.loads(line) for line in calls.read_text().splitlines()]

            self.assertEqual(len(actual), 1)
            self.assertEqual(actual[0]['args'][:4], ['--config', 'unused', '-o', 'json'])
            self.assertEqual(actual[0]['args'][4:7], ['pipeline', 'run', 'existing-pipeline'])
            self.assertGreaterEqual(actual[0]['completed'] - actual[0]['started'], 0.6)
            self.assertEqual(len(rows), len(actual))
            self.assertEqual(rows[0]['status'], 'ok')
            self.assertLess(rows[0]['dispatch_elapsed'], 0.4)
            self.assertGreater(rows[0]['completed_elapsed'], 0.4)
            self.assertNotIn('group_id', rows[0])
            self.assertEqual(sorted(item['arrival_id'] for item in arrivals), list(range(40)))
            self.assertTrue(all(item['serialization_key'] is None for item in arrivals))

            counts = Counter(item['outcome'] for item in arrivals)
            observed = summary['arrivals']
            self.assertEqual(observed['scheduled'], 40)
            self.assertEqual(observed['dispatched'], len(actual))
            self.assertEqual(observed['successful'], len(actual))
            self.assertGreater(observed['dropped'], 0)
            self.assertEqual(observed['expired'], 1)
            self.assertEqual(observed['blocked'], 0)
            self.assertEqual(observed['queue_peak'], 1)
            self.assertEqual(observed['queued_at_deadline'], 1)
            for outcome in ('dispatched', 'dropped', 'expired', 'blocked'):
                self.assertEqual(observed[outcome], counts[outcome])
            self.assertEqual(sum(counts.values()), 40)
            self.assertTrue(observed['conserved'])


class GroupTrafficArrivalTests(unittest.TestCase):
    def run_traffic(self, *, fail_first_group=False, overloaded=False):
        requests, errors = [], []
        histories = {}
        active = set()
        state_lock = threading.Lock()

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                group = body['session_id']
                text = body['message'][0]['text']
                marker = re.search(r'LB_TURN=(\d+) LB_TOKEN=(\w+) LB_PREVIOUS=(\w+)', text)
                turn, token, previous = int(marker[1]), marker[2], marker[3]
                with state_lock:
                    if group in active:
                        errors.append('same group overlapped')
                    if (turn, previous) != histories.get(group, (1, 'none')):
                        errors.append('group turn or previous token changed')
                    active.add(group)
                    requests.append({'group': group, 'turn': turn, 'token': token})
                time.sleep(0.09 if overloaded else 0.01)
                failing = fail_first_group and group.endswith('g0000')
                payload = json.dumps(
                    {
                        'code': 0,
                        'data': {
                            'session_id': group,
                            'reply_to': token,
                            'message': [{'type': 'Plain', 'text': 'BAD' if failing else f'OK GROUP_ACK={token}'}],
                        },
                    }
                ).encode()
                with state_lock:
                    histories[group] = (turn + 1, token)
                    active.remove(group)
                self.send_response(200)
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
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
                                'name': 'chat',
                                'expect': 'OK',
                                'http_group': {
                                    'url': f'http://127.0.0.1:{server.server_port}/sync',
                                    'secret_env': 'LANGBOT_ARRIVAL_TEST_SECRET',
                                    'message': 'ai hello',
                                },
                            }
                        ]
                    )
                )
                output = root / 'output'
                argv = [
                    'regression_traffic',
                    '--lbctl',
                    'unused',
                    '--config',
                    'unused',
                    '--cases',
                    str(cases),
                    '--output',
                    str(output),
                    '--duration',
                    '0.6',
                    '--rps',
                    '40' if overloaded else '10',
                    '--workers',
                    '2',
                    '--groups',
                    '2',
                    '--cooldown',
                    '0',
                    '--arrival-mode',
                    'open-loop',
                    '--queue-capacity',
                    '1' if overloaded else '8',
                ]
                exit_code = 0
                with (
                    patch.object(sys, 'argv', argv),
                    patch.dict('os.environ', {'LANGBOT_ARRIVAL_TEST_SECRET': 'test-only'}),
                    redirect_stdout(io.StringIO()),
                ):
                    try:
                        main()
                    except SystemExit as exc:
                        exit_code = exc.code
                summary = json.loads((output / 'summary.json').read_text())
                rows = [json.loads(line) for line in (output / 'requests.jsonl').read_text().splitlines()]
                arrivals = [json.loads(line) for line in (output / 'arrivals.jsonl').read_text().splitlines()]
                return exit_code, summary, rows, arrivals, requests, errors
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_group_entrypoint_preserves_turns_and_reports_arrival_latency(self):
        code, summary, rows, arrivals, requests, errors = self.run_traffic()
        self.assertEqual(code, 0)
        self.assertEqual(errors, [])
        self.assertEqual(len(requests), 6)
        self.assertEqual(len(rows), 6)
        self.assertEqual(sorted(item['arrival_id'] for item in arrivals), list(range(6)))
        self.assertTrue(summary['arrivals']['conserved'])
        self.assertEqual(summary['arrivals']['dispatched'], len(requests))
        self.assertEqual(summary['cases']['chat']['arrival_latency_count'], 6)
        self.assertGreater(summary['cases']['chat']['arrival_p95_seconds'], 0)
        for row in rows:
            self.assertAlmostEqual(row['arrival_seconds'], row['completed_elapsed'] - row['scheduled_elapsed'])
            self.assertGreaterEqual(row['completed_elapsed'], row['dispatch_elapsed'] + row['seconds'])

    def test_failed_group_blocks_future_arrivals_while_other_group_continues(self):
        code, summary, rows, arrivals, requests, errors = self.run_traffic(fail_first_group=True)
        self.assertEqual(code, 1)
        self.assertEqual(errors, [])
        self.assertEqual(sum(item['group'].endswith('g0000') for item in requests), 1)
        self.assertEqual(summary['arrivals']['blocked'], 2)
        self.assertEqual(summary['arrivals']['failed'], 1)
        self.assertEqual(summary['arrivals']['successful'], 3)
        self.assertEqual(sorted(item['arrival_id'] for item in arrivals), list(range(6)))
        self.assertTrue(summary['arrivals']['conserved'])

    def test_overload_is_retained_as_failure_with_actual_wire_count(self):
        code, summary, rows, arrivals, requests, errors = self.run_traffic(overloaded=True)
        self.assertEqual(code, 1)
        self.assertEqual(errors, [])
        self.assertEqual(summary['arrivals']['scheduled'], 24)
        self.assertEqual(sorted(item['arrival_id'] for item in arrivals), list(range(24)))
        self.assertEqual(summary['arrivals']['dispatched'], len(requests))
        self.assertEqual(len(rows), len(requests))
        self.assertGreater(summary['arrivals']['dropped'] + summary['arrivals']['expired'], 0)
        self.assertTrue(summary['arrivals']['conserved'])

    def test_open_loop_rejects_fixed_request_limit_before_creating_output(self):
        argv = [
            'regression_traffic',
            '--lbctl',
            'unused',
            '--config',
            'unused',
            '--cases',
            'unused',
            '--output',
            'unused',
            '--arrival-mode',
            'open-loop',
            '--max-requests',
            '2',
        ]
        with patch.object(sys, 'argv', argv), self.assertRaises(SystemExit) as raised:
            main()
        self.assertEqual(raised.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
