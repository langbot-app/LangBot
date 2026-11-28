"""Bounded fixed-arrival scheduling with explicit outcomes for undispatched work."""

import time
from collections import Counter, deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from tools.regression.mixload_pacing import planned_group_slots
from tools.regression.observability_contract import _interrupt_reason_for_exception


def run_open_loop(
    *,
    started,
    duration,
    rps,
    workers,
    queue_capacity,
    execute,
    key_for,
    blocked,
    settle,
    stop,
    drain_all=False,
    drain_timeout=300,
    action_writer=None,
    action_name='arrival',
):
    """Schedule every arrival and optionally drain all admitted work.

    ``key_for`` returns a serialization key, or None for independent requests.
    ``execute`` returns the completed request record. ``settle`` journals every
    arrival exactly once, including work that never reaches the target service.
    """
    deadline = started + duration
    drain_deadline = deadline + drain_timeout
    scheduled = planned_group_slots(duration, rps)
    next_arrival = 0
    pending = deque()
    active = {}
    busy = set()
    counts = Counter()
    queue_peak = 0
    at_deadline = None

    def finish(arrival, outcome, row=None, *, error=None, interrupt_reason=None):
        counts[outcome] += 1
        action = arrival.pop('_action_result', None)
        settle(arrival, outcome, row)
        if action_writer is not None and action is not None:
            if interrupt_reason is not None:
                action.metadata['interrupt_reason'] = interrupt_reason
            status = {
                'dispatched': 'succeeded',
                'dropped': 'blocked',
                'blocked': 'blocked',
                'expired': 'expired',
                'failed': 'failed',
                'interrupted': 'interrupted',
            }[outcome]
            action_writer.finish(action, status, error=error)

    def invoke(item):
        if stop.is_set() or (not drain_all and time.monotonic() >= deadline):
            return None
        return execute(item)

    def arrival(index):
        item = {
            'arrival_id': index,
            'scheduled_elapsed': index / rps,
            'serialization_key': key_for(index),
        }
        if action_writer is not None:
            action = action_writer.begin(action_name, metadata={'arrival_id': index})
            item.update(action_id=action.action_id, trace_id=action.trace_id, _action_result=action)
        return item

    def completed():
        for future in list(active):
            if not future.done():
                continue
            item = active.pop(future)
            key = item['serialization_key']
            if key is not None:
                busy.remove(key)
            try:
                row = future.result()
            except Exception as exc:  # noqa: BLE001
                finish(item, 'failed', error=exc)
                continue
            finish(item, 'expired' if row is None else 'dispatched', row)

    def dispatch(pool):
        # Scan once so an occupied group cannot hold up independent groups.
        waiting = len(pending)
        for _ in range(waiting):
            item = pending.popleft()
            key = item['serialization_key']
            if blocked(key):
                finish(item, 'blocked')
            elif (
                len(active) < workers
                and key not in busy
                and (drain_all or time.monotonic() < deadline)
                and not stop.is_set()
            ):
                if key is not None:
                    busy.add(key)
                active[pool.submit(invoke, item)] = item
            else:
                pending.append(item)

    pool = ThreadPoolExecutor(max_workers=workers)
    timed_out_drain = False
    aborted = False
    try:
        while True:
            completed()
            now = time.monotonic()
            if stop.is_set():
                at_deadline = len(pending)
                while pending:
                    item = pending.popleft()
                    finish(item, 'blocked' if blocked(item['serialization_key']) else 'expired')
                while next_arrival < scheduled:
                    item = arrival(next_arrival)
                    finish(item, 'blocked' if blocked(item['serialization_key']) else 'expired')
                    next_arrival += 1
                break

            if now >= deadline:
                at_deadline = len(pending)
                if not drain_all:
                    while pending:
                        item = pending.popleft()
                        finish(item, 'blocked' if blocked(item['serialization_key']) else 'expired')
                    while next_arrival < scheduled:
                        item = arrival(next_arrival)
                        finish(item, 'blocked' if blocked(item['serialization_key']) else 'expired')
                        next_arrival += 1
                    break
                while next_arrival < scheduled:
                    item = arrival(next_arrival)
                    next_arrival += 1
                    if blocked(item['serialization_key']):
                        finish(item, 'blocked')
                    else:
                        pending.append(item)
                        queue_peak = max(queue_peak, len(pending))
                dispatch(pool)
                if not active and not pending:
                    break
                if now >= drain_deadline:
                    while pending:
                        item = pending.popleft()
                        finish(item, 'blocked' if blocked(item['serialization_key']) else 'expired')
                    if active:
                        timed_out_drain = True
                    break
                if active:
                    wait(active, timeout=0.05, return_when=FIRST_COMPLETED)
                continue

            dispatch(pool)
            # Catch up all fixed arrivals even when the observer was descheduled.
            while next_arrival < scheduled and started + next_arrival / rps <= now:
                item = arrival(next_arrival)
                next_arrival += 1
                key = item['serialization_key']
                if blocked(key):
                    finish(item, 'blocked')
                elif len(active) < workers and key not in busy and (drain_all or time.monotonic() < deadline):
                    if key is not None:
                        busy.add(key)
                    active[pool.submit(invoke, item)] = item
                elif queue_capacity is None or len(pending) < queue_capacity:
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
            if timed_out_drain and not future.done():
                future.cancel()
                finish(
                    item,
                    'interrupted',
                    error=TimeoutError('drain timeout exceeded'),
                    interrupt_reason='timeout',
                )
                continue
            try:
                row = future.result()
            except Exception as exc:  # noqa: BLE001
                finish(item, 'failed', error=exc)
                continue
            finish(item, 'expired' if row is None else 'dispatched', row)
    except BaseException as exc:
        aborted = True
        if action_writer is not None:
            action_writer.interrupt_active(reason=_interrupt_reason_for_exception(exc), error=exc)
        raise
    finally:
        pool.shutdown(wait=not (timed_out_drain or aborted), cancel_futures=timed_out_drain or aborted)

    dispatched = counts['dispatched']
    undispatched = sum(counts[name] for name in ('dropped', 'expired', 'blocked', 'failed', 'interrupted'))
    return {
        'scheduled': scheduled,
        'dispatched': dispatched,
        'dropped': counts['dropped'],
        'expired': counts['expired'],
        'blocked': counts['blocked'],
        'failed': counts['failed'],
        'interrupted': counts['interrupted'],
        'queue_capacity': queue_capacity,
        'queue_peak': queue_peak,
        'queued_at_deadline': at_deadline,
        'drain_all': drain_all,
        'drain_timeout_seconds': drain_timeout if drain_all else None,
        'conserved': scheduled == dispatched + undispatched,
    }
