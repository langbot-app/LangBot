"""A gate must fail closed on timeout, missing verdict, and inner failure."""

import os
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from regression_gate import supervise


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

    def test_timeout_is_failed_without_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            result = supervise([sys.executable, '-c', 'import time; time.sleep(30)'], Path(directory) / 'gate', 0.1, {})
            self.assertFalse(result['passed'])
            self.assertTrue(result['timed_out'])
            self.assertLess(result['elapsed_seconds'], 2)

    def test_teardown_failure_overrides_successful_smoke_verdict(self):
        from regression_ci import main

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'ci'

            def fail_teardown(args):
                verdict = args.output / 'gate' / 'gate.json'
                verdict.parent.mkdir(parents=True)
                verdict.write_text(json.dumps({'passed': True}))
                raise RuntimeError('sandbox teardown failed')

            with (
                patch('regression_ci.run', side_effect=fail_teardown),
                patch.object(
                    sys, 'argv', ['regression_ci', '--output', str(output), '--lbctl', 'unused', '--plugins', 'unused']
                ),
                self.assertRaises(RuntimeError),
            ):
                main()
            result = json.loads((output / 'gate/gate.json').read_text())
            self.assertFalse(result['passed'])
            self.assertIn('sandbox teardown failed', result['infrastructure_error'])

    def test_zero_exit_without_business_verdict_is_failed(self):
        with tempfile.TemporaryDirectory() as directory:
            result = supervise([sys.executable, '-c', 'pass'], Path(directory) / 'gate', 5, {})
            self.assertFalse(result['passed'])


if __name__ == '__main__':
    unittest.main()
