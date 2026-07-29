from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.platform.sources.http_bot import HttpBotAdapter
from langbot.pkg.platform.sources import http_bot as http_bot_module


def _session(key):
    session = SimpleNamespace()
    session._langbot_session_key = key
    return session


def _adapter(app, execution_context) -> HttpBotAdapter:
    adapter = HttpBotAdapter.model_construct(
        config={'signature_required': False},
        logger=SimpleNamespace(execution_context=execution_context),
        bot_uuid='bot-a',
        outbound_states={},
        idempotency_cache={},
        sync_waiters={},
        inbound_tasks=set(),
    )
    object.__setattr__(adapter, 'ap', app)
    return adapter


@pytest.mark.asyncio
async def test_http_bot_reset_removes_only_exact_execution_scope():
    context = ExecutionContext(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=3,
        bot_uuid='bot-a',
    )
    target_key = ('instance-a', 'workspace-a', 3, 'bot-a', 'person', 'shared-session')
    retained_keys = [
        ('instance-b', 'workspace-a', 3, 'bot-a', 'person', 'shared-session'),
        ('instance-a', 'workspace-b', 3, 'bot-a', 'person', 'shared-session'),
        ('instance-a', 'workspace-a', 4, 'bot-a', 'person', 'shared-session'),
        ('instance-a', 'workspace-a', 3, 'bot-b', 'person', 'shared-session'),
        ('instance-a', 'workspace-a', 3, 'bot-a', 'group', 'shared-session'),
        ('instance-a', 'workspace-a', 3, 'bot-a', 'person', 'other-session'),
    ]
    sessions = [_session(target_key), *[_session(key) for key in retained_keys], SimpleNamespace()]
    app = SimpleNamespace(sess_mgr=SimpleNamespace(session_list=sessions))
    adapter = _adapter(app, context)

    removed = await adapter._reset_session('person', 'shared-session')

    assert removed is True
    assert [getattr(session, '_langbot_session_key', None) for session in app.sess_mgr.session_list] == [
        *retained_keys,
        None,
    ]


@pytest.mark.asyncio
async def test_http_bot_reset_fails_closed_without_trusted_scope():
    app = SimpleNamespace(sess_mgr=SimpleNamespace(session_list=[]))
    adapter = _adapter(app, None)

    with pytest.raises(RuntimeError, match='trusted execution scope'):
        await adapter._reset_session('person', 'shared-session')


@pytest.mark.asyncio
async def test_http_bot_bounds_inbound_listener_tasks(monkeypatch):
    monkeypatch.setattr(http_bot_module, '_INBOUND_TASK_MAX', 1)
    adapter = _adapter(SimpleNamespace(), None)
    started = asyncio.Event()
    release = asyncio.Event()

    async def blocking_listener():
        started.set()
        await release.wait()

    first = adapter._start_inbound_task(blocking_listener())
    await started.wait()
    rejected = adapter._start_inbound_task(blocking_listener())

    assert first is not None
    assert rejected is None
    assert len(adapter.inbound_tasks) == 1

    release.set()
    await first
    await asyncio.sleep(0)
    assert adapter.inbound_tasks == set()


def test_http_bot_outbound_state_has_a_hard_capacity(monkeypatch):
    monkeypatch.setattr(http_bot_module, '_OUTBOUND_STATE_MAX', 2)
    monkeypatch.setattr(http_bot_module, '_OUTBOUND_PRUNE_SCAN_MAX', 2)
    adapter = _adapter(SimpleNamespace(), None)
    first = adapter._outbound_state('first')
    second = adapter._outbound_state('second')
    first.queue.put_nowait({})
    second.queue.put_nowait({})

    with pytest.raises(RuntimeError, match='outbound session capacity reached'):
        adapter._next_sequence('third', is_final=True)

    assert len(adapter.outbound_states) == 2
    assert adapter._next_sequence('first', is_final=True) == 1


def test_http_bot_outbound_state_pruning_is_bounded_and_reclaims_stale(monkeypatch):
    monkeypatch.setattr(http_bot_module, '_OUTBOUND_STATE_MAX', 2)
    monkeypatch.setattr(http_bot_module, '_OUTBOUND_PRUNE_SCAN_MAX', 1)
    monkeypatch.setattr(http_bot_module, '_OUTBOUND_IDLE_SECONDS', 10)
    adapter = _adapter(SimpleNamespace(), None)
    stale = adapter._outbound_state('stale')
    stale.last_active = time.monotonic() - 11
    adapter._outbound_state('active')

    assert adapter._next_sequence('replacement', is_final=True) == 1
    assert set(adapter.outbound_states) == {'active', 'replacement'}


def test_http_bot_idempotency_cache_has_a_hard_capacity(monkeypatch):
    monkeypatch.setattr(http_bot_module, '_IDEMPOTENCY_MAX', 2)
    monkeypatch.setattr(http_bot_module, '_IDEMPOTENCY_PRUNE_SCAN_MAX', 1)
    adapter = _adapter(SimpleNamespace(), None)

    assert adapter._reserve_idempotency_key('first') == 'accepted'
    assert adapter._reserve_idempotency_key('second') == 'accepted'
    assert adapter._reserve_idempotency_key('third') == 'overloaded'
    assert len(adapter.idempotency_cache) == 2
    assert adapter._reserve_idempotency_key('first') == 'duplicate'


def test_http_bot_idempotency_cache_reclaims_expired_oldest(monkeypatch):
    monkeypatch.setattr(http_bot_module, '_IDEMPOTENCY_MAX', 2)
    monkeypatch.setattr(http_bot_module, '_IDEMPOTENCY_PRUNE_SCAN_MAX', 1)
    monkeypatch.setattr(http_bot_module, '_IDEMPOTENCY_TTL', 10)
    adapter = _adapter(SimpleNamespace(), None)
    adapter.idempotency_cache = {
        'expired': time.monotonic() - 11,
        'active': time.monotonic(),
    }

    assert adapter._reserve_idempotency_key('replacement') == 'accepted'
    assert set(adapter.idempotency_cache) == {'active', 'replacement'}
