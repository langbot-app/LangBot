"""Tests for resource evidence that is safe to collect in CI and containers."""

import tempfile
from pathlib import Path
import unittest

from tools.regression.observations import read_process_snapshot, read_system_snapshot


class ObservationTests(unittest.TestCase):
    def test_process_snapshot_includes_io_counters(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            process = root / '123'
            (process / 'task' / '123').mkdir(parents=True)
            (process / 'task' / '123' / 'children').write_text('')
            (process / 'status').write_text('VmRSS: 12 kB\nThreads: 3\n')
            # The parser only needs the command name separator and utime/stime
            # positions from /proc/<pid>/stat.
            (process / 'stat').write_text('123 (python) S 0 0 0 0 0 0 0 0 0 0 7 5\n')
            (process / 'io').write_text('read_bytes: 1024\nwrite_bytes: 2048\nsyscr: 4\nsyscw: 5\n')
            (process / 'fd').mkdir()
            snapshot = read_process_snapshot(123, proc_root=root, clock_ticks=100)
            self.assertEqual(snapshot['rss_bytes'], 12 * 1024)
            self.assertEqual(snapshot['threads'], 3)
            self.assertEqual(snapshot['io_read_bytes'], 1024)
            self.assertEqual(snapshot['io_write_bytes'], 2048)
            self.assertEqual(snapshot['io_syscr'], 4)
            self.assertEqual(snapshot['io_syscw'], 5)
            self.assertEqual(snapshot['cpu_seconds'], 0.12)

    def test_system_snapshot_keeps_unavailable_metrics_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cgroup = root / 'cgroup'
            cgroup.mkdir()
            (cgroup / 'memory.current').write_text('4096\n')
            (cgroup / 'memory.max').write_text('max\n')
            (cgroup / 'cpu.stat').write_text('usage_usec 12\nnr_throttled 2\nthrottled_usec 7\n')
            (cgroup / 'io.stat').write_text('8:0 rbytes=100 wbytes=200\n')
            (root / 'meminfo').write_text('MemTotal:       100 kB\nMemAvailable:    25 kB\n')
            (root / 'pressure').mkdir()
            (root / 'pressure' / 'cpu').write_text('some avg10=1.00 avg60=2.00 avg300=3.00 total=4\n')
            snapshot = read_system_snapshot(proc_root=root, cgroup_root=cgroup)
            self.assertEqual(snapshot['cgroup']['memory_current_bytes'], 4096)
            self.assertNotIn('memory_max_bytes', snapshot['cgroup'])
            self.assertEqual(snapshot['cgroup']['cpu_nr_throttled'], 2)
            self.assertEqual(snapshot['cgroup']['io_read_bytes'], 100)
            self.assertEqual(snapshot['memory']['MemAvailable'], 25 * 1024)
            self.assertEqual(snapshot['pressure']['cpu']['some_avg10'], 1)
            self.assertEqual(snapshot['pressure']['memory'], {})


if __name__ == '__main__':
    unittest.main()
