"""
RateLimit stage unit tests

Tests the actual RateLimit implementation from pkg.pipeline.ratelimit
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch
from importlib import import_module
import langbot_plugin.api.entities.builtin.provider.session as provider_session


def get_modules():
    """Lazy import to ensure proper initialization order"""
    # Import pipelinemgr first to trigger proper stage registration
    ratelimit = import_module('langbot.pkg.pipeline.ratelimit.ratelimit')
    entities = import_module('langbot.pkg.pipeline.entities')
    algo_module = import_module('langbot.pkg.pipeline.ratelimit.algo')
    return ratelimit, entities, algo_module


def get_fixedwin_module():
    """Lazy import of FixedWindowAlgo"""
    return import_module('langbot.pkg.pipeline.ratelimit.algos.fixedwin')


class TestFixedWindowAlgo:
    """Tests for the actual FixedWindowAlgo implementation.

    IMPORTANT: These tests verify the real algorithm logic, not mocks.
    """

    @pytest.fixture
    def mock_app_for_algo(self):
        """Create mock app for algorithm initialization."""
        mock_app = Mock()
        mock_app.logger = Mock()
        return mock_app

    @pytest.fixture
    def sample_query_with_rate_limit(self, sample_query):
        """Create query with rate limit configuration."""
        sample_query.pipeline_config = {
            'safety': {
                'rate-limit': {
                    'window-length': 60,  # 60 seconds window
                    'limitation': 10,     # 10 requests per window
                    'strategy': 'drop',
                }
            }
        }
        return sample_query

    @pytest.mark.asyncio
    async def test_fixedwin_algo_initialization(self, mock_app_for_algo):
        """Test that FixedWindowAlgo initializes correctly."""
        fixedwin = get_fixedwin_module()

        algo = fixedwin.FixedWindowAlgo(mock_app_for_algo)
        await algo.initialize()

        assert algo.containers_lock is not None
        assert algo.containers == {}

    @pytest.mark.asyncio
    async def test_fixedwin_within_limit_returns_true(self, mock_app_for_algo, sample_query_with_rate_limit):
        """Test that requests within limit are allowed."""
        fixedwin = get_fixedwin_module()

        algo = fixedwin.FixedWindowAlgo(mock_app_for_algo)
        await algo.initialize()

        # Make requests within limit
        for i in range(10):
            result = await algo.require_access(
                sample_query_with_rate_limit,
                provider_session.LauncherTypes.PERSON,
                '12345'
            )
            assert result is True, f"Request {i+1} should be allowed"

    @pytest.mark.asyncio
    async def test_fixedwin_exceeds_limit_drop_strategy(self, mock_app_for_algo, sample_query_with_rate_limit):
        """Test that exceeding limit with 'drop' strategy returns False."""
        fixedwin = get_fixedwin_module()

        algo = fixedwin.FixedWindowAlgo(mock_app_for_algo)
        await algo.initialize()

        # Exhaust the limit
        for i in range(10):
            await algo.require_access(
                sample_query_with_rate_limit,
                provider_session.LauncherTypes.PERSON,
                '12345'
            )

        # Next request should be denied
        result = await algo.require_access(
            sample_query_with_rate_limit,
            provider_session.LauncherTypes.PERSON,
            '12345'
        )

        assert result is False, "Request exceeding limit should be denied"

    @pytest.mark.asyncio
    async def test_fixedwin_different_sessions_isolated(self, mock_app_for_algo, sample_query_with_rate_limit):
        """Test that different sessions have independent rate limits."""
        fixedwin = get_fixedwin_module()

        algo = fixedwin.FixedWindowAlgo(mock_app_for_algo)
        await algo.initialize()

        # Exhaust limit for session 1
        for i in range(10):
            await algo.require_access(
                sample_query_with_rate_limit,
                provider_session.LauncherTypes.PERSON,
                'session1'
            )

        # Session 2 should still have its own limit
        result = await algo.require_access(
            sample_query_with_rate_limit,
            provider_session.LauncherTypes.PERSON,
            'session2'
        )

        assert result is True, "Different session should have independent limit"

    @pytest.mark.asyncio
    async def test_fixedwin_limit_one_request(self, mock_app_for_algo, sample_query):
        """Test with limitation=1 allows only one request."""
        fixedwin = get_fixedwin_module()

        sample_query.pipeline_config = {
            'safety': {
                'rate-limit': {
                    'window-length': 60,
                    'limitation': 1,  # Only 1 request allowed
                    'strategy': 'drop',
                }
            }
        }

        algo = fixedwin.FixedWindowAlgo(mock_app_for_algo)
        await algo.initialize()

        # First request allowed
        result1 = await algo.require_access(
            sample_query,
            provider_session.LauncherTypes.PERSON,
            '12345'
        )
        assert result1 is True

        # Second request denied
        result2 = await algo.require_access(
            sample_query,
            provider_session.LauncherTypes.PERSON,
            '12345'
        )
        assert result2 is False

    @pytest.mark.asyncio
    async def test_fixedwin_container_persists(self, mock_app_for_algo, sample_query_with_rate_limit):
        """Test that container is created and persists across requests."""
        fixedwin = get_fixedwin_module()

        algo = fixedwin.FixedWindowAlgo(mock_app_for_algo)
        await algo.initialize()

        # First request creates container
        await algo.require_access(
            sample_query_with_rate_limit,
            provider_session.LauncherTypes.PERSON,
            '12345'
        )

        # Key format: 'LauncherTypes.PERSON_12345' (enum string representation)
        expected_key = 'LauncherTypes.PERSON_12345'
        assert expected_key in algo.containers
        container = algo.containers[expected_key]

        # Container should have records
        assert len(container.records) > 0

    @pytest.mark.asyncio
    async def test_fixedwin_new_window_clears_records(self, mock_app_for_algo, sample_query):
        """Test that a new time window starts fresh records.

        This test verifies the window calculation logic:
        - Records are keyed by window start timestamp
        - When window advances, new key is created
        """
        fixedwin = get_fixedwin_module()

        # Use a very short window for testing
        sample_query.pipeline_config = {
            'safety': {
                'rate-limit': {
                    'window-length': 1,  # 1 second window for fast test
                    'limitation': 5,
                    'strategy': 'drop',
                }
            }
        }

        algo = fixedwin.FixedWindowAlgo(mock_app_for_algo)
        await algo.initialize()

        # Make requests in current window
        now = int(time.time())
        window_start = now - now % 1

        for i in range(5):
            await algo.require_access(sample_query, provider_session.LauncherTypes.PERSON, 'test')

        # Key format: 'LauncherTypes.PERSON_test'
        expected_key = 'LauncherTypes.PERSON_test'
        container = algo.containers[expected_key]
        assert window_start in container.records
        assert container.records[window_start] == 5

        # Wait for next window (1 second)
        await asyncio.sleep(1.1)

        # New request should be allowed (new window)
        result = await algo.require_access(sample_query, provider_session.LauncherTypes.PERSON, 'test')
        assert result is True, "New window should allow new requests"

    @pytest.mark.asyncio
    async def test_fixedwin_wait_strategy_blocks_until_next_window(self, mock_app_for_algo, sample_query):
        """Test that 'wait' strategy blocks until next window.

        NOTE: This test is timing-sensitive and may take ~1 second.
        """
        fixedwin = get_fixedwin_module()

        # Use 1-second window for testability
        sample_query.pipeline_config = {
            'safety': {
                'rate-limit': {
                    'window-length': 1,
                    'limitation': 1,  # Only 1 request per second
                    'strategy': 'wait',
                }
            }
        }

        algo = fixedwin.FixedWindowAlgo(mock_app_for_algo)
        await algo.initialize()

        # First request allowed
        start_time = time.time()
        result1 = await algo.require_access(
            sample_query,
            provider_session.LauncherTypes.PERSON,
            'wait_test'
        )
        assert result1 is True

        # Exhaust limit
        await algo.require_access(sample_query, provider_session.LauncherTypes.PERSON, 'wait_test')

        # Third request should wait and then succeed
        result3 = await algo.require_access(
            sample_query,
            provider_session.LauncherTypes.PERSON,
            'wait_test'
        )
        elapsed = time.time() - start_time

        assert result3 is True, "After wait, request should succeed"
        # Should have waited approximately until next window
        # With 1-second window, elapsed should be > 0.5 second (allowing for timing variance)
        # Note: This is a timing-sensitive test, so we use a generous tolerance
        assert elapsed >= 0.5, f"Should have waited for next window, elapsed={elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_fixedwin_release_access(self, mock_app_for_algo, sample_query_with_rate_limit):
        """Test that release_access does nothing (current implementation)."""
        fixedwin = get_fixedwin_module()

        algo = fixedwin.FixedWindowAlgo(mock_app_for_algo)
        await algo.initialize()

        # release_access is empty in current implementation
        await algo.release_access(
            sample_query_with_rate_limit,
            provider_session.LauncherTypes.PERSON,
            '12345'
        )

        # Should not raise or change state
        assert 'person_12345' not in algo.containers


# Original mock-based tests for RateLimit stage integration
@pytest.mark.asyncio
async def test_require_access_allowed(mock_app, sample_query):
    """Test RequireRateLimitOccupancy allows access when rate limit is not exceeded"""
    ratelimit, entities, algo_module = get_modules()

    sample_query.launcher_type = provider_session.LauncherTypes.PERSON
    sample_query.launcher_id = '12345'
    sample_query.pipeline_config = {}

    # Create mock algorithm that allows access
    mock_algo = Mock(spec=algo_module.ReteLimitAlgo)
    mock_algo.require_access = AsyncMock(return_value=True)
    mock_algo.initialize = AsyncMock()

    stage = ratelimit.RateLimit(mock_app)

    # Patch the algorithm selection to use our mock
    with patch.object(algo_module, 'preregistered_algos', []):
        stage.algo = mock_algo

    result = await stage.process(sample_query, 'RequireRateLimitOccupancy')

    assert result.result_type == entities.ResultType.CONTINUE
    assert result.new_query == sample_query
    mock_algo.require_access.assert_called_once_with(sample_query, 'person', '12345')


@pytest.mark.asyncio
async def test_require_access_denied(mock_app, sample_query):
    """Test RequireRateLimitOccupancy denies access when rate limit is exceeded"""
    ratelimit, entities, algo_module = get_modules()

    sample_query.launcher_type = provider_session.LauncherTypes.PERSON
    sample_query.launcher_id = '12345'
    sample_query.pipeline_config = {}

    # Create mock algorithm that denies access
    mock_algo = Mock(spec=algo_module.ReteLimitAlgo)
    mock_algo.require_access = AsyncMock(return_value=False)
    mock_algo.initialize = AsyncMock()

    stage = ratelimit.RateLimit(mock_app)

    # Patch the algorithm selection to use our mock
    with patch.object(algo_module, 'preregistered_algos', []):
        stage.algo = mock_algo

    result = await stage.process(sample_query, 'RequireRateLimitOccupancy')

    assert result.result_type == entities.ResultType.INTERRUPT
    assert result.user_notice != ''
    mock_algo.require_access.assert_called_once()


@pytest.mark.asyncio
async def test_release_access(mock_app, sample_query):
    """Test ReleaseRateLimitOccupancy releases rate limit occupancy"""
    ratelimit, entities, algo_module = get_modules()

    sample_query.launcher_type = provider_session.LauncherTypes.PERSON
    sample_query.launcher_id = '12345'
    sample_query.pipeline_config = {}

    # Create mock algorithm
    mock_algo = Mock(spec=algo_module.ReteLimitAlgo)
    mock_algo.release_access = AsyncMock()
    mock_algo.initialize = AsyncMock()

    stage = ratelimit.RateLimit(mock_app)

    # Patch the algorithm selection to use our mock
    with patch.object(algo_module, 'preregistered_algos', []):
        stage.algo = mock_algo

    result = await stage.process(sample_query, 'ReleaseRateLimitOccupancy')

    assert result.result_type == entities.ResultType.CONTINUE
    assert result.new_query == sample_query
    mock_algo.release_access.assert_called_once_with(sample_query, 'person', '12345')
