"""
Tests for langbot.pkg.storage.mgr module.

Tests storage manager initialization and provider selection.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from langbot.pkg.storage.mgr import StorageMgr
from langbot.pkg.storage.providers.localstorage import LocalStorageProvider
from langbot.pkg.storage.providers.s3storage import S3StorageProvider


class TestStorageMgr:
    """Test StorageMgr class."""

    def test_init_stores_app_reference(self):
        """StorageMgr should store the application reference."""
        mock_app = Mock()
        storage_mgr = StorageMgr(mock_app)
        assert storage_mgr.ap == mock_app

    @pytest.mark.asyncio
    async def test_initialize_default_local(self):
        """Should use local storage by default."""
        mock_app = Mock()
        mock_app.instance_config = Mock()
        mock_app.instance_config.data = {}
        mock_app.logger = Mock()

        storage_mgr = StorageMgr(mock_app)

        with patch.object(LocalStorageProvider, "initialize", new_callable=AsyncMock):
            await storage_mgr.initialize()
            assert isinstance(storage_mgr.storage_provider, LocalStorageProvider)
            mock_app.logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_initialize_with_explicit_local(self):
        """Should use local storage when explicitly configured."""
        mock_app = Mock()
        mock_app.instance_config = Mock()
        mock_app.instance_config.data = {"storage": {"use": "local"}}
        mock_app.logger = Mock()

        storage_mgr = StorageMgr(mock_app)

        with patch.object(LocalStorageProvider, "initialize", new_callable=AsyncMock):
            await storage_mgr.initialize()
            assert isinstance(storage_mgr.storage_provider, LocalStorageProvider)

    @pytest.mark.asyncio
    async def test_initialize_with_s3(self):
        """Should use S3 storage when configured."""
        mock_app = Mock()
        mock_app.instance_config = Mock()
        mock_app.instance_config.data = {
            "storage": {"use": "s3", "s3": {"endpoint_url": "https://s3.amazonaws.com"}}
        }
        mock_app.logger = Mock()

        storage_mgr = StorageMgr(mock_app)

        with patch.object(S3StorageProvider, "initialize", new_callable=AsyncMock):
            await storage_mgr.initialize()
            assert isinstance(storage_mgr.storage_provider, S3StorageProvider)

    @pytest.mark.asyncio
    async def test_initialize_invalid_type_defaults_to_local(self):
        """Should default to local storage for invalid storage type."""
        mock_app = Mock()
        mock_app.instance_config = Mock()
        mock_app.instance_config.data = {"storage": {"use": "invalid_type"}}
        mock_app.logger = Mock()

        storage_mgr = StorageMgr(mock_app)

        with patch.object(LocalStorageProvider, "initialize", new_callable=AsyncMock):
            await storage_mgr.initialize()
            assert isinstance(storage_mgr.storage_provider, LocalStorageProvider)

    @pytest.mark.asyncio
    async def test_initialize_calls_provider_initialize(self):
        """Should call the provider's initialize method."""
        mock_app = Mock()
        mock_app.instance_config = Mock()
        mock_app.instance_config.data = {}
        mock_app.logger = Mock()

        storage_mgr = StorageMgr(mock_app)

        with patch.object(
            LocalStorageProvider, "initialize", new_callable=AsyncMock
        ) as mock_init:
            await storage_mgr.initialize()
            mock_init.assert_called_once()


class TestStorageProviderBase:
    """Test StorageProvider base class methods."""

    def test_provider_stores_app_reference(self):
        """Provider should store app reference."""
        mock_app = Mock()

        # Use LocalStorageProvider as concrete implementation
        with patch("os.path.exists", return_value=True):
            with patch("os.makedirs"):
                provider = LocalStorageProvider(mock_app)
                assert provider.ap == mock_app

    @pytest.mark.asyncio
    async def test_provider_base_initialize(self):
        """Provider base initialize should be callable and do nothing."""
        mock_app = Mock()

        with patch("os.path.exists", return_value=True):
            with patch("os.makedirs"):
                provider = LocalStorageProvider(mock_app)
                # Initialize should not raise
                await provider.initialize()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])