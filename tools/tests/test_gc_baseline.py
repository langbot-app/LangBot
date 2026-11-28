"""Contract tests for the GC baseline tool.

The measurement itself is host-dependent, so these pin the parts that must hold
on any host: phases leave counts behind rather than references, ``DEBUG_SAVEALL``
does not leak into later phases, ``freeze`` is always undone, and a failing
preload is reported instead of aborting the run.
"""

import gc
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.entrypoints import gc_baseline


class ScanCostTests(unittest.TestCase):
    def test_reports_one_duration_per_sample(self):
        result = gc_baseline.scan_cost(4)

        self.assertEqual(result['samples'], 4)
        self.assertEqual(len(result['durations_ms']), 4)
        self.assertLessEqual(result['min_ms'], result['median_ms'])
        self.assertLessEqual(result['median_ms'], result['max_ms'])

    def test_collected_total_sums_every_sample(self):
        with mock.patch.object(gc_baseline, 'collect', side_effect=[(1.0, 0), (2.0, 5), (3.0, 7)]):
            result = gc_baseline.scan_cost(3)

        self.assertEqual(result['collected_total'], 12)

    def test_zero_collected_still_reports_a_cost(self):
        """A scan that frees nothing still paid for scanning; that is the point."""
        with mock.patch.object(gc_baseline, 'collect', return_value=(12.5, 0)):
            result = gc_baseline.scan_cost(2)

        self.assertEqual(result['collected_total'], 0)
        self.assertEqual(result['median_ms'], 12.5)


class FreezeAttributionTests(unittest.TestCase):
    def test_freezes_before_measuring_and_unfreezes_after(self):
        calls = []
        real_freeze, real_unfreeze = gc.freeze, gc.unfreeze

        def freeze():
            calls.append('freeze')
            real_freeze()

        def unfreeze():
            calls.append('unfreeze')
            real_unfreeze()

        with (
            mock.patch.object(gc_baseline.gc, 'freeze', freeze),
            mock.patch.object(gc_baseline.gc, 'unfreeze', unfreeze),
        ):
            result = gc_baseline.freeze_attribution(2)

        self.assertEqual(calls, ['freeze', 'unfreeze'])
        self.assertEqual(result['samples'], 2)
        self.assertGreaterEqual(result['frozen_objects'], 1)

    def test_unfreezes_even_when_the_scan_raises(self):
        calls = []
        before_freeze_count = gc.get_freeze_count()
        real_freeze, real_unfreeze = gc.freeze, gc.unfreeze

        def freeze():
            calls.append('freeze')
            real_freeze()

        def unfreeze():
            calls.append('unfreeze')
            real_unfreeze()

        with (
            mock.patch.object(gc_baseline.gc, 'freeze', freeze),
            mock.patch.object(gc_baseline.gc, 'unfreeze', unfreeze),
        ):
            with mock.patch.object(gc_baseline, 'scan_cost', side_effect=RuntimeError('boom')):
                with self.assertRaises(RuntimeError):
                    gc_baseline.freeze_attribution(1)

        self.assertEqual(calls, ['freeze', 'unfreeze'])
        self.assertEqual(gc.get_freeze_count(), before_freeze_count)


class SaveallTests(unittest.TestCase):
    def test_collects_types_and_restores_debug_flags(self):
        before = gc.get_debug()
        self.addCleanup(gc.set_debug, before)

        class Leaky:
            def __init__(self):
                self.self_ref = self

        # A reference cycle: only the collector can free this.
        leaked = [Leaky() for _ in range(50)]
        del leaked, Leaky

        result = gc_baseline.saveall_type_sample()

        self.assertGreaterEqual(result['collected'], 1)
        self.assertTrue(any('Leaky' in name for name in result['top_types']))
        self.assertIsInstance(result['duration_ms'], float)
        self.assertEqual(gc.get_debug(), before)

    def test_empty_heap_still_returns_a_well_formed_result(self):
        """A freshly imported heap can legitimately hold no garbage to sample."""
        gc.collect(2)
        result = gc_baseline.saveall_type_sample()

        self.assertIsInstance(result['collected'], int)
        self.assertGreaterEqual(result['collected'], 0)
        self.assertIsInstance(result['top_types'], dict)

    def test_does_not_leave_garbage_behind(self):
        class Leaky:
            def __init__(self):
                self.self_ref = self

        leaked = [Leaky() for _ in range(10)]
        del leaked, Leaky

        result = gc_baseline.saveall_type_sample()

        self.assertEqual(gc.garbage, [])
        self.assertEqual(gc.collect(2), 0)
        self.assertIn('not comparable', result['note'])

    def test_restores_debug_flags_when_collect_raises(self):
        before = gc.get_debug()
        self.addCleanup(gc.set_debug, before)

        with mock.patch.object(gc_baseline.gc, 'collect', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                gc_baseline.saveall_type_sample()

        self.assertEqual(gc.get_debug(), before)


class PreloadTests(unittest.TestCase):
    def test_returns_loaded_names(self):
        result = gc_baseline.preload(['json'])

        self.assertEqual(result['loaded'], ['json'])
        self.assertEqual(result['failed'], [])

    def test_reports_a_failing_module_without_aborting(self):
        result = gc_baseline.preload(['json', 'langbot_definitely_not_a_module', 'platform'])

        self.assertEqual(result['loaded'], ['json', 'platform'])
        self.assertEqual(len(result['failed']), 1)
        self.assertIn('ModuleNotFoundError', result['failed'][0]['error'])

    def test_resolves_profile_and_deduplicates_extra_loads(self):
        modules = gc_baseline.resolve_preload_modules('core', ['langbot.pkg.core.app', 'json'])

        self.assertEqual(modules, ['langbot.pkg.core.app', 'json'])

    def test_unknown_profile_raises_value_error(self):
        with self.assertRaisesRegex(ValueError, 'unknown profile'):
            gc_baseline.resolve_preload_modules('does-not-exist')


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.args = mock.Mock(samples=1, load=[], saveall=False, profile=None)
        self.args.profiles_file = gc_baseline._DEFAULT_PROFILES_PATH

    def test_report_is_json_serializable(self):
        report = gc_baseline.build_report(self.args)

        json.dumps(report)  # must not raise
        self.assertIn('tracked', report['objects'])
        self.assertIn('top_function_modules', report['objects'])
        self.assertIn('scan_share_pct', report['attribution'])
        self.assertIsNone(report['preload']['profile'])

    def test_function_module_histogram_contains_scalars(self):
        histogram = gc_baseline.function_module_histogram(limit=5)

        self.assertGreaterEqual(len(histogram), 1)
        for name, count in histogram.items():
            self.assertIsInstance(name, str)
            self.assertIsInstance(count, int)

    def test_build_report_does_not_duplicate_src_in_sys_path(self):
        gc_baseline.build_report(self.args)
        first_count = sys.path.count(gc_baseline._REPO_SRC_PATH)
        gc_baseline.build_report(self.args)
        second_count = sys.path.count(gc_baseline._REPO_SRC_PATH)

        self.assertEqual(first_count, 1)
        self.assertEqual(second_count, 1)

    def test_attribution_handles_positive_and_zero_baseline(self):
        with (
            mock.patch.object(
                gc_baseline,
                'scan_cost',
                return_value={'samples': 1, 'median_ms': 100.0, 'collected_total': 0},
            ),
            mock.patch.object(
                gc_baseline,
                'freeze_attribution',
                return_value={'samples': 1, 'median_ms': 2.5, 'frozen_objects': 100},
            ),
        ):
            report = gc_baseline.build_report(self.args)
        self.assertEqual(report['attribution']['scan_share_pct'], 97.5)

        with (
            mock.patch.object(
                gc_baseline,
                'scan_cost',
                return_value={'samples': 1, 'median_ms': 0.0, 'collected_total': 0},
            ),
            mock.patch.object(
                gc_baseline,
                'freeze_attribution',
                return_value={'samples': 1, 'median_ms': 0.0, 'frozen_objects': 100},
            ),
        ):
            zero_report = gc_baseline.build_report(self.args)
        self.assertIsNone(zero_report['attribution']['scan_share_pct'])
        self.assertNotIn('scan cost attributable', gc_baseline.summarize(zero_report))

    def test_saveall_is_only_sampled_when_requested(self):
        without = gc_baseline.build_report(self.args)
        self.assertNotIn('saveall', without)

        self.args.saveall = True
        with_saveall = gc_baseline.build_report(self.args)
        self.assertIn('saveall', with_saveall)

    def test_summary_mentions_the_sample_count(self):
        report = gc_baseline.build_report(self.args)
        text = gc_baseline.summarize(report)

        self.assertIn('full scan (n=1)', text)
        self.assertIn('tracked objects:', text)
        self.assertIn('Top function modules:', text)

    def test_summary_lists_preload_failures(self):
        report = gc_baseline.build_report(self.args)
        report['preload']['failed'] = [{'module': 'nope', 'error': 'ModuleNotFoundError: x'}]
        text = gc_baseline.summarize(report)

        self.assertIn('FAILED nope', text)

    def test_summary_lists_saveall_top_types(self):
        report = gc_baseline.build_report(self.args)
        report['saveall'] = {
            'duration_ms': 12.3,
            'collected': 4,
            'top_types': {'example.Leaky': 4},
            'note': 'DEBUG_SAVEALL timings are not comparable to normal scans',
        }
        text = gc_baseline.summarize(report)

        self.assertIn('DEBUG_SAVEALL: 4 unreachable objects, 12.3 ms', text)
        self.assertIn('example.Leaky: 4', text)


class CompareTests(unittest.TestCase):
    def _sample_report(self, *, profile='core', tracked=240000, scan_ms=100.0, frozen_ms=1.0, share=99.0):
        return {
            'platform': {'python': '3.12.14', 'implementation': 'CPython', 'system': 'Linux', 'machine': 'x86_64'},
            'preload': {'profile': profile, 'loaded': ['langbot.pkg.core.app'], 'failed': []},
            'objects': {
                'tracked': tracked,
                'top_types': {'builtins.function': 40000, 'builtins.dict': 30000},
                'top_function_modules': {'lark_oapi': 60000},
            },
            'scan': {'median_ms': scan_ms},
            'frozen_scan': {'median_ms': frozen_ms},
            'attribution': {'scan_share_pct': share},
        }

    def test_computes_deltas_without_warnings_when_context_matches(self):
        before = self._sample_report(tracked=240000, scan_ms=100.0, frozen_ms=1.0, share=99.0)
        after = self._sample_report(tracked=180000, scan_ms=70.0, frozen_ms=1.0, share=98.6)
        after['objects']['top_function_modules'] = {'lark_oapi': 10000}

        comparison = gc_baseline.compare_reports(before, after)

        self.assertEqual(comparison['warnings'], [])
        self.assertEqual(comparison['metrics']['tracked_objects']['delta'], -60000)
        self.assertEqual(comparison['metrics']['scan_median_ms']['delta'], -30.0)
        self.assertEqual(comparison['top_function_module_deltas'][0]['delta'], -50000)

    def test_warns_when_profile_or_platform_differs(self):
        before = self._sample_report(profile='core')
        after = self._sample_report(profile='load-complete')
        after['platform']['system'] = 'Darwin'
        after['objects']['top_function_modules'] = {'litellm.utils': 460}

        comparison = gc_baseline.compare_reports(before, after)
        text = gc_baseline.summarize_comparison(comparison)

        self.assertTrue(any('profile differs' in item for item in comparison['warnings']))
        self.assertTrue(any('platform differs' in item for item in comparison['warnings']))
        self.assertIn('WARNING:', text)
        self.assertIn('outside top-N', text)
        by_name = {item['name']: item for item in comparison['top_function_module_deltas']}
        self.assertIsNone(by_name['lark_oapi']['after'])
        self.assertIsNone(by_name['lark_oapi']['delta'])

    def test_keeps_large_outside_top_n_histogram_entries(self):
        before = {f'shared_{index}': index for index in range(11)}
        after = {name: count + 1 for name, count in before.items()}
        before['large_only'] = 60000

        deltas = gc_baseline._histogram_deltas(before, after, limit=10)

        self.assertIn('large_only', {item['name'] for item in deltas})

    def test_negative_baseline_uses_magnitude_for_percent_delta(self):
        delta = gc_baseline._metric_delta(-10.0, 10.0)

        self.assertEqual(delta['delta'], 20.0)
        self.assertEqual(delta['delta_pct'], 200.0)

    def test_rejects_malformed_report_shapes(self):
        with self.assertRaisesRegex(ValueError, 'before report must be a JSON object'):
            gc_baseline.compare_reports([], self._sample_report())

        malformed = self._sample_report()
        malformed['preload'] = None
        with self.assertRaisesRegex(ValueError, 'before report.preload must be a JSON object'):
            gc_baseline.compare_reports(malformed, self._sample_report())


class ProfileTests(unittest.TestCase):
    def test_shipped_profiles_are_valid_and_documented(self):
        path = Path(__file__).resolve().parents[1] / 'profiles' / 'gc-baseline.json'
        data = json.loads(path.read_text())

        self.assertEqual(data['version'], 1)
        for name, profile in data['profiles'].items():
            self.assertIsInstance(profile['modules'], list, name)
            self.assertTrue(profile['description'].strip(), name)
        # Every profile must say what population it represents; comparing a
        # `core` run against the #2852 baseline is the mistake this guards.
        self.assertIn('load-complete', data['profiles'])
        self.assertIn('Not the #2852 baseline', data['profiles']['core']['description'])


class MainTests(unittest.TestCase):
    def test_samples_must_be_positive(self):
        with self.assertRaises(SystemExit):
            gc_baseline.main(['measure', '--samples', '0'])

    def test_unknown_profile_exits(self):
        with self.assertRaises(SystemExit):
            gc_baseline.main(['measure', '--profile', 'nonexistent', '--samples', '1'])

    def test_malformed_profiles_file_exits_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'profiles.json'
            path.write_text(json.dumps({'profiles': {'bad': {'modules': [{}]}}}), encoding='utf-8')

            with contextlib.redirect_stderr(io.StringIO()) as error:
                with self.assertRaises(SystemExit):
                    gc_baseline.main(
                        ['measure', '--profile', 'bad', '--profiles-file', str(path), '--samples', '1']
                    )

            self.assertIn('modules must be a list of module names', error.getvalue())

    def test_json_flag_emits_json(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            gc_baseline.main(['measure', '--profile', 'bare', '--samples', '1', '--json'])

        report = json.loads(buffer.getvalue())
        self.assertEqual(report['preload']['profile'], 'bare')

    def test_compare_cli_emits_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            before_path = Path(tmpdir) / 'before.json'
            after_path = Path(tmpdir) / 'after.json'
            for target in (before_path, after_path):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    gc_baseline.main(['measure', '--profile', 'bare', '--samples', '1', '--json'])
                target.write_text(buffer.getvalue(), encoding='utf-8')

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                exit_code = gc_baseline.main(['compare', str(before_path), str(after_path), '--json'])

            self.assertEqual(exit_code, 0)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload['warnings'], [])
            self.assertIn('tracked_objects', payload['metrics'])

    def test_compare_cli_rejects_malformed_json_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            before_path = Path(tmpdir) / 'before.json'
            after_path = Path(tmpdir) / 'after.json'
            before_path.write_text('[]', encoding='utf-8')
            after_path.write_text('{}', encoding='utf-8')

            with contextlib.redirect_stderr(io.StringIO()) as error:
                with self.assertRaises(SystemExit):
                    gc_baseline.main(['compare', str(before_path), str(after_path)])

            self.assertIn('before report must be a JSON object', error.getvalue())


if __name__ == '__main__':
    unittest.main()
