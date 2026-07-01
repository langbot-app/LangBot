"""
Valkey distributed rate-limit integration tests.

Real-Valkey tests for ValkeyFixedWindowAlgo. Marked slow + integration and
gated on TEST_VALKEY_URL (skips when unset), mirroring
tests/integration/persistence/test_migrations_postgres.py.

Run locally (requires a Valkey/valkey-bundle instance):
    TEST_VALKEY_URL=valkey://localhost:6380 \
        uv run pytest tests/integration/pipeline/test_valkey_ratelimit.py -m slow -q

These tests use synchronous INCR/GET semantics, so assertions immediately after
each request are reliable; no time.sleep is needed except the legitimate
wait-strategy and window-rollover tests.
"""

from __future__ import annotations

import os
import math
import time
import asyncio
from urllib.parse import urlparse
from unittest.mock import Mock

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.slow]

TEST_VALKEY_URL = os.environ.get('TEST_VALKEY_URL') or pytest.skip('TEST_VALKEY_URL not set', allow_module_level=True)


def _parse_url(url: str) -> dict:
    """Parse a valkey://host:port/db URL into a config dict."""
    parsed = urlparse(url)
    db = 0
    if parsed.path and parsed.path.strip('/'):
        try:
            db = int(parsed.path.strip('/'))
        except ValueError:
            db = 0
    return {
        'host': parsed.hostname or 'localhost',
        'port': parsed.port or 6379,
        'db': db,
        'password': parsed.password or '',
        'username': parsed.username or '',
        'tls': parsed.scheme in ('valkeys', 'rediss'),
    }


def _make_app(valkey_cfg: dict) -> Mock:
    app = Mock()
    app.logger = Mock()
    instance_config = Mock()
    instance_config.data = {'valkey': valkey_cfg}
    app.instance_config = instance_config
    return app


def _make_query(window_length: int, limitation: int, strategy: str) -> Mock:
    query = Mock()
    query.pipeline_config = {
        'safety': {
            'rate-limit': {
                'window-length': window_length,
                'limitation': limitation,
                'strategy': strategy,
            }
        }
    }
    return query


def _get_algo_cls():
    from importlib import import_module

    import_module('langbot.pkg.pipeline.pipelinemgr')
    module = import_module('langbot.pkg.pipeline.ratelimit.algos.valkey_fixwin')
    return module.ValkeyFixedWindowAlgo


async def _new_algo(valkey_cfg: dict):
    algo_cls = _get_algo_cls()
    algo = algo_cls(_make_app(valkey_cfg))
    await algo.initialize()
    return algo


@pytest.fixture
def valkey_cfg():
    return _parse_url(TEST_VALKEY_URL)


@pytest.fixture
def unique_launcher_id():
    """A unique launcher id per test to avoid window-key collisions."""
    return f'it-{int(time.time() * 1000)}-{os.getpid()}'


@pytest.fixture
async def cleanup_keys(valkey_cfg):
    """Delete every langbot:ratelimit:fixwin:* key before and after each test."""

    async def _flush():
        algo = await _new_algo(valkey_cfg)
        client = await algo._ensure_client()
        cursor = b'0'
        pattern = 'langbot:ratelimit:fixwin:*'
        while True:
            cursor, keys = await client.scan(cursor, match=pattern, count=1000)
            if keys:
                await client.delete(keys)
            if cursor in (b'0', '0', 0):
                break
        await client.close()

    await _flush()
    yield
    await _flush()


class TestValkeyRateLimitIntegration:
    @pytest.mark.asyncio
    async def test_within_limit_allowed(self, valkey_cfg, unique_launcher_id, cleanup_keys):
        algo = await _new_algo(valkey_cfg)
        query = _make_query(window_length=60, limitation=5, strategy='drop')

        for i in range(5):
            allowed = await algo.require_access(query, 'person', unique_launcher_id)
            assert allowed is True, f'request {i + 1} should be allowed'

    @pytest.mark.asyncio
    async def test_exceeds_limit_drop_denied(self, valkey_cfg, unique_launcher_id, cleanup_keys):
        algo = await _new_algo(valkey_cfg)
        query = _make_query(window_length=60, limitation=5, strategy='drop')

        for _ in range(5):
            assert await algo.require_access(query, 'person', unique_launcher_id) is True

        # The 6th request in the same window must be denied.
        assert await algo.require_access(query, 'person', unique_launcher_id) is False

    @pytest.mark.asyncio
    async def test_window_rollover_resets(self, valkey_cfg, unique_launcher_id, cleanup_keys):
        algo = await _new_algo(valkey_cfg)
        query = _make_query(window_length=1, limitation=2, strategy='drop')

        # Exhaust the current 1-second window.
        assert await algo.require_access(query, 'person', unique_launcher_id) is True
        assert await algo.require_access(query, 'person', unique_launcher_id) is True
        assert await algo.require_access(query, 'person', unique_launcher_id) is False

        # Cross the window boundary; a new window key allows requests again.
        await asyncio.sleep(1.2)
        assert await algo.require_access(query, 'person', unique_launcher_id) is True

    @pytest.mark.asyncio
    async def test_wait_strategy(self, valkey_cfg, unique_launcher_id, cleanup_keys):
        algo = await _new_algo(valkey_cfg)
        query = _make_query(window_length=1, limitation=1, strategy='wait')

        assert await algo.require_access(query, 'person', unique_launcher_id) is True

        start = time.time()
        # This second request is over the limit; 'wait' should sleep to the next
        # window boundary, then succeed.
        result = await algo.require_access(query, 'person', unique_launcher_id)
        elapsed = time.time() - start

        assert result is True
        # The wait must complete within roughly one window (it sleeps to the next
        # boundary, never longer), proving it neither hung nor skipped the wait
        # into an indefinite loop. Upper-bounded rather than lower-bounded to stay
        # non-flaky regardless of where in the window the test starts.
        assert elapsed <= 1.0 + 0.5, f'wait took {elapsed:.3f}s, expected <= ~1 window'

    @pytest.mark.asyncio
    async def test_different_sessions_isolated(self, valkey_cfg, unique_launcher_id, cleanup_keys):
        algo = await _new_algo(valkey_cfg)
        query = _make_query(window_length=60, limitation=2, strategy='drop')

        id_a = f'{unique_launcher_id}-a'
        id_b = f'{unique_launcher_id}-b'

        # Exhaust session A.
        assert await algo.require_access(query, 'person', id_a) is True
        assert await algo.require_access(query, 'person', id_a) is True
        assert await algo.require_access(query, 'person', id_a) is False

        # Session B has an independent counter.
        assert await algo.require_access(query, 'person', id_b) is True
        assert await algo.require_access(query, 'person', id_b) is True
        assert await algo.require_access(query, 'person', id_b) is False

    @pytest.mark.asyncio
    async def test_multi_worker_shared_counter(self, valkey_cfg, unique_launcher_id, cleanup_keys):
        """Two separate algo instances, each owning its own GlideClient (two
        simulated worker processes) pointing at the same Valkey/db/key, share a
        single counter — proving cross-process rate limiting."""
        algo_a = await _new_algo(valkey_cfg)
        algo_b = await _new_algo(valkey_cfg)

        limitation = 6
        query = _make_query(window_length=60, limitation=limitation, strategy='drop')

        from_a = math.ceil(limitation / 2)
        from_b = limitation - from_a

        for _ in range(from_a):
            assert await algo_a.require_access(query, 'person', unique_launcher_id) is True
        for _ in range(from_b):
            assert await algo_b.require_access(query, 'person', unique_launcher_id) is True

        # The shared window is now exhausted; either instance must deny.
        assert await algo_a.require_access(query, 'person', unique_launcher_id) is False
        assert await algo_b.require_access(query, 'person', unique_launcher_id) is False
