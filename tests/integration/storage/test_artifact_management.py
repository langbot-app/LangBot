"""Named output managers, run input grants and bounded read leases on real storage."""
# ruff: noqa: F811

import asyncio
from dataclasses import replace
import datetime as dt
import uuid

import pytest
import sqlalchemy as sa

from langbot.pkg.api.authz import PermissionDeniedError
from langbot.pkg.api.context import PrincipalContext, PrincipalType
from langbot.pkg.entity.persistence.agent_run import AgentRun
from langbot.pkg.entity.persistence.apikey import ApiKey
from langbot.pkg.entity.persistence.artifact import Artifact, ArtifactReference
from langbot.pkg.entity.persistence.workspace import WorkspaceMembership
from langbot.pkg.storage import artifacts as artifact_module
from langbot.pkg.storage.artifacts import ArtifactError
from tests.integration.storage.test_artifact_run_outputs import _BODY, _create, _end_run, _start_run
from tests.integration.storage.test_artifacts import (
    _BODY as _UPLOAD_BODY,
    _expire,
    _upload,
    artifact_replicas,  # noqa: F401 -- pytest fixture
    persistence_case,  # noqa: F401 -- fixture dependency
    replicas,  # noqa: F401 -- fixture dependency
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _system(case):
    return replace(case.a.context, trigger_principal=PrincipalContext(PrincipalType.SYSTEM))


async def _key_manager(case, *, scopes=('resource.view', 'resource.manage')):
    key = await case.a.app.apikey_service.create_api_key(case.context, 'output-manager', scopes=scopes)
    context = replace(
        case.context,
        principal=PrincipalContext(PrincipalType.API_KEY, api_key_uuid=key['uuid']),
        workspace=replace(case.context.workspace, permissions=frozenset(scopes)),
    )
    return context, {'X-API-Key': key['key']}, key['uuid']


async def _pins(case, asset_id):
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        return (
            (
                await uow.execute(
                    sa.select(ArtifactReference.__table__).where(
                        ArtifactReference.artifact_id == asset_id,
                    )
                )
            )
            .mappings()
            .all()
        )


async def test_manager_key_is_private_and_conflicting_batch_does_not_partly_publish(artifact_replicas):
    case = artifact_replicas
    run = await _start_run(case)
    manager, headers, _key_uuid = await _key_manager(case)
    first, second = await _create(case, run, 'key.bin'), await _create(case, run, 'new.bin')
    await case.a.app.artifact_service.commit_run_outputs(run, [first['id']], manager_context=manager)
    url = '/api/v1/artifacts/' + first['id']
    assert (await case.b.client.get(url + '/content', headers=headers)).status_code == 200
    assert (await case.b.client.get(url, headers=case.headers)).status_code == 404
    other, other_headers, _ = await _key_manager(case)
    assert (await case.b.client.get(url, headers=other_headers)).status_code == 404
    with pytest.raises(ArtifactError) as failure:
        await case.b.app.artifact_service.commit_run_outputs(
            run, [second['id'], first['id']], manager_context=case.context
        )
    assert failure.value.error_code == 'artifact_manager_conflict'
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        row = (await uow.execute(sa.select(Artifact.manager_type).where(Artifact.id == second['id']))).one()
    assert row.manager_type is None and not await _pins(case, second['id'])
    await case.a.app.artifact_service.release(manager, first['id'])
    third = await _create(case, run, 'third.bin')
    repeated = await case.b.app.artifact_service.commit_run_outputs(
        run, [first['id'], third['id']], manager_context=manager
    )
    assert [entry['id'] for entry in repeated] == [first['id'], third['id']]
    assert repeated[1]['lifecycle'] == 'persistent' and len(await _pins(case, third['id'])) == 1
    assert repeated[0]['lifecycle'] == 'temporary' and not await _pins(case, first['id'])
    assert await case.b.app.artifact_service.expire_run_outputs(run) == 1
    assert (await case.b.app.artifact_service.get(manager, first['id']))['expires_at'] == repeated[0]['expires_at']
    with pytest.raises(ArtifactError) as failure:
        await case.b.app.artifact_service.delete(manager, first['id'])
    assert failure.value.error_code == 'artifact_in_use'
    await _end_run(case, run)
    await case.b.app.artifact_service.delete(manager, first['id'])
    assert (await case.b.client.get(url, headers=headers)).status_code == 404
    with pytest.raises(FileNotFoundError):
        await case.b.app.artifact_service.get(other, first['id'])


async def test_publication_rechecks_membership_and_named_key_state(artifact_replicas):
    case = artifact_replicas
    run = await _start_run(case)
    output = await _create(case, run)
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        await uow.execute(
            sa.update(WorkspaceMembership)
            .where(
                WorkspaceMembership.account_uuid == case.context.account_uuid,
            )
            .values(role='viewer')
        )
    with pytest.raises(PermissionDeniedError):
        await case.a.app.artifact_service.commit_run_outputs(run, [output['id']], manager_context=case.context)
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        await uow.execute(
            sa.update(WorkspaceMembership)
            .where(
                WorkspaceMembership.account_uuid == case.context.account_uuid,
            )
            .values(role='owner')
        )
    manager, _headers, key_uuid = await _key_manager(case)
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        await uow.execute(sa.update(ApiKey).where(ApiKey.uuid == key_uuid).values(status='revoked'))
    with pytest.raises(ArtifactError) as failure:
        await case.a.app.artifact_service.commit_run_outputs(run, [output['id']], manager_context=manager)
    assert failure.value.error_code == 'artifact_publish_not_authorized'
    for identity in ('global-oss-api-key', str(uuid.uuid4())):
        invalid = replace(manager, principal=PrincipalContext(PrincipalType.API_KEY, api_key_uuid=identity))
        with pytest.raises(ArtifactError) as failure:
            await case.a.app.artifact_service.commit_run_outputs(run, [output['id']], manager_context=invalid)
        assert failure.value.error_code == 'artifact_publish_not_authorized'
    assert not await _pins(case, output['id'])


async def test_read_lease_blocks_delete_and_gc_without_pinning_retention(artifact_replicas, monkeypatch):
    case = artifact_replicas
    asset = await _upload(case)
    await case.a.app.artifact_service.retain(case.context, asset['id'])
    store = case.a.app.storage_mgr.content_store
    original = store._read
    started, proceed = asyncio.Event(), asyncio.Event()

    async def slow(*args, **kwargs):
        started.set()
        await proceed.wait()
        return await original(*args, **kwargs)

    monkeypatch.setattr(store, '_read', slow)
    task = asyncio.create_task(case.a.app.artifact_service.read(case.context, asset['id']))
    try:
        await asyncio.wait_for(started.wait(), 5)
        released = await case.b.app.artifact_service.release(case.context, asset['id'])
        assert released['expires_at'] is not None
        with pytest.raises(ArtifactError) as failure:
            await case.b.app.artifact_service.delete(case.context, asset['id'])
        assert failure.value.error_code == 'artifact_in_use'
        await _expire(case.b, case.context, asset['id'])
        assert await case.b.app.artifact_service.collect_expired(_system(case)) == 0
        assert [pin['holder_type'] for pin in await _pins(case, asset['id'])] == ['read_lease']
    finally:
        proceed.set()
        result = await task
    assert result['content'] == _UPLOAD_BODY
    assert not await _pins(case, asset['id'])
    assert await case.b.app.artifact_service.collect_expired(_system(case)) == 1


async def test_read_cancellation_timeout_and_abandoned_lease_are_recoverable(artifact_replicas, monkeypatch):
    case = artifact_replicas
    asset = await _upload(case)
    store = case.a.app.storage_mgr.content_store
    started = asyncio.Event()

    async def stalled(*_args, **_kwargs):
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(store, '_read', stalled)
    task = asyncio.create_task(case.a.app.artifact_service.read(case.context, asset['id']))
    await asyncio.wait_for(started.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not await _pins(case, asset['id'])
    monkeypatch.setattr(artifact_module, 'READ_TIMEOUT_SECONDS', 0.02)
    with pytest.raises(ArtifactError) as failure:
        await case.a.app.artifact_service.read(case.context, asset['id'])
    assert failure.value.error_code == 'artifact_read_timeout' and not await _pins(case, asset['id'])
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        await uow.execute(
            sa.insert(ArtifactReference).values(
                workspace_uuid=case.context.workspace_uuid,
                artifact_id=asset['id'],
                holder_type='read_lease',
                holder_id='crashed-reader',
                expires_at=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - dt.timedelta(seconds=1),
            )
        )
    await _expire(case.b, case.context, asset['id'])
    assert await case.b.app.artifact_service.collect_expired(_system(case)) == 1


async def test_debug_input_binding_protects_live_run_without_sharing_to_other_runs(artifact_replicas):
    case = artifact_replicas
    producer, consumer, other = await _start_run(case), await _start_run(case), await _start_run(case)
    asset = await _create(case, producer)
    await case.a.app.artifact_service.commit_run_outputs(producer, [asset['id']], manager_context=case.context)
    await _end_run(case, producer)
    await case.a.app.artifact_service.bind_run_inputs(case.context, consumer, [asset['id']])
    with pytest.raises(FileNotFoundError):
        await case.b.app.artifact_service.read_bound_run_input(other, asset['id'])
    await case.b.app.artifact_service.release(case.context, asset['id'])
    with pytest.raises(ArtifactError) as failure:
        await case.a.app.artifact_service.delete(case.context, asset['id'])
    assert failure.value.error_code == 'artifact_in_use'
    await _expire(case.b, case.context, asset['id'])
    assert (await case.b.app.artifact_service.read_bound_run_input(consumer, asset['id']))['content'] == _BODY
    assert await case.b.app.artifact_service.collect_expired(_system(case)) == 0
    await case.a.app.artifact_service.release_run_inputs(consumer)
    assert await case.b.app.artifact_service.collect_expired(_system(case)) == 1


async def test_crashed_input_consumer_does_not_leave_a_permanent_pin(artifact_replicas):
    case = artifact_replicas
    asset = await _upload(case)
    consumer = await _start_run(case)
    await case.a.app.artifact_service.bind_run_inputs(case.context, consumer, [asset['id']])
    await _expire(case.b, case.context, asset['id'])
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        await uow.execute(
            sa.update(AgentRun)
            .where(AgentRun.run_id == consumer.trigger_principal.run_id)
            .values(
                execution_lease_expires_at=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
                - dt.timedelta(seconds=1),
            )
        )
    with pytest.raises(FileNotFoundError):
        await case.b.app.artifact_service.read_bound_run_input(consumer, asset['id'])
    assert await case.b.app.artifact_service.collect_expired(_system(case)) == 1


async def test_legacy_committed_output_remains_private_and_preserved(artifact_replicas):
    case = artifact_replicas
    run = await _start_run(case)
    asset = await _create(case, run)
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        await uow.execute(sa.update(Artifact).where(Artifact.id == asset['id']).values(expires_at=None))
        await uow.execute(
            sa.insert(ArtifactReference).values(
                workspace_uuid=case.context.workspace_uuid,
                artifact_id=asset['id'],
                holder_type='run_output_commit',
                holder_id=run.trigger_principal.run_id,
            )
        )
    with pytest.raises(ArtifactError) as failure:
        await case.b.app.artifact_service.commit_run_outputs(run, [asset['id']], manager_context=case.context)
    assert failure.value.error_code == 'artifact_legacy_commit_unmanaged'
    assert (await case.b.client.get('/api/v1/artifacts/' + asset['id'], headers=case.headers)).status_code == 404
    await _end_run(case, run)
    assert await case.b.app.artifact_service.collect_expired(_system(case)) == 0


async def test_late_upload_and_publication_cannot_outlive_run_lease(artifact_replicas, monkeypatch):
    case = artifact_replicas
    run = await _start_run(case)
    service = case.a.app.artifact_service
    put = service.content.put
    now = artifact_module._now
    late = now() + dt.timedelta(minutes=5)

    async def completed_after_lease(*args, **kwargs):
        reference = await put(*args, **kwargs)
        monkeypatch.setattr(artifact_module, '_now', lambda: late)
        return reference

    monkeypatch.setattr(service.content, 'put', completed_after_lease)
    with pytest.raises(ArtifactError) as failure:
        await _create(case, run)
    assert failure.value.error_code == 'artifact_run_not_active'
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        assert (await uow.execute(sa.select(Artifact.id))).first() is None
        assert (await uow.execute(sa.select(artifact_module.ContentObject.ref))).first() is None
    monkeypatch.setattr(service.content, 'put', put)
    monkeypatch.setattr(artifact_module, '_now', now)
    outputs = [await _create(case, run, name) for name in ('first.bin', 'last.bin')]
    ids = sorted(output['id'] for output in outputs)
    row = service._row

    async def lease_expires_after_batch_lock(*args, **kwargs):
        result = await row(*args, **kwargs)
        if kwargs.get('run_read') and kwargs.get('lock') and result['id'] == ids[-1]:
            monkeypatch.setattr(artifact_module, '_now', lambda: late)
        return result

    monkeypatch.setattr(service, '_row', lease_expires_after_batch_lock)
    with pytest.raises(ArtifactError) as failure:
        await service.commit_run_outputs(run, ids, manager_context=case.context)
    assert failure.value.error_code == 'artifact_run_not_active'
    for asset_id in ids:
        assert not await _pins(case, asset_id)


async def test_read_waiting_for_asset_lock_rechecks_even_persistent_run_output(artifact_replicas, monkeypatch):
    case = artifact_replicas
    run = await _start_run(case)
    output = await _create(case, run)
    service = case.a.app.artifact_service
    await service.commit_run_outputs(run, [output['id']], manager_context=case.context)
    authorized = asyncio.Event()
    proceed = asyncio.Event()
    authorize = service._authorize_run
    late = artifact_module._now() + dt.timedelta(minutes=5)

    async def after_authorization(context):
        result = await authorize(context)
        authorized.set()
        await proceed.wait()
        return result

    monkeypatch.setattr(service, '_authorize_run', after_authorization)
    task = asyncio.create_task(service.read_run_output(run, output['id']))
    try:
        await asyncio.wait_for(authorized.wait(), 5)
        async with case.b.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
            await uow.execute(sa.update(Artifact).where(Artifact.id == output['id']).values(id=Artifact.id))
            proceed.set()
            await asyncio.sleep(0)
            monkeypatch.setattr(artifact_module, '_now', lambda: late)
        with pytest.raises(ArtifactError) as failure:
            await asyncio.wait_for(task, 5)
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    assert failure.value.error_code == 'artifact_run_not_active'
    assert [pin['holder_type'] for pin in await _pins(case, output['id'])] == ['principal']
