"""Counterexamples for bounded group load scheduling and missed-slot accounting."""

import math
import unittest

from tools.regression.mixload_pacing import allocate_group_slot, planned_group_slots


class PacingTests(unittest.TestCase):
    def test_phase_budget_uses_the_smaller_of_rate_window_and_request_cap(self):
        self.assertEqual(planned_group_slots(4, 2), 8)
        self.assertEqual(planned_group_slots(0.51, 2), 2)
        self.assertEqual(planned_group_slots(0.07, 100), 7)
        self.assertEqual(planned_group_slots(math.nextafter(0.07, math.inf), 100), 8)
        self.assertEqual(planned_group_slots(4, 2, 3), 3)
        self.assertEqual(planned_group_slots(4, 2, 11), 8)
        self.assertEqual(planned_group_slots(1e-300, 1e-300), 1)
        for args in ((0, 1), (1, 0), (1, math.inf), (math.nan, 1), (1, 1, 0), (1, 1, True)):
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    planned_group_slots(*args)

    def test_due_boundary_does_not_send_early(self):
        now = math.nextafter(3 / 0.7, 0.0)
        result = allocate_group_slot(3, now, 0.7, 10, [True, True])
        self.assertEqual(result[:4], (3, None, 3, 3))
        self.assertGreater(result[-1], 0)
        self.assertEqual(allocate_group_slot(3, 3 / 0.7, 0.7, 10, [True, True]), (4, 1, 3, 3, 0.0))

    def test_late_wake_considers_only_latest_slot_and_never_catches_up(self):
        # Slots 0 through 4 are due. Dispatch only 4; do not burst 0..3.
        result = allocate_group_slot(0, 2.1, 2, 10, [True, True, True])
        self.assertEqual(result, (5, 1, 0, 4, 0.0))
        next_result = allocate_group_slot(result[0], 2.1, 2, 10, [True, True, True])
        self.assertEqual(next_result[:4], (5, None, 5, 5))
        self.assertAlmostEqual(next_result[-1], 0.4)

    def test_busy_assigned_group_is_not_replaced_or_queued(self):
        result = allocate_group_slot(4, 2.0, 2, 10, [True, False, True])
        self.assertEqual(result, (5, None, 4, 5, 0.5))
        # Having become available does not permit replay of group 1's missed slot.
        self.assertEqual(allocate_group_slot(5, 2.25, 2, 10, [True, True, True]), (5, None, 5, 5, 0.25))
        self.assertEqual(allocate_group_slot(5, 2.5, 2, 10, [True, True, True]), (6, 2, 5, 5, 0.0))

    def test_no_reported_wait_or_dispatch_after_last_slot(self):
        self.assertEqual(allocate_group_slot(2, 2, 1, 3, [False]), (3, None, 2, 3, 0.0))
        self.assertEqual(allocate_group_slot(3, 2, 1, 3, [True]), (3, None, 3, 3, 0.0))

    def test_stalls_preserve_exact_case_slot_allocations_and_total_accounting(self):
        # Group identities are fixed by slot. A stall can change observed mix
        # only via explicit shed counts, never by opportunistic reassignment.
        wanted = {0: 4, 1: 3, 2: 3}
        sent, missed = dict.fromkeys(wanted, 0), dict.fromkeys(wanted, 0)
        next_slot = 0
        for instant, availability in (
            (0, [True, True, True]),
            (0.5, [True, False, True]),
            (1.6, [True, True, True]),
            (4.5, [True, True, True]),
        ):
            next_slot, group, start, end, _ = allocate_group_slot(next_slot, instant, 2, 10, availability)
            if group is not None:
                sent[group] += 1
            for slot in range(start, end):
                missed[slot % 3] += 1
        self.assertEqual(next_slot, 10)
        self.assertEqual(sent, {0: 3, 1: 0, 2: 0})
        self.assertEqual({group: sent[group] + missed[group] for group in sent}, wanted)
