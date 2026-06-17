"""
ValkeyFixedWindowAlgo unit tests.

These tests exercise the distributed fixed-window rate-limit algorithm with a
MOCKED glide client (no real Valkey server). They cover: registry membership,
key schema / window math, within-limit allow, over-limit drop, wait-strategy
retry, fail-open on client error, client-config construction, release no-op, and
the import guard.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock, patch
from importlib import import_module


def get_valkey_fixwin_module():
    """Lazy import to ensure proper pipeline initialization order."""
    # Preload pipelinemgr so stage/algo registration happens in the right order
    # (mirrors conftest behaviour and avoids circular-import on direct import).
    import_module('langbot.pkg.pipeline.pipelinemgr')
    return import_module('langbot.pkg.pipeline.ratelimit.algos.valkey_fixwin')


def get_algo_module():
    import_module('langbot.pkg.pipeline.pipelinemgr')
    return import_module('langbot.pkg.pipeline.ratelimit.algo')


@pytest.fixture
def mock_app_for_algo():
    """Mock app with a configurable top-level `valkey:` config block."""
    mock_app = Mock()
    mock_app.logger = Mock()
    instance_config = Mock()
    instance_config.data = {
        'valkey': {
            'host': 'valkey.example.com',
            'port': 6390,
            'db': 3,
        }
    }
    mock_app.instance_config = instance_config
    return mock_app


def make_query(sample_query, *, window_length=60, limitation=10, strategy='drop'):
    sample_query.pipeline_config = {
        'safety': {
            'rate-limit': {
                'window-length': window_length,
                'limitation': limitation,
                'strategy': strategy,
            }
        }
    }
    return sample_query


async def make_algo(mock_app_for_algo, mocked_result=None):
    """Construct an initialized algo with its glide client/script stubbed out."""
    valkey_fixwin = get_valkey_fixwin_module()
    algo = valkey_fixwin.ValkeyFixedWindowAlgo(mock_app_for_algo)
    await algo.initialize()
    # Stub the lazily-created client so no real connection is attempted.
    mock_client = AsyncMock()
    if mocked_result is not None:
        mock_client.invoke_script = AsyncMock(return_value=mocked_result)
    algo._client = mock_client
    return algo, mock_client


class TestValkeyFixedWindowAlgo:
    @pytest.mark.asyncio
    async def test_registered_in_preregistered_algos(self):
        valkey_fixwin = get_valkey_fixwin_module()
        algo_module = get_algo_module()

        names = [cls.name for cls in algo_module.preregistered_algos]
        assert 'valkey_fixwin' in names
        assert valkey_fixwin.ValkeyFixedWindowAlgo.name == 'valkey_fixwin'

    @pytest.mark.asyncio
    async def test_key_schema_and_window_math(self, mock_app_for_algo, sample_query):
        valkey_fixwin = get_valkey_fixwin_module()
        algo, _ = await make_algo(mock_app_for_algo, mocked_result=1)

        window_size = 60
        fixed_now = 1_000_000_123  # arbitrary timestamp
        expected_window_start = fixed_now - fixed_now % window_size

        captured = {}

        async def fake_run_script(key, limitation, ws):
            captured['key'] = key
            captured['window_size'] = ws
            return 1

        algo._run_script = fake_run_script

        query = make_query(sample_query, window_length=window_size, limitation=10)
        with patch.object(valkey_fixwin.time, 'time', return_value=float(fixed_now)):
            result = await algo.require_access(query, 'person', '12345')

        assert result is True
        assert captured['key'] == f'langbot:ratelimit:fixwin:person:12345:{expected_window_start}'
        assert captured['window_size'] == window_size
        # Direct window-start helper check.
        assert algo._window_start(fixed_now, window_size) == expected_window_start

    @pytest.mark.asyncio
    async def test_within_limit_allows(self, mock_app_for_algo, sample_query):
        algo, mock_client = await make_algo(mock_app_for_algo)
        query = make_query(sample_query, limitation=5)

        # Simulate sequential counter increments staying within the limit.
        for i in range(1, 6):
            mock_client.invoke_script = AsyncMock(return_value=i)
            result = await algo.require_access(query, 'person', '12345')
            assert result is True, f'request {i} should be allowed'

    @pytest.mark.asyncio
    async def test_exceeds_limit_drop_returns_false(self, mock_app_for_algo, sample_query):
        algo, mock_client = await make_algo(mock_app_for_algo, mocked_result=-1)
        query = make_query(sample_query, limitation=5, strategy='drop')

        result = await algo.require_access(query, 'person', '12345')
        assert result is False

    @pytest.mark.asyncio
    async def test_exceeds_limit_wait_retries_next_window(self, mock_app_for_algo, sample_query):
        valkey_fixwin = get_valkey_fixwin_module()
        algo, _ = await make_algo(mock_app_for_algo)
        query = make_query(sample_query, window_length=60, limitation=1, strategy='wait')

        # First script call denies (-1), second (after wait) allows (1).
        results = iter([-1, 1])

        async def fake_run_script(key, limitation, ws):
            return next(results)

        algo._run_script = fake_run_script

        sleep_mock = AsyncMock()
        with patch.object(valkey_fixwin.asyncio, 'sleep', sleep_mock):
            result = await algo.require_access(query, 'person', '12345')

        assert result is True
        sleep_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fail_open_on_client_error(self, mock_app_for_algo, sample_query):
        algo, _ = await make_algo(mock_app_for_algo)
        query = make_query(sample_query, limitation=5)

        async def boom(key, limitation, ws):
            # A connection-type error simulates a real Valkey/infra failure.
            # (builtin ConnectionError is an OSError subclass, caught by the
            # narrowed fail-open handler.)
            raise ConnectionError('valkey down')

        algo._run_script = boom

        result = await algo.require_access(query, 'person', '12345')
        assert result is True  # fail-open
        assert mock_app_for_algo.logger.warning.called
        # Ensure no credential value is in the logged args.
        for call in mock_app_for_algo.logger.warning.call_args_list:
            for arg in call.args:
                lowered = str(arg).lower()
                assert 'password' not in lowered
                assert 'secret' not in lowered
                assert 's3cret' not in lowered

    @pytest.mark.asyncio
    async def test_programming_error_propagates(self, mock_app_for_algo, sample_query):
        """A programming bug (not an infra error) must NOT be swallowed by the
        fail-open handler — it should propagate so regressions fail loudly."""
        algo, _ = await make_algo(mock_app_for_algo)
        query = make_query(sample_query, limitation=5)

        async def bug(key, limitation, ws):
            raise KeyError('renamed_config_key')

        algo._run_script = bug

        with pytest.raises(KeyError):
            await algo.require_access(query, 'person', '12345')

    @pytest.mark.asyncio
    async def test_invalid_window_size_raises(self, mock_app_for_algo, sample_query):
        """window-length <= 0 is a misconfiguration and must raise, not be
        silently swallowed as a ZeroDivisionError fail-open."""
        algo, _ = await make_algo(mock_app_for_algo)
        query = make_query(sample_query, window_length=0, limitation=5)

        with pytest.raises(ValueError):
            await algo.require_access(query, 'person', '12345')

    @pytest.mark.asyncio
    async def test_fail_closed_denies_on_error(self, mock_app_for_algo, sample_query):
        """With valkey.fail_strategy='closed', a Valkey error denies the request."""
        valkey_fixwin = get_valkey_fixwin_module()
        mock_app_for_algo.instance_config.data = {
            'valkey': {'host': 'localhost', 'port': 6390, 'fail_strategy': 'closed'}
        }
        algo = valkey_fixwin.ValkeyFixedWindowAlgo(mock_app_for_algo)
        await algo.initialize()
        algo._client = AsyncMock()
        query = make_query(sample_query, limitation=5)

        async def boom(key, limitation, ws):
            raise ConnectionError('valkey down')

        algo._run_script = boom

        result = await algo.require_access(query, 'person', '12345')
        assert result is False  # fail-closed

    @pytest.mark.asyncio
    async def test_invalid_fail_strategy_raises(self, mock_app_for_algo):
        """An unknown fail_strategy is a misconfiguration and must raise at init."""
        valkey_fixwin = get_valkey_fixwin_module()
        mock_app_for_algo.instance_config.data = {'valkey': {'host': 'localhost', 'fail_strategy': 'bogus'}}
        algo = valkey_fixwin.ValkeyFixedWindowAlgo(mock_app_for_algo)
        with pytest.raises(ValueError):
            await algo.initialize()

    @pytest.mark.asyncio
    async def test_configurable_key_prefix(self, mock_app_for_algo, sample_query):
        """valkey.key_prefix overrides the default key namespace."""
        valkey_fixwin = get_valkey_fixwin_module()
        mock_app_for_algo.instance_config.data = {'valkey': {'host': 'localhost', 'key_prefix': 'tenant-a:rl'}}
        algo = valkey_fixwin.ValkeyFixedWindowAlgo(mock_app_for_algo)
        await algo.initialize()
        algo._client = AsyncMock()

        captured = {}

        async def fake_run_script(key, limitation, ws):
            captured['key'] = key
            return 1

        algo._run_script = fake_run_script

        fixed_now = 1_000_000_123
        window_size = 60
        expected_window_start = fixed_now - fixed_now % window_size
        query = make_query(sample_query, window_length=window_size, limitation=10)
        with patch.object(valkey_fixwin.time, 'time', return_value=float(fixed_now)):
            await algo.require_access(query, 'person', '12345')

        assert captured['key'] == f'tenant-a:rl:person:12345:{expected_window_start}'

    @pytest.mark.asyncio
    async def test_client_config_build(self, mock_app_for_algo):
        valkey_fixwin = get_valkey_fixwin_module()

        # Configure password + username + tls to exercise credential path.
        mock_app_for_algo.instance_config.data = {
            'valkey': {
                'host': 'valkey.example.com',
                'port': 6390,
                'db': 3,
                'password': 's3cret',
                'username': 'limiter',
                'tls': True,
            }
        }

        algo = valkey_fixwin.ValkeyFixedWindowAlgo(mock_app_for_algo)
        await algo.initialize()

        captured = {}

        async def fake_create(conf):
            captured['conf'] = conf
            return AsyncMock()

        with patch.object(valkey_fixwin.GlideClient, 'create', side_effect=fake_create):
            await algo._ensure_client()

        conf = captured['conf']
        assert conf.client_name == 'langbot_ratelimit_client'
        assert conf.lazy_connect is True
        assert conf.database_id == 3
        assert conf.use_tls is True
        assert conf.credentials is not None
        assert conf.addresses[0].host == 'valkey.example.com'
        assert conf.addresses[0].port == 6390

    @pytest.mark.asyncio
    async def test_client_config_no_credentials_without_password(self, mock_app_for_algo):
        valkey_fixwin = get_valkey_fixwin_module()
        # mock_app_for_algo default config has no password.
        algo = valkey_fixwin.ValkeyFixedWindowAlgo(mock_app_for_algo)
        await algo.initialize()

        captured = {}

        async def fake_create(conf):
            captured['conf'] = conf
            return AsyncMock()

        with patch.object(valkey_fixwin.GlideClient, 'create', side_effect=fake_create):
            await algo._ensure_client()

        assert captured['conf'].credentials is None

    @pytest.mark.asyncio
    async def test_release_access_noop(self, mock_app_for_algo, sample_query):
        algo, _ = await make_algo(mock_app_for_algo)
        query = make_query(sample_query)
        # Should not raise or alter any state.
        await algo.release_access(query, 'person', '12345')

    @pytest.mark.asyncio
    async def test_import_guard(self, mock_app_for_algo):
        valkey_fixwin = get_valkey_fixwin_module()
        with patch.object(valkey_fixwin, 'VALKEY_AVAILABLE', False):
            with pytest.raises(ImportError) as exc_info:
                valkey_fixwin.ValkeyFixedWindowAlgo(mock_app_for_algo)
            assert 'valkey-glide' in str(exc_info.value)
