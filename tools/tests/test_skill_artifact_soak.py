"""The repeat harness must not convert partial pytest runs into acceptance."""

import json
import signal
import subprocess
import sys
import time
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from tools.entrypoints.skill_artifact_soak import main, report_counts, run_scenario


class ReportCountsTests(unittest.TestCase):
    def count(self, xml):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.xml'
            path.write_text(xml)
            return report_counts(path)

    def test_nested_suites_count_cases_once(self):
        self.assertEqual(
            self.count('<testsuites tests="2"><testsuite tests="2"><testcase/><testcase/></testsuite></testsuites>'),
            {'tests': 2, 'failures': 0, 'errors': 0, 'skipped': 0},
        )

    def test_skips_and_failures_remain_visible(self):
        counts = self.count(
            '<testsuite><testcase><skipped type="pytest.xfail"/></testcase>'
            '<testcase><failure/></testcase><testcase><error/></testcase></testsuite>'
        )
        self.assertEqual(counts, {'tests': 3, 'failures': 1, 'errors': 1, 'skipped': 1})

    def test_empty_report_has_no_tests(self):
        self.assertEqual(self.count('<testsuites/>')['tests'], 0)


def _wait_for(path):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if path.exists():
            return json.loads(path.read_text())
        time.sleep(0.02)
    raise AssertionError('Scenario never started its detached child')


def _tree_command(pid_file, *, exit_parent=False):
    child = 'import os,signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)'
    script = (
        'import json,os,subprocess,sys,time; '
        f'child=subprocess.Popen([sys.executable,"-c",{child!r}],start_new_session=True); '
        f'open({str(pid_file)!r},"w").write(json.dumps([os.getpid(),child.pid])); '
        + ('time.sleep(0.15)' if exit_parent else 'time.sleep(60)')
    )
    return [sys.executable, '-c', script]


def _assert_gone(pids):
    assert all(not Path(f'/proc/{pid}').exists() for pid in pids), f'Leaked descendants: {pids}'


@unittest.skipUnless(sys.platform == 'linux', 'Linux subreaper contract')
class ProcessCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def test_sigint_cleans_owned_tree(self):
        self._check_harness_interrupt(signal.SIGINT)

    def test_sigterm_cleans_owned_tree(self):
        self._check_harness_interrupt(signal.SIGTERM)

    def test_timeout_reaps_detached_term_ignoring_child_and_preserves_unrelated(self):
        tmp_path = self.directory
        pid_file = tmp_path / 'pids.json'
        unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        try:
            with (tmp_path / 'scenario.log').open('w') as output:
                code, error = run_scenario(_tree_command(pid_file), output, timeout=0.8)
            assert (code, error) == (124, 'scenario timeout')
            _assert_gone(_wait_for(pid_file))
            assert unrelated.poll() is None
        finally:
            unrelated.terminate()
            unrelated.wait(timeout=5)

    def test_successful_parent_with_leaked_detached_child_fails_and_cleans(self):
        tmp_path = self.directory
        pid_file = tmp_path / 'pids.json'
        with (tmp_path / 'scenario.log').open('w') as output:
            code, error = run_scenario(_tree_command(pid_file, exit_parent=True), output, timeout=8)
        assert code == 1 and error is None
        _assert_gone(_wait_for(pid_file))
        assert 'left child processes running' in (tmp_path / 'scenario.log').read_text()

    def _check_harness_interrupt(self, signum):
        tmp_path = self.directory
        pid_file = tmp_path / 'pids.json'
        result_file = tmp_path / 'result.json'
        command = _tree_command(pid_file)
        script = (
            'import json; from tools.entrypoints.skill_artifact_soak import run_scenario; '
            f'output=open({str(tmp_path / "scenario.log")!r},"w"); '
            f'result=run_scenario({command!r},output,30); '
            f'open({str(result_file)!r},"w").write(json.dumps(result))'
        )
        harness = subprocess.Popen([sys.executable, '-c', script])
        try:
            pids = _wait_for(pid_file)
            # Allow the detached child to install its TERM handler before interruption.
            time.sleep(0.15)
            harness.send_signal(signum)
            assert harness.wait(timeout=10) == 0
            assert json.loads(result_file.read_text()) == [128 + signum, 'scenario interrupted']
            _assert_gone(pids)
        finally:
            if harness.poll() is None:
                harness.terminate()
                harness.wait(timeout=10)

    def test_clean_scenario_retains_exit_status(self):
        tmp_path = self.directory
        with (tmp_path / 'scenario.log').open('w') as output:
            assert run_scenario([sys.executable, '-c', 'print("clean")'], output, timeout=5) == (0, None)
        assert (tmp_path / 'scenario.log').read_text().strip() == 'clean'


@unittest.skipUnless(sys.platform == 'linux', 'Linux pidfd contract')
class CleanupRaceTests(unittest.TestCase):
    def test_missing_pidfd_fails_before_spawning_scenario(self):
        from tools.entrypoints import skill_artifact_soak as harness

        with (
            patch.object(harness.os, 'pidfd_open', side_effect=OSError('unavailable')),
            patch.object(harness.subprocess, 'Popen') as spawn,
        ):
            with self.assertRaisesRegex(RuntimeError, 'requires Linux pidfd'):
                harness.run_scenario(['unused'], None, 1)
        spawn.assert_not_called()

    def test_empty_proc_snapshot_does_not_override_live_waitpid_child(self):
        from tools.entrypoints import skill_artifact_soak as harness

        with (
            patch.object(harness, '_reap_children', side_effect=[False, False, True]) as reap,
            patch.object(harness, '_descendants', return_value={}),
            patch.object(harness, '_signal_owned'),
            patch.object(harness.time, 'sleep'),
        ):
            self.assertTrue(harness._cleanup_descendants())
        self.assertEqual(reap.call_count, 3)

    def test_pidfd_identity_mismatch_is_not_signaled(self):
        from tools.entrypoints import skill_artifact_soak as harness

        fields = ['S', '1'] + ['0'] * 17 + ['new-start']
        with (
            patch.object(harness.os, 'pidfd_open', return_value=99),
            patch.object(harness.Path, 'read_text', return_value='123 (child) ' + ' '.join(fields)),
            patch.object(harness.signal, 'pidfd_send_signal') as send,
            patch.object(harness.os, 'close') as close,
        ):
            harness._signal_owned({123: 'old-start'}, signal.SIGTERM)
        send.assert_not_called()
        close.assert_called_once_with(99)


class ManifestTests(unittest.TestCase):
    def test_timeout_keeps_reason_even_without_junit(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'evidence'
            with (
                patch('subprocess.check_output', side_effect=['candidate\n', '']),
                patch('tools.entrypoints.skill_artifact_soak.run_scenario', return_value=(124, 'scenario timeout')),
            ):
                self.assertEqual(main(['--output', str(output), '--duration', '1', 'test_case.py']), 1)
            row = json.loads((output / 'rounds.ndjson').read_text())
            self.assertEqual(row['exit_code'], 124)
            self.assertEqual(row['error'], 'scenario timeout')
            self.assertEqual(row['status'], 'failed')
            self.assertIn('report_error', row)

    def test_supervision_failure_is_recorded_not_passed(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'evidence'
            with (
                patch('subprocess.check_output', side_effect=['candidate\n', '']),
                patch('tools.entrypoints.skill_artifact_soak.run_scenario', side_effect=RuntimeError('cleanup failed')),
            ):
                self.assertEqual(main(['--output', str(output), '--duration', '1', 'test_case.py']), 1)
            row = json.loads((output / 'rounds.ndjson').read_text())
            self.assertEqual(row['status'], 'failed')
            self.assertIn('supervision failed', row['error'])


if __name__ == '__main__':
    unittest.main()
