"""Behavioral contracts for StorageMgr lifecycle."""

from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.storage.mgr import StorageMgr


@pytest.mark.asyncio
async def test_shutdown_releases_content_store_and_active_provider():
    storage_mgr = StorageMgr(Mock())
    storage_mgr.content_store.shutdown = AsyncMock()
    storage_mgr.storage_provider = Mock(shutdown=AsyncMock())

    await storage_mgr.shutdown()

    storage_mgr.content_store.shutdown.assert_awaited_once_with()
    storage_mgr.storage_provider.shutdown.assert_awaited_once_with()
