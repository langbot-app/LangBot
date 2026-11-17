"""Authenticated Artifact lifecycle across independent Core replicas and stores."""
# ruff: noqa: F811

from __future__ import annotations

import asyncio
from dataclasses import replace
import datetime as dt
import hashlib
import io
from types import SimpleNamespace
import uuid

import pytest
import sqlalchemy as sa
from quart.datastructures import FileStorage

from langbot.pkg.api.application import ApplicationAPIException
from langbot.pkg.api.authz import permissions_for_role
from langbot.pkg.api.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext
from langbot.pkg.api.http.controller.groups.artifacts import ArtifactsRouterGroup
from langbot.pkg.api.http.service.apikey import ApiKeyService
from langbot.pkg.entity.persistence.artifact import Artifact, ArtifactReference
from langbot.pkg.entity.persistence.content import ContentAlias, ContentObject
from langbot.pkg.entity.persistence.workspace import Workspace, WorkspaceExecutionState
from langbot.pkg.storage.artifacts import ArtifactService
from langbot.pkg.storage.artifact_publication import ArtifactPublicationService
from tests.integration.skill.test_persistent_skill_replicas import (
    _auth,
    _close_replica,
    _data,
    _select_backend,
    persistence_case,  # noqa: F401 -- fixture dependency of replicas
    replicas,  # noqa: F401 -- shared disposable database/MinIO fixture
)


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
_BODY = b'Artifact persistence: exact bytes \x00\xff\n'


@pytest.fixture
async def artifact_replicas(replicas):
    async def attach(replica):
        if replica.engine.dialect.name == 'sqlite':

            @sa.event.listens_for(replica.engine.sync_engine, 'connect')
            def enable_foreign_keys(connection, _record):
                cursor = connection.cursor()
                cursor.execute('PRAGMA foreign_keys=ON')
                cursor.close()

            async with replica.engine.connect() as connection:
                await connection.execute(sa.text('PRAGMA foreign_keys=ON'))
        replica.app.artifact_service = ArtifactService(replica.app)
        replica.app.artifact_publication_service = ArtifactPublicationService(replica.app)
        replica.app.apikey_service = ApiKeyService(replica.app)
        await ArtifactsRouterGroup(replica.app, replica.client.app).initialize()
        if replicas.minio:
            _select_backend(replica, 'archive')
        return replica

    async def create(name):
        return await attach(await replicas.create(name))

    a = await attach(replicas.b)
    b = await create('artifact-core-b')
    account = await a.app.user_service.get_authenticated_account(replicas.token)
    context = RequestContext(
        instance_uuid=a.context.instance_uuid,
        placement_generation=a.context.placement_generation,
        request_id='artifact-test',
        auth_type='user_token',
        principal=PrincipalContext(PrincipalType.ACCOUNT, account_uuid=account.uuid),
        workspace=WorkspaceContext(
            workspace_uuid=a.context.workspace_uuid,
            membership_uuid=None,
            role='owner',
            permissions=permissions_for_role('owner'),
        ),
    )
    return SimpleNamespace(
        a=a,
        b=b,
        context=context,
        headers=_auth(replicas.token, a.context.workspace_uuid),
        create=create,
        minio=replicas.minio,
    )


async def _upload(case, name='report.bin', body=_BODY):
    return await _data(
        await case.a.client.post(
            '/api/v1/artifacts',
            headers=case.headers,
            files={'file': FileStorage(io.BytesIO(body), filename=name, content_type='application/octet-stream')},
        )
    )


async def _expire(replica, context, artifact_id):
    async with replica.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
        await uow.execute(
            sa.update(Artifact)
            .where(Artifact.workspace_uuid == context.workspace_uuid, Artifact.id == artifact_id)
            .values(expires_at=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - dt.timedelta(seconds=1))
        )


async def _content_ref(replica, context, artifact_id):
    async with replica.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
        return (
            await uow.execute(
                sa.select(Artifact.content_ref).where(
                    Artifact.workspace_uuid == context.workspace_uuid, Artifact.id == artifact_id
                )
            )
        ).scalar_one()


async def test_upload_download_survives_core_replacement(artifact_replicas):
    case = artifact_replicas
    uploaded = await _upload(case)
    artifact_id = uploaded['id']
    assert uploaded['name'] == 'report.bin'
    assert uploaded['size'] == len(_BODY)
    assert uploaded['digest'] == hashlib.sha256(_BODY).hexdigest()
    assert uploaded['expires_at'] is not None
    assert 'content_ref' not in uploaded and 'locator' not in uploaded
    url = f'/api/v1/artifacts/{artifact_id}'
    for replica in (case.a, case.b):
        metadata = await _data(await replica.client.get(url, headers=case.headers))
        assert metadata == uploaded
        downloaded = await replica.client.get(url + '/content', headers=case.headers)
        assert downloaded.status_code == 200 and await downloaded.get_data() == _BODY
        assert downloaded.headers['ETag'] == '"' + uploaded['digest'] + '"'
        assert downloaded.headers['X-Content-Type-Options'] == 'nosniff'
        assert 'attachment;' in downloaded.headers['Content-Disposition']
    assert (await case.b.client.get(url)).status_code == 401
    limited = await case.b.client.get(url + '/content?max_bytes=1', headers=case.headers)
    assert limited.status_code == 413
    ref = await _content_ref(case.a, case.context, artifact_id)
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        backend = (await uow.execute(sa.select(ContentObject.backend).where(ContentObject.ref == ref))).scalar_one()
    assert backend == ('archive' if case.minio else 'database')
    await _close_replica(case.a)
    fresh = await case.create('artifact-core-restarted')
    downloaded = await fresh.client.get(url + '/content', headers=case.headers)
    assert downloaded.status_code == 200 and await downloaded.get_data() == _BODY


async def test_owner_workspace_and_principal_boundaries(artifact_replicas):
    case = artifact_replicas
    artifact_id = (await _upload(case))['id']
    other = replace(
        case.context,
        principal=PrincipalContext(PrincipalType.ACCOUNT, account_uuid=str(uuid.uuid4())),
    )
    for operation in ('get', 'read', 'retain', 'release', 'delete'):
        with pytest.raises(ApplicationAPIException) as failure:
            await case.b.app.application_api.execute('artifact.' + operation, other, {'artifact_id': artifact_id})
        assert failure.value.error.status_code in {403, 404}
    for principal in (
        PrincipalContext(PrincipalType.API_KEY, api_key_uuid=str(uuid.uuid4())),
        PrincipalContext(PrincipalType.PLUGIN, installation_uuid=str(uuid.uuid4())),
        PrincipalContext(PrincipalType.PROCESSOR, processor_uuid=str(uuid.uuid4()), run_id='other-run'),
    ):
        with pytest.raises(ApplicationAPIException) as failure:
            await case.b.app.application_api.execute(
                'artifact.get', replace(case.context, principal=principal), {'artifact_id': artifact_id}
            )
        assert failure.value.error.status_code in {401, 403, 404}

    # A valid second execution binding isolates data even when the Account is identical.
    workspace = str(uuid.uuid4())
    async with case.a.engine.begin() as conn:
        await conn.execute(
            sa.insert(Workspace).values(
                uuid=workspace,
                instance_uuid=case.context.instance_uuid,
                name='Other Workspace',
                slug='other',
                source='cloud_projection',
            )
        )
        await conn.execute(
            sa.insert(WorkspaceExecutionState).values(
                workspace_uuid=workspace, instance_uuid=case.context.instance_uuid, source='cloud'
            )
        )
    foreign = replace(case.context, workspace=replace(case.context.workspace, workspace_uuid=workspace))
    with pytest.raises(ApplicationAPIException) as failure:
        await case.b.app.application_api.execute('artifact.get', foreign, {'artifact_id': artifact_id})
    assert failure.value.error.status_code == 404
    assert (
        await case.b.client.get(f'/api/v1/artifacts/{artifact_id}/content', headers=case.headers)
    ).status_code == 200


async def test_retain_release_delete_and_expiry(artifact_replicas):
    case = artifact_replicas
    artifact_id = (await _upload(case))['id']
    url = f'/api/v1/artifacts/{artifact_id}'
    for replica in (case.a, case.b):
        retained = await _data(await replica.client.post(url + '/retain', headers=case.headers))
        assert retained['expires_at'] is None
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        assert (await uow.execute(sa.select(sa.func.count()).select_from(ArtifactReference))).scalar_one() == 1
    assert (await case.a.client.delete(url, headers=case.headers)).status_code == 409
    released = await _data(await case.b.client.post(url + '/release', headers=case.headers))
    assert released['expires_at'] is not None
    repeated = await _data(await case.a.client.post(url + '/release', headers=case.headers))
    assert repeated['expires_at'] == released['expires_at']
    assert (await case.a.client.get(url + '/content', headers=case.headers)).status_code == 200
    await _data(await case.a.client.delete(url, headers=case.headers))
    assert (await case.b.client.get(url, headers=case.headers)).status_code == 404

    expired_id = (await _upload(case, 'expired.bin'))['id']
    await _expire(case.a, case.context, expired_id)
    expired_url = f'/api/v1/artifacts/{expired_id}'
    for suffix in ('', '/content'):
        assert (await case.b.client.get(expired_url + suffix, headers=case.headers)).status_code == 410
    assert (await case.b.client.post(expired_url + '/retain', headers=case.headers)).status_code == 410


async def test_retain_and_delete_serialize_across_replicas(artifact_replicas):
    case = artifact_replicas
    artifact_id = (await _upload(case))['id']
    url = f'/api/v1/artifacts/{artifact_id}'
    retained, deleted = await asyncio.gather(
        case.a.client.post(url + '/retain', headers=case.headers),
        case.b.client.delete(url, headers=case.headers),
    )
    assert (retained.status_code, deleted.status_code) in {(200, 409), (404, 200)}
    final = await case.b.client.get(url + '/content', headers=case.headers)
    assert final.status_code == (200 if retained.status_code == 200 else 404)
    if final.status_code == 200:
        assert await final.get_data() == _BODY


async def test_gc_protects_pins_and_retries_failed_object_deletion(artifact_replicas, monkeypatch):
    case = artifact_replicas
    live_id = (await _upload(case, 'keep.bin'))['id']
    await _data(await case.a.client.post(f'/api/v1/artifacts/{live_id}/retain', headers=case.headers))
    expired_id = (await _upload(case, 'reclaim.bin'))['id']
    content_ref = await _content_ref(case.a, case.context, expired_id)
    await _expire(case.a, case.context, expired_id)
    system = replace(case.a.context, trigger_principal=PrincipalContext(PrincipalType.SYSTEM))
    provider = original_delete = None
    if case.minio:
        store = case.a.app.storage_mgr.content_store
        provider, _location = await store._s3('archive')
        original_delete = provider.delete

        async def unavailable(_key):
            raise OSError('injected object deletion outage')

        monkeypatch.setattr(provider, 'delete', unavailable)
        assert await case.a.app.artifact_service.collect_expired(system) == 0
        async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
            tombstone = (
                await uow.execute(sa.select(Artifact.deleted_at).where(Artifact.id == expired_id))
            ).scalar_one()
            locator = (
                await uow.execute(sa.select(ContentObject.locator).where(ContentObject.ref == content_ref))
            ).scalar_one()
        assert tombstone is not None and locator is not None
        assert (
            await case.b.client.get(f'/api/v1/artifacts/{expired_id}/content', headers=case.headers)
        ).status_code == 404
        monkeypatch.setattr(provider, 'delete', original_delete)
    assert await case.a.app.artifact_service.collect_expired(system) == 1
    assert await case.b.app.artifact_service.collect_expired(system) == 0
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        assert (await uow.execute(sa.select(Artifact.id).where(Artifact.id == expired_id))).first() is None
        assert (await uow.execute(sa.select(ContentObject.ref).where(ContentObject.ref == content_ref))).first() is None
    kept = await case.b.client.get(f'/api/v1/artifacts/{live_id}/content', headers=case.headers)
    assert kept.status_code == 200 and await kept.get_data() == _BODY
    if case.minio:
        assert not await provider.exists(locator['key'])


async def test_integrity_failure_is_reported_to_the_downloader(artifact_replicas):
    case = artifact_replicas
    artifact_id = (await _upload(case))['id']
    ref = await _content_ref(case.a, case.context, artifact_id)
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        await uow.execute(sa.update(ContentObject).where(ContentObject.ref == ref).values(digest='0' * 64))
    response = await case.b.client.get(f'/api/v1/artifacts/{artifact_id}/content', headers=case.headers)
    assert response.status_code == 422
    assert 'artifact_integrity_failed' in await response.get_data(as_text=True)


async def test_gc_checks_existing_content_references_before_deleting_bytes(artifact_replicas):
    case = artifact_replicas
    artifact_id = (await _upload(case))['id']
    content_ref = await _content_ref(case.a, case.context, artifact_id)
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        await uow.execute(
            sa.insert(ContentAlias).values(
                workspace_uuid=case.context.workspace_uuid,
                key='retained-alias',
                content_ref=content_ref,
            )
        )
    await _expire(case.a, case.context, artifact_id)
    system = replace(case.a.context, trigger_principal=PrincipalContext(PrincipalType.SYSTEM))
    assert await case.a.app.artifact_service.collect_expired(system) == 0
    assert await case.b.app.storage_mgr.content_store.get(system, content_ref) == _BODY
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        await uow.execute(sa.delete(ContentAlias).where(ContentAlias.key == 'retained-alias'))
    assert await case.a.app.artifact_service.collect_expired(system) == 1


async def test_slow_download_does_not_block_another_core_writer(artifact_replicas, monkeypatch):
    case = artifact_replicas
    artifact_id = (await _upload(case))['id']
    store = case.a.app.storage_mgr.content_store
    original_read = store._read
    started, proceed = asyncio.Event(), asyncio.Event()

    async def stalled_read(*args, **kwargs):
        started.set()
        await proceed.wait()
        return await original_read(*args, **kwargs)

    monkeypatch.setattr(store, '_read', stalled_read)
    download = asyncio.create_task(case.a.app.artifact_service.read(case.context, artifact_id))
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        retained = await asyncio.wait_for(
            case.b.app.artifact_service.retain(case.context, artifact_id),
            timeout=5,
        )
        assert retained['lifecycle'] == 'persistent'
    finally:
        proceed.set()
        result = await download
    assert result['content'] == _BODY


async def test_api_key_ownership_and_missing_permissions(artifact_replicas):
    case = artifact_replicas
    key = 'artifact-test-global-key'
    for replica in (case.a, case.b):
        replica.app.instance_config.data['api']['global_api_key'] = key
    headers = {'X-API-Key': key}
    metadata = await _data(
        await case.a.client.post(
            '/api/v1/artifacts',
            headers=headers,
            files={'file': FileStorage(io.BytesIO(_BODY), filename='key-owned.bin')},
        )
    )
    url = '/api/v1/artifacts/' + metadata['id']
    downloaded = await case.b.client.get(url + '/content', headers=headers)
    assert downloaded.status_code == 200 and await downloaded.get_data() == _BODY
    assert (await case.a.client.get(url, headers=case.headers)).status_code == 404
    denied = replace(
        case.context,
        principal=PrincipalContext(PrincipalType.API_KEY, api_key_uuid='global-oss-api-key'),
        workspace=replace(case.context.workspace, permissions=frozenset()),
    )
    with pytest.raises(ApplicationAPIException) as failure:
        await case.a.app.application_api.execute('artifact.get', denied, {'artifact_id': metadata['id']})
    assert failure.value.error.status_code == 403
