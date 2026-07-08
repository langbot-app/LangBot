"""
Tests for storage manager and provider selection
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from langbot.pkg.storage.mgr import StorageMgr
from langbot.pkg.storage.providers.localstorage import LocalStorageProvider
from langbot.pkg.storage.providers.s3storage import S3StorageProvider


class TestStorageProviderSelection:
    """Test storage provider selection based on configuration"""

    @pytest.mark.asyncio
    async def test_default_to_local_storage(self):
        """Test that local storage is used by default when no config is provided"""
        # Mock application
        mock_app = Mock()
        mock_app.instance_config = Mock()
        mock_app.instance_config.data = {}
        mock_app.logger = Mock()

        storage_mgr = StorageMgr(mock_app)

        with patch.object(LocalStorageProvider, 'initialize', new_callable=AsyncMock) as mock_init:
            await storage_mgr.initialize()
            assert isinstance(storage_mgr.storage_provider, LocalStorageProvider)
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_explicit_local_storage(self):
        """Test that local storage is used when explicitly configured"""
        # Mock application
        mock_app = Mock()
        mock_app.instance_config = Mock()
        mock_app.instance_config.data = {'storage': {'use': 'local'}}
        mock_app.logger = Mock()

        storage_mgr = StorageMgr(mock_app)

        with patch.object(LocalStorageProvider, 'initialize', new_callable=AsyncMock) as mock_init:
            await storage_mgr.initialize()
            assert isinstance(storage_mgr.storage_provider, LocalStorageProvider)
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_s3_storage_provider_selection(self):
        """Test that S3 storage is used when configured"""
        # Mock application
        mock_app = Mock()
        mock_app.instance_config = Mock()
        mock_app.instance_config.data = {
            'storage': {
                'use': 's3',
                's3': {
                    'endpoint_url': 'https://s3.amazonaws.com',
                    'access_key_id': 'test_key',
                    'secret_access_key': 'test_secret',
                    'region': 'us-east-1',
                    'bucket': 'test-bucket',
                },
            }
        }
        mock_app.logger = Mock()

        storage_mgr = StorageMgr(mock_app)

        with patch.object(S3StorageProvider, 'initialize', new_callable=AsyncMock) as mock_init:
            await storage_mgr.initialize()
            assert isinstance(storage_mgr.storage_provider, S3StorageProvider)
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_storage_type_defaults_to_local(self):
        """Test that invalid storage type defaults to local storage"""
        # Mock application
        mock_app = Mock()
        mock_app.instance_config = Mock()
        mock_app.instance_config.data = {'storage': {'use': 'invalid_type'}}
        mock_app.logger = Mock()

        storage_mgr = StorageMgr(mock_app)

        with patch.object(LocalStorageProvider, 'initialize', new_callable=AsyncMock) as mock_init:
            await storage_mgr.initialize()
            assert isinstance(storage_mgr.storage_provider, LocalStorageProvider)
            mock_init.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
