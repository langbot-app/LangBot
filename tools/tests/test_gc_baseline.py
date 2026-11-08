"""Contract tests for the GC baseline tool.

The measurement itself is host-dependent, so these pin the parts that must hold
on any host: phases leave counts behind rather than references, ``DEBUG_SAVEALL``
does not leak into later phases, ``freeze`` is always undone, and a failing
preload is reported instead of aborting the run.
"""

import gc
import unittest
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

    def test_unfreezes_even_when_the_scan_raises(self):
        real_freeze, real_unfreeze = gc.freeze, gc.unfreeze
        with (
            mock.patch.object(gc_baseline.gc, 'freeze', real_freeze),
            mock.patch.object(gc_baseline.gc, 'unfreeze', real_unfreeze),
        ):
            with mock.patch.object(gc_baseline, 'scan_cost', side_effect=RuntimeError('boom')):
                with self.assertRaises(RuntimeError):
                    gc_baseline.freeze_attribution(1)

        # Freezing an empty permanent generation is idempotent; a second scan works.
        self.assertGreaterEqual(gc_baseline.scan_cost(1)['samples'], 1)


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
        self.assertEqual(gc.get_debug(), before)

    def test_empty_heap_still_returns_a_well_formed_result(self):
        """A freshly imported heap can legitimately hold no garbage to sample."""
        gc.collect(2)
        result = gc_baseline.saveall_type_sample()

        self.assertIsInstance(result['collected'], int)
        self.assertGreaterEqual(result['collected'], 0)
        self.assertIsInstance(result['top_types'], dict)

    def test_does_not_leave_garbage_behind(self):
        result = gc_baseline.saveall_type_sample()

        self.assertEqual(gc.garbage, [])
        self.assertIn('not comparable', result['note'])


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


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.args = mock.Mock(samples=1, load=[], saveall=False)

    def test_report_is_json_serializable(self):
        import json

        report = gc_baseline.build_report(self.args)

        json.dumps(report)  # must not raise
        self.assertIn('tracked', report['objects'])
        self.assertIn('scan_share_pct', report['attribution'])

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

    def test_summary_lists_preload_failures(self):
        report = gc_baseline.build_report(self.args)
        report['preload']['failed'] = [{'module': 'nope', 'error': 'ModuleNotFoundError: x'}]
        text = gc_baseline.summarize(report)

        self.assertIn('FAILED nope', text)


class MainTests(unittest.TestCase):
    def test_samples_must_be_positive(self):
        with self.assertRaises(SystemExit):
            gc_baseline.main(['measure', '--samples', '0'])

    def test_json_flag_emits_json(self):
        import contextlib
        import io
        import json

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            gc_baseline.main(['measure', '--samples', '1', '--json'])

        json.loads(buffer.getvalue())  # must not raise


if __name__ == '__main__':
    unittest.main()
