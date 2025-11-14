from __future__ import annotations

import boto3
from botocore.exceptions import ClientError

from ...core import app
from .. import provider


class S3StorageProvider(provider.StorageProvider):
    """S3 object storage provider"""

    def __init__(self, ap: app.Application):
        super().__init__(ap)
        self.s3_client = None
        self.bucket_name = None

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

        # Initialize S3 client
        session = boto3.session.Session()
        self.s3_client = session.client(
            service_name='s3',
            region_name=region_name,
            endpoint_url=endpoint_url if endpoint_url else None,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

        # Ensure bucket exists
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
            self.s3_client.put_object(
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
        """Load bytes from S3"""
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=key,
            )
            return response['Body'].read()
        except Exception as e:
            self.ap.logger.error(f'Failed to load from S3: {e}')
            raise

    async def exists(
        self,
        key: str,
    ) -> bool:
        """Check if object exists in S3"""
        try:
            self.s3_client.head_object(
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
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=key,
            )
        except Exception as e:
            self.ap.logger.error(f'Failed to delete from S3: {e}')
            raise

    async def delete_dir_recursive(
        self,
        dir_path: str,
    ):
        """Delete all objects with the given prefix (directory)"""
        try:
            # Ensure dir_path ends with /
            if not dir_path.endswith('/'):
                dir_path = dir_path + '/'

            # List all objects with the prefix
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=dir_path)

            # Delete all objects
            for page in pages:
                if 'Contents' in page:
                    objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]
                    if objects_to_delete:
                        self.s3_client.delete_objects(
                            Bucket=self.bucket_name,
                            Delete={'Objects': objects_to_delete},
                        )
        except Exception as e:
            self.ap.logger.error(f'Failed to delete directory from S3: {e}')
            raise
