"""Resource byte caches remain disposable, scoped and fully verified."""

import hashlib
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock
import zipfile

import pytest
import sqlalchemy as sa
from langbot_plugin.skill_store import SkillStore

from langbot.pkg.entity.persistence.content import ContentObject
from langbot.pkg.entity.persistence.skill import SkillVersion
from langbot.pkg.skill import database_repository
from langbot.pkg.skill.repository import SkillRepository
from tests.unit_tests.storage.test_content_store import WORKSPACE, context, storage as content_storage


storage = content_storage


@pytest.fixture
async def resources(storage, tmp_path, monkeypatch):
    if not hasattr(SkillStore, 'list_publication_manifest_resources'):
        pytest.skip('requires publication resource SDK')
    manager = storage.ap.persistence_mgr
    async with manager.get_db_engine().begin() as connection:
        await connection.run_sync(lambda sync: SkillVersion.__table__.create(sync))
    objects = {}

    async def save(key, value):
        objects[key] = value

    async def load(key, *, max_bytes):
        assert manager.current_session() is None
        assert len(objects[key]) <= max_bytes
        return objects[key]

    provider = SimpleNamespace(save=save, delete=AsyncMock(), load_bounded=AsyncMock(side_effect=load))
    content = storage.content_store
    monkeypatch.setattr(content, '_s3', AsyncMock(return_value=(provider, {})))
    storage.ap.instance_config.data['storage']['content'] = {'backend': 'archive'}
    storage.ap.instance_config.data['skills'] = {'persistence': 'database', 'root': str(tmp_path / 'cache')}
    storage.ap.storage_mgr = storage
    storage.ap.box_service = SimpleNamespace(file_transfer_mode='network')
    repo = SkillRepository(storage.ap)
    source = SkillStore(str(tmp_path / 'source'))
    skill = source.create_skill({'name': 'packet', 'description': 'Read resources', 'instructions': 'Use guide.'})
    skill = source.write_skill_file('packet', 'payload.bin', 'UNSELECTED-PAYLOAD', base_revision=skill['revision'])
    versions = []
    for index in range(3):
        skill = source.write_skill_file(
            'packet', 'guide.md', f'verified guide {index}', base_revision=skill['revision']
        )
        publication = source.export_skill_publication('packet', skill['revision'])
        archive = publication['file_bytes']
        ref = await content.put(context(), owner_type='skill', owner='packet', key=skill['revision'], value=archive)
        async with manager.tenant_uow(WORKSPACE) as uow:
            await uow.execute(
                sa.insert(SkillVersion).values(
                    uuid=f'version-{index}',
                    workspace_uuid=WORKSPACE,
                    instance_uuid='instance',
                    name='packet',
                    revision=skill['revision'],
                    manifest_json=publication['manifest'],
                    skill_json=publication['skill'],
                    content_ref=ref,
                )
            )
        versions.append(
            {'revision': skill['revision'], 'ref': ref, 'archive': archive, 'manifest': publication['manifest']}
        )

    async def read(index=0):
        return await repo.read_skill_resource(
            context(), 'packet', 'guide.md', expected_revision=versions[index]['revision']
        )

    return SimpleNamespace(
        storage=storage,
        repo=repo,
        provider=provider,
        versions=versions,
        read=read,
        objects=objects,
        key=lambda index: ('instance', WORKSPACE, versions[index]['ref']),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('limit', ['bytes', 'entries', 'oversized'])
async def test_resource_cache_limits_and_lru_hits(resources, monkeypatch, limit):
    archive_size = len(resources.versions[0]['archive'])
    assert all(len(version['archive']) == archive_size for version in resources.versions)
    monkeypatch.setattr(database_repository, '_RESOURCE_CACHE_BYTES', archive_size * 2)
    monkeypatch.setattr(database_repository, '_RESOURCE_CACHE_ENTRIES', 2)
    if limit == 'entries':
        monkeypatch.setattr(database_repository, '_RESOURCE_CACHE_ENTRIES', 1)
    elif limit == 'oversized':
        monkeypatch.setattr(database_repository, '_RESOURCE_CACHE_BYTES', archive_size - 1)
    else:
        monkeypatch.setattr(database_repository, '_RESOURCE_CACHE_BYTES', archive_size * 2 - 1)
    assert (await resources.read())['content'] == 'verified guide 0'
    assert (await resources.read())['content'] == 'verified guide 0'
    if limit == 'oversized':
        assert resources.provider.load_bounded.await_count == 2
        assert not resources.repo._database._resource_archives
        return
    assert resources.provider.load_bounded.await_count == 1
    assert (await resources.read(1))['content'] == 'verified guide 1'
    assert (await resources.read(1))['content'] == 'verified guide 1'
    assert resources.provider.load_bounded.await_count == 2
    assert (await resources.read())['content'] == 'verified guide 0'
    assert resources.provider.load_bounded.await_count == 3
    assert resources.repo._database._resource_archive_bytes == archive_size


@pytest.mark.asyncio
async def test_cache_hits_refresh_lru_and_restarting_core_is_a_cold_read(resources, monkeypatch):
    monkeypatch.setattr(database_repository, '_RESOURCE_CACHE_ENTRIES', 2)
    await resources.read(0)
    await resources.read(1)
    await resources.read(0)
    await resources.read(2)
    await resources.read(0)
    assert resources.provider.load_bounded.await_count == 3
    await resources.read(1)
    assert resources.provider.load_bounded.await_count == 4
    other_core = SkillRepository(resources.storage.ap)
    assert (
        await other_core.read_skill_resource(
            context(), 'packet', 'guide.md', expected_revision=resources.versions[0]['revision']
        )
    )['content'] == 'verified guide 0'
    assert resources.provider.load_bounded.await_count == 5


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [FileNotFoundError('missing reference'), RuntimeError('database unavailable')])
async def test_warm_bytes_cannot_bypass_live_content_metadata(resources, monkeypatch, failure):
    await resources.read()
    monkeypatch.setattr(resources.storage.content_store, '_row', AsyncMock(side_effect=failure))
    with pytest.raises(type(failure), match=str(failure)):
        await resources.read()
    assert resources.provider.load_bounded.await_count == 1


@pytest.mark.asyncio
async def test_missing_version_is_rejected_even_with_verified_cached_bytes(resources):
    await resources.read()
    async with resources.storage.ap.persistence_mgr.tenant_uow(WORKSPACE) as uow:
        await uow.execute(sa.delete(SkillVersion).where(SkillVersion.revision == resources.versions[0]['revision']))
    with pytest.raises(ValueError, match='pinned revision'):
        await resources.read()
    assert resources.provider.load_bounded.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('damage', ['bytes', 'unselected_member', 'member_digest', 'metadata', 'manifest'])
async def test_cached_bytes_are_checked_against_live_digest_and_full_manifest(resources, damage):
    await resources.read()
    entry = resources.repo._database._resource_archives[resources.key(0)]
    if damage == 'metadata':
        async with resources.storage.ap.persistence_mgr.tenant_uow(WORKSPACE) as uow:
            await uow.execute(
                sa.update(ContentObject)
                .where(ContentObject.ref == resources.versions[0]['ref'])
                .values(digest='0' * 64)
            )
    elif damage == 'manifest':
        async with resources.storage.ap.persistence_mgr.tenant_uow(WORKSPACE) as uow:
            await uow.execute(
                sa.update(SkillVersion)
                .where(SkillVersion.revision == resources.versions[0]['revision'])
                .values(manifest_json={**resources.versions[0]['manifest'], 'total_bytes': 0})
            )
    else:
        assert b'UNSELECTED-PAYLOAD' in entry['value']
        if damage == 'member_digest':
            output = io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(entry['value'])) as source, zipfile.ZipFile(output, 'w') as target:
                for member in source.infolist():
                    target.writestr(member, source.read(member).replace(b'UNSELECTED-PAYLOAD', b'UNSELECTED-POISON!'))
            entry['value'] = output.getvalue()
        else:
            entry['value'] = entry['value'].replace(b'UNSELECTED-PAYLOAD', b'UNSELECTED-POISON!')
        if damage in {'unselected_member', 'member_digest'}:
            # Even matching archive metadata cannot skip an unread member's CRC/SHA.
            entry['digest'] = hashlib.sha256(entry['value']).hexdigest()
            async with resources.storage.ap.persistence_mgr.tenant_uow(WORKSPACE) as uow:
                await uow.execute(
                    sa.update(ContentObject)
                    .where(ContentObject.ref == resources.versions[0]['ref'])
                    .values(digest=entry['digest'])
                )
    with pytest.raises((ValueError, zipfile.BadZipFile)):
        await resources.read()
    assert resources.key(0) not in resources.repo._database._resource_archives
    if damage != 'metadata':
        assert resources.provider.load_bounded.await_count == 1
