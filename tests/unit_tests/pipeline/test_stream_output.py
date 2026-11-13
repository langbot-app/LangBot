"""A Query keeps one streaming mode for its whole turn."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.pipeline.stream_output import STREAM_OUTPUT_KEY, stream_output_enabled


@pytest.mark.asyncio
async def test_mode_recorded_at_ingress_wins_over_later_adapter_answers():
    adapter = SimpleNamespace(is_stream_output_supported=AsyncMock(return_value=False))
    query = SimpleNamespace(adapter=adapter, variables={STREAM_OUTPUT_KEY: True})

    assert await stream_output_enabled(query) is True
    adapter.is_stream_output_supported.assert_not_awaited()


@pytest.mark.asyncio
async def test_first_answer_is_kept_when_ingress_recorded_nothing():
    adapter = SimpleNamespace(is_stream_output_supported=AsyncMock(side_effect=[True, False]))
    query = SimpleNamespace(adapter=adapter, variables={})

    assert await stream_output_enabled(query) is True
    assert await stream_output_enabled(query) is True
    assert query.variables[STREAM_OUTPUT_KEY] is True
    adapter.is_stream_output_supported.assert_awaited_once()


@pytest.mark.asyncio
async def test_adapter_without_streaming_support_does_not_stream():
    query = SimpleNamespace(adapter=object(), variables={})

    assert await stream_output_enabled(query) is False
