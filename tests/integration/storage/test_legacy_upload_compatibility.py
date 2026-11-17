"""Legacy HTTP uploads must return readable handles or reject before persistence."""
# ruff: noqa: F811

import io

import pytest
import sqlalchemy as sa
from quart.datastructures import FileStorage

from langbot.pkg.entity.persistence.artifact import Artifact, ArtifactReference
from langbot.pkg.entity.persistence.content import ContentAlias, ContentObject
from tests.integration.storage.test_artifacts import (
    artifact_replicas,  # noqa: F401
    persistence_case,  # noqa: F401
    replicas,  # noqa: F401
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _counts(case):
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        return [
            (await uow.execute(sa.select(sa.func.count()).select_from(model))).scalar_one()
            for model in (Artifact, ArtifactReference, ContentAlias, ContentObject)
        ]


@pytest.mark.parametrize('route,extension,field', [('images', '.png', 'file_key'), ('documents', '.txt', 'file_id')])
async def test_legacy_upload_effective_limit_and_no_residue(artifact_replicas, route, extension, field):
    case = artifact_replicas
    for replica in (case.a, case.b):
        replica.app.instance_config.data['storage']['max_object_read_bytes'] = 4
    before = await _counts(case)
    rejected = await case.a.client.post(
        '/api/v1/files/' + route,
        headers=case.headers,
        files={'file': FileStorage(io.BytesIO(b'12345'), filename='test' + extension)},
    )
    assert rejected.status_code == 413
    assert await _counts(case) == before
    accepted = await case.a.client.post(
        '/api/v1/files/' + route,
        headers=case.headers,
        files={'file': FileStorage(io.BytesIO(b'1234'), filename='test' + extension)},
    )
    assert accepted.status_code == 200
    data = (await accepted.get_json())['data']
    for replica in (case.a, case.b):
        assert (
            await replica.app.storage_mgr.load_scoped_object_key(
                case.context,
                data[field],
                expected_owner_type='upload_image' if route == 'images' else 'upload_document',
            )
            == b'1234'
        )
    if route == 'images':
        response = await case.b.client.get('/api/v1/files/image/' + data[field], headers=case.headers)
        assert response.status_code == 200
        assert await response.get_data() == b'1234'


@pytest.mark.parametrize(
    'route,extension,field,mime',
    [
        ('images', '.png', 'file_key', 'image/png'),
        ('documents', '.txt', 'file_id', 'text/plain'),
    ],
)
@pytest.mark.parametrize('length', [255, 256, 1024])
async def test_legacy_long_filename_remains_readable(artifact_replicas, route, extension, field, mime, length):
    case = artifact_replicas
    name = 'a' * (length - len(extension)) + extension
    response = await case.a.client.post(
        '/api/v1/files/' + route,
        headers=case.headers,
        files={'file': FileStorage(io.BytesIO(b'legacy'), filename=name)},
    )
    assert response.status_code == 200
    data = (await response.get_json())['data']
    assert data[field].endswith(extension)
    metadata = await case.a.app.artifact_service.get(case.context, data['artifact_id'])
    assert len(metadata['name']) <= 255
    assert metadata['name'].endswith(extension)
    assert metadata['mime_type'] == mime
    if length == 255:
        assert metadata['name'] == name
    assert (
        await case.b.app.storage_mgr.load_scoped_object_key(
            case.context, data[field], expected_owner_type='upload_image' if route == 'images' else 'upload_document'
        )
        == b'legacy'
    )
    downloaded = await case.b.client.get('/api/v1/artifacts/' + data['artifact_id'] + '/content', headers=case.headers)
    assert downloaded.status_code == 200
    assert await downloaded.get_data() == b'legacy'
    assert (await case.b.client.get('/api/v1/artifacts/' + data['artifact_id'] + '/content')).status_code == 401


async def test_legacy_document_unbounded_extension_keeps_handle(artifact_replicas):
    case = artifact_replicas
    response = await case.a.client.post(
        '/api/v1/files/documents',
        headers=case.headers,
        files={'file': FileStorage(io.BytesIO(b'legacy'), filename='name.' + 'x' * 300)},
    )
    assert response.status_code == 200
    data = (await response.get_json())['data']
    metadata = await case.a.app.artifact_service.get(case.context, data['artifact_id'])
    assert len(metadata['name']) <= 255
    assert metadata['mime_type'] == 'application/octet-stream'
    assert (
        await case.b.app.storage_mgr.load_scoped_object_key(
            case.context, data['file_id'], expected_owner_type='upload_document'
        )
        == b'legacy'
    )
