"""Credential-session TTL enforcement for the platform adapter flows."""

import asyncio
import time

import pytest

from langbot.pkg.platform.credential_setup import _sweep_credential_sessions


_NOW = 10_000


@pytest.fixture
def sweep(monkeypatch):
    """Freeze wall time only during the synchronous sweep."""

    def sweep_at_fixed_time(stores):
        with monkeypatch.context() as patch:
            patch.setattr(time, 'time', lambda: _NOW)
            return _sweep_credential_sessions(stores)

    return sweep_at_fixed_time


def _session(age_seconds: float, **extra):
    return {'status': 'pending', 'created_at': _NOW - age_seconds, **extra}


def test_sweep_evicts_only_expired_sessions_using_each_store_ttl(sweep):
    shared_age = 400
    fresh = _session(299, app_secret='still-needed')
    boundary = _session(300)
    long_lived = _session(shared_age)
    short = {'expired': _session(shared_age), 'fresh': fresh, 'boundary': boundary}
    long = {'still-valid': long_lived}

    assert sweep([(short, 300), (long, 900), ({}, 60)]) == 1
    assert short == {'fresh': fresh, 'boundary': boundary}
    assert long == {'still-valid': long_lived}
    assert fresh['app_secret'] == 'still-needed'
    assert sweep([(short, 300), (long, 900)]) == 0


def test_sweep_removes_multiple_expired_and_malformed_sessions_and_scrubs_retained_reference(sweep):
    expired = _session(1000, app_secret='fixture-a', client_secret='fixture-b', secret='fixture-c')
    malformed = {'status': 'pending'}
    store = {'expired': expired, 'also-expired': _session(1001), 'broken': malformed}

    assert sweep([(store, 900)]) == 3
    assert store == {}
    assert {name: expired[name] for name in ('app_secret', 'client_secret', 'secret')} == {
        'app_secret': None,
        'client_secret': None,
        'secret': None,
    }


async def test_sweep_cancels_pending_exchange_task(sweep):
    started = asyncio.Event()
    blocked = asyncio.Event()

    async def exchange():
        started.set()
        await blocked.wait()

    task = asyncio.create_task(exchange())
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        store = {'old': _session(1000, task=task)}
        assert sweep([(store, 900)]) == 1
        assert store == {}
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(asyncio.shield(task), timeout=2)
        assert task.cancelled()
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def test_sweep_does_not_cancel_finished_exchange(sweep):
    # Calling cancel() on a completed asyncio task is a no-op, so use a
    # strict probe to distinguish skipping it from pointless cancellation.
    class CompletedExchange:
        def done(self):
            return True

        def cancel(self):
            pytest.fail('completed exchange should not be cancelled')

    store = {'old': _session(1000, task=CompletedExchange())}

    assert sweep([(store, 900)]) == 1
    assert store == {}
