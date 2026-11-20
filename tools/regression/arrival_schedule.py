"""Bounded fixed-arrival scheduling with explicit outcomes for undispatched work."""

from collections import Counter, deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import time

from tools.regression.mixload_pacing import planned_group_slots


def run_open_loop(*, started, duration, rps, workers, queue_capacity, execute, key_for, blocked, settle, stop):
    """Schedule every arrival before the deadline and drain only dispatched work.

    ``key_for`` returns a serialization key, or None for independent requests.
    ``execute`` returns the completed request record. ``settle`` journals every
    arrival exactly once, including work that never reaches the target service.
    """
    deadline = started + duration
    scheduled = planned_group_slots(duration, rps)
    next_arrival = 0
    pending = deque()
    active = {}
    busy = set()
    counts = Counter()
    queue_peak = 0
    at_deadline = None

    def finish(arrival, outcome, row=None):
        counts[outcome] += 1
        settle(arrival, outcome, row)

    def invoke(item):
        if time.monotonic() >= deadline or stop.is_set():
            return None
        return execute(item)

    def arrival(index):
        return {
            'arrival_id': index,
            'scheduled_elapsed': index / rps,
            'serialization_key': key_for(index),
        }

    def completed():
        for future in list(active):
            if not future.done():
                continue
            item = active.pop(future)
            key = item['serialization_key']
            if key is not None:
                busy.remove(key)
            row = future.result()
            finish(item, 'expired' if row is None else 'dispatched', row)

    def dispatch(pool):
        # Scan once so an occupied group cannot hold up independent groups.
        waiting = len(pending)
        for _ in range(waiting):
            item = pending.popleft()
            key = item['serialization_key']
            if blocked(key):
                finish(item, 'blocked')
            elif len(active) < workers and key not in busy and time.monotonic() < deadline and not stop.is_set():
                if key is not None:
                    busy.add(key)
                active[pool.submit(invoke, item)] = item
            else:
                pending.append(item)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        while True:
            completed()
            now = time.monotonic()
            if now >= deadline or stop.is_set():
                at_deadline = len(pending)
                while pending:
                    item = pending.popleft()
                    finish(item, 'blocked' if blocked(item['serialization_key']) else 'expired')
                while next_arrival < scheduled:
                    item = arrival(next_arrival)
                    finish(item, 'blocked' if blocked(item['serialization_key']) else 'expired')
                    next_arrival += 1
                break

            dispatch(pool)
            # Catch up all fixed arrivals even when the observer was descheduled.
            while next_arrival < scheduled and started + next_arrival / rps <= now:
                item = arrival(next_arrival)
                next_arrival += 1
                key = item['serialization_key']
                if blocked(key):
                    finish(item, 'blocked')
                elif len(active) < workers and key not in busy and time.monotonic() < deadline:
                    if key is not None:
                        busy.add(key)
                    active[pool.submit(invoke, item)] = item
                elif len(pending) < queue_capacity:
                    pending.append(item)
                    queue_peak = max(queue_peak, len(pending))
                else:
                    finish(item, 'dropped')
            dispatch(pool)
            wake = min(deadline, started + next_arrival / rps) if next_arrival < scheduled else deadline
            delay = max(0, min(0.05, wake - time.monotonic()))
            if active:
                wait(active, timeout=delay, return_when=FIRST_COMPLETED)
            else:
                stop.wait(delay)

        # No queued request is admitted during drain, even if a slot becomes free.
        for future in list(active):
            item = active.pop(future)
            row = future.result()
            finish(item, 'expired' if row is None else 'dispatched', row)

    dispatched = counts['dispatched']
    undispatched = sum(counts[name] for name in ('dropped', 'expired', 'blocked'))
    return {
        'scheduled': scheduled,
        'dispatched': dispatched,
        'dropped': counts['dropped'],
        'expired': counts['expired'],
        'blocked': counts['blocked'],
        'queue_capacity': queue_capacity,
        'queue_peak': queue_peak,
        'queued_at_deadline': at_deadline,
        'conserved': scheduled == dispatched + undispatched,
    }
