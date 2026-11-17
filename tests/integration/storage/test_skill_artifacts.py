"""Skill references preserve source identity, authority and package ownership."""
# ruff: noqa: F811

import asyncio
from dataclasses import replace
import io
import json
import uuid

import pytest
import sqlalchemy as sa
from quart.datastructures import FileStorage

from langbot.pkg.api.authz import PermissionDeniedError
from langbot.pkg.api.context import PrincipalContext, PrincipalType
from langbot.pkg.entity.persistence.agent_run import AgentRun
from langbot.pkg.entity.persistence.artifact import Artifact, ArtifactReference
from langbot.pkg.entity.persistence.content import ContentObject
from langbot.pkg.entity.persistence.skill import SkillVersion
from langbot.pkg.storage.artifacts import ArtifactError
from tests.integration.skill.test_persistent_skill_replicas import _data, _zip_package, _NAME, _GUIDE
from tests.integration.storage.test_artifact_run_outputs import _start_run, _end_run
from tests.integration.storage.test_artifacts import (
    artifact_replicas,  # noqa: F401
    persistence_case,  # noqa: F401
    replicas,  # noqa: F401
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _install(case):
    result = await _data(
        await case.a.client.post(
            '/api/v1/skills/install/upload',
            headers=case.headers,
            files={'file': FileStorage(io.BytesIO(_zip_package()), filename='probe.zip')},
        )
    )
    return result['skills'][0]['revision']


async def _create(case, revision, path='references/guide.md', context=None):
    return await case.a.app.artifact_service.create_skill_resource(
        context or case.context,
        _NAME,
        revision,
        path,
    )


async def _system(case):
    return replace(case.a.context, trigger_principal=PrincipalContext(PrincipalType.SYSTEM))


async def test_skill_artifact_fixed_version_no_copies_and_restart(artifact_replicas):
    case = artifact_replicas
    revision = await _install(case)
    first = await _create(case, revision)
    assert first['source'] == 'skill_resource'
    assert await _create(case, revision) == first
    await case.a.app.skill_repository.write_skill_file(
        case.a.context,
        _NAME,
        'references/guide.md',
        'new bytes',
        base_revision=revision,
    )
    current = await case.a.app.skill_repository.get_skill(case.a.context, _NAME, snapshot=False)
    second = await _create(case, current['revision'])
    fresh = await case.create('skill-artifact-fresh-core')
    assert (await fresh.app.artifact_service.read(case.context, first['id']))['content'] == _GUIDE.encode()
    assert (await fresh.app.artifact_service.read(case.context, second['id']))['content'] == b'new bytes'
    assert first['digest'] != second['digest']
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        assert not (
            await uow.execute(sa.select(ContentObject.ref).where(ContentObject.owner_type == 'artifact'))
        ).first()
        rows = (await uow.execute(sa.select(Artifact.content_ref))).scalars().all()
        packages = (await uow.execute(sa.select(SkillVersion.content_ref))).scalars().all()
        assert set(rows).issubset(packages)


async def test_skill_artifact_owner_permissions_and_conversion(artifact_replicas):
    case = artifact_replicas
    revision = await _install(case)
    item = await _create(case, revision)
    other = replace(case.context, principal=PrincipalContext(PrincipalType.ACCOUNT, account_uuid=str(uuid.uuid4())))
    for action in ('get', 'read', 'retain', 'release', 'delete'):
        with pytest.raises(FileNotFoundError):
            await getattr(case.b.app.artifact_service, action)(other, item['id'])
    denied = replace(case.context, workspace=replace(case.context.workspace, permissions=frozenset()))
    with pytest.raises(PermissionDeniedError):
        await case.a.app.artifact_service.read(denied, item['id'])
    with pytest.raises(PermissionDeniedError):
        await _create(case, revision, context=denied)
    with pytest.raises(PermissionDeniedError):
        await case.a.app.artifact_service.bind_run_inputs(case.context, await _start_run(case), [item['id']])


async def test_skill_artifact_gc_never_deletes_package_or_other_reference(artifact_replicas):
    case = artifact_replicas
    revision = await _install(case)
    a = await _create(case, revision)
    b = await _create(case, revision, 'scripts/probe.py')
    await case.a.app.artifact_service.delete(case.context, a['id'])
    assert await case.b.app.artifact_service.collect_expired(await _system(case)) == 1
    assert (await case.b.app.artifact_service.read(case.context, b['id']))['content'].startswith(b'#!/')
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        assert (await uow.execute(sa.select(SkillVersion.uuid))).first()
        assert (await uow.execute(sa.select(ContentObject.ref).where(ContentObject.owner_type == 'skill'))).first()
    # Catalogue deletion does not rewrite or remove the retained immutable version.
    await _data(await case.a.client.delete(f'/api/v1/skills/{_NAME}', headers=case.headers))
    assert (await case.b.app.artifact_service.read(case.context, b['id']))['content'].startswith(b'#!/')


async def test_skill_artifact_read_lease_cancel_releases_pin(artifact_replicas, monkeypatch):
    case = artifact_replicas
    item = await _create(case, await _install(case))
    entered, release = asyncio.Event(), asyncio.Event()
    reader = case.b.app.skill_repository.read_artifact_resource

    async def slow(*args, **kwargs):
        entered.set()
        await release.wait()
        return await reader(*args, **kwargs)

    monkeypatch.setattr(case.b.app.skill_repository, 'read_artifact_resource', slow)
    task = asyncio.create_task(case.b.app.artifact_service.read(case.context, item['id']))
    await asyncio.wait_for(entered.wait(), 5)
    with pytest.raises(ArtifactError, match='in use'):
        await case.a.app.artifact_service.delete(case.context, item['id'])
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        assert not (await uow.execute(sa.select(ArtifactReference.artifact_id))).first()
    await case.a.app.artifact_service.delete(case.context, item['id'])
    assert await case.a.app.artifact_service.collect_expired(await _system(case)) == 1


async def test_run_skill_artifact_requires_persisted_pin_and_active_run(artifact_replicas):
    case = artifact_replicas
    revision = await _install(case)
    context = await _start_run(case)
    service = case.a.app.artifact_service
    with pytest.raises(PermissionDeniedError):
        await service.create_run_skill_resource(context, _NAME, revision, 'references/guide.md')
    async with case.a.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
        await uow.execute(
            sa.update(AgentRun)
            .where(AgentRun.run_id == context.trigger_principal.run_id)
            .values(
                metadata_json=json.dumps({'activated_skills': {_NAME: revision}}),
            )
        )
    item = await service.create_run_skill_resource(context, _NAME, revision, 'references/guide.md')
    assert (await service.read_run_skill_resource(context, item['id']))['content'] == _GUIDE.encode()
    with pytest.raises(FileNotFoundError):
        await service.read(case.context, item['id'])
    with pytest.raises(FileNotFoundError):
        await service.read_run_skill_resource(await _start_run(case), item['id'])
    await _end_run(case, context)
    with pytest.raises(ArtifactError):
        await service.read_run_skill_resource(context, item['id'])


async def test_skill_artifact_foreign_workspace_denied(artifact_replicas):
    from langbot.pkg.entity.persistence.workspace import Workspace, WorkspaceExecutionState

    case = artifact_replicas
    item = await _create(case, await _install(case))
    workspace = str(uuid.uuid4())
    async with case.a.engine.begin() as conn:
        await conn.execute(
            sa.insert(Workspace).values(
                uuid=workspace,
                instance_uuid=case.context.instance_uuid,
                name='Other',
                slug='other',
                source='cloud_projection',
            )
        )
        await conn.execute(
            sa.insert(WorkspaceExecutionState).values(
                workspace_uuid=workspace,
                instance_uuid=case.context.instance_uuid,
                source='cloud',
            )
        )
    context = replace(case.context, workspace=replace(case.context.workspace, workspace_uuid=workspace))
    for action in ('get', 'read', 'retain', 'release', 'delete'):
        with pytest.raises(FileNotFoundError):
            await getattr(case.b.app.artifact_service, action)(context, item['id'])


async def test_skill_artifact_registration_failure_is_atomic_and_retryable(artifact_replicas):
    case = artifact_replicas
    revision = await _install(case)

    def fail_insert(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith('INSERT INTO artifacts '):
            raise RuntimeError('injected artifact insert failure')

    sa.event.listen(case.a.engine.sync_engine, 'before_cursor_execute', fail_insert)
    try:
        with pytest.raises(RuntimeError, match='injected artifact insert failure'):
            await _create(case, revision)
    finally:
        sa.event.remove(case.a.engine.sync_engine, 'before_cursor_execute', fail_insert)
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        assert not (await uow.execute(sa.select(Artifact.id))).first()
    a, b = await asyncio.gather(_create(case, revision), _create(case, revision))
    assert a == b
    assert (await case.b.app.artifact_service.read(case.context, a['id']))['content'] == _GUIDE.encode()


async def test_skill_artifact_version_fk_blocks_delete_until_collected(artifact_replicas):
    case = artifact_replicas
    item = await _create(case, await _install(case))
    with pytest.raises(sa.exc.IntegrityError):
        async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
            await uow.execute(sa.delete(SkillVersion))
    assert (await case.b.app.artifact_service.read(case.context, item['id']))['content'] == _GUIDE.encode()
    await case.a.app.artifact_service.delete(case.context, item['id'])
    assert await case.a.app.artifact_service.collect_expired(await _system(case)) == 1
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        await uow.execute(sa.delete(SkillVersion))


async def test_run_skill_live_lease_protects_expired_reference(artifact_replicas):
    from tests.integration.storage.test_artifacts import _expire

    case = artifact_replicas
    revision = await _install(case)
    context = await _start_run(case)
    async with case.a.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
        await uow.execute(
            sa.update(AgentRun)
            .where(AgentRun.run_id == context.trigger_principal.run_id)
            .values(
                metadata_json=json.dumps({'activated_skills': {_NAME: revision}}),
            )
        )
    service = case.a.app.artifact_service
    item = await service.create_run_skill_resource(context, _NAME, revision, 'references/guide.md')
    await _expire(case.a, context, item['id'])
    assert await service.collect_expired(await _system(case)) == 0
    assert (await service.read_run_skill_resource(context, item['id']))['content'] == _GUIDE.encode()
    await _end_run(case, context)
    assert await service.collect_expired(await _system(case)) == 1


async def test_skill_artifact_http_and_mcp_preserve_source_owner(artifact_replicas):
    from mcp import types
    from langbot.pkg.api.mcp.context import bind_request_context, reset_request_context
    from langbot.pkg.api.mcp.server import LangBotMCPServer

    case = artifact_replicas
    revision = await _install(case)
    payload = {'skill_name': _NAME, 'revision': revision, 'path': 'references/guide.md'}
    metadata = await _data(
        await case.a.client.post(
            '/api/v1/artifacts/skill-resources',
            headers=case.headers,
            json=payload,
        )
    )
    url = '/api/v1/artifacts/' + metadata['id']
    assert await _data(await case.b.client.get(url, headers=case.headers)) == metadata
    downloaded = await case.b.client.get(url + '/content', headers=case.headers)
    assert downloaded.status_code == 200 and await downloaded.get_data() == _GUIDE.encode()
    blocks = await _data(await case.b.client.get(url + '/read?max_chars=8', headers=case.headers))
    assert json.loads(blocks[0]['text'])['text'] == _GUIDE[:8]
    assert (await case.b.client.get(url + '/read')).status_code == 401
    key = 'skill-artifact-test-global-key'
    for replica in (case.a, case.b):
        replica.app.instance_config.data['api']['global_api_key'] = key
    for suffix in ('', '/read', '/content'):
        assert (await case.b.client.get(url + suffix, headers={'X-API-Key': key})).status_code == 404
    server = LangBotMCPServer(case.b.app)
    token = bind_request_context(case.context)
    try:
        response = await server.mcp.call_tool('create_skill_resource_artifact', payload)
        result = response.content if isinstance(response, types.CallToolResult) else response[0]
        assert json.loads(result[0].text)['id'] == metadata['id']
        response = await server.mcp.call_tool('read_artifact_content', {'artifact_id': metadata['id'], 'max_chars': 8})
        result = response.content if isinstance(response, types.CallToolResult) else response[0]
        assert json.loads(result[0].text)['text'] == _GUIDE[:8]
    finally:
        reset_request_context(token)


async def test_skill_artifact_gc_transaction_failure_preserves_package_and_retry(artifact_replicas):
    case = artifact_replicas
    item = await _create(case, await _install(case))
    await case.a.app.artifact_service.delete(case.context, item['id'])

    def fail_after_delete(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith('DELETE FROM artifacts '):
            raise RuntimeError('injected failure after artifact metadata delete')

    sa.event.listen(case.b.engine.sync_engine, 'after_cursor_execute', fail_after_delete)
    try:
        assert await case.b.app.artifact_service.collect_expired(await _system(case)) == 0
    finally:
        sa.event.remove(case.b.engine.sync_engine, 'after_cursor_execute', fail_after_delete)
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        row = (await uow.execute(sa.select(Artifact.__table__).where(Artifact.id == item['id']))).mappings().one()
        assert row['deleted_at'] is not None
        assert (
            await uow.execute(sa.select(SkillVersion.uuid).where(SkillVersion.uuid == row['source_version_id']))
        ).first()
        assert (await uow.execute(sa.select(ContentObject.ref).where(ContentObject.ref == row['content_ref']))).first()
    with pytest.raises(FileNotFoundError):
        await case.a.app.artifact_service.read(case.context, item['id'])
    assert await case.a.app.artifact_service.collect_expired(await _system(case)) == 1
    assert await case.b.app.artifact_service.collect_expired(await _system(case)) == 0
    # Retrying registration after collection resolves the same still-authoritative package.
    recreated = await _create(
        case, (await case.a.app.skill_repository.get_skill(case.a.context, _NAME, snapshot=False))['revision']
    )
    assert (await case.b.app.artifact_service.read(case.context, recreated['id']))['content'] == _GUIDE.encode()


@pytest.mark.parametrize('winner', ['delete', 'register'])
async def test_skill_artifact_registration_serializes_version_delete(artifact_replicas, monkeypatch, winner):
    case = artifact_replicas
    revision = await _install(case)
    descriptor_ready, descriptor_release = asyncio.Event(), asyncio.Event()
    registration_inserted, registration_release = asyncio.Event(), asyncio.Event()
    competing_statement = asyncio.Event()
    repo = case.a.app.skill_repository
    resolve = repo.resolve_artifact_resource
    service = case.a.app.artifact_service
    get_row = service._row

    async def paused_resolve(*args, **kwargs):
        result = await resolve(*args, **kwargs)
        descriptor_ready.set()
        await descriptor_release.wait()
        return result

    async def paused_row(*args, **kwargs):
        result = await get_row(*args, **kwargs)
        if winner == 'register':
            registration_inserted.set()
            await registration_release.wait()
        return result

    monkeypatch.setattr(repo, 'resolve_artifact_resource', paused_resolve)
    monkeypatch.setattr(service, '_row', paused_row)

    def observe_competitor(connection, cursor, statement, parameters, context, executemany):
        if winner == 'delete' and statement.startswith('UPDATE skill_versions '):
            competing_statement.set()
        if winner == 'register' and statement.startswith('DELETE FROM skill_versions'):
            competing_statement.set()

    engine = case.a.engine if winner == 'delete' else case.b.engine
    sa.event.listen(engine.sync_engine, 'before_cursor_execute', observe_competitor)
    registration = asyncio.create_task(_create(case, revision))
    deletion = None
    try:
        await asyncio.wait_for(descriptor_ready.wait(), 5)
        if winner == 'delete':
            async with case.b.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
                await uow.execute(sa.delete(SkillVersion).where(SkillVersion.revision == revision))
                descriptor_release.set()
                # Registration now waits on the deletion's writer/FK transaction, not a stale snapshot.
                await asyncio.wait_for(competing_statement.wait(), 5)
            with pytest.raises(FileNotFoundError):
                await registration
            async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
                assert not (await uow.execute(sa.select(Artifact.id))).first()
        else:
            descriptor_release.set()
            await asyncio.wait_for(registration_inserted.wait(), 5)

            async def delete_version():
                async with case.b.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
                    await uow.execute(sa.delete(SkillVersion).where(SkillVersion.revision == revision))

            deletion = asyncio.create_task(delete_version())
            await asyncio.wait_for(competing_statement.wait(), 5)
            registration_release.set()
            item = await registration
            with pytest.raises(sa.exc.IntegrityError):
                await deletion
            assert (await case.b.app.artifact_service.read(case.context, item['id']))['content'] == _GUIDE.encode()
    finally:
        descriptor_release.set()
        registration_release.set()
        for task in (registration, deletion):
            if task is not None and not task.done():
                task.cancel()
        await asyncio.gather(*(task for task in (registration, deletion) if task is not None), return_exceptions=True)
        sa.event.remove(engine.sync_engine, 'before_cursor_execute', observe_competitor)


async def test_run_skill_creation_budget_denies_before_bytes_or_registration(artifact_replicas, monkeypatch):
    case = artifact_replicas
    revision = await _install(case)
    context = await _start_run(case)
    async with case.a.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
        await uow.execute(
            sa.update(AgentRun)
            .where(AgentRun.run_id == context.trigger_principal.run_id)
            .values(
                metadata_json=json.dumps({'activated_skills': {_NAME: revision}}),
            )
        )

    async def forbidden_read(*args, **kwargs):
        pytest.fail('An over-budget registration must not fetch any package bytes')

    monkeypatch.setattr(case.a.app.storage_mgr.content_store, '_read', forbidden_read)
    with pytest.raises(ValueError, match='requested read limit'):
        await case.a.app.artifact_service.create_run_skill_resource(
            context,
            _NAME,
            revision,
            'references/guide.md',
            max_bytes=len(_GUIDE.encode()) - 1,
        )
    async with case.a.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
        assert not (await uow.execute(sa.select(Artifact.id))).first()
