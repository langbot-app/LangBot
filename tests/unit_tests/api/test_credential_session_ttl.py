"""Credential-session TTL enforcement for the platform adapter flows.

Every adapter registration flow (Lark one-click app, DingTalk device flow, WeCom
bot, QQ Official bind) parks a short-lived secret in an in-memory session dict
between the platform handshake and the caller persisting it. The per-route
cleanups only run when another request arrives, so an abandoned flow would keep
its secret in memory past its validity window. These tests cover the sweeper that
enforces the TTL on a timer and scrubs the secret as it evicts.
"""

import time

from langbot.pkg.api.http.controller.groups.platform.adapters import (
    _sweep_credential_sessions,
)


def _session(age_seconds: float, **extra):
    return {'status': 'pending', 'created_at': time.time() - age_seconds, **extra}


def test_expired_sessions_are_evicted():
    store = {'old': _session(1000)}
    assert _sweep_credential_sessions([(store, 900)]) == 1
    assert store == {}


def test_fresh_sessions_survive():
    store = {'new': _session(10)}
    assert _sweep_credential_sessions([(store, 900)]) == 0
    assert 'new' in store


def test_secret_is_scrubbed_on_eviction():
    """The evicted dict must not keep the credential readable."""
    session = _session(1000, app_secret='super-secret', client_secret='other', secret='third')
    store = {'old': session}
    _sweep_credential_sessions([(store, 900)])

    assert store == {}
    assert session['app_secret'] is None
    assert session['client_secret'] is None
    assert session['secret'] is None


def test_ttl_is_per_store():
    """A store with a shorter window expires while a longer one keeps its entry."""
    short, long = {'s': _session(400)}, {'l': _session(400)}
    assert _sweep_credential_sessions([(short, 300), (long, 900)]) == 1
    assert short == {}
    assert 'l' in long


def test_pending_task_is_cancelled_on_eviction():
    class FakeTask:
        def __init__(self):
            self.cancelled = False

        def done(self):
            return False

        def cancel(self):
            self.cancelled = True

    task = FakeTask()
    store = {'old': _session(1000, task=task)}
    _sweep_credential_sessions([(store, 900)])
    assert task.cancelled is True


def test_finished_task_is_not_cancelled():
    class DoneTask:
        def __init__(self):
            self.cancelled = False

        def done(self):
            return True

        def cancel(self):  # pragma: no cover - must not be called
            self.cancelled = True

    task = DoneTask()
    store = {'old': _session(1000, task=task)}
    _sweep_credential_sessions([(store, 900)])
    assert task.cancelled is False


def test_session_without_created_at_is_evicted():
    """A malformed session must not become immortal."""
    store = {'broken': {'status': 'pending'}}
    assert _sweep_credential_sessions([(store, 900)]) == 1
    assert store == {}


def test_multiple_expired_sessions_in_one_store():
    store = {f's{i}': _session(1000) for i in range(5)}
    assert _sweep_credential_sessions([(store, 900)]) == 5
    assert store == {}


def test_empty_stores_are_harmless():
    assert _sweep_credential_sessions([({}, 900), ({}, 60)]) == 0
