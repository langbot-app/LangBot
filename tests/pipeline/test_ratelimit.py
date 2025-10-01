"""
RateLimit stage unit tests

Tests the actual RateLimit implementation from pkg.pipeline.ratelimit
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from importlib import import_module
import langbot_plugin.api.entities.builtin.provider.session as provider_session


def get_modules():
    """Lazy import to ensure proper initialization order"""
    # Import pipelinemgr first to trigger proper stage registration
    pipelinemgr = import_module('pkg.pipeline.pipelinemgr')
    ratelimit = import_module('pkg.pipeline.ratelimit.ratelimit')
    entities = import_module('pkg.pipeline.entities')
    algo_module = import_module('pkg.pipeline.ratelimit.algo')
    return ratelimit, entities, algo_module


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
    mock_algo.require_access.assert_called_once_with(
        sample_query,
        'person',
        '12345'
    )


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
    mock_algo.release_access.assert_called_once_with(
        sample_query,
        'person',
        '12345'
    )
