"""Real authenticated Skill and content operations across independent replicas.

SQLite is always exercised; PostgreSQL and MinIO use the explicitly supplied
LANGBOT_PERSISTENCE_* endpoints. Skill trees are disposable, separate caches.
"""

from __future__ import annotations

import asyncio
import base64
import copy
from dataclasses import replace
import io
import logging
import os
from pathlib import Path
import shutil
from types import SimpleNamespace
import uuid
import zipfile

import pytest
import sqlalchemy as sa
import yaml
from quart import Quart
from quart.datastructures import FileStorage
from sqlalchemy.ext.asyncio import create_async_engine
from langbot_plugin.skill_store import SkillStore

from langbot.pkg.api.application import ApplicationAPI
from langbot.pkg.api.http.authz import WorkspaceRequiredError
from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.api.http.controller.groups.files import FilesRouterGroup
from langbot.pkg.api.http.controller.groups.skills import SkillsRouterGroup
from langbot.pkg.api.http.controller.groups.user import UserRouterGroup
from langbot.pkg.api.http.controller.groups.workspaces import WorkspacesRouterGroup
from langbot.pkg.api.http.service.skill import SkillService
from langbot.pkg.api.http.service.user import UserService
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.content import ContentObject
from langbot.pkg.persistence.mgr import PersistenceManager
from langbot.pkg.skill.manager import SkillManager
from langbot.pkg.skill.repository import SkillRepository
from langbot.pkg.storage.mgr import StorageMgr
from langbot.pkg.workspace.collaboration import WorkspaceCollaborationService
from langbot.pkg.workspace.errors import WorkspaceGenerationMismatchError
from langbot.pkg.workspace.service import WorkspaceService

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not hasattr(SkillStore, 'restore_skill_publication'),
        reason='database publications require the coordinated SDK',
    ),
]

_NAME = 'replica-probe'
_SCRIPT = b'#!/usr/bin/env python3\nprint("immutable replica bytes")\n'
_BINARY = bytes(range(256)) * 16
_GUIDE = '# Replica guide\nOriginal reference bytes.\n'
_PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jWZkAAAAASUVORK5CYII=')


def _zip_package():
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(
            f'{_NAME}/SKILL.md',
            f'---\nname: {_NAME}\ndescription: Immutable replica probe\nreleased: 2024-01-02\n---\n\nRead references/guide.md.\n',
        )
        script = zipfile.ZipInfo(f'{_NAME}/scripts/probe.py')
        script.external_attr = 0o100755 << 16
        archive.writestr(script, _SCRIPT)
        archive.writestr(f'{_NAME}/references/payload.bin', _BINARY)
        archive.writestr(f'{_NAME}/references/guide.md', _GUIDE)
    return output.getvalue()


def _auth(token, workspace=None):
    headers = {'Authorization': f'Bearer {token}'}
    if workspace:
        headers['X-Workspace-Id'] = workspace
    return headers


async def _data(response):
    assert response.status_code == 200, await response.get_data(as_text=True)
    payload = await response.get_json()
    assert payload['code'] == 0, payload
    return payload['data']


def _assert_package(content):
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        assert archive.read('scripts/probe.py') == _SCRIPT
        assert archive.read('references/payload.bin') == _BINARY
        assert archive.read('references/guide.md').decode() == _GUIDE
        assert archive.getinfo('scripts/probe.py').external_attr >> 16 & 0o111
        metadata = yaml.safe_load(archive.read('SKILL.md').decode().split('---', 2)[1])
        assert str(metadata['released']) == '2024-01-02'


def _discard_cache(replica):
    cache = replica.root / 'skills' / '.database-cache'
    assert cache.is_dir(), 'Snapshot reads must have materialized a replica-local cache'
    # Publications are sealed read-only; this case owns the cache and has no live run.
    for directory, _children, _files in os.walk(cache):
        os.chmod(directory, 0o700)
    shutil.rmtree(cache)


async def _close_replica(replica):
    if replica.closed:
        return
    try:
        storage = getattr(replica.app, 'storage_mgr', None)
        if storage is not None:
            await storage.shutdown()
    finally:
        await replica.engine.dispose()
        replica.closed = True


def _select_backend(replica, backend):
    # Change only the default destination; historical named locators remain configured.
    replica.app.instance_config.data['storage']['content']['backend'] = backend


async def _assert_backend(replica, owner_type, key, expected):
    async with replica.app.persistence_mgr.tenant_uow(replica.context.workspace_uuid) as uow:
        row = (
            await uow.execute(
                sa.select(ContentObject.backend, ContentObject.value, ContentObject.locator).where(
                    ContentObject.workspace_uuid == replica.context.workspace_uuid,
                    ContentObject.owner_type == owner_type,
                    ContentObject.key == key,
                )
            )
        ).one()
    assert row.backend == expected
    assert (row.value is not None) == (expected == 'database')
    assert (row.locator is not None) == (expected != 'database')


async def _assert_metadata_without_cache(replica, headers, revision):
    cache = replica.root / 'skills' / '.database-cache'
    assert not cache.exists()
    listed = await _data(await replica.client.get('/api/v1/skills', headers=headers))
    assert [skill['name'] for skill in listed['skills']] == [_NAME]
    await replica.app.skill_mgr.ensure_loaded(replica.context)
    metadata = await replica.app.skill_repository.get_skill(replica.context, _NAME, snapshot=False)
    assert metadata['revision'] == revision and metadata['metadata']['released'] == '2024-01-02'
    assert not cache.exists(), 'Catalog and metadata reads must not materialize Skill files'


@pytest.fixture(params=['sqlite-database', 'postgres-database', 'postgres-minio'])
async def persistence_case(request, tmp_path):
    postgres = request.param != 'sqlite-database'
    minio = request.param == 'postgres-minio'
    url = (
        os.environ.get('LANGBOT_PERSISTENCE_POSTGRES_URL')
        if postgres
        else f'sqlite+aiosqlite:///{tmp_path / "state.db"}'
    )
    if not url:
        pytest.skip('LANGBOT_PERSISTENCE_POSTGRES_URL identifies the disposable PostgreSQL service')
    content = {'backend': 'database'}
    if minio:
        names = ('ENDPOINT', 'ACCESS_KEY', 'SECRET_KEY')
        values = {name: os.environ.get('LANGBOT_PERSISTENCE_MINIO_' + name) for name in names}
        if not all(values.values()):
            pytest.skip('LANGBOT_PERSISTENCE_MINIO_ENDPOINT/ACCESS_KEY/SECRET_KEY are required')
        content['backends'] = {
            'archive': {
                'type': 's3',
                'endpoint_url': values['ENDPOINT'],
                'access_key_id': values['ACCESS_KEY'],
                'secret_access_key': values['SECRET_KEY'],
                'region': 'us-east-1',
                'bucket': 'langbot-phase3-' + uuid.uuid4().hex,
            }
        }
    admin = None
    schema = None
    s3 = None
    bucket_created = False
    options = {}
    try:
        if postgres:
            admin = create_async_engine(url)
            candidate = 'skill_replicas_' + uuid.uuid4().hex
            async with admin.begin() as connection:
                await connection.execute(sa.text(f'CREATE SCHEMA {candidate}'))
            schema = candidate
            options['connect_args'] = {'server_settings': {'search_path': schema}}
        if minio:
            import boto3
            from botocore.config import Config

            config = content['backends']['archive']
            s3 = boto3.client(
                's3',
                endpoint_url=config['endpoint_url'],
                aws_access_key_id=config['access_key_id'],
                aws_secret_access_key=config['secret_access_key'],
                region_name=config['region'],
                config=Config(
                    connect_timeout=5, read_timeout=10, retries={'max_attempts': 0}, s3={'addressing_style': 'path'}
                ),
            )
            await asyncio.to_thread(s3.create_bucket, Bucket=config['bucket'])
            bucket_created = True
        yield SimpleNamespace(url=url, options=options, content=content, minio=minio)
    finally:
        try:
            if s3 is not None:
                try:
                    if bucket_created:
                        bucket = content['backends']['archive']['bucket']
                        objects = await asyncio.to_thread(s3.list_objects_v2, Bucket=bucket, MaxKeys=1000)
                        assert not objects.get('IsTruncated'), (
                            'This low-load case exceeded its owned-bucket cleanup budget'
                        )
                        keys = [{'Key': item['Key']} for item in objects.get('Contents', [])]
                        if keys:
                            deleted = await asyncio.to_thread(
                                s3.delete_objects, Bucket=bucket, Delete={'Objects': keys}
                            )
                            assert not deleted.get('Errors'), deleted.get('Errors')
                        await asyncio.to_thread(s3.delete_bucket, Bucket=bucket)
                finally:
                    await asyncio.to_thread(s3.close)
        finally:
            if admin is not None:
                try:
                    if schema is not None:
                        async with admin.begin() as connection:
                            await connection.execute(sa.text(f'DROP SCHEMA {schema} CASCADE'))
                finally:
                    await admin.dispose()


@pytest.fixture
async def replicas(tmp_path, monkeypatch, persistence_case):
    monkeypatch.chdir(tmp_path)
    instance = 'skill-replicas-' + uuid.uuid4().hex
    created = []

    async def create(name):
        root = tmp_path / name
        root.mkdir()
        engine = create_async_engine(persistence_case.url, **persistence_case.options)
        replica = SimpleNamespace(app=None, engine=engine, root=root, closed=False)
        created.append(replica)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        application = SimpleNamespace(
            logger=logging.getLogger('skill-replicas'),
            instance_config=SimpleNamespace(
                data={
                    'system': {
                        'jwt': {'secret': 'skill-replica-test-only', 'expire': 3600},
                        'allow_modify_login_info': True,
                    },
                    'api': {'global_api_key': ''},
                    'skills': {'persistence': 'database', 'root': str(root / 'skills')},
                    'storage': {
                        'use': 'persistent',
                        'content': copy.deepcopy(persistence_case.content),
                        'local': {'path': str(root / 'legacy-storage')},
                    },
                    'box': {'enabled': False, 'local': {'host_root': str(root / 'box')}},
                }
            ),
        )
        replica.app = application
        application.persistence_mgr = PersistenceManager(application)
        application.persistence_mgr.db = SimpleNamespace(get_engine=lambda: engine)
        application.application_api = ApplicationAPI(application)
        application.workspace_service = WorkspaceService(application, instance_uuid=instance)
        await application.workspace_service.ensure_singleton_workspace()
        application.workspace_collaboration_service = WorkspaceCollaborationService(
            application, application.workspace_service
        )
        application.user_service = UserService(application)
        application.storage_mgr = StorageMgr(application)
        await application.storage_mgr.initialize()
        application.skill_repository = SkillRepository(application)
        application.skill_service = SkillService(application)
        application.skill_mgr = SkillManager(application)
        await application.skill_mgr.initialize()
        http = Quart('skill-replica-' + name)
        for router in (UserRouterGroup, WorkspacesRouterGroup, SkillsRouterGroup, FilesRouterGroup):
            await router(application, http).initialize()
        binding = await application.workspace_service.get_execution_binding()
        replica.client = http.test_client()
        replica.context = ExecutionContext(
            instance_uuid=binding.instance_uuid,
            workspace_uuid=binding.workspace_uuid,
            placement_generation=binding.placement_generation,
        )
        return replica

    try:
        first = await create('core-a')
        credentials = {'user': 'owner@example.com', 'password': 'owner-password'}
        await _data(await first.client.post('/api/v1/user/init', json=credentials))
        token = (await _data(await first.client.post('/api/v1/user/auth', json=credentials)))['token']
        second = await create('core-b')
        yield SimpleNamespace(a=first, b=second, token=token, create=create, minio=persistence_case.minio)
    finally:
        for replica in reversed(created):
            await _close_replica(replica)


async def test_skill_publications_survive_cache_loss_and_replica_cas(replicas):
    a, b = replicas.a, replicas.b
    headers = _auth(replicas.token, a.context.workspace_uuid)
    assert a.engine is not b.engine and a.root != b.root and a.context == b.context
    assert (await b.client.get('/api/v1/skills')).status_code == 401
    installed = await _data(
        await a.client.post(
            '/api/v1/skills/install/upload',
            headers=headers,
            files={'file': FileStorage(io.BytesIO(_zip_package()), filename='probe.zip')},
        )
    )
    assert len(installed['skills']) == 1
    original = installed['skills'][0]['revision']
    assert original.startswith('sha256:')
    for replica in (a, b):
        await _assert_metadata_without_cache(replica, headers, original)
    skill = (await _data(await b.client.get(f'/api/v1/skills/{_NAME}', headers=headers)))['skill']
    assert skill['metadata']['released'] == '2024-01-02' and skill['revision'] == original
    read = await _data(await b.client.get(f'/api/v1/skills/{_NAME}/files/scripts/probe.py', headers=headers))
    assert read['content'].encode() == _SCRIPT
    package_url = f'/api/v1/skills/{_NAME}/package?revision={original}'
    first_package = await a.client.get(package_url, headers=headers)
    assert first_package.status_code == 200
    original_package = await first_package.get_data()
    _assert_package(original_package)
    assert (await b.client.get(package_url)).status_code == 401
    assert await (await b.client.get(package_url, headers=headers)).get_data() == original_package

    for replica in (a, b):
        snapshot = await replica.app.skill_repository.get_skill(
            replica.context, _NAME, snapshot=True, revision=original
        )
        assert Path(snapshot['package_root']).is_relative_to(replica.root)
        assert Path(snapshot['package_root'], 'references/payload.bin').read_bytes() == _BINARY
        _discard_cache(replica)
    for replica in (a, b):
        await _assert_metadata_without_cache(replica, headers, original)
    assert await (await b.client.get(package_url, headers=headers)).get_data() == original_package
    recovered = await b.app.skill_repository.get_skill(b.context, _NAME, snapshot=True, revision=original)
    assert recovered['metadata']['released'] == '2024-01-02' and recovered['revision'] == original
    assert Path(recovered['package_root'], 'scripts/probe.py').read_bytes() == _SCRIPT
    assert Path(recovered['package_root'], 'scripts/probe.py').stat().st_mode & 0o111
    await _assert_backend(a, 'skill', original, 'database')
    if replicas.minio:
        for replica in (a, b):
            _select_backend(replica, 'archive')
            assert await (await replica.client.get(package_url, headers=headers)).get_data() == original_package

    await b.app.skill_mgr.ensure_loaded(b.context)
    assert b.app.skill_mgr.get_skill_by_name(b.context, _NAME)['revision'] == original
    writes = await asyncio.gather(
        *[
            replica.client.put(
                f'/api/v1/skills/{_NAME}', headers=headers, json={'base_revision': original, 'description': description}
            )
            for replica, description in ((a, 'writer-a'), (b, 'writer-b'))
        ]
    )
    assert sorted(response.status_code for response in writes) == [200, 409]
    winner = await _data(next(response for response in writes if response.status_code == 200))
    current = winner['skill']['revision']
    assert current != original
    await _assert_backend(b, 'skill', current, 'archive' if replicas.minio else 'database')
    current_package_url = f'/api/v1/skills/{_NAME}/package?revision={current}'
    current_package = await (await b.client.get(current_package_url, headers=headers)).get_data()
    _assert_package(current_package)
    if replicas.minio:
        for replica in (a, b):
            _select_backend(replica, 'database')
            assert await (await replica.client.get(current_package_url, headers=headers)).get_data() == current_package
    await b.app.skill_mgr.ensure_loaded(b.context)
    assert b.app.skill_mgr.get_skill_by_name(b.context, _NAME)['revision'] == current
    await _close_replica(a)
    fresh = await replicas.create('core-a-restarted-empty-cache')
    assert await (await fresh.client.get(package_url, headers=headers)).get_data() == original_package
    assert await (await fresh.client.get(current_package_url, headers=headers)).get_data() == current_package
    if replicas.minio:
        database_again = await _data(
            await fresh.client.put(
                f'/api/v1/skills/{_NAME}',
                headers=headers,
                json={'base_revision': current, 'description': 'database after named S3'},
            )
        )
        current = database_again['skill']['revision']
        await _assert_backend(fresh, 'skill', current, 'database')
        assert await (await b.client.get(current_package_url, headers=headers)).get_data() == current_package
    restarted = (await _data(await fresh.client.get(f'/api/v1/skills/{_NAME}', headers=headers)))['skill']
    assert restarted['metadata']['released'] == '2024-01-02' and restarted['revision'] == current
    with pytest.raises(WorkspaceGenerationMismatchError):
        await b.app.skill_repository.get_skill(replace(b.context, placement_generation=2), _NAME, snapshot=True)
    bad_path = await b.client.get(f'/api/v1/skills/{_NAME}/files/references/%2e%2e/%2e%2e/secret', headers=headers)
    assert bad_path.status_code == 400
    await _data(await fresh.client.delete(f'/api/v1/skills/{_NAME}', headers=headers))
    assert (await b.client.get(f'/api/v1/skills/{_NAME}', headers=headers)).status_code == 404
    await b.app.skill_mgr.ensure_loaded(b.context)
    assert b.app.skill_mgr.get_skill_by_name(b.context, _NAME) is None
    assert await (await fresh.client.get(package_url, headers=headers)).get_data() == original_package


async def test_persistent_public_media_and_private_uploads_cross_replicas(replicas):
    a, b = replicas.a, replicas.b
    headers = _auth(replicas.token, a.context.workspace_uuid)
    uploaded = await _data(
        await a.client.post(
            '/api/v1/files/images', headers=headers, files={'file': FileStorage(io.BytesIO(_PNG), filename='pixel.png')}
        )
    )
    key = uploaded['file_key']
    image_url = '/api/v1/files/image/' + key
    assert await (await b.client.get(image_url, headers=headers)).get_data() == _PNG
    await _assert_backend(a, 'upload_image', key, 'database')
    assert (await b.client.get(image_url)).status_code == 401
    stale = key.split('/')
    stale[3] = str(int(stale[3]) + 1)
    assert (await b.client.get('/api/v1/files/image/' + '/'.join(stale), headers=headers)).status_code == 404
    foreign = key.replace(a.context.workspace_uuid, str(uuid.uuid4()))
    assert (await b.client.get('/api/v1/files/image/' + foreign, headers=headers)).status_code == 404

    media = os.urandom(1024 * 1024)
    async with a.app.persistence_mgr.tenant_uow(a.context.workspace_uuid):
        _digest, media_key, size = await a.app.storage_mgr.media_cache.save_media(media, 'application/octet-stream')
    assert size == len(media)
    media_url = '/api/v1/files/media/' + Path(media_key).name
    response = await b.client.get(media_url)
    assert response.status_code == 200 and await response.get_data() == media
    await _assert_backend(a, 'public_media', media_key, 'database')
    retained = [(image_url, _PNG, headers), (media_url, media, {})]
    if replicas.minio:
        for backend, payload in (('archive', media[:2048]), ('database', media[:1024])):
            for replica in (a, b):
                _select_backend(replica, backend)
            another = await _data(
                await a.client.post(
                    '/api/v1/files/images',
                    headers=headers,
                    files={'file': FileStorage(io.BytesIO(_PNG), filename='pixel.png')},
                )
            )
            await _assert_backend(a, 'upload_image', another['file_key'], backend)
            retained.append(('/api/v1/files/image/' + another['file_key'], _PNG, headers))
            async with a.app.persistence_mgr.tenant_uow(a.context.workspace_uuid):
                _hash, saved_key, _size = await a.app.storage_mgr.media_cache.save_media(
                    payload, 'application/octet-stream'
                )
            await _assert_backend(a, 'public_media', saved_key, backend)
            retained.append(('/api/v1/files/media/' + Path(saved_key).name, payload, {}))
            for replica in (a, b):
                for url, expected, auth in retained:
                    result = await replica.client.get(url, headers=auth)
                    assert result.status_code == 200 and await result.get_data() == expected
    private_ref = await a.app.storage_mgr.content_store.alias_ref(a.context, key)
    assert private_ref
    assert (await b.client.get('/api/v1/files/media/' + private_ref)).status_code == 404
    private_media_key = 'media_cache/' + uuid.uuid4().hex + '.png'
    await a.app.storage_mgr.content_store.put(
        a.context, owner_type='skill', owner='private-probe', key=private_media_key, value=b'private bytes'
    )
    assert (await b.client.get('/api/v1/files/media/' + Path(private_media_key).name)).status_code == 404
    with pytest.raises(WorkspaceRequiredError):
        await b.app.storage_mgr.content_store.get(replace(b.context, workspace_uuid=str(uuid.uuid4())), private_ref)
    with pytest.raises(ValueError, match='Invalid public media key'):
        await b.app.storage_mgr.content_store.get_public_media(key)

    await _close_replica(a)
    fresh = await replicas.create('core-a-restarted-empty-cache')
    for url, expected, auth in retained:
        result = await fresh.client.get(url, headers=auth)
        assert result.status_code == 200 and await result.get_data() == expected
    assert not any(path.is_file() for path in Path('data/storage').rglob('*'))
