from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.service.apikey import ApiKeyService


@pytest.mark.asyncio
@pytest.mark.parametrize('api_key', [None, 123, b'lbk_bytes', '', 'plain_key', ' LBK_bad', 'sk-lbk_fake'])
async def test_verify_api_key_rejects_non_lbk_keys_without_db_query(api_key):
    persistence_mgr = SimpleNamespace(execute_async=AsyncMock())
    service = ApiKeyService(SimpleNamespace(persistence_mgr=persistence_mgr))

    result = await service.verify_api_key(api_key)

    assert result is False
    persistence_mgr.execute_async.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('db_row', 'expected'),
    [
        (object(), True),
        (None, False),
    ],
)
async def test_verify_api_key_keeps_db_validation_for_lbk_keys(db_row, expected):
    query_result = Mock()
    query_result.first.return_value = db_row
    persistence_mgr = SimpleNamespace(execute_async=AsyncMock(return_value=query_result))
    service = ApiKeyService(SimpleNamespace(persistence_mgr=persistence_mgr))

    result = await service.verify_api_key('lbk_valid_format')

    assert result is expected
    persistence_mgr.execute_async.assert_awaited_once()
