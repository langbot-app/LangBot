"""Legacy upload handles retain their wire fields and share Artifact content."""
# ruff: noqa: F811

import io

import pytest
import sqlalchemy as sa
from quart.datastructures import FileStorage

from langbot.pkg.entity.persistence.artifact import Artifact
from langbot.pkg.entity.persistence.content import ContentAlias, ContentObject
from langbot.pkg.storage.artifacts import ArtifactError
from tests.integration.storage.test_artifacts import artifact_replicas, persistence_case, replicas  # noqa: F401

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize(
    ('kind', 'field', 'name'), [('images', 'file_key', 'sample.png'), ('documents', 'file_id', 'sample.txt')]
)
async def test_legacy_upload_alias_and_principal_hold_independently(artifact_replicas, kind, field, name):
    case = artifact_replicas
    body = b'legacy upload bytes'
    response = await case.a.client.post(
        '/api/v1/files/' + kind,
        headers=case.headers,
        files={'file': FileStorage(io.BytesIO(body), filename=name)},
    )
    assert response.status_code == 200
    data = (await response.get_json())['data']
    key, artifact_id = data[field], data['artifact_id']
    service = case.a.app.artifact_service
    assert (await service.read(case.context, artifact_id))['content'] == body
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        ref = (await uow.execute(sa.select(Artifact.content_ref).where(Artifact.id == artifact_id))).scalar_one()
        assert (
            await uow.execute(sa.select(ContentAlias.content_ref).where(ContentAlias.key == key))
        ).scalar_one() == ref
        assert (
            await uow.execute(sa.select(sa.func.count()).select_from(ContentObject).where(ContentObject.ref == ref))
        ).scalar_one() == 1
    await service.retain(case.context, artifact_id)
    await case.a.app.storage_mgr.content_store.delete_alias(case.context, key)
    assert (await service.get(case.context, artifact_id))['lifecycle'] == 'persistent'
    assert (await case.b.app.artifact_service.read(case.context, artifact_id))['content'] == body
    with pytest.raises(ArtifactError, match='still in use'):
        await service.delete(case.context, artifact_id)
    await service.release(case.context, artifact_id)
    assert (await service.get(case.context, artifact_id))['lifecycle'] == 'temporary'
    await service.delete(case.context, artifact_id)
    with pytest.raises(FileNotFoundError):
        await service.read(case.context, artifact_id)


async def test_removing_last_legacy_alias_restores_artifact_expiration(artifact_replicas):
    case = artifact_replicas
    result = await case.a.app.artifact_service.create_legacy_upload(
        case.context,
        owner_type='upload_document',
        owner='account:' + case.context.principal.account_uuid,
        key='legacy.txt',
        value=b'legacy',
        filename='legacy.txt',
        mime_type='text/plain',
    )
    artifact_id = result['artifact']['id']
    assert result['artifact']['lifecycle'] == 'persistent'
    await case.a.app.storage_mgr.content_store.delete_alias(case.context, result['file_key'])
    assert (await case.a.app.artifact_service.get(case.context, artifact_id))['lifecycle'] == 'temporary'
    await case.a.app.artifact_service.delete(case.context, artifact_id)


async def test_legacy_alias_collision_rolls_back_new_artifact_and_bytes(artifact_replicas):
    case = artifact_replicas
    service = case.a.app.artifact_service
    kwargs = dict(
        owner_type='upload_document',
        owner='account:' + case.context.principal.account_uuid,
        key='same-key.txt',
        filename='same-key.txt',
        mime_type='text/plain',
    )
    first = await service.create_legacy_upload(case.context, value=b'original', **kwargs)
    with pytest.raises(sa.exc.IntegrityError):
        await service.create_legacy_upload(case.context, value=b'replacement must roll back', **kwargs)
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        for model in (Artifact, ContentAlias, ContentObject):
            assert (await uow.execute(sa.select(sa.func.count()).select_from(model))).scalar_one() == 1
    assert (await case.b.app.artifact_service.read(case.context, first['artifact']['id']))['content'] == b'original'


async def test_legacy_upload_cancel_rolls_back_bytes_and_metadata(artifact_replicas, monkeypatch):
    import asyncio

    case = artifact_replicas
    service = case.a.app.artifact_service
    original = service._create_owned
    written = asyncio.Event()
    wait = asyncio.Event()

    async def paused(*args, **kwargs):
        result = await original(*args, **kwargs)
        written.set()
        await wait.wait()
        return result

    monkeypatch.setattr(service, '_create_owned', paused)
    task = asyncio.create_task(
        service.create_legacy_upload(
            case.context,
            owner_type='upload_document',
            owner='account:' + case.context.principal.account_uuid,
            key='cancel.txt',
            value=b'uncommitted bytes',
            filename='cancel.txt',
            mime_type='text/plain',
        )
    )
    await asyncio.wait_for(written.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        for model in (Artifact, ContentAlias, ContentObject):
            assert (await uow.execute(sa.select(sa.func.count()).select_from(model))).scalar_one() == 0


async def test_legacy_nonpersistent_fallback_does_not_claim_artifact(artifact_replicas, monkeypatch):
    from unittest.mock import AsyncMock

    case = artifact_replicas
    manager = case.a.app.storage_mgr
    monkeypatch.setattr(type(manager), 'persistent_content', property(lambda self: False))
    saved = AsyncMock(return_value='legacy-scoped-key')
    monkeypatch.setattr(manager, 'save_scoped', saved)
    result = await case.a.app.artifact_service.create_legacy_upload(
        case.context,
        owner_type='upload_document',
        owner='account:' + case.context.principal.account_uuid,
        key='legacy.txt',
        value=b'legacy bytes',
        filename='legacy.txt',
    )
    assert result == {'artifact': None, 'file_key': 'legacy-scoped-key'}
    saved.assert_awaited_once_with(
        case.context,
        owner_type='upload_document',
        owner='account:' + case.context.principal.account_uuid,
        key='legacy.txt',
        value=b'legacy bytes',
    )
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        assert not (await uow.execute(sa.select(Artifact.id))).first()


async def test_alias_delete_serializes_with_other_core_retain(artifact_replicas, monkeypatch):
    import asyncio
    from contextlib import asynccontextmanager
    from dataclasses import replace
    from langbot.pkg.api.context import PrincipalContext, PrincipalType

    case = artifact_replicas
    result = await case.a.app.artifact_service.create_legacy_upload(
        case.context,
        owner_type='upload_document',
        owner='account:' + case.context.principal.account_uuid,
        key='racing.txt',
        value=b'shared alias and principal',
        filename='racing.txt',
    )
    artifact_id = result['artifact']['id']
    locked, release, retain_attempted = asyncio.Event(), asyncio.Event(), asyncio.Event()
    original = case.a.app.persistence_mgr.tenant_uow

    @asynccontextmanager
    async def paused_uow(*args, **kwargs):
        async with original(*args, **kwargs) as uow:

            class Proxy:
                def __getattr__(self, name):
                    return getattr(uow, name)

                async def execute(self, statement, *params, **options):
                    result = await uow.execute(statement, *params, **options)
                    if str(statement).startswith('UPDATE artifacts ') and not locked.is_set():
                        locked.set()
                        await release.wait()
                    return result

            yield Proxy()

    def observe_retain(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith('UPDATE artifacts '):
            retain_attempted.set()

    monkeypatch.setattr(case.a.app.persistence_mgr, 'tenant_uow', paused_uow)
    sa.event.listen(case.b.engine.sync_engine, 'before_cursor_execute', observe_retain)
    deleting = asyncio.create_task(case.a.app.storage_mgr.content_store.delete_alias(case.context, result['file_key']))
    retaining = None
    try:
        await asyncio.wait_for(locked.wait(), 5)
        retaining = asyncio.create_task(case.b.app.artifact_service.retain(case.context, artifact_id))
        await asyncio.wait_for(retain_attempted.wait(), 5)
        release.set()
        await deleting
        assert (await retaining)['lifecycle'] == 'persistent'
    finally:
        release.set()
        for task in (deleting, retaining):
            if task is not None and not task.done():
                task.cancel()
        await asyncio.gather(*(task for task in (deleting, retaining) if task is not None), return_exceptions=True)
        sa.event.remove(case.b.engine.sync_engine, 'before_cursor_execute', observe_retain)
    assert (await case.b.app.artifact_service.read(case.context, artifact_id))[
        'content'
    ] == b'shared alias and principal'
    system = replace(case.b.context, trigger_principal=PrincipalContext(PrincipalType.SYSTEM))
    assert await case.b.app.artifact_service.collect_expired(system) == 0
