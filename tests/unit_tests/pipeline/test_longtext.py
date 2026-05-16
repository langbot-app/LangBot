"""
LongTextProcessStage unit tests
"""

from importlib import import_module
from unittest.mock import AsyncMock

import pytest


def get_modules():
    """Lazy import to ensure proper initialization order"""
    longtext = import_module('langbot.pkg.pipeline.longtext.longtext')
    entities = import_module('langbot.pkg.pipeline.entities')
    return longtext, entities


@pytest.mark.asyncio
async def test_empty_response_message_chain_continues_without_processing(mock_app, sample_query):
    """Empty response chains should be a no-op for long text processing."""
    longtext, entities = get_modules()

    sample_query.resp_message_chain = []
    sample_query.pipeline_config = {
        'output': {
            'long-text-processing': {
                'threshold': 1,
            },
        },
    }

    stage = longtext.LongTextProcessStage(mock_app)
    stage.strategy_impl = AsyncMock()

    result = await stage.process(sample_query, 'LongTextProcessStage')

    assert result.result_type == entities.ResultType.CONTINUE
    assert result.new_query == sample_query
    stage.strategy_impl.process.assert_not_called()
