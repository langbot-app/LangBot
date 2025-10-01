"""
RateLimit stage unit tests
"""

import pytest
from unittest.mock import AsyncMock, Mock
from importlib import import_module


def get_ratelimit_module():
    return import_module('pkg.pipeline.ratelimit.ratelimit')


def get_entities_module():
    return import_module('pkg.pipeline.entities')


@pytest.mark.asyncio
async def test_ratelimit_require_access_allowed(mock_app, sample_query):
    """Test rate limiter allows access"""
    ratelimit = get_ratelimit_module()
    entities = get_entities_module()

    stage = ratelimit.RateLimit(mock_app)

    # Mock rate limit algorithm
    mock_algo = Mock()
    mock_algo.require_access = AsyncMock(return_value=True)
    mock_algo.release_access = AsyncMock()
    stage.algo = mock_algo

    # Test request access
    result = await stage.process(sample_query, 'RequireRateLimitOccupancy')

    assert result.result_type == entities.ResultType.CONTINUE
    mock_algo.require_access.assert_called_once()


@pytest.mark.asyncio
async def test_ratelimit_require_access_denied(mock_app, sample_query):
    """Test rate limiter denies access"""
    ratelimit = get_ratelimit_module()
    entities = get_entities_module()

    stage = ratelimit.RateLimit(mock_app)

    # Mock rate limit algorithm
    mock_algo = Mock()
    mock_algo.require_access = AsyncMock(return_value=False)
    stage.algo = mock_algo

    # Test request access denied
    result = await stage.process(sample_query, 'RequireRateLimitOccupancy')

    assert result.result_type == entities.ResultType.INTERRUPT
    assert result.user_notice == '请求数超过限速器设定值,已丢弃本消息。'
    mock_algo.require_access.assert_called_once()


@pytest.mark.asyncio
async def test_ratelimit_release_access(mock_app, sample_query):
    """Test releasing rate limiter occupancy"""
    ratelimit = get_ratelimit_module()
    entities = get_entities_module()

    stage = ratelimit.RateLimit(mock_app)

    # Mock rate limit algorithm
    mock_algo = Mock()
    mock_algo.release_access = AsyncMock()
    stage.algo = mock_algo

    # Test release access
    result = await stage.process(sample_query, 'ReleaseRateLimitOccupancy')

    assert result.result_type == entities.ResultType.CONTINUE
    mock_algo.release_access.assert_called_once()
