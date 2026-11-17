"""Real Core processes share persistent assets without shared file roots."""
# ruff: noqa: F811

import hashlib
import os

import pytest

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


def test_artifact_download_survives_core_replacement(core_pair):
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
