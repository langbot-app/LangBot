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
from unittest.mock import Mock, patch
from importlib import import_module
from botocore.exceptions import ClientError


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

    @pytest.mark.asyncio
    async def test_shutdown_closes_client_once(self):
        s3storage = get_s3storage_module()
        provider = s3storage.S3StorageProvider(Mock())
        client = Mock()
        provider.s3_client = client

        await provider.shutdown()
        await provider.shutdown()

        client.close.assert_called_once_with()
        assert provider.s3_client is None


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
        assert [bucket['Name'] for bucket in s3_mock.list_buckets()['Buckets']] == ['test-langbot-storage']

    @pytest.mark.asyncio
    async def test_initialize_uses_existing_bucket(self, mock_app_with_s3_config, s3_mock):
        """Test that initialize uses existing bucket without creating."""
        s3storage = get_s3storage_module()

        # Pre-create bucket in mock
        s3_mock.create_bucket(Bucket='test-langbot-storage')

        provider = s3storage.S3StorageProvider(mock_app_with_s3_config)
        with (
            patch.object(s3storage.boto3.session.Session, 'client', return_value=s3_mock),
            patch.object(s3_mock, 'head_bucket', wraps=s3_mock.head_bucket) as head_bucket,
            patch.object(s3_mock, 'create_bucket', wraps=s3_mock.create_bucket) as create_bucket,
        ):
            await provider.initialize()

        assert provider.s3_client is s3_mock
        head_bucket.assert_called_once_with(Bucket='test-langbot-storage')
        create_bucket.assert_not_called()

    @pytest.mark.asyncio
    async def test_s3_object_lifecycle(self, mock_app_with_s3_config, s3_mock):
        """Read back exact bytes and deletion through an independent Moto client."""
        provider = get_s3storage_module().S3StorageProvider(mock_app_with_s3_config)
        await provider.initialize()
        bucket, key = 'test-langbot-storage', 'test/file.bin'
        data = b'Hello, S3!\x00\xff'

        assert not await provider.exists(key)
        await provider.save(key, data)
        assert await provider.exists(key)
        with s3_mock.get_object(Bucket=bucket, Key=key)['Body'] as body:
            assert body.read() == data
        assert await provider.load(key) == data
        assert await provider.size(key) == len(data)

        await provider.delete(key)
        assert not await provider.exists(key)
        with pytest.raises(ClientError) as error:
            s3_mock.head_object(Bucket=bucket, Key=key)
        assert error.value.response['ResponseMetadata']['HTTPStatusCode'] == 404

    @pytest.mark.asyncio
    async def test_bounded_load_rejects_oversized_object(self, mock_app_with_s3_config, s3_mock):
        s3storage = get_s3storage_module()
        provider = s3storage.S3StorageProvider(mock_app_with_s3_config)
        await provider.initialize()
        await provider.save('test/oversized.bin', b'12345')

        with pytest.raises(ValueError, match='4-byte read limit'):
            await provider.load_bounded('test/oversized.bin', max_bytes=4)

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
        """Test that delete_dir_recursive handles a path with a trailing slash."""
        s3storage = get_s3storage_module()

        provider = s3storage.S3StorageProvider(mock_app_with_s3_config)
        await provider.initialize()

        # Save object
        await provider.save('mydir/file.txt', b'data')

        await provider.delete_dir_recursive('mydir/')

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

        with pytest.raises(ClientError) as exc_info:
            await provider.load('nonexistent.txt')
        assert exc_info.value.response['Error']['Code'] == 'NoSuchKey'

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

        with pytest.raises(ClientError) as exc_info:
            await provider.size('nonexistent.txt')
        assert exc_info.value.response['Error']['Code'] == '404'
