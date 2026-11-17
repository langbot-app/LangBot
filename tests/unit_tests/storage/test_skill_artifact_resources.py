"""Immutable Skill Artifact sources reuse authoritative package bytes."""

from dataclasses import replace

import pytest
import sqlalchemy as sa

from langbot.pkg.entity.persistence.content import ContentObject
from tests.unit_tests.storage.test_content_store import OTHER, WORKSPACE, context
from tests.unit_tests.storage.test_skill_resource_cache import resources as resource_fixture, storage as storage_fixture


resources = resource_fixture
storage = storage_fixture


@pytest.mark.asyncio
async def test_artifact_source_is_fixed_without_copy_or_cache(resources):
    repo = resources.repo
    version = resources.versions[0]
    async with resources.storage.ap.persistence_mgr.tenant_uow(WORKSPACE) as uow:
        before = await uow.session.scalar(sa.select(sa.func.count()).select_from(ContentObject))
    source = await repo.resolve_artifact_resource(
        context(), 'packet', 'guide.md', expected_revision=version['revision']
    )
    assert source['version_id'] == 'version-0'
    assert source['content_ref'] == version['ref']
    assert source['revision'] != resources.versions[-1]['revision']
    repo._database._resource_archives.clear()
    assert await repo.read_artifact_resource(context(), source, max_bytes=100) == b'verified guide 0'
    # The fixture deliberately has no registry table: reads cannot resolve latest.
    async with resources.storage.ap.persistence_mgr.tenant_uow(WORKSPACE) as uow:
        after = await uow.session.scalar(sa.select(sa.func.count()).select_from(ContentObject))
    assert before == after


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'field,value',
    [
        ('content_ref', 'content:forged'),
        ('revision', 'sha256:' + '0' * 64),
        ('digest', '0' * 64),
        ('size', 1),
        ('path', 'payload.bin'),
    ],
)
async def test_artifact_source_rejects_identity_substitution(resources, field, value):
    source = await resources.repo.resolve_artifact_resource(
        context(), 'packet', 'guide.md', expected_revision=resources.versions[0]['revision']
    )
    with pytest.raises(ValueError, match='identity'):
        await resources.repo.read_artifact_resource(context(), {**source, field: value}, max_bytes=100)


@pytest.mark.asyncio
async def test_artifact_source_rejects_scope_limits_and_missing_version(resources):
    source = await resources.repo.resolve_artifact_resource(
        context(), 'packet', 'guide.md', expected_revision=resources.versions[0]['revision']
    )
    for ctx in (context(OTHER), replace(context(), instance_uuid='another-instance')):
        with pytest.raises((ValueError, FileNotFoundError)):
            await resources.repo.read_artifact_resource(ctx, source, max_bytes=100)
    with pytest.raises(FileNotFoundError):
        await resources.repo.read_artifact_resource(context(), {**source, 'version_id': 'missing'}, max_bytes=100)
    with pytest.raises(ValueError, match='read limit'):
        await resources.repo.read_artifact_resource(context(), source, max_bytes=1)
    with pytest.raises(ValueError, match='explicit revision'):
        await resources.repo.resolve_artifact_resource(context(), 'packet', 'guide.md', expected_revision=None)


@pytest.mark.asyncio
@pytest.mark.parametrize('path', ['../secret', '/etc/passwd', '..\\secret', '%2e%2e/secret', 'missing'])
async def test_artifact_source_rejects_escaping_or_missing_path(resources, path):
    with pytest.raises((ValueError, FileNotFoundError)):
        await resources.repo.resolve_artifact_resource(
            context(), 'packet', path, expected_revision=resources.versions[0]['revision']
        )


@pytest.mark.asyncio
async def test_binary_resource_and_corrupt_archive(resources, tmp_path):
    from langbot_plugin.skill_store import SkillStore
    from langbot.pkg.entity.persistence.skill import SkillVersion

    tree = tmp_path / 'binary-package'
    tree.mkdir()
    (tree / 'SKILL.md').write_text('---\nname: binary\ndescription: Binary resource\n---\nRead bytes.\n')
    expected = b'\x89PNG\r\n\x1a\n\xff\x00'
    (tree / 'picture.png').write_bytes(expected)
    store = SkillStore(str(tmp_path / 'binary-store'))
    skill = store.import_skill_directory(str(tree), {'name': 'binary'}, source_root=str(tmp_path))
    publication = store.export_skill_publication('binary', skill['revision'])
    ref = await resources.storage.content_store.put(
        context(), owner_type='skill', owner='binary', key=skill['revision'], value=publication['file_bytes']
    )
    async with resources.storage.ap.persistence_mgr.tenant_uow(WORKSPACE) as uow:
        await uow.execute(
            sa.insert(SkillVersion).values(
                uuid='binary-version',
                workspace_uuid=WORKSPACE,
                instance_uuid='instance',
                name='binary',
                revision=skill['revision'],
                manifest_json=publication['manifest'],
                skill_json=publication['skill'],
                content_ref=ref,
            )
        )
    source = await resources.repo.resolve_artifact_resource(
        context(), 'binary', 'picture.png', expected_revision=skill['revision']
    )
    assert source['mime_type'] == 'image/png'
    assert await resources.repo.read_artifact_resource(context(), source, max_bytes=100) == expected
    resources.provider.load_bounded.side_effect = None
    resources.provider.load_bounded.return_value = b'corrupt'
    with pytest.raises(ValueError):
        await resources.repo.read_artifact_resource(context(), source, max_bytes=100)


@pytest.mark.asyncio
async def test_source_survives_replacement_host_mime_registry(resources, monkeypatch):
    import mimetypes

    source = await resources.repo.resolve_artifact_resource(
        context(), 'packet', 'guide.md', expected_revision=resources.versions[0]['revision']
    )
    monkeypatch.setattr(mimetypes, 'guess_type', lambda path: ('application/x-host-specific', None))
    assert await resources.repo.read_artifact_resource(context(), source, max_bytes=100) == b'verified guide 0'
    assert source['mime_type'] != 'application/x-host-specific'


@pytest.mark.asyncio
async def test_resolve_budget_denies_before_archive_read(resources):
    resources.provider.load_bounded.reset_mock()
    with pytest.raises(ValueError, match='requested read limit'):
        await resources.repo.resolve_artifact_resource(
            context(),
            'packet',
            'guide.md',
            expected_revision=resources.versions[0]['revision'],
            max_bytes=1,
        )
    resources.provider.load_bounded.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('limit', [0, -1, True, 1.5, None])
async def test_resolve_budget_rejects_invalid_limits_without_archive_read(resources, limit):
    resources.provider.load_bounded.reset_mock()
    with pytest.raises(ValueError, match='positive integer'):
        await resources.repo.resolve_artifact_resource(
            context(),
            'packet',
            'guide.md',
            expected_revision=resources.versions[0]['revision'],
            max_bytes=limit,
        )
    resources.provider.load_bounded.assert_not_called()
