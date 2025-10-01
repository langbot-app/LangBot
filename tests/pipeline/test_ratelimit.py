"""
RateLimit stage unit tests
"""

import pytest
from unittest.mock import AsyncMock, Mock

from pkg.pipeline.ratelimit.ratelimit import RateLimit
from pkg.pipeline import entities as pipeline_entities


@pytest.mark.asyncio
async def test_ratelimit_require_access_allowed(mock_app, sample_query):
    """Test rate limiter allows access"""
    stage = RateLimit(mock_app)

    # Mock rate limit algorithm
    mock_algo = Mock()
    mock_algo.require_access = AsyncMock(return_value=True)
    mock_algo.release_access = AsyncMock()
    stage.algo = mock_algo

    # Test request access
    result = await stage.process(sample_query, 'RequireRateLimitOccupancy')

    assert result.result_type == pipeline_entities.ResultType.CONTINUE
    mock_algo.require_access.assert_called_once()


@pytest.mark.asyncio
async def test_ratelimit_require_access_denied(mock_app, sample_query):
    """Test rate limiter denies access"""
    stage = RateLimit(mock_app)

    # Mock rate limit algorithm
    mock_algo = Mock()
    mock_algo.require_access = AsyncMock(return_value=False)
    stage.algo = mock_algo

    # Test request access denied
    result = await stage.process(sample_query, 'RequireRateLimitOccupancy')

    assert result.result_type == pipeline_entities.ResultType.INTERRUPT
    assert result.user_notice == '请求数超过限速器设定值,已丢弃本消息。'
    mock_algo.require_access.assert_called_once()


@pytest.mark.asyncio
async def test_ratelimit_release_access(mock_app, sample_query):
    """Test releasing rate limiter occupancy"""
    stage = RateLimit(mock_app)

    # Mock rate limit algorithm
    mock_algo = Mock()
    mock_algo.release_access = AsyncMock()
    stage.algo = mock_algo

    # Test release access
    result = await stage.process(sample_query, 'ReleaseRateLimitOccupancy')

    assert result.result_type == pipeline_entities.ResultType.CONTINUE
    mock_algo.release_access.assert_called_once()
