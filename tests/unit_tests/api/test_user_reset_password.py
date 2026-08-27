"""Regression tests for recovery-key hardening (#2392).

Covers two attack surfaces reported in GHSA-4xcp-6758-rxqv:

1. ``genkeys.py`` generated ``system.recovery_key`` with only 24 bits of
   entropy (``secrets.token_hex(3)``), making the whole keyspace brute-forceable.
2. ``POST /api/v1/user/reset-password`` (unauthenticated) checked its failure
   counter across ``await`` points, so concurrent guesses all passed the gate
   before any accounting happened; admission is now a synchronous fixed-window
   quota consumed at entry, plus constant-time key comparison.
"""

from __future__ import annotations

import asyncio
import logging
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import quart

from langbot.pkg.api.http.controller.groups import user as user_module
from langbot.pkg.api.http.controller.groups.user import UserRouterGroup
from langbot.pkg.core.stages.genkeys import GenKeysStage

pytestmark = pytest.mark.asyncio

STORED_KEY = 'Rk9SX1RFU1RfUkVDT1ZFUllfS0VZXzEyMzQ1Njc4OTA='


@pytest.fixture(autouse=True)
def _reset_quota_state():
    """Reset the module-level admission-quota state before each test."""
    user_module._reset_password_state['window_started_at'] = 0.0
    user_module._reset_password_state['attempts'] = 0
    yield
    user_module._reset_password_state['window_started_at'] = 0.0
    user_module._reset_password_state['attempts'] = 0


@pytest.fixture(autouse=True)
def _fast_sleep(monkeypatch):
    """Neutralize the fixed 3s delay so tests run instantly."""
    monkeypatch.setattr(user_module, 'asyncio', SimpleNamespace(sleep=AsyncMock()))


# ---------------------------------------------------------------------------
# genkeys.py: recovery-key entropy
# ---------------------------------------------------------------------------


def _make_genkeys_ap(existing_key: str) -> SimpleNamespace:
    """Build a minimal Application mock for GenKeysStage.

    Mirrors the real boot order: no ``logger`` attribute is set because
    GenKeysStage runs before SetupLoggerStage.
    """
    return SimpleNamespace(
        instance_config=SimpleNamespace(
            data={'system': {'jwt': {'secret': 'jwt-secret'}, 'recovery_key': existing_key}},
            dump_config=AsyncMock(),
        ),
    )


async def test_recovery_key_generation_uses_high_entropy():
    """Newly generated recovery keys must carry at least 256 bits (#2392).

    The legacy generator produced 6 hex chars (24 bits); the keyspace was
    exhaustible within hours. The replacement must be at least 32 chars.
    """
    ap = _make_genkeys_ap(existing_key='')

    await GenKeysStage().run(ap)

    key = ap.instance_config.data['system']['recovery_key']
    assert len(key) >= 32, f'recovery key has only {len(key)} chars'
    assert ap.instance_config.dump_config.called


async def test_legacy_low_entropy_key_preserved_with_warning(caplog):
    """A legacy 6-char key must keep working but emit a warning, without ap.logger."""
    ap = _make_genkeys_ap(existing_key='ABC123')

    with caplog.at_level(logging.WARNING, logger='langbot.pkg.core.stages.genkeys'):
        await GenKeysStage().run(ap)

    assert ap.instance_config.data['system']['recovery_key'] == 'ABC123'
    assert any('Low-entropy' in record.message for record in caplog.records)
    assert not ap.instance_config.dump_config.called


async def test_recovery_key_generation_preserves_existing_key():
    """An explicitly configured recovery key must not be regenerated on boot."""
    ap = _make_genkeys_ap(existing_key='my-own-strong-recovery-key-0123456789')

    await GenKeysStage().run(ap)

    assert ap.instance_config.data['system']['recovery_key'] == 'my-own-strong-recovery-key-0123456789'
    assert not ap.instance_config.dump_config.called


# ---------------------------------------------------------------------------
# POST /api/v1/user/reset-password: admission quota + constant-time compare
# ---------------------------------------------------------------------------


async def _create_client():
    """Create a Quart test client with a mocked Application."""
    quart_app = quart.Quart(__name__)

    user_obj = SimpleNamespace(uuid='user-uuid', user='admin@example.com')
    reset_password = AsyncMock()
    get_user_by_email = AsyncMock(return_value=user_obj)

    ap = SimpleNamespace(
        user_service=SimpleNamespace(
            is_initialized=AsyncMock(return_value=True),
            get_user_by_email=get_user_by_email,
            reset_password=reset_password,
        ),
        instance_config=SimpleNamespace(
            data={'system': {'recovery_key': STORED_KEY}},
        ),
    )

    router = UserRouterGroup(ap, quart_app)
    await router.initialize()

    client = quart_app.test_client()
    return client, reset_password, get_user_by_email


def _payload(key: str = STORED_KEY) -> dict:
    return {'user': 'admin@example.com', 'recovery_key': key, 'new_password': 'NewPass1!'}


async def test_correct_key_resets_password():
    """A correct recovery key resets the password and returns success."""
    client, reset_password, _ = await _create_client()

    resp = await client.post('/api/v1/user/reset-password', json=_payload())

    assert resp.status_code == 200
    assert (await resp.get_json())['code'] == 0
    reset_password.assert_awaited_once_with('admin@example.com', 'NewPass1!')


async def test_wrong_key_rejected_without_reset():
    """A wrong recovery key returns 403 and never touches the password."""
    client, reset_password, _ = await _create_client()

    resp = await client.post('/api/v1/user/reset-password', json=_payload(key='WRONG'))

    assert resp.status_code == 403
    reset_password.assert_not_awaited()


async def test_non_string_recovery_key_does_not_crash():
    """Malformed recovery-key payloads must be rejected, not raise a 500.

    Constant-time comparison via hmac.compare_digest on bytes requires the
    input to be a str; other JSON types must fail closed.
    """
    client, reset_password, _ = await _create_client()

    resp = await client.post(
        '/api/v1/user/reset-password',
        json={'user': 'admin@example.com', 'recovery_key': 12345, 'new_password': 'NewPass1!'},
    )

    assert resp.status_code == 403
    reset_password.assert_not_awaited()


async def test_non_ascii_recovery_key_does_not_crash():
    """Non-ASCII keys must compare safely (encode-based constant-time compare)."""
    client, _, _ = await _create_client()

    resp = await client.post(
        '/api/v1/user/reset-password',
        json={'user': 'admin@example.com', 'recovery_key': '奇数密钥不是ASCII', 'new_password': 'NewPass1!'},
    )

    assert resp.status_code == 403


async def test_quota_exhausted_after_max_attempts():
    """After MAX admitted attempts even a correct key must be rejected with 429 (#2392).

    Every admission consumes quota regardless of outcome; the legacy endpoint
    accepted every guess independently, exhausting the 24-bit keyspace via bursts.
    """
    client, reset_password, _ = await _create_client()

    for _ in range(user_module._MAX_RESET_ATTEMPTS_PER_WINDOW):
        resp = await client.post('/api/v1/user/reset-password', json=_payload(key='WRONG'))
        assert resp.status_code == 403

    # The very next request carries the CORRECT key but has no quota left.
    resp = await client.post('/api/v1/user/reset-password', json=_payload())
    assert resp.status_code == 429
    reset_password.assert_not_awaited()


async def test_quota_rejects_before_touching_user_lookup():
    """An exhausted quota must reject early, before the sleep and any service calls."""
    client, _, get_user_by_email = await _create_client()

    user_module._reset_password_state['attempts'] = user_module._MAX_RESET_ATTEMPTS_PER_WINDOW
    user_module._reset_password_state['window_started_at'] = time.monotonic()

    resp = await client.post('/api/v1/user/reset-password', json=_payload())

    assert resp.status_code == 429
    get_user_by_email.assert_not_awaited()


async def test_window_rolls_over_and_admits_again():
    """Once the fixed window elapses, the quota resets and a correct key works again."""
    client, reset_password, _ = await _create_client()

    user_module._reset_password_state['attempts'] = user_module._MAX_RESET_ATTEMPTS_PER_WINDOW
    user_module._reset_password_state['window_started_at'] = time.monotonic() - user_module._RESET_WINDOW_SECONDS - 1

    resp = await client.post('/api/v1/user/reset-password', json=_payload())

    assert resp.status_code == 200
    reset_password.assert_awaited_once()


async def test_success_does_not_restore_quota():
    """A successful reset does NOT restore quota: brute-force budget survives wins (#2392).

    The legacy clear-on-success let attackers interleave correct-looking states;
    success only proves knowledge of the key once, it must not refill attempts.
    """
    client, _, _ = await _create_client()

    for _ in range(user_module._MAX_RESET_ATTEMPTS_PER_WINDOW - 1):
        resp = await client.post('/api/v1/user/reset-password', json=_payload(key='WRONG'))
        assert resp.status_code == 403

    # Last slot is spent on the genuine reset.
    resp = await client.post('/api/v1/user/reset-password', json=_payload())
    assert resp.status_code == 200

    # Quota is exhausted; even a correct key waits for the next window.
    resp = await client.post('/api/v1/user/reset-password', json=_payload())
    assert resp.status_code == 429


async def test_concurrent_burst_cannot_bypass_quota(monkeypatch):
    """A 20-request burst yields exactly {403: 5, 429: 15} (#2392 regression).

    The vulnerable version accounted failures after several awaits, letting all
    concurrent requests pass the gate ({403: 20}). Admission is now synchronous
    and await-free, so total admissions are capped regardless of scheduling.
    """

    # Swap the AsyncMock sleep for a real cooperative yield so tasks actually
    # interleave mid-handler like they do under production load.
    async def _yield_sleep(_seconds):
        await asyncio.sleep(0)

    monkeypatch.setattr(user_module, 'asyncio', SimpleNamespace(sleep=_yield_sleep))

    client, reset_password, _ = await _create_client()

    responses = await asyncio.gather(
        *(client.post('/api/v1/user/reset-password', json=_payload(key='WRONG')) for _ in range(20))
    )

    status_counts: dict[int, int] = {}
    for resp in responses:
        status_counts[resp.status_code] = status_counts.get(resp.status_code, 0) + 1

    assert status_counts == {403: 5, 429: 15}
    reset_password.assert_not_awaited()
