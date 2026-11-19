"""Pure monotonic slot allocation for the opt-in group mixload."""

from bisect import bisect_right
import math
import sys


def planned_group_slots(duration, rps, max_requests=None):
    """Count absolute slots at times i / rps strictly before the phase deadline."""
    if not math.isfinite(duration) or not math.isfinite(rps) or duration <= 0 or rps <= 0:
        raise ValueError('duration and RPS must be positive finite numbers')
    if max_requests is not None and (type(max_requests) is not int or max_requests < 1):
        raise ValueError('max_requests must be a positive integer')
    product = duration * rps
    if not math.isfinite(product):
        raise ValueError('planned slot count must be finite')
    # Positive subnormal operands can round their product to zero although slot
    # zero is strictly before every positive deadline.
    planned = max(1, math.ceil(product))
    if max_requests is not None:
        planned = min(planned, max_requests)
    if planned > sys.maxsize:
        raise ValueError('planned slot count exceeds supported range')
    # Ceil is the mathematical count. Recheck its edge at the same
    # represented boundary the dispatcher uses (e.g. 0.07 * 100 > 7.0).
    if (planned - 1) / rps >= duration:
        planned = max(1, planned - 1)
    elif planned / rps < duration and (max_requests is None or planned < max_requests):
        planned += 1
    return planned


def allocate_group_slot(next_slot, now_elapsed, rps, planned, available):
    """Return next slot, group index or None, missed range, and seconds to wait.

    A late scheduler may consider only the newest due slot. Its assigned group
    is determined by the slot number, not by worker timing or other availability.
    Earlier due slots and a busy newest slot are accounted for but not replayed.
    The caller must stop at the phase deadline and account for any remaining tail.
    """
    if not math.isfinite(now_elapsed) or not math.isfinite(rps) or rps <= 0:
        raise ValueError('elapsed time must be finite and RPS must be positive and finite')
    if not available or not 0 <= next_slot <= planned:
        raise ValueError('invalid group availability or slot range')
    if next_slot == planned:
        return next_slot, None, next_slot, next_slot, 0.0

    def due(slot):
        return slot / rps

    # Compare represented deadlines directly. floor(elapsed * rps) can pick
    # a slot just before its due boundary through multiplication rounding.
    next_due_slot = bisect_right(range(planned), now_elapsed, lo=next_slot, key=due)
    if next_due_slot == next_slot:
        return next_slot, None, next_slot, next_slot, due(next_slot) - now_elapsed

    slot = next_due_slot - 1
    group_index = slot % len(available)
    if available[group_index]:
        return next_due_slot, group_index, next_slot, slot, 0.0

    wait = due(next_due_slot) - now_elapsed if next_due_slot < planned else 0.0
    return next_due_slot, None, next_slot, next_due_slot, wait
