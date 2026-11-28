"""A gate must fail closed on timeout, missing verdict, and inner failure."""

import os
import json
from pathlib import Path
import signal
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from tools.entrypoints.regression_gate import supervise


class GateTest(unittest.TestCase):
    def test_success_records_elapsed_time_and_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'gate'
            code = (
                'from pathlib import Path; import json; '
                f'p=Path({str(output / "suite")!r}); p.mkdir(); '
                '(p/"summary.json").write_text(json.dumps({"passed":True,"requests":1}))'
            )
            result = supervise([sys.executable, '-c', code], output, 5, {'test': os.getpid()})
            self.assertTrue(result['passed'])
            self.assertLess(result['elapsed_seconds'], 5)
            self.assertGreater(result['resource_peaks']['test']['rss_bytes'], 0)
            samples = [json.loads(line) for line in (output / 'resources.jsonl').read_text().splitlines()]
            self.assertTrue(samples)
            self.assertIn('system', samples[0])
            self.assertIn('memory', samples[0]['system'])
            observations = [json.loads(line) for line in (output / 'observations.jsonl').read_text().splitlines()]
            self.assertTrue(observations)
            self.assertEqual(observations[0]['source'], 'regression_gate')
            manifest = json.loads((output / 'run-manifest.json').read_text())
            self.assertEqual(manifest['completeness'], 'complete')
            self.assertEqual(manifest['trace_index']['traces'], 0)
            self.assertTrue((output / 'trace-index.json').is_file())

    def test_timeout_is_failed_without_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            result = supervise([sys.executable, '-c', 'import time; time.sleep(30)'], Path(directory) / 'gate', 0.1, {})
            self.assertFalse(result['passed'])
            self.assertTrue(result['timed_out'])
            self.assertLess(result['elapsed_seconds'], 2)

    def test_teardown_failure_overrides_successful_smoke_verdict(self):
        from tools.entrypoints.regression_ci import main

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'ci'

            def fail_teardown(args):
                verdict = args.output / 'gate' / 'gate.json'
                verdict.parent.mkdir(parents=True)
                verdict.write_text(json.dumps({'passed': True}))
                raise RuntimeError('sandbox teardown failed')

            with (
                patch('tools.entrypoints.regression_ci.run', side_effect=fail_teardown),
                patch.object(
                    sys,
                    'argv',
                    [
                        'tools.entrypoints.regression_ci',
                        '--output',
                        str(output),
                        '--lbctl',
                        'unused',
                        '--plugins',
                        'unused',
                    ],
                ),
                self.assertRaises(RuntimeError),
            ):
                main()
            result = json.loads((output / 'gate/gate.json').read_text())
            self.assertFalse(result['passed'])
            self.assertIn('sandbox teardown failed', result['infrastructure_error'])

    def test_gate_requires_both_zero_process_exit_and_successful_business_verdict(self):
        for process_exit, suite_passed in ((23, True), (0, False)):
            with self.subTest(process_exit=process_exit, suite_passed=suite_passed):
                with tempfile.TemporaryDirectory() as directory:
                    output = Path(directory) / 'gate'
                    code = (
                        'from pathlib import Path; import json; '
                        f'p=Path({str(output / "suite")!r}); p.mkdir(); '
                        f'(p/"summary.json").write_text(json.dumps({{"passed": {suite_passed!r}, "requests": 7}})); '
                        f'raise SystemExit({process_exit})'
                    )

                    result = supervise([sys.executable, '-c', code], output, 5, {})
                    persisted = json.loads((output / 'gate.json').read_text())

                    self.assertFalse(result['passed'])
                    self.assertFalse(result['timed_out'])
                    self.assertEqual(result['exit_code'], process_exit)
                    self.assertEqual(result['requests'], 7)
                    self.assertEqual(persisted, result)

    def test_zero_exit_without_business_verdict_is_failed(self):
        with tempfile.TemporaryDirectory() as directory:
            result = supervise([sys.executable, '-c', 'pass'], Path(directory) / 'gate', 5, {})
            self.assertFalse(result['passed'])

    def test_gate_periodic_observations_are_classified_as_global_not_unindexed(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'gate'
            code = (
                'import json, time; from pathlib import Path; '
                'time.sleep(0.15); '
                f'p=Path({str(output / "suite")!r}); p.mkdir(); '
                '(p/"summary.json").write_text(json.dumps({"passed":True,"requests":1}))'
            )
            result = supervise([sys.executable, '-c', code], output, 5, {})
            self.assertTrue(result['passed'])
            observations = [json.loads(line) for line in (output / 'observations.jsonl').read_text().splitlines()]
            self.assertTrue(observations)
            self.assertTrue(all(sample['scope'] == 'global' and sample['trace_id'] is None for sample in observations))
            index = json.loads((output / 'trace-index.json').read_text())
            self.assertEqual(index['global_observations'], len(observations))
            self.assertEqual(index['missing_trace_observations'], 0)
            self.assertEqual(index['unindexed_records'], 0)
            manifest = json.loads((output / 'run-manifest.json').read_text())
            self.assertEqual(manifest['completeness'], 'complete')
            self.assertEqual(manifest['trace_index']['global_observations'], len(observations))
            self.assertEqual(manifest['trace_index']['unindexed_records'], 0)

    def test_timeout_reconciles_child_inflight_actions_into_interrupted_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'gate'
            actions_path = output / 'suite' / 'actions.jsonl'
            code = (
                'import time; from pathlib import Path; '
                'from tools.regression.observability_contract import ActionWriter; '
                f'w = ActionWriter(Path({str(actions_path)!r})); '
                'w.begin("suite_action", trace_id="Y-1111222233334444"); '
                'time.sleep(30)'
            )
            result = supervise([sys.executable, '-c', code], output, 0.35, {})
            self.assertFalse(result['passed'])
            self.assertTrue(result['timed_out'])
            records = [json.loads(line) for line in actions_path.read_text().splitlines()]
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]['status'], 'interrupted')
            self.assertEqual(records[0]['trace_id'], 'Y-1111222233334444')
            self.assertEqual(records[0]['metadata']['interrupt_reason'], 'timeout')
            manifest = json.loads((output / 'run-manifest.json').read_text())
            self.assertEqual(manifest['completeness'], 'interrupted')
            self.assertEqual(manifest['interrupted_reason'], 'timeout')
            self.assertEqual(manifest['actions']['interrupted'], 1)
            self.assertEqual(manifest['trace_index']['traces'], 1)

    def test_child_sigkill_reconciles_inflight_actions_into_interrupted_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'gate'
            actions_path = output / 'suite' / 'actions.jsonl'
            code = (
                'import os, signal; from pathlib import Path; '
                'from tools.regression.observability_contract import ActionWriter; '
                f'w = ActionWriter(Path({str(actions_path)!r})); '
                'w.begin("killed_action", trace_id="Y-9999888877776666"); '
                'os.kill(os.getpid(), signal.SIGKILL)'
            )
            result = supervise([sys.executable, '-c', code], output, 5, {})
            self.assertFalse(result['passed'])
            self.assertEqual(result['exit_code'], -signal.SIGKILL)
            records = [json.loads(line) for line in actions_path.read_text().splitlines()]
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]['status'], 'interrupted')
            self.assertEqual(records[0]['trace_id'], 'Y-9999888877776666')
            self.assertEqual(records[0]['metadata']['interrupt_reason'], 'sigkill')
            manifest = json.loads((output / 'run-manifest.json').read_text())
            self.assertEqual(manifest['completeness'], 'interrupted')
            self.assertEqual(manifest['interrupted_reason'], 'sigkill')
            self.assertEqual(manifest['actions']['interrupted'], 1)

    def test_gate_supervising_regression_traffic_sigterm_marks_gate_manifest_interrupted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'gate'
            traffic_output = output / 'suite' / 'phase'
            ready_path = root / 'cli-ready.txt'
            pid_path = root / 'traffic.pid'
            cli = root / 'lbctl-slow'
            cli.write_text(
                f'#!{sys.executable}\n'
                'import os, time; from pathlib import Path; '
                f'Path({str(pid_path)!r}).write_text(str(os.getppid())); '
                f'Path({str(ready_path)!r}).write_text("ready"); '
                'time.sleep(2)\n'
            )
            cli.chmod(0o700)
            cases = root / 'cases.json'
            cases.write_text(
                json.dumps([{'name': 'chat', 'args': ['pipeline', 'run', 'demo', '--message', 'hi'], 'expect': 'OK'}])
            )
            sent = threading.Event()

            def send_sigterm():
                deadline = time.monotonic() + 5
                while not ready_path.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                if ready_path.exists() and pid_path.exists():
                    os.kill(int(pid_path.read_text().strip()), signal.SIGTERM)
                    sent.set()

            killer = threading.Thread(target=send_sigterm, daemon=True)
            killer.start()
            command = [
                sys.executable,
                '-m',
                'tools.entrypoints.regression_traffic',
                '--lbctl',
                str(cli),
                '--config',
                'unused',
                '--cases',
                str(cases),
                '--output',
                str(traffic_output),
                '--duration',
                '5',
                '--rps',
                '1',
                '--workers',
                '1',
                '--cooldown',
                '0',
                '--arrival-mode',
                'open-loop',
            ]
            result = supervise(command, output, 10, {})
            killer.join(timeout=5)
            self.assertTrue(sent.is_set())
            self.assertFalse(result['passed'])
            self.assertEqual(result['exit_code'], -signal.SIGTERM)
            manifest = json.loads((output / 'run-manifest.json').read_text())
            self.assertEqual(manifest['completeness'], 'interrupted')
            self.assertEqual(manifest['interrupted_reason'], 'cancelled')
            self.assertGreaterEqual(manifest['actions']['interrupted'], 1)
            self.assertGreaterEqual(manifest['trace_index']['traces'], 1)

    def test_gate_collects_existing_actions_jsonl_after_drain_timeout_exit_one(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'gate'
            actions_path = output / 'suite' / 'actions.jsonl'
            code = (
                'from pathlib import Path; '
                'from tools.regression.observability_contract import ActionWriter; '
                f'w = ActionWriter(Path({str(actions_path)!r})); '
                'w.begin("drain_op", trace_id="Y-5555666677778888"); '
                'w.interrupt_active(reason="timeout"); '
                'raise SystemExit(1)'
            )
            result = supervise([sys.executable, '-c', code], output, 5, {})
            self.assertFalse(result['passed'])
            self.assertEqual(result['exit_code'], 1)
            manifest = json.loads((output / 'run-manifest.json').read_text())
            self.assertEqual(manifest['completeness'], 'interrupted')
            self.assertEqual(manifest['actions']['interrupted'], 1)
            self.assertEqual(manifest['actions']['interrupt_reasons'], {'timeout': 1})
            self.assertEqual(manifest['trace_index']['traces'], 1)

    def test_gate_survives_sigkill_truncated_inflight_jsonl_and_marks_interrupted(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'gate'
            actions_path = output / 'suite' / 'actions.jsonl'
            code = (
                'import os, signal; from pathlib import Path; '
                'from tools.regression.observability_contract import ActionWriter, inflight_journal_path; '
                f'p = Path({str(actions_path)!r}); '
                'w = ActionWriter(p); '
                'w.begin("good_action", trace_id="Y-aaaa1111bbbb2222"); '
                'j = inflight_journal_path(p); '
                'j.write_text(j.read_text() + "{\\"event\\":\\"action_started\\",\\"action_id\\":\\"a-cut"); '
                'os.kill(os.getpid(), signal.SIGKILL)'
            )
            result = supervise([sys.executable, '-c', code], output, 5, {})
            self.assertFalse(result['passed'])
            self.assertEqual(result['exit_code'], -signal.SIGKILL)
            manifest = json.loads((output / 'run-manifest.json').read_text())
            self.assertEqual(manifest['completeness'], 'interrupted')
            self.assertEqual(manifest['interrupted_reason'], 'sigkill')
            self.assertGreaterEqual(manifest['actions']['interrupted'], 2)
            self.assertEqual(manifest['actions']['corrupt_lines'], 1)
            self.assertEqual(manifest['trace_index']['traces'], 1)


if __name__ == '__main__':
    unittest.main()
