"""Legacy upload admission preserves storage bounds and long-name compatibility."""
# ruff: noqa: F811

import pytest
import sqlalchemy as sa

from langbot.pkg.entity.persistence.artifact import Artifact
from langbot.pkg.entity.persistence.content import ContentAlias, ContentObject
from langbot.pkg.storage.artifacts import ArtifactError, MAX_ARTIFACT_BYTES
from tests.integration.storage.test_artifacts import artifact_replicas, persistence_case, replicas  # noqa: F401

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def arguments(case, filename='sample.txt'):
    return dict(
        owner_type='upload_document',
        owner='account:' + case.context.principal.account_uuid,
        key='logical-key.txt',
        filename=filename,
        mime_type='text/plain',
    )


@pytest.mark.parametrize('configured', [3, MAX_ARTIFACT_BYTES + 100])
async def test_legacy_bound_rejects_before_any_persistence(artifact_replicas, configured):
    case = artifact_replicas
    case.a.app.instance_config.data['storage']['max_object_read_bytes'] = configured
    value = b'x' * (min(configured, MAX_ARTIFACT_BYTES) + 1)
    with pytest.raises(ArtifactError) as failure:
        await case.a.app.artifact_service.create_legacy_upload(case.context, value=value, **arguments(case))
    assert failure.value.status_code == 413
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        for model in (Artifact, ContentAlias, ContentObject):
            assert (await uow.execute(sa.select(sa.func.count()).select_from(model))).scalar_one() == 0


async def test_legacy_exact_bound_and_long_filename_preserve_handle_and_type(artifact_replicas):
    case = artifact_replicas
    case.a.app.instance_config.data['storage']['max_object_read_bytes'] = 3
    filename = 'long-name-' * 40 + '.txt'
    result = await case.a.app.artifact_service.create_legacy_upload(
        case.context,
        value=b'abc',
        **arguments(case, filename),
    )
    metadata = result['artifact']
    assert metadata['name'] == 'logical-key.txt'
    assert metadata['mime_type'] == 'text/plain'
    assert await case.a.app.storage_mgr._load_content_alias(case.context, result['file_key']) == b'abc'
    # The compatibility adapter does not relax the ordinary Artifact upload contract.
    with pytest.raises(ValueError, match='Invalid artifact filename'):
        await case.a.app.artifact_service.create(case.context, filename, b'abc', 'text/plain')


async def test_long_legacy_name_cannot_hide_invalid_path_or_control_characters(artifact_replicas):
    case = artifact_replicas
    for filename in ('a' * 300 + '/file.txt', 'a' * 300 + '\x00.txt'):
        with pytest.raises(ValueError, match='Invalid artifact filename'):
            await case.a.app.artifact_service.create_legacy_upload(
                case.context,
                value=b'abc',
                **arguments(case, filename),
            )
