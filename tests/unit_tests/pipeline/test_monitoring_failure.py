"""A stage exception must finish the original monitoring row."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.pipeline.monitoring_helper import MonitoringHelper
from langbot.pkg.pipeline.pool import get_query_execution_context


@pytest.mark.asyncio
async def test_exception_finishes_original_message_even_if_error_detail_write_fails(sample_query):
    sample_query.variables['_monitoring_message_id'] = 'original-message'
    service = SimpleNamespace(
        update_message_status=AsyncMock(), record_message=AsyncMock(side_effect=RuntimeError('detail failure'))
    )
    app = SimpleNamespace(monitoring_service=service, logger=Mock())
    await MonitoringHelper.record_query_error(
        app, sample_query, 'bot', 'bot', 'pipeline', 'pipeline', KeyError('random')
    )
    service.update_message_status.assert_awaited_once_with(
        get_query_execution_context(sample_query), message_id='original-message', status='error', level='error'
    )
