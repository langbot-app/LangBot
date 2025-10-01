"""
Integration tests for pipeline stages

These tests import and test the actual pipeline code.
Run from project root: pytest tests/pipeline/test_stages_integration.py
"""

import sys
import os
import pytest
from unittest.mock import AsyncMock, Mock

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


@pytest.mark.asyncio
async def test_bansess_whitelist_integration(mock_app, sample_query):
    """Integration test for bansess whitelist"""
    # Import after path is set
    from pkg.pipeline.bansess.bansess import BanSessionCheckStage
    from pkg.pipeline import entities as pipeline_entities
    import langbot_plugin.api.entities.builtin.provider.session as provider_session

    sample_query.pipeline_config['trigger'] = {
        'access-control': {
            'mode': 'whitelist',
            'whitelist': [f'{sample_query.launcher_type.value}_{sample_query.launcher_id}'],
        }
    }

    stage = BanSessionCheckStage(mock_app)
    await stage.initialize({})

    result = await stage.process(sample_query, 'BanSessionCheckStage')

    assert result.result_type == pipeline_entities.ResultType.CONTINUE


@pytest.mark.asyncio
async def test_ratelimit_integration(mock_app, sample_query):
    """Integration test for ratelimit"""
    from pkg.pipeline.ratelimit.ratelimit import RateLimit
    from pkg.pipeline import entities as pipeline_entities

    stage = RateLimit(mock_app)

    # Mock rate limit algorithm
    mock_algo = Mock()
    mock_algo.require_access = AsyncMock(return_value=True)
    mock_algo.release_access = AsyncMock()
    stage.algo = mock_algo

    result = await stage.process(sample_query, 'RequireRateLimitOccupancy')

    assert result.result_type == pipeline_entities.ResultType.CONTINUE
    mock_algo.require_access.assert_called_once()
