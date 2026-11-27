"""Read-only memory evidence tests using a deliberately small fake proc tree."""

import json
from pathlib import Path
import tempfile
import unittest

from tools.regression.vdb_benchmark_memory import (
    CgroupTracker,
    MemorySampler,
    ProcessIdentity,
    partition_stages,
    read_identity,
    role_snapshot,
    summarize_memory,
)


def fake_process(proc, pid, ticks, rss=64, child=None, *, pss=27, cgroup='/job'):
    directory = proc / str(pid)
    (directory / 'task' / str(pid)).mkdir(exist_ok=True, parents=True)
    tokens = ['S'] + ['0'] * 18 + [str(ticks)]
    (directory / 'stat').write_text(f'{pid} (has ) in comm ) ' + ' '.join(tokens))
    metric = f'VmRSS: {rss} kB\n' if rss is not None else ''
    (directory / 'status').write_text(metric + 'VmHWM: 130 kB\nRssAnon: 47 kB\n')
    if pss is not None:
        (directory / 'smaps_rollup').write_text(f'Pss: {pss} kB\n')
    (directory / 'task' / str(pid) / 'children').write_text(str(child) if child else '')
    (directory / 'cgroup').write_text(f'0::{cgroup}\n')
    return directory


def snapshot(proto, phase, role, **fields):
    result = {
        'monotonic_ns': proto,
        'finished_monotonic_ns': proto + 1,
        'phase': phase,
        'roles': {'core': role},
        'host_mem_available_bytes': None,
        'cgroups': [],
    }
    result.update(fields)
    return result


class MemorySamplerTest(unittest.TestCase):
    def test_exact_identity_discovers_worker_but_excludes_other_owned_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = Path(tmp)
            fake_process(proc, 42, 700, rss=90, child=43, pss=71)
            fake_process(proc, 43, 701, rss=50, child=44, pss=None)
            fake_process(proc, 44, 702, rss=40)
            root = read_identity(proc, 42)
            self.assertEqual(root, ProcessIdentity(42, 700))
            role, descendants = role_snapshot(proc, root, set(), pss_sampled=True, protected={ProcessIdentity(44, 702)})
            self.assertTrue(role['discovery_complete'])
            self.assertEqual(role['rss_tree_sum_bytes'], 140 * 1024)
            self.assertIsNone(role['pss_tree_bytes'])
            self.assertEqual(descendants, {ProcessIdentity(43, 701)})
            fake_process(proc, 42, 900)
            recycled, _ = role_snapshot(proc, root, descendants, pss_sampled=True, protected={ProcessIdentity(44, 702)})
            self.assertFalse(recycled['root_alive'])
            self.assertIsNone(recycled['rss_tree_sum_bytes'])
            self.assertEqual([x['pid'] for x in recycled['processes']], [43])

    def test_cgroup_retained_after_root_exit_and_unavailable_events_not_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc, mount = root / 'proc', root / 'sys'
            (proc / 'self').mkdir(parents=True)
            group = mount / 'job'
            group.mkdir(parents=True)
            (proc / 'self/mountinfo').write_text(f'29 24 0:25 / {mount} rw - cgroup2 cgroup rw\n')
            fake_process(proc, 42, 700)
            (group / 'memory.current').write_text('10000')
            (group / 'memory.max').write_text('max')
            (group / 'memory.events').write_text('oom 0\noom_kill 0\n')
            levels = CgroupTracker(proc)
            roots = {'core': ProcessIdentity(42, 700)}
            before = levels.snapshot(roots)
            self.assertIsNone(before[0]['max_bytes'])
            self.assertTrue(before[0]['unlimited'])
            (proc / '42/stat').unlink()
            (group / 'memory.events').write_text('oom 1\noom_kill 1\n')
            after = levels.snapshot(roots)
            exited, _ = role_snapshot(proc, roots['core'], set(), pss_sampled=True)
            summary = summarize_memory(
                [snapshot(1, 'baseline', exited, cgroups=before), snapshot(2, 'benchmark', exited, cgroups=after)]
            )
            self.assertTrue(summary['cgroup_oom_kill_observed'])
            self.assertEqual(summary['cgroup_v2'][0]['events_delta']['oom_kill'], 1)
            self.assertIsNone(summarize_memory([snapshot(1, 'benchmark', exited)])['cgroup_oom_kill_observed'])

    def test_complete_monotonic_stage_and_short_or_incomplete_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'events.jsonl'
            events = [
                {'stage': 'case:baseline', 'event': 'start', 'monotonic_ns': 10},
                {'stage': 'case:baseline', 'event': 'end', 'monotonic_ns': 14},
                {'stage': 'case:upload', 'event': 'start', 'monotonic_ns': 15},
                {'stage': 'case:upload', 'event': 'end', 'monotonic_ns': 15},
                {'stage': 'case:ingest', 'event': 'start', 'monotonic_ns': 17},
            ]
            path.write_text(''.join(json.dumps(r) + '\n' for r in events))
            samples, counts, errors = partition_stages(
                [snapshot(n, 'benchmark', {}) for n in (9, 10, 13, 15, 18)], path
            )
            self.assertEqual(counts['case:baseline'], 2)
            self.assertEqual(counts['case:ingest'], 0)
            self.assertEqual(samples[0]['phase'], 'benchmark')
            self.assertEqual(samples[-1]['phase'], 'benchmark')
            self.assertIn('Incomplete stage event window', errors)

    def test_sampler_records_baseline_work_recovery_and_fails_closed_missing_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc = root / 'proc'
            fake_process(proc, 42, 700, 60, child=43)
            fake_process(proc, 43, 800, 50)
            fake_process(proc, 44, 900, 60)
            (proc / 'meminfo').write_text('MemAvailable: 991 kB\n')
            output = root / 'result'
            with MemorySampler(output, roots={'core': 42, 'runtime': 44}, interval_seconds=0.05, proc_root=proc) as m:
                m.mark('baseline')
                self.assertTrue(m.wait_for_samples('baseline', minimum=2))
                fake_process(proc, 42, 700, 80, child=43)
                m.mark('benchmark')
                self.assertTrue(m.wait_for_samples('benchmark', minimum=2))
                fake_process(proc, 42, 700, 64, child=43)
                m.mark('recovery')
                self.assertTrue(m.wait_for_samples('recovery', minimum=2))
            data = json.loads((output / 'memory-summary.json').read_text())
            self.assertTrue(data['sampling_complete'])
            self.assertEqual(
                data['roles']['core']['benchmark']['root_peak_delta_from_baseline_median_bytes'], 20 * 1024
            )
            self.assertEqual(data['roles']['core']['recovery']['root_last_delta_from_baseline_median_bytes'], 4 * 1024)
            self.assertIsNone(data['cgroup_oom_kill_observed'])
            self.assertEqual(data['host_mem_available_min_bytes'], 991 * 1024)
            output = root / 'missing'
            with MemorySampler(output, roots={'core': 42, 'runtime': 45}, interval_seconds=0.05, proc_root=proc) as m:
                m.mark('baseline')
                self.assertFalse(m.wait_for_samples('baseline', minimum=1, timeout=0.18))
            data = json.loads((output / 'memory-summary.json').read_text())
            self.assertFalse(data['sampling_complete'])
            self.assertEqual(data['roles']['runtime']['baseline']['root_rss_samples'], 0)
