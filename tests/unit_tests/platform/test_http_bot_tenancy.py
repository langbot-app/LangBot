from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.platform.sources.http_bot import HttpBotAdapter
from langbot.pkg.platform.sources import http_bot as http_bot_module


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
    assert hasattr(adapter, 'ap')  # BotManager only injects declared application fields.
    adapter.ap = app
    return adapter


@pytest.mark.asyncio
@pytest.mark.parametrize('launcher_type', ['person', 'group'])
async def test_http_bot_reset_uses_trusted_scope_and_persistent_context_service(launcher_type):
    context = ExecutionContext(
        instance_uuid='instance-a', workspace_uuid='workspace-a', placement_generation=3, bot_uuid='bot-a'
    )
    reset = AsyncMock(return_value={'reset': True})
    app = SimpleNamespace(monitoring_service=SimpleNamespace(reset_session_context=reset))
    adapter = _adapter(app, context)

    assert await adapter._reset_session(launcher_type, 'shared-session') is True
    reset.assert_awaited_once_with(context, 'bot-a', f'{launcher_type}_shared-session')
    reset.side_effect = LookupError('Session not found')
    assert await adapter._reset_session(launcher_type, 'missing') is False
    reset.side_effect = RuntimeError('Session is processing a task')
    with pytest.raises(RuntimeError, match='processing'):
        await adapter._reset_session(launcher_type, 'busy')


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
