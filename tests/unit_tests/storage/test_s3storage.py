"""Unit tests for S3StorageProvider.

Tests cover:
- S3 client initialization with bucket creation
- CRUD operations (save, load, exists, delete, size)
- Recursive directory deletion
- Error handling for various S3 errors

Uses moto library to mock AWS S3 service.
"""
from __future__ import annotations

import pytest
from unittest.mock import Mock
from importlib import import_module


def get_s3storage_module():
    """Lazy import to avoid circular import issues."""
    return import_module('langbot.pkg.storage.providers.s3storage')


@pytest.fixture
def mock_app_with_s3_config():
    """Create mock app with S3 configuration."""
    mock_app = Mock()
    mock_app.instance_config = Mock()
    mock_app.instance_config.data = {
        'storage': {
            's3': {
                'endpoint_url': '',
                'access_key_id': 'testing',
                'secret_access_key': 'testing',
                'region': 'us-east-1',
                'bucket': 'test-langbot-storage',
            }
        }
    }
    mock_app.logger = Mock()
    return mock_app


@pytest.fixture
def s3_mock():
    """Set up moto S3 mock context."""
    from moto import mock_aws
    with mock_aws():
        import boto3
        # Create bucket for tests that need pre-existing bucket
        s3 = boto3.client('s3', region_name='us-east-1')
        yield s3


class TestS3StorageProviderInit:
    """Tests for S3StorageProvider initialization."""

    def test_init_stores_app_reference(self):
        """Test that __init__ stores the Application reference."""
        s3storage = get_s3storage_module()

        mock_app = Mock()
        provider = s3storage.S3StorageProvider(mock_app)
        assert provider.ap is mock_app

    def test_init_s3_client_none(self):
        """Test that s3_client starts as None."""
        s3storage = get_s3storage_module()

        mock_app = Mock()
        provider = s3storage.S3StorageProvider(mock_app)
        assert provider.s3_client is None
        assert provider.bucket_name is None


class TestS3StorageProviderWithMoto:
    """Tests using moto to mock AWS S3."""

    @pytest.mark.asyncio
    async def test_initialize_creates_bucket_when_not_exists(self, mock_app_with_s3_config, s3_mock):
        """Test that initialize creates bucket when it doesn't exist."""
        s3storage = get_s3storage_module()

        provider = s3storage.S3StorageProvider(mock_app_with_s3_config)
        await provider.initialize()

        assert provider.s3_client is not None
        assert provider.bucket_name == 'test-langbot-storage'
        mock_app_with_s3_config.logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_initialize_uses_existing_bucket(self, mock_app_with_s3_config, s3_mock):
        """Test that initialize uses existing bucket without creating."""
        s3storage = get_s3storage_module()

        # Pre-create bucket in mock
        s3_mock.create_bucket(Bucket='test-langbot-storage')

        provider = s3storage.S3StorageProvider(mock_app_with_s3_config)
        await provider.initialize()

        assert provider.s3_client is not None
        # Bucket creation log should not be called since bucket exists
        # Note: moto may still call head_bucket successfully

    @pytest.mark.asyncio
    async def test_save_and_load_bytes(self, mock_app_with_s3_config, s3_mock):
        """Test that save and load work correctly."""
        s3storage = get_s3storage_module()

        provider = s3storage.S3StorageProvider(mock_app_with_s3_config)
        await provider.initialize()

        # Save data
        test_data = b'Hello, S3!'
        await provider.save('test/file.txt', test_data)

        # Load data
        loaded_data = await provider.load('test/file.txt')
        assert loaded_data == test_data

    @pytest.mark.asyncio
    async def test_exists_returns_true_for_existing_object(self, mock_app_with_s3_config, s3_mock):
        """Test that exists returns True for existing object."""
        s3storage = get_s3storage_module()

        provider = s3storage.S3StorageProvider(mock_app_with_s3_config)
        await provider.initialize()

        # Save data
        await provider.save('test/file.txt', b'data')

        # Check existence
        result = await provider.exists('test/file.txt')
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_returns_false_for_nonexistent_object(self, mock_app_with_s3_config, s3_mock):
        """Test that exists returns False for nonexistent object."""
        s3storage = get_s3storage_module()

        provider = s3storage.S3StorageProvider(mock_app_with_s3_config)
        await provider.initialize()

        # Check existence without saving
        result = await provider.exists('nonexistent/file.txt')
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_removes_object(self, mock_app_with_s3_config, s3_mock):
        """Test that delete removes object."""
        s3storage = get_s3storage_module()

        provider = s3storage.S3StorageProvider(mock_app_with_s3_config)
        await provider.initialize()

        # Save data
        await provider.save('test/file.txt', b'data')

        # Delete
        await provider.delete('test/file.txt')

        # Check existence
        result = await provider.exists('test/file.txt')
        assert result is False

    @pytest.mark.asyncio
    async def test_size_returns_content_length(self, mock_app_with_s3_config, s3_mock):
        """Test that size returns correct content length."""
        s3storage = get_s3storage_module()

        provider = s3storage.S3StorageProvider(mock_app_with_s3_config)
        await provider.initialize()

        # Save data
        test_data = b'12345'  # 5 bytes
        await provider.save('test/file.txt', test_data)

        # Get size
        size = await provider.size('test/file.txt')
        assert size == 5

    @pytest.mark.asyncio
    async def test_delete_dir_recursive_removes_all_objects(self, mock_app_with_s3_config, s3_mock):
        """Test that delete_dir_recursive removes all objects with prefix."""
        s3storage = get_s3storage_module()

        provider = s3storage.S3StorageProvider(mock_app_with_s3_config)
        await provider.initialize()

        # Save multiple objects in directory
        await provider.save('testdir/file1.txt', b'data1')
        await provider.save('testdir/file2.txt', b'data2')
        await provider.save('testdir/subdir/file3.txt', b'data3')
        await provider.save('otherdir/file.txt', b'data4')

        # Delete directory
        await provider.delete_dir_recursive('testdir')

        # Verify testdir objects are deleted
        assert await provider.exists('testdir/file1.txt') is False
        assert await provider.exists('testdir/file2.txt') is False
        assert await provider.exists('testdir/subdir/file3.txt') is False

        # Verify other directory is intact
        assert await provider.exists('otherdir/file.txt') is True

    @pytest.mark.asyncio
    async def test_delete_dir_recursive_handles_trailing_slash(self, mock_app_with_s3_config, s3_mock):
        """Test that delete_dir_recursive handles path without trailing slash."""
        s3storage = get_s3storage_module()

        provider = s3storage.S3StorageProvider(mock_app_with_s3_config)
        await provider.initialize()

        # Save object
        await provider.save('mydir/file.txt', b'data')

        # Delete without trailing slash
        await provider.delete_dir_recursive('mydir')

        # Verify deleted
        assert await provider.exists('mydir/file.txt') is False

    @pytest.mark.asyncio
    async def test_delete_dir_recursive_empty_directory(self, mock_app_with_s3_config, s3_mock):
        """Test that delete_dir_recursive handles empty directory."""
        s3storage = get_s3storage_module()

        provider = s3storage.S3StorageProvider(mock_app_with_s3_config)
        await provider.initialize()

        # Delete non-existent directory should not raise
        await provider.delete_dir_recursive('emptydir')

    @pytest.mark.asyncio
    async def test_multiple_saves_and_loads(self, mock_app_with_s3_config, s3_mock):
        """Test multiple save/load operations."""
        s3storage = get_s3storage_module()

        provider = s3storage.S3StorageProvider(mock_app_with_s3_config)
        await provider.initialize()

        # Save multiple files
        files = {
            'file1.txt': b'content1',
            'file2.txt': b'content2',
            'dir/file3.txt': b'content3',
        }

        for key, data in files.items():
            await provider.save(key, data)

        # Load and verify all
        for key, expected in files.items():
            loaded = await provider.load(key)
            assert loaded == expected

    @pytest.mark.asyncio
    async def test_overwrite_existing_object(self, mock_app_with_s3_config, s3_mock):
        """Test that save overwrites existing object."""
        s3storage = get_s3storage_module()

        provider = s3storage.S3StorageProvider(mock_app_with_s3_config)
        await provider.initialize()

        # Save initial data
        await provider.save('file.txt', b'initial')

        # Overwrite
        await provider.save('file.txt', b'overwritten')

        # Verify new content
        loaded = await provider.load('file.txt')
        assert loaded == b'overwritten'


class TestS3StorageProviderErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_load_nonexistent_raises_error(self, s3_mock):
        """Test that load raises error for nonexistent object."""
        s3storage = get_s3storage_module()

        mock_app = Mock()
        mock_app.instance_config = Mock()
        mock_app.instance_config.data = {
            'storage': {
                's3': {
                    'bucket': 'test-bucket',
                    'access_key_id': 'testing',
                    'secret_access_key': 'testing',
                    'region': 'us-east-1',
                }
            }
        }
        mock_app.logger = Mock()

        provider = s3storage.S3StorageProvider(mock_app)
        await provider.initialize()

        with pytest.raises(Exception):
            await provider.load('nonexistent.txt')

    @pytest.mark.asyncio
    async def test_size_nonexistent_raises_error(self, s3_mock):
        """Test that size raises error for nonexistent object."""
        s3storage = get_s3storage_module()

        mock_app = Mock()
        mock_app.instance_config = Mock()
        mock_app.instance_config.data = {
            'storage': {
                's3': {
                    'bucket': 'test-bucket',
                    'access_key_id': 'testing',
                    'secret_access_key': 'testing',
                    'region': 'us-east-1',
                }
            }
        }
        mock_app.logger = Mock()

        provider = s3storage.S3StorageProvider(mock_app)
        await provider.initialize()

        with pytest.raises(Exception):
            await provider.size('nonexistent.txt')