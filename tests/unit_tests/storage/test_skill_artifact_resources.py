"""Immutable Skill Artifact sources reuse authoritative package bytes."""

import asyncio
from dataclasses import replace
from unittest.mock import AsyncMock

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
    for key in list(repo._database._resource_archives):
        repo._database._discard_resource_archive(key)
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
    # Existing verified immutable bytes may remain usable; a cold source must reject corruption.
    resources.repo._database._discard_resource_archive(('instance', WORKSPACE, ref))
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


@pytest.mark.asyncio
async def test_artifact_continuations_share_bounded_archive_with_legacy_reader(resources):
    source = await resources.repo.resolve_artifact_resource(
        context(), 'packet', 'guide.md', expected_revision=resources.versions[0]['revision']
    )
    for _ in range(32):
        assert await resources.repo.read_artifact_resource(context(), source, max_bytes=100) == b'verified guide 0'
    assert (await resources.read())['content'] == 'verified guide 0'
    assert resources.provider.load_bounded.await_count == 1
    assert resources.repo._database._resource_archive_bytes == len(resources.versions[0]['archive'])


@pytest.mark.asyncio
async def test_concurrent_artifact_and_legacy_cache_misses_are_coalesced(resources):
    version = resources.versions[0]
    source = await resources.repo.resolve_artifact_resource(
        context(), 'packet', 'guide.md', expected_revision=version['revision']
    )
    resources.repo._database._discard_resource_archive(resources.key(0))
    resources.provider.load_bounded.reset_mock()
    results = await asyncio.gather(
        *[resources.repo.read_artifact_resource(context(), source, max_bytes=100) for _ in range(8)],
        resources.read(),
    )
    assert results[:-1] == [b'verified guide 0'] * 8
    assert results[-1]['content'] == 'verified guide 0'
    assert resources.provider.load_bounded.await_count == 1


@pytest.mark.asyncio
async def test_cached_artifact_still_requires_live_content_and_version(resources, monkeypatch):
    from langbot.pkg.entity.persistence.skill import SkillVersion

    source = await resources.repo.resolve_artifact_resource(
        context(), 'packet', 'guide.md', expected_revision=resources.versions[0]['revision']
    )
    content = resources.storage.content_store
    original = content._row
    probe = AsyncMock(side_effect=FileNotFoundError('reference removed'))
    monkeypatch.setattr(content, '_row', probe)
    with pytest.raises(FileNotFoundError, match='reference removed'):
        await resources.repo.read_artifact_resource(context(), source, max_bytes=100)
    assert probe.call_args.kwargs['metadata_only'] is True
    monkeypatch.setattr(content, '_row', original)
    async with resources.storage.ap.persistence_mgr.tenant_uow(WORKSPACE) as uow:
        await uow.execute(sa.delete(SkillVersion).where(SkillVersion.uuid == source['version_id']))
    with pytest.raises(FileNotFoundError):
        await resources.repo.read_artifact_resource(context(), source, max_bytes=100)
    assert resources.provider.load_bounded.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('damage', ['bytes', 'metadata', 'manifest'])
async def test_artifact_cache_verifies_digest_manifest_and_discards_damage(resources, damage):
    from langbot.pkg.entity.persistence.skill import SkillVersion

    source = await resources.repo.resolve_artifact_resource(
        context(), 'packet', 'guide.md', expected_revision=resources.versions[0]['revision']
    )
    entry = resources.repo._database._resource_archives[resources.key(0)]
    if damage == 'bytes':
        entry['value'] = entry['value'].replace(b'UNSELECTED-PAYLOAD', b'UNSELECTED-POISON!')
    else:
        async with resources.storage.ap.persistence_mgr.tenant_uow(WORKSPACE) as uow:
            if damage == 'metadata':
                await uow.execute(
                    sa.update(ContentObject).where(ContentObject.ref == source['content_ref']).values(digest='0' * 64)
                )
            else:
                await uow.execute(
                    sa.update(SkillVersion)
                    .where(SkillVersion.uuid == source['version_id'])
                    .values(manifest_json={**resources.versions[0]['manifest'], 'total_bytes': 0})
                )
    with pytest.raises(ValueError):
        await resources.repo.read_artifact_resource(context(), source, max_bytes=100)
    # Invalid manifests are rejected before consulting the cache; byte/digest failures evict it.
    if damage != 'manifest':
        assert resources.key(0) not in resources.repo._database._resource_archives


@pytest.mark.asyncio
@pytest.mark.parametrize('limit', ['entries', 'bytes', 'oversized'])
async def test_artifact_cache_obeys_lru_and_byte_bounds(resources, monkeypatch, limit):
    from langbot.pkg.skill import database_repository

    size = len(resources.versions[0]['archive'])
    monkeypatch.setattr(database_repository, '_RESOURCE_CACHE_ENTRIES', 1 if limit == 'entries' else 256)
    monkeypatch.setattr(
        database_repository, '_RESOURCE_CACHE_BYTES', size - 1 if limit == 'oversized' else size * 2 - 1
    )
    sources = []
    for version in resources.versions[:2]:
        sources.append(
            await resources.repo.resolve_artifact_resource(
                context(), 'packet', 'guide.md', expected_revision=version['revision']
            )
        )
    assert await resources.repo.read_artifact_resource(context(), sources[0], max_bytes=100) == b'verified guide 0'
    assert resources.provider.load_bounded.await_count == 3
    assert resources.repo._database._resource_archive_bytes <= database_repository._RESOURCE_CACHE_BYTES
    assert len(resources.repo._database._resource_archives) <= database_repository._RESOURCE_CACHE_ENTRIES
    if limit == 'oversized':
        assert not resources.repo._database._resource_archives


@pytest.mark.asyncio
async def test_replacement_core_reads_authority_after_artifact_cache_warms(resources):
    from langbot.pkg.skill.repository import SkillRepository

    source = await resources.repo.resolve_artifact_resource(
        context(), 'packet', 'guide.md', expected_revision=resources.versions[0]['revision']
    )
    other = SkillRepository(resources.storage.ap)
    assert await other.read_artifact_resource(context(), source, max_bytes=100) == b'verified guide 0'
    assert resources.provider.load_bounded.await_count == 2


@pytest.mark.asyncio
async def test_cancelled_artifact_cache_miss_does_not_publish_or_hold_workspace_lock(resources):
    source = await resources.repo.resolve_artifact_resource(
        context(), 'packet', 'guide.md', expected_revision=resources.versions[0]['revision']
    )
    resources.repo._database._discard_resource_archive(resources.key(0))
    resources.provider.load_bounded.reset_mock()
    original_load = resources.provider.load_bounded.side_effect
    entered = asyncio.Event()
    release = asyncio.Event()

    async def delayed_load(*args, **kwargs):
        entered.set()
        await release.wait()
        return await original_load(*args, **kwargs)

    resources.provider.load_bounded.side_effect = delayed_load
    reading = asyncio.create_task(resources.repo.read_artifact_resource(context(), source, max_bytes=100))
    await asyncio.wait_for(entered.wait(), timeout=5)
    reading.cancel()
    with pytest.raises(asyncio.CancelledError):
        await reading
    assert resources.key(0) not in resources.repo._database._resource_archives
    release.set()
    assert (
        await asyncio.wait_for(resources.repo.read_artifact_resource(context(), source, max_bytes=100), timeout=5)
        == b'verified guide 0'
    )
    assert resources.provider.load_bounded.await_count == 2
