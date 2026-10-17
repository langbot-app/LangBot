from unittest.mock import Mock

import httpx
import pytest

from langbot.pkg.telemetry.telemetry import TelemetryManager


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'ack,expected',
    [
        ({'stored': 1, 'rejected': 0}, True),
        ({'stored': 0, 'rejected': 1}, False),
        ({'stored': 1, 'rejected': 1}, False),
        ({'stored': 0, 'rejected': 0}, False),
        ({}, False),
        ({'stored': True, 'rejected': 0}, False),
    ],
)
async def test_batch_requires_complete_ack(ack, expected):
    app = Mock()
    manager = TelemetryManager(app)
    manager.telemetry_config = {'url': 'https://telemetry.test'}
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={'code': 0, 'data': ack}))
    ) as client:
        manager._client = client
        assert await manager.send({'records': [{'event_id': 'a' * 163}]}) is expected
