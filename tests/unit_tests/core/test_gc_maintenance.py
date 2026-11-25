"""Unit tests for periodic cyclic garbage collection (LANG-578)."""

from __future__ import annotations

import asyncio
import gc
from unittest.mock import Mock

import pytest

from langbot.pkg.utils.gc_maintenance import GarbageCollectionMaintainer


class _ConnectionLike:
    """Mimics an SSL transport/protocol pair: only reclaimable by the cycle collector."""

    def __init__(self) -> None:
        self.peer = _Peer(self)
        self.buffer = bytearray(4096)


class _Peer:
    def __init__(self, owner: _ConnectionLike) -> None:
        self.owner = owner


def _live_connections() -> int:
    return sum(1 for obj in gc.get_objects() if type(obj) is _ConnectionLike)


def _open_and_close_long_lived_connection() -> None:
    conn = _ConnectionLike()
    # A connection that stays open across younger collections is promoted to
    # the oldest generation before it is closed.
    gc.collect(1)
    del conn


def test_long_lived_cycles_grow_until_full_collection_and_maintainer_bounds_them():
    was_enabled = gc.isenabled()
    gc.collect()
    gc.disable()  # make the "rare automatic full collection" deterministic
    try:
        counts = []
        for _ in range(5):
            for _ in range(40):
                _open_and_close_long_lived_connection()
            counts.append(_live_connections())
        # Without a full collection the garbage grows linearly with reconnects.
        assert counts == [40, 80, 120, 160, 200]

        maintainer = GarbageCollectionMaintainer(freeze_after_seconds=0, collect_interval_seconds=60)
        bounded = []
        for _ in range(5):
            for _ in range(40):
                _open_and_close_long_lived_connection()
            maintainer.collect_once()
            bounded.append(_live_connections())
        assert bounded == [0, 0, 0, 0, 0]
        assert maintainer.snapshot()['collections_total'] == 5
        assert maintainer.snapshot()['collected_total'] > 0
    finally:
        gc.collect()
        if was_enabled:
            gc.enable()


def test_freeze_once_collects_before_freezing_and_reports_frozen_objects():
    calls = []
    maintainer = GarbageCollectionMaintainer(
        freeze_after_seconds=1,
        collect_interval_seconds=1,
        collect=lambda generation: calls.append(('collect', generation)) or 3,
        freeze=lambda: calls.append(('freeze', None)),
        freeze_count=lambda: 1234,
    )

    assert maintainer.freeze_once() == 1234
    assert calls == [('collect', 2), ('freeze', None)]
    snapshot = maintainer.snapshot()
    assert snapshot['frozen'] is True
    assert snapshot['frozen_objects'] == 1234
    assert snapshot['last_collected'] == 3


@pytest.mark.asyncio
async def test_run_freezes_then_collects_periodically_and_stops():
    collect = Mock(return_value=0)
    freeze = Mock()
    logger = Mock()
    maintainer = GarbageCollectionMaintainer(
        freeze_after_seconds=0.01,
        collect_interval_seconds=0.01,
        logger=logger,
        collect=collect,
        freeze=freeze,
        freeze_count=lambda: 7,
    )

    maintainer.start()
    maintainer.start()  # idempotent
    await asyncio.sleep(0.1)
    assert maintainer.running
    await maintainer.stop()

    assert not maintainer.running
    freeze.assert_called_once_with()
    # One collection before freezing plus at least one periodic collection.
    assert collect.call_count >= 2
    assert all(call.args == (2,) for call in collect.call_args_list)
    logger.info.assert_called_once()


def test_defaults_do_not_freeze_the_heap():
    # Frozen objects that later become cyclic garbage (replaced model catalog
    # snapshots, reloaded bots) are never reclaimed, so freezing must be opt-in.
    maintainer = GarbageCollectionMaintainer()
    assert maintainer.freeze_after_seconds == 0
    assert maintainer.collect_interval_seconds > 0
    assert maintainer.enabled


@pytest.mark.asyncio
async def test_run_without_freeze_only_collects_periodically():
    collect = Mock(return_value=0)
    freeze = Mock()
    maintainer = GarbageCollectionMaintainer(
        freeze_after_seconds=0,
        collect_interval_seconds=0.01,
        collect=collect,
        freeze=freeze,
        freeze_count=lambda: 0,
    )

    maintainer.start()
    await asyncio.sleep(0.1)
    await maintainer.stop()

    freeze.assert_not_called()
    assert collect.call_count >= 2
    assert maintainer.snapshot()['frozen'] is False


@pytest.mark.asyncio
async def test_disabled_maintainer_does_not_start_a_task():
    maintainer = GarbageCollectionMaintainer(freeze_after_seconds=0, collect_interval_seconds=0)
    maintainer.start()
    assert not maintainer.enabled
    assert not maintainer.running
    await maintainer.stop()


def test_slow_collection_is_logged_as_warning(monkeypatch):
    logger = Mock()
    times = iter([10.0, 10.75])
    monkeypatch.setattr('langbot.pkg.utils.gc_maintenance.time.perf_counter', lambda: next(times))
    maintainer = GarbageCollectionMaintainer(collect=lambda generation: 0, logger=logger)

    maintainer.collect_once()

    logger.warning.assert_called_once()
    assert maintainer.snapshot()['max_duration_ms'] == pytest.approx(750.0)


@pytest.mark.parametrize('value', [-1, float('nan'), float('inf'), 'abc'])
def test_invalid_intervals_are_rejected(value):
    with pytest.raises(ValueError):
        GarbageCollectionMaintainer(freeze_after_seconds=value)
    with pytest.raises(ValueError):
        GarbageCollectionMaintainer(collect_interval_seconds=value)
