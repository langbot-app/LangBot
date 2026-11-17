"""Run output publication preserves origin and permits only the named manager."""
# ruff: noqa: F811

import asyncio
from dataclasses import replace
import datetime as dt
import hashlib
import uuid

import pytest
import sqlalchemy as sa

from langbot.pkg.api.context import PrincipalContext, PrincipalType
from langbot.pkg.entity.persistence.agent_run import AgentRun
from langbot.pkg.entity.persistence.artifact import Artifact, ArtifactReference
from langbot.pkg.entity.persistence.content import ContentObject
from langbot.pkg.entity.persistence.workspace import Workspace, WorkspaceExecutionState
from langbot.pkg.storage.artifacts import ArtifactError
from langbot.pkg.utils.execution_lease import host_execution_lease
from tests.integration.skill.test_persistent_skill_replicas import _close_replica
from tests.integration.storage.test_artifact_run_inputs import _run_context
from tests.integration.storage.test_artifacts import (
    _expire,
    artifact_replicas,  # noqa: F401 -- pytest fixture
    persistence_case,  # noqa: F401 -- fixture dependency
    replicas,  # noqa: F401 -- fixture dependency
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
_BODY = b'Generated output: exact bytes \x00\xff\n'


async def _start_run(case, run_id=None):
    context = _run_context(case, run_id)
    async with case.a.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
        await uow.execute(
            sa.insert(AgentRun).values(
                run_id=context.trigger_principal.run_id,
                workspace_id=context.workspace_uuid,
                runner_id='plugin:test/runner/default',
                status='running',
                **host_execution_lease(),
            )
        )
    return context


async def _end_run(case, context):
    async with case.a.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
        await uow.execute(
            sa.update(AgentRun)
            .where(
                AgentRun.workspace_id == context.workspace_uuid,
                AgentRun.run_id == context.trigger_principal.run_id,
            )
            .values(status='completed')
        )


async def _create(case, context, name='result.bin'):
    return await case.a.app.artifact_service.create_run_output(context, name, _BODY, 'application/octet-stream')


async def _output_rows(case, context):
    async with case.a.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
        return (
            (
                await uow.execute(
                    sa.select(Artifact.__table__).where(
                        Artifact.owner_type == 'run_output',
                        Artifact.owner_id == context.trigger_principal.run_id,
                    )
                )
            )
            .mappings()
            .all()
        )


async def test_run_output_isolated_from_input_accounts_and_other_runs(artifact_replicas):
    case = artifact_replicas
    context = await _start_run(case)
    output = await _create(case, context)
    assert output['source'] == 'tool_output' and output['lifecycle'] == 'temporary'
    assert output['digest'] == hashlib.sha256(_BODY).hexdigest() and output['size'] == len(_BODY)
    read = await case.b.app.artifact_service.read_run_output(context, output['id'])
    assert read['content'] == _BODY and read['metadata'] == output
    with pytest.raises(FileNotFoundError):
        await case.b.app.artifact_service.read_run_output(await _start_run(case), output['id'])
    with pytest.raises(FileNotFoundError):
        await case.b.app.artifact_service.read_run_input(context, output['id'])
    input_asset = await case.a.app.artifact_service.create_run_input(
        context, 'input.bin', _BODY, 'application/octet-stream'
    )
    with pytest.raises(FileNotFoundError):
        await case.b.app.artifact_service.read_run_output(context, input_asset['id'])
    with pytest.raises(ArtifactError) as failure:
        await case.b.app.artifact_service.read_run_output(context, output['id'], max_bytes=1)
    assert failure.value.error_code == 'artifact_too_large'
    for method, suffix in (('get', ''), ('get', '/content'), ('post', '/retain'), ('delete', '')):
        assert (
            await getattr(case.b.client, method)(
                '/api/v1/artifacts/' + output['id'] + suffix,
                headers=case.headers,
            )
        ).status_code == 404
    other_workspace = str(uuid.uuid4())
    async with case.a.engine.begin() as conn:
        await conn.execute(
            sa.insert(Workspace).values(
                uuid=other_workspace,
                instance_uuid=context.instance_uuid,
                name='Other',
                slug='output-other',
                source='cloud_projection',
            )
        )
        await conn.execute(
            sa.insert(WorkspaceExecutionState).values(
                workspace_uuid=other_workspace,
                instance_uuid=context.instance_uuid,
                source='cloud',
            )
        )
    with pytest.raises(ArtifactError) as failure:
        await case.b.app.artifact_service.read_run_output(
            replace(context, workspace_uuid=other_workspace), output['id']
        )
    assert failure.value.error_code == 'artifact_run_not_active'


async def test_published_outputs_are_manageable_after_completion_and_restart(artifact_replicas):
    case = artifact_replicas
    context = await _start_run(case)
    kept, transient = await _create(case, context, 'keep.bin'), await _create(case, context, 'temporary.bin')
    committed = await case.a.app.artifact_service.commit_run_outputs(
        context, [kept['id']], manager_context=case.context
    )
    assert committed[0]['lifecycle'] == 'persistent' and committed[0]['expires_at'] is None
    assert (
        await case.b.app.artifact_service.commit_run_outputs(context, [kept['id']], manager_context=case.context)
        == committed
    )
    rows = await _output_rows(case, context)
    retained = next(row for row in rows if row['id'] == kept['id'])
    assert (retained['owner_type'], retained['owner_id']) == ('run_output', context.trigger_principal.run_id)
    assert (retained['manager_type'], retained['manager_id']) == ('account', case.context.account_uuid)
    async with case.a.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
        pins = (
            (
                await uow.execute(
                    sa.select(ArtifactReference.__table__).where(
                        ArtifactReference.artifact_id == kept['id'],
                    )
                )
            )
            .mappings()
            .all()
        )
        backend = (
            await uow.execute(
                sa.select(ContentObject.backend).where(
                    ContentObject.ref == retained['content_ref'],
                )
            )
        ).scalar_one()
    assert len(pins) == 1 and pins[0]['holder_type'] == 'principal'
    assert pins[0]['holder_id'] == 'account:' + case.context.account_uuid
    assert backend == ('archive' if case.minio else 'database')
    assert (await case.a.client.delete('/api/v1/artifacts/' + kept['id'], headers=case.headers)).status_code == 409
    await _end_run(case, context)
    assert await case.b.app.artifact_service.expire_run_outputs(context) == 1
    assert await case.a.app.artifact_service.expire_run_outputs(context) == 0
    system = replace(case.a.context, trigger_principal=PrincipalContext(PrincipalType.SYSTEM))
    assert await case.b.app.artifact_service.collect_expired(system) == 1
    with pytest.raises(ArtifactError) as failure:
        await case.a.app.artifact_service.read_run_output(context, kept['id'])
    assert failure.value.error_code == 'artifact_run_not_active'
    await _close_replica(case.a)
    restarted = await case.create('run-output-restarted-core')
    assert (await restarted.app.artifact_service.read(case.context, kept['id']))['content'] == _BODY
    assert (await restarted.client.get('/api/v1/artifacts/' + transient['id'], headers=case.headers)).status_code == 404
    released = await restarted.app.artifact_service.release(case.context, kept['id'])
    assert released['expires_at'] is not None
    assert await restarted.app.artifact_service.release(case.context, kept['id']) == released
    await restarted.app.artifact_service.retain(case.context, kept['id'])
    await restarted.app.artifact_service.release(case.context, kept['id'])
    await restarted.app.artifact_service.delete(case.context, kept['id'])
    assert await restarted.app.artifact_service.collect_expired(system) == 1


async def test_output_commit_authorizes_entire_batch_before_pinning(artifact_replicas):
    case = artifact_replicas
    context = await _start_run(case)
    mine, foreign = await _create(case, context), await _create(case, await _start_run(case), 'foreign.bin')
    input_asset = await case.a.app.artifact_service.create_run_input(context, 'input.txt', b'input', 'text/plain')
    for inaccessible in (foreign['id'], input_asset['id'], 'art_' + '0' * 32):
        with pytest.raises(FileNotFoundError):
            await case.b.app.artifact_service.commit_run_outputs(
                context, [mine['id'], inaccessible], manager_context=case.context
            )
        async with case.a.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            assert (await uow.execute(sa.select(ArtifactReference.artifact_id))).first() is None
        assert (await case.a.app.artifact_service.read_run_output(context, mine['id']))['metadata'][
            'expires_at'
        ] is not None
    for invalid in ([], [foreign['id'], foreign['id']], [None], ['art_' + '1' * 32] * 101):
        with pytest.raises(ValueError):
            await case.a.app.artifact_service.commit_run_outputs(context, invalid, manager_context=case.context)


async def test_output_commit_and_finish_serialize_the_batch(artifact_replicas):
    case = artifact_replicas
    context = await _start_run(case)
    ids = [(await _create(case, context, name))['id'] for name in ('a.bin', 'b.bin')]

    async def finish():
        await _end_run(case, context)
        return await case.b.app.artifact_service.expire_run_outputs(context)

    committed, expired = await asyncio.gather(
        case.a.app.artifact_service.commit_run_outputs(context, list(reversed(ids)), manager_context=case.context),
        finish(),
        return_exceptions=True,
    )
    assert not isinstance(expired, BaseException)
    rows = await _output_rows(case, context)
    if isinstance(committed, ArtifactError):
        assert committed.error_code in {'artifact_expired', 'artifact_run_not_active'} and expired == 2
        assert all(row['manager_type'] is None for row in rows)
    else:
        assert isinstance(committed, list) and expired == 0
        assert [asset['id'] for asset in committed] == list(reversed(ids))
        assert all(row['expires_at'] is None for row in rows)


async def test_output_batch_cancellation_rolls_back_storage(artifact_replicas):
    case = artifact_replicas
    context = await _start_run(case)
    created, locators = [], []
    with pytest.raises(asyncio.CancelledError):
        async with case.a.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            for name in ('first.bin', 'second.bin'):
                metadata = await _create(case, context, name)
                created.append(metadata['id'])
                content_ref = (
                    await uow.execute(sa.select(Artifact.content_ref).where(Artifact.id == metadata['id']))
                ).scalar_one()
                locator = (
                    await uow.execute(sa.select(ContentObject.locator).where(ContentObject.ref == content_ref))
                ).scalar_one()
                if locator is not None:
                    locators.append(locator)
            raise asyncio.CancelledError()
    async with case.a.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
        assert (await uow.execute(sa.select(ContentObject.ref).where(ContentObject.owner.in_(created)))).first() is None
    for artifact_id in created:
        with pytest.raises(FileNotFoundError):
            await case.b.app.artifact_service.read_run_output(context, artifact_id)
    store = case.a.app.storage_mgr.content_store
    await asyncio.sleep(0)
    if store._cleanup_tasks:
        await asyncio.gather(*store._cleanup_tasks)
    if case.minio:
        provider, _ = await store._s3('archive')
        assert locators and not any([await provider.exists(locator['key']) for locator in locators])


async def test_active_run_outlives_ttl_but_crashed_run_is_collectible(artifact_replicas):
    case = artifact_replicas
    context = await _start_run(case)
    output = await _create(case, context)
    await _expire(case.a, context, output['id'])
    assert (await case.b.app.artifact_service.read_run_output(context, output['id']))['content'] == _BODY
    system = replace(case.a.context, trigger_principal=PrincipalContext(PrincipalType.SYSTEM))
    assert await case.b.app.artifact_service.collect_expired(system) == 0
    async with case.a.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
        await uow.execute(
            sa.update(AgentRun)
            .where(AgentRun.run_id == context.trigger_principal.run_id)
            .values(
                execution_lease_expires_at=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
                - dt.timedelta(seconds=1),
            )
        )
    with pytest.raises(ArtifactError) as failure:
        await case.a.app.artifact_service.read_run_output(context, output['id'])
    assert failure.value.error_code == 'artifact_run_not_active'
    assert await case.b.app.artifact_service.collect_expired(system) == 1


async def test_output_methods_require_trusted_run_context_and_real_lease(artifact_replicas):
    case = artifact_replicas
    for context in (
        case.context,
        case.a.context,
        replace(case.a.context, trigger_principal=PrincipalContext(PrincipalType.SYSTEM)),
        replace(case.a.context, trigger_principal=PrincipalContext(PrincipalType.PROCESSOR)),
    ):
        for method, arguments in (
            ('create_run_output', ('output.txt', b'output', 'text/plain')),
            ('read_run_output', ('art_' + '0' * 32,)),
            ('expire_run_outputs', ()),
        ):
            with pytest.raises(PermissionError):
                await getattr(case.a.app.artifact_service, method)(context, *arguments)
    unknown = _run_context(case)
    for method, arguments, options in (
        ('create_run_output', ('output.txt', b'output', 'text/plain'), {}),
        ('read_run_output', ('art_' + '0' * 32,), {}),
        ('commit_run_outputs', (['art_' + '0' * 32],), {'manager_context': case.context}),
    ):
        with pytest.raises(ArtifactError) as failure:
            await getattr(case.a.app.artifact_service, method)(unknown, *arguments, **options)
        assert failure.value.error_code == 'artifact_run_not_active'


async def test_remote_claim_lease_protects_outputs_until_it_expires(artifact_replicas):
    case = artifact_replicas
    context = await _start_run(case)
    async with case.a.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
        await uow.execute(
            sa.update(AgentRun)
            .where(AgentRun.run_id == context.trigger_principal.run_id)
            .values(
                status='claimed',
                execution_owner_id=None,
                execution_lease_expires_at=None,
                claimed_by_runtime_id='remote-runtime',
                claim_token='test-claim',
                claim_lease_expires_at=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
                + dt.timedelta(seconds=120),
            )
        )
    output = await _create(case, context)
    await _expire(case.a, context, output['id'])
    assert (await case.b.app.artifact_service.read_run_output(context, output['id']))['content'] == _BODY
    system = replace(case.a.context, trigger_principal=PrincipalContext(PrincipalType.SYSTEM))
    assert await case.b.app.artifact_service.collect_expired(system) == 0
    async with case.a.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
        await uow.execute(
            sa.update(AgentRun)
            .where(AgentRun.run_id == context.trigger_principal.run_id)
            .values(
                claim_lease_expires_at=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - dt.timedelta(seconds=1),
            )
        )
    with pytest.raises(ArtifactError) as failure:
        await case.a.app.artifact_service.read_run_output(context, output['id'])
    assert failure.value.error_code == 'artifact_run_not_active'
    assert await case.b.app.artifact_service.collect_expired(system) == 1
