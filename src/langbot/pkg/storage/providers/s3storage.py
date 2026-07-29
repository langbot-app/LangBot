from __future__ import annotations

import asyncio

import boto3
from botocore.exceptions import ClientError

from ...core import app
from ...utils import bounded_executor
from .. import provider


class S3StorageProvider(provider.StorageProvider):
    """S3 object storage provider"""

    def __init__(self, ap: app.Application):
        super().__init__(ap)
        self.s3_client = None
        self.bucket_name = None
        self._io_semaphore = asyncio.Semaphore(16)

    async def initialize(self):
        """Initialize S3 client with configuration from config.yaml"""
        storage_config = self.ap.instance_config.data.get('storage', {})
        s3_config = storage_config.get('s3', {})

        # Get S3 configuration
        endpoint_url = s3_config.get('endpoint_url', '')
        access_key_id = s3_config.get('access_key_id', '')
        secret_access_key = s3_config.get('secret_access_key', '')
        region_name = s3_config.get('region', 'us-east-1')
        self.bucket_name = s3_config.get('bucket', 'langbot-storage')
        try:
            max_concurrency = int(s3_config.get('max_concurrency', 16))
        except (TypeError, ValueError):
            max_concurrency = 16
        self._io_semaphore = asyncio.Semaphore(max(1, min(max_concurrency, 128)))

        # Initialize S3 client
        session = boto3.session.Session()
        self.s3_client = session.client(
            service_name='s3',
            region_name=region_name,
            endpoint_url=endpoint_url if endpoint_url else None,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

        await self._run_io(self._ensure_bucket)

    async def shutdown(self) -> None:
        """Close the botocore HTTP connection pool without blocking the loop."""

        client = self.s3_client
        self.s3_client = None
        if client is not None:
            await bounded_executor.run_blocking_cleanup(client.close)

    async def _run_io(self, operation, /, *args, **kwargs):
        """Run one blocking boto3 operation behind a bounded concurrency gate."""

        async with self._io_semaphore:
            return await asyncio.to_thread(operation, *args, **kwargs)

    def _ensure_bucket(self) -> None:
        """Probe/create the bucket without blocking the application event loop."""

        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                # Bucket doesn't exist, create it
                try:
                    self.s3_client.create_bucket(Bucket=self.bucket_name)
                    self.ap.logger.info(f'Created S3 bucket: {self.bucket_name}')
                except Exception as create_error:
                    self.ap.logger.error(f'Failed to create S3 bucket: {create_error}')
                    raise
            else:
                self.ap.logger.error(f'Failed to access S3 bucket: {e}')
                raise

    async def save(
        self,
        key: str,
        value: bytes,
    ):
        """Save bytes to S3"""
        try:
            await self._run_io(
                self.s3_client.put_object,
                Bucket=self.bucket_name,
                Key=key,
                Body=value,
            )
        except Exception as e:
            self.ap.logger.error(f'Failed to save to S3: {e}')
            raise

    async def load(
        self,
        key: str,
    ) -> bytes:
        return await self.load_bounded(key, max_bytes=provider.HARD_MAX_STORAGE_OBJECT_BYTES)

    async def load_bounded(
        self,
        key: str,
        *,
        max_bytes: int,
    ) -> bytes:
        """Load bytes from S3"""
        max_bytes = provider.normalize_read_limit(max_bytes)
        try:
            return await self._run_io(self._load_sync, key, max_bytes)
        except Exception as e:
            self.ap.logger.error(f'Failed to load from S3: {e}')
            raise

    def _load_sync(self, key: str, max_bytes: int) -> bytes:
        response = self.s3_client.get_object(
            Bucket=self.bucket_name,
            Key=key,
        )
        body = response['Body']
        try:
            declared_size = response.get('ContentLength')
            if declared_size is not None and declared_size > max_bytes:
                raise ValueError(f'Storage object exceeds the {max_bytes}-byte read limit')
            value = body.read(max_bytes + 1)
            if len(value) > max_bytes:
                raise ValueError(f'Storage object exceeds the {max_bytes}-byte read limit')
            return value
        finally:
            body.close()

    async def exists(
        self,
        key: str,
    ) -> bool:
        """Check if object exists in S3"""
        try:
            await self._run_io(
                self.s3_client.head_object,
                Bucket=self.bucket_name,
                Key=key,
            )
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                self.ap.logger.error(f'Failed to check existence in S3: {e}')
                raise

    async def delete(
        self,
        key: str,
    ):
        """Delete object from S3"""
        try:
            await self._run_io(
                self.s3_client.delete_object,
                Bucket=self.bucket_name,
                Key=key,
            )
        except Exception as e:
            self.ap.logger.error(f'Failed to delete from S3: {e}')
            raise

    async def size(
        self,
        key: str,
    ) -> int:
        """Get object size from S3 without downloading it"""
        try:
            response = await self._run_io(
                self.s3_client.head_object,
                Bucket=self.bucket_name,
                Key=key,
            )
            return response['ContentLength']
        except Exception as e:
            self.ap.logger.error(f'Failed to get size from S3: {e}')
            raise

    async def delete_dir_recursive(
        self,
        dir_path: str,
    ):
        """Delete all objects with the given prefix (directory)"""
        try:
            await self._run_io(self._delete_dir_recursive_sync, dir_path)
        except Exception as e:
            self.ap.logger.error(f'Failed to delete directory from S3: {e}')
            raise

    def _delete_dir_recursive_sync(self, dir_path: str) -> None:
        if not dir_path.endswith('/'):
            dir_path = dir_path + '/'

        paginator = self.s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=self.bucket_name, Prefix=dir_path)
        for page in pages:
            if 'Contents' not in page:
                continue
            objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]
            if objects_to_delete:
                self.s3_client.delete_objects(
                    Bucket=self.bucket_name,
                    Delete={'Objects': objects_to_delete},
                )
