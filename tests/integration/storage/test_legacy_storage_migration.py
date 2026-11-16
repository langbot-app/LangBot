"""Real local-to-persistent assets, interruption recovery and source boundaries."""

import os
from pathlib import Path
import shutil

import pytest
import sqlalchemy as sa

from langbot.pkg.api.http.service.maintenance import MaintenanceService
from langbot.pkg.entity.persistence.content import ContentAlias, ContentObject
from langbot.pkg.persistence.legacy_migration import WorkspaceMigration
from langbot.pkg.storage import migration
from langbot.pkg.storage.media import MediaCache
from langbot.pkg.storage.providers import localstorage
from tests.integration.skill import test_persistent_skill_replicas as persistence_tests
from tests.integration.skill.test_persistent_skill_replicas import (
    _PNG,
    _auth,
)

persistence_case = persistence_tests.persistence_case
replicas = persistence_tests.replicas

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.skill_persistence]


def _source(replicas):
    root = Path(localstorage.LOCAL_STORAGE_PATH).absolute()
    root.mkdir(parents=True, exist_ok=True)
    key = replicas.a.app.storage_mgr.scoped_object_key(
        replicas.a.context, owner_type='upload_image', owner='legacy-owner', key='image.png'
    )
    image = root / key
    image.parent.mkdir(parents=True)
    image.write_bytes(_PNG)
    media_key = 'media_cache/' + MediaCache.hash_bytes(b'public-old') + '.png'
    media = root / media_key
    media.parent.mkdir()
    media.write_bytes(b'public-old')
    for replica in (replicas.a, replicas.b):
        replica.app.legacy_storage_source_exists = True
        if replicas.minio:
            replica.app.instance_config.data['storage']['content']['backend'] = 'archive'
    return root, key, media_key


async def _content_rows(replica):
    async with replica.app.persistence_mgr.tenant_uow(replica.context.workspace_uuid) as uow:
        return (await uow.execute(sa.select(ContentObject.__table__))).mappings().all()


@pytest.mark.contract('legacy_asset_import')
async def test_legacy_assets_keep_urls_privacy_and_survive_source_loss(replicas):
    root, key, media_key = _source(replicas)
    a, b = replicas.a, replicas.b
    result = await migration.initialize_storage_migration(a.app, source_required=True)
    assert result == {'files': 2, 'bytes': len(_PNG) + len(b'public-old')}
    rows = await _content_rows(a)
    assert len(rows) == 2
    assert {row['backend'] for row in rows} == {'archive' if replicas.minio else 'database'}
    assert {(row['owner_type'], row['public_media']) for row in rows} == {
        ('upload_image', False),
        ('public_media', True),
    }
    headers = _auth(replicas.token, b.context.workspace_uuid)
    image_url = '/api/v1/files/image/' + key
    media_url = '/api/v1/files/media/' + Path(media_key).name
    assert await (await b.client.get(image_url, headers=headers)).get_data() == _PNG
    assert (await b.client.get(image_url)).status_code == 401
    assert await (await b.client.get(media_url)).get_data() == b'public-old'
    assert (await b.client.get('/api/v1/files/media/' + Path(key).name)).status_code == 404

    for path in (root / key, root / media_key):
        os.utime(path, (1, 1))
    assert await a.app.storage_mgr.media_cache.cleanup(1, 0) == {
        'expired_deleted': 0,
        'size_deleted': 0,
        'bytes_freed': 0,
    }
    assert await MaintenanceService(a.app)._cleanup_expired_uploaded_files(a.context, 1) == 0
    assert (root / key).read_bytes() == _PNG and (root / media_key).read_bytes() == b'public-old'

    shutil.rmtree(root)
    b.app.legacy_storage_source_exists = False
    assert await migration.initialize_storage_migration(b.app, source_required=True) == {'files': 0, 'bytes': 0}
    assert await (await b.client.get(image_url, headers=headers)).get_data() == _PNG
    assert await (await b.client.get(media_url)).get_data() == b'public-old'


async def test_resume_rechecks_committed_source_and_target_without_recounting(replicas, monkeypatch):
    root, key, media_key = _source(replicas)
    a = replicas.a
    original = migration._import_asset
    calls = 0

    async def interrupted(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError('intentional interruption before second asset')
        await original(*args, **kwargs)

    monkeypatch.setattr(migration, '_import_asset', interrupted)
    with pytest.raises(RuntimeError, match='intentional interruption'):
        await migration.initialize_storage_migration(a.app, source_required=True)
    monkeypatch.setattr(migration, '_import_asset', original)
    state = await WorkspaceMigration(a.app, a.context, 'storage-filesystem-v1').checkpoint()
    assert state['status'] == 'failed' and state['progress']['files'] == 1
    async with a.app.persistence_mgr.tenant_uow(a.context.workspace_uuid) as uow:
        assert (await uow.execute(sa.select(ContentAlias))).first() is None

    a.app.legacy_storage_source_exists = False
    with pytest.raises(FileNotFoundError, match='pending|volume'):
        await migration.initialize_storage_migration(a.app)
    a.app.legacy_storage_source_exists = True
    replacement = root.parent / 'replacement-source'
    shutil.copytree(root, replacement)
    monkeypatch.setattr(localstorage, 'LOCAL_STORAGE_PATH', str(replacement))
    with pytest.raises(ValueError, match='source changed'):
        await migration.initialize_storage_migration(a.app, source_required=True)
    monkeypatch.setattr(localstorage, 'LOCAL_STORAGE_PATH', str(root))

    media = root / media_key
    timestamp = media.stat()
    media.write_bytes(b'public-new')
    os.utime(media, ns=(timestamp.st_atime_ns, timestamp.st_mtime_ns))
    with pytest.raises(ValueError, match='conflict'):
        await migration.initialize_storage_migration(a.app, source_required=True)
    media.write_bytes(b'public-old')
    os.utime(media, ns=(timestamp.st_atime_ns, timestamp.st_mtime_ns))

    row = (await _content_rows(a))[0]
    if replicas.minio:
        from botocore.exceptions import ClientError

        provider, _ = await a.app.storage_mgr.content_store._s3('archive', row['locator'])
        await provider.delete(row['locator']['key'])
        with pytest.raises(ClientError):
            await migration.initialize_storage_migration(a.app, source_required=True)
        await provider.save(row['locator']['key'], b'public-old')
    else:
        async with a.app.persistence_mgr.tenant_uow(a.context.workspace_uuid) as uow:
            await uow.execute(sa.update(ContentObject).where(ContentObject.ref == row['ref']).values(value=b'broken'))
        with pytest.raises(ValueError, match='digest'):
            await migration.initialize_storage_migration(a.app, source_required=True)
        async with a.app.persistence_mgr.tenant_uow(a.context.workspace_uuid) as uow:
            await uow.execute(
                sa.update(ContentObject).where(ContentObject.ref == row['ref']).values(value=b'public-old')
            )
    state = await WorkspaceMigration(a.app, a.context, 'storage-filesystem-v1').checkpoint()
    assert state['status'] != 'completed' and state['progress']['files'] == 1
    async with a.app.persistence_mgr.tenant_uow(a.context.workspace_uuid) as uow:
        await uow.execute(sa.delete(ContentObject).where(ContentObject.ref == row['ref']))
    with pytest.raises(FileNotFoundError, match='Previously imported'):
        await migration.initialize_storage_migration(a.app, source_required=True)
    async with a.app.persistence_mgr.tenant_uow(a.context.workspace_uuid) as uow:
        await uow.execute(sa.insert(ContentObject).values(**dict(row)))
    assert await migration.initialize_storage_migration(a.app, source_required=True) == {
        'files': 2,
        'bytes': len(_PNG) + len(b'public-old'),
    }
    assert len(await _content_rows(a)) == 2
    assert (root / key).read_bytes() == _PNG


async def test_unknown_private_layouts_and_links_fail_before_any_import(replicas):
    root, key, _media_key = _source(replicas)
    a = replicas.a
    foreign = root / 'v1' / ('0' * 24)
    foreign.mkdir()
    with pytest.raises(ValueError, match='unknown instance'):
        await migration.initialize_storage_migration(a.app, source_required=True)
    foreign.rmdir()
    inactive = (
        root / 'v1' / a.app.storage_mgr._digest(a.context.instance_uuid, 24) / '00000000-0000-0000-0000-000000000009'
    )
    inactive.mkdir()
    with pytest.raises(ValueError, match='inactive Workspace'):
        await migration.initialize_storage_migration(a.app, source_required=True)
    inactive.rmdir()
    unscoped = root / 'old-private-file.bin'
    unscoped.write_bytes(b'never publish this private file')
    with pytest.raises(ValueError, match='Unsupported legacy storage layout'):
        await migration.initialize_storage_migration(a.app, source_required=True)
    unscoped.unlink()
    image = root / key
    outside = root.parent / 'private-sentinel'
    outside.write_bytes(b'outside-private')
    image.unlink()
    image.symlink_to(outside)
    with pytest.raises(ValueError, match='without links'):
        await migration.initialize_storage_migration(a.app, source_required=True)
    assert outside.read_bytes() == b'outside-private'
    assert await _content_rows(a) == []


async def test_unseen_optional_source_is_not_marked_complete(replicas, monkeypatch):
    a = replicas.a
    a.app.legacy_storage_source_exists = False
    assert await migration.initialize_storage_migration(a.app) == {'files': 0, 'bytes': 0}
    assert await WorkspaceMigration(a.app, a.context, 'storage-filesystem-v1').checkpoint() is None
    with pytest.raises(FileNotFoundError, match='required'):
        await migration.initialize_storage_migration(a.app, source_required=True)

    async def no_active_bindings():
        return []

    a.app.legacy_storage_source_exists = True
    monkeypatch.setattr(a.app.workspace_service, 'list_active_execution_bindings', no_active_bindings)
    assert await migration.initialize_storage_migration(a.app) == {'files': 0, 'bytes': 0}
    with pytest.raises(ValueError, match='active Workspace'):
        await migration.initialize_storage_migration(a.app, source_required=True)
