from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.service.apikey import ApiKeyService
from langbot.pkg.entity.persistence.apikey import ApiKeyStatus


@pytest.mark.asyncio
@pytest.mark.parametrize('api_key', [None, 123, b'lbk_bytes', '', 'plain_key', ' LBK_bad', 'sk-lbk_fake'])
async def test_verify_api_key_rejects_non_lbk_keys_without_db_query(api_key):
    persistence_mgr = SimpleNamespace(execute_async=AsyncMock())
    instance_config = SimpleNamespace(data={'api': {'global_api_key': ''}})
    workspace_service = SimpleNamespace(get_execution_binding=AsyncMock())
    service = ApiKeyService(
        SimpleNamespace(
            persistence_mgr=persistence_mgr,
            instance_config=instance_config,
            workspace_service=workspace_service,
        )
    )

    result = await service.verify_api_key(api_key)

    assert result is False
    persistence_mgr.execute_async.assert_not_awaited()
    workspace_service.get_execution_binding.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('key_exists', [True, False])
async def test_verify_api_key_keeps_db_validation_for_lbk_keys(key_exists):
    key = (
        SimpleNamespace(
            id=1,
            uuid='key-uuid',
            workspace_uuid='workspace-a',
            status=ApiKeyStatus.ACTIVE.value,
            expires_at=None,
            scopes=[],
        )
        if key_exists
        else None
    )
    discovery_result = Mock()
    discovery_result.first.return_value = key
    query_results = [discovery_result]
    if key_exists:
        scoped_result = Mock()
        scoped_result.first.return_value = key
        update_result = Mock()
        update_result.scalar_one_or_none.return_value = key.id
        query_results.extend([scoped_result, update_result])
    persistence_mgr = SimpleNamespace(execute_async=AsyncMock(side_effect=query_results))
    instance_config = SimpleNamespace(data={'api': {'global_api_key': ''}})
    workspace_service = SimpleNamespace(
        get_execution_binding=AsyncMock(
            return_value=SimpleNamespace(
                instance_uuid='instance-a',
                workspace_uuid='workspace-a',
                placement_generation=1,
            )
        )
    )
    service = ApiKeyService(
        SimpleNamespace(
            persistence_mgr=persistence_mgr,
            instance_config=instance_config,
            workspace_service=workspace_service,
        )
    )

    result = await service.verify_api_key('lbk_valid_format')

    assert result is key_exists
    assert persistence_mgr.execute_async.await_count == (3 if key_exists else 1)
    if key_exists:
        workspace_service.get_execution_binding.assert_awaited_once_with('workspace-a')
    else:
        workspace_service.get_execution_binding.assert_not_awaited()
