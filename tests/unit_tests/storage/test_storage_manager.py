"""
Tests for langbot.pkg.storage.mgr module.

Tests storage manager initialization and provider selection.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from langbot.pkg.storage.mgr import StorageMgr
from langbot.pkg.storage.providers.localstorage import LocalStorageProvider


class TestStorageMgr:
    """Test StorageMgr class."""

    def test_init_stores_app_reference(self):
        """StorageMgr should store the application reference."""
        mock_app = Mock()
        storage_mgr = StorageMgr(mock_app)
        assert storage_mgr.ap == mock_app

    @pytest.mark.asyncio
    async def test_shutdown_delegates_to_active_provider(self):
        storage_mgr = StorageMgr(Mock())
        storage_mgr.storage_provider = Mock(shutdown=AsyncMock())

        await storage_mgr.shutdown()

        storage_mgr.storage_provider.shutdown.assert_awaited_once()


class TestStorageProviderBase:
    """Test StorageProvider base class methods."""

    def test_provider_stores_app_reference(self):
        """Provider should store app reference."""
        mock_app = Mock()

        # Use LocalStorageProvider as concrete implementation
        with patch('os.path.exists', return_value=True):
            with patch('os.makedirs'):
                provider = LocalStorageProvider(mock_app)
                assert provider.ap == mock_app

    @pytest.mark.asyncio
    async def test_provider_base_initialize(self):
        """Provider base initialize should be callable and do nothing."""
        mock_app = Mock()

        with patch('os.path.exists', return_value=True):
            with patch('os.makedirs'):
                provider = LocalStorageProvider(mock_app)
                # Initialize should not raise
                await provider.initialize()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
