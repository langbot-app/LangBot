"""Real Core processes share persistent assets without shared file roots."""
# ruff: noqa: F811

import asyncio
from contextlib import closing
import hashlib
import os

import boto3
from botocore.config import Config
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.entity.persistence.artifact import Artifact
from langbot.pkg.entity.persistence.content import ContentObject
from tests.e2e.test_skill_persistence_replicas import _data, _start, _stop, core_pair  # noqa: F401


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(os.environ.get('LANGBOT_PERSISTENCE_CORE_E2E') != '1', reason='explicit two-Core acceptance'),
]


@pytest.fixture
def core_pair_configure():
    def configure(root, config):
        if os.environ.get('LANGBOT_ARTIFACT_CORE_S3') == '1':
            config['storage']['content'] = {
                'backend': 'artifacts',
                'backends': {
                    'artifacts': {
                        'type': 's3',
                        'endpoint_url': os.environ['LANGBOT_PERSISTENCE_MINIO_ENDPOINT'],
                        'access_key_id': os.environ['LANGBOT_PERSISTENCE_MINIO_ACCESS_KEY'],
                        'secret_access_key': os.environ['LANGBOT_PERSISTENCE_MINIO_SECRET_KEY'],
                        'bucket': 'artifact-core-acceptance',
                    }
                },
            }
        return []

    return configure


async def _backing_content(artifact_id):
    engine = create_async_engine(os.environ['LANGBOT_PERSISTENCE_CORE_POSTGRES_URL'])
    assert engine.dialect.name == 'postgresql'
    try:
        async with engine.connect() as connection:
            return (
                (
                    await connection.execute(
                        sa.select(
                            ContentObject.backend,
                            ContentObject.locator,
                            ContentObject.digest,
                            ContentObject.size,
                            ContentObject.value,
                        )
                        .join(
                            Artifact,
                            sa.and_(
                                Artifact.content_ref == ContentObject.ref,
                                Artifact.workspace_uuid == ContentObject.workspace_uuid,
                            ),
                        )
                        .where(Artifact.id == artifact_id)
                    )
                )
                .mappings()
                .one()
            )
    finally:
        await engine.dispose()


def _assert_minio_object(row, expected):
    location = row['locator']
    endpoint = os.environ['LANGBOT_PERSISTENCE_MINIO_ENDPOINT'].rstrip('/')
    assert row['backend'] == 'artifacts' and row['value'] is None
    assert location['endpoint_url'] == endpoint and location['bucket'] == 'artifact-core-acceptance'
    assert location['key'].startswith('content/')
    # Verify actual object bytes independently of either Core and its cache.
    # Never attach SDK debug output or the replica configuration to CI.
    with closing(
        boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=os.environ['LANGBOT_PERSISTENCE_MINIO_ACCESS_KEY'],
            aws_secret_access_key=os.environ['LANGBOT_PERSISTENCE_MINIO_SECRET_KEY'],
            region_name=location['region'],
            config=Config(
                connect_timeout=5, read_timeout=10, retries={'max_attempts': 0}, s3={'addressing_style': 'path'}
            ),
        )
    ) as store:
        object_data = store.get_object(Bucket=location['bucket'], Key=location['key'])
        assert object_data['ContentLength'] == len(expected)
        with closing(object_data['Body']) as stream:
            assert stream.read() == expected


@pytest.mark.artifact_persistence
@pytest.mark.contract('uploaded_artifact_postgres_minio')
def test_artifact_download_survives_core_replacement(core_pair, request):
    use_minio = os.environ.get('LANGBOT_ARTIFACT_CORE_S3') == '1'
    if request.config.getoption('--required-suite') == 'artifact_persistence':
        assert use_minio, 'The required uploaded Artifact suite must use the named MinIO backend'
    a, b = core_pair.a, core_pair.b
    headers = {'Authorization': f'Bearer {core_pair.token}'}
    body = b'Persistent artifact across real Core processes\x00\xff'
    metadata = _data(
        a.client.post(
            '/api/v1/artifacts',
            headers=headers,
            files={'file': ('report.bin', body, 'application/octet-stream')},
        )
    )
    url = '/api/v1/artifacts/' + metadata['id']
    assert metadata['digest'] == hashlib.sha256(body).hexdigest()
    stored = asyncio.run(_backing_content(metadata['id']))
    assert stored['digest'] == metadata['digest'] and stored['size'] == len(body)
    if use_minio:
        _assert_minio_object(stored, body)
    else:
        assert stored['backend'] == 'database' and stored['value'] == body and stored['locator'] is None
    assert _data(a.client.post(url + '/retain', headers=headers))['lifecycle'] == 'persistent'
    assert b.client.get(url + '/content').status_code == 401
    assert b.client.get(url + '/content', headers=headers).content == body
    assert b.client.get(url + '/content?max_bytes=1', headers=headers).status_code == 413
    assert b.client.delete(url, headers=headers).status_code == 409
    assert a.root != b.root
    _stop(a.process)
    assert b.process.is_running()
    assert b.client.get(url + '/content', headers=headers).content == body
    _start(a)
    assert a.client.get(url + '/content', headers=headers).content == body
    assert _data(a.client.get(url, headers=headers))['expires_at'] is None
    _data(b.client.post(url + '/release', headers=headers))
    assert _data(b.client.delete(url, headers=headers))['deleted'] is True
    assert a.client.get(url + '/content', headers=headers).status_code == 404

    maximum = b'x' * (10 * 1024 * 1024)
    full = _data(
        a.client.post(
            '/api/v1/artifacts',
            headers=headers,
            files={'file': ('maximum.bin', maximum, 'application/octet-stream')},
        )
    )
    assert full['size'] == len(maximum) and full['digest'] == hashlib.sha256(maximum).hexdigest()
    assert (
        a.client.post(
            '/api/v1/artifacts',
            headers=headers,
            files={'file': ('oversized.bin', maximum + b'x', 'application/octet-stream')},
        ).status_code
        == 413
    )
    _data(a.client.delete('/api/v1/artifacts/' + full['id'], headers=headers))
