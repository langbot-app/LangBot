"""Run output persistence preserves the original run's access boundary."""
# ruff: noqa: F811

import asyncio
from dataclasses import replace
import hashlib
import uuid

import pytest
import sqlalchemy as sa

from langbot.pkg.api.context import PrincipalContext, PrincipalType
from langbot.pkg.entity.persistence.artifact import Artifact, ArtifactReference
from langbot.pkg.entity.persistence.content import ContentObject
from langbot.pkg.entity.persistence.workspace import Workspace, WorkspaceExecutionState
from langbot.pkg.storage.artifacts import ArtifactError
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
    context = _run_context(case)
    output = await _create(case, context)
    assert output['source'] == 'tool_output' and output['lifecycle'] == 'temporary'
    assert output['digest'] == hashlib.sha256(_BODY).hexdigest() and output['size'] == len(_BODY)
    assert 'content_ref' not in output
    read = await case.b.app.artifact_service.read_run_output(context, output['id'])
    assert read['content'] == _BODY and read['metadata'] == output
    with pytest.raises(FileNotFoundError):
        await case.b.app.artifact_service.read_run_output(_run_context(case), output['id'])
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
        response = await getattr(case.b.client, method)(
            '/api/v1/artifacts/' + output['id'] + suffix,
            headers=case.headers,
        )
        assert response.status_code == 404

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
    with pytest.raises(FileNotFoundError):
        await case.b.app.artifact_service.read_run_output(
            replace(context, workspace_uuid=other_workspace),
            output['id'],
        )


async def test_committed_outputs_survive_run_expiry_gc_and_core_replacement(artifact_replicas):
    case = artifact_replicas
    context = _run_context(case)
    kept = await _create(case, context, 'keep.bin')
    transient = await _create(case, context, 'temporary.bin')
    committed = await case.a.app.artifact_service.commit_run_outputs(context, [kept['id']])
    assert committed[0]['id'] == kept['id'] and committed[0]['lifecycle'] == 'persistent'
    assert committed[0]['expires_at'] is None and committed[0]['source'] == 'tool_output'
    assert await case.b.app.artifact_service.commit_run_outputs(context, [kept['id']]) == committed
    rows = await _output_rows(case, context)
    assert {(row['owner_type'], row['owner_id']) for row in rows} == {('run_output', context.trigger_principal.run_id)}
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
                    ContentObject.ref == next(row['content_ref'] for row in rows if row['id'] == kept['id']),
                )
            )
        ).scalar_one()
    assert len(pins) == 1 and pins[0]['holder_type'] == 'run_output_commit'
    assert pins[0]['holder_id'] == context.trigger_principal.run_id
    assert backend == ('archive' if case.minio else 'database')
    assert await case.b.app.artifact_service.expire_run_outputs(context) == 1
    assert await case.a.app.artifact_service.expire_run_outputs(context) == 0
    with pytest.raises(ArtifactError) as failure:
        await case.a.app.artifact_service.read_run_output(context, transient['id'])
    assert failure.value.error_code == 'artifact_expired'
    system = replace(case.a.context, trigger_principal=PrincipalContext(PrincipalType.SYSTEM))
    assert await case.b.app.artifact_service.collect_expired(system) == 1
    with pytest.raises(FileNotFoundError):
        await case.a.app.artifact_service.read_run_output(context, transient['id'])
    await _close_replica(case.a)
    restarted = await case.create('run-output-restarted-core')
    assert (await restarted.app.artifact_service.read_run_output(context, kept['id']))['content'] == _BODY
    assert (await restarted.client.get('/api/v1/artifacts/' + kept['id'], headers=case.headers)).status_code == 404


async def test_output_commit_authorizes_entire_batch_before_pinning(artifact_replicas):
    case = artifact_replicas
    context = _run_context(case)
    mine = await _create(case, context)
    foreign = await _create(case, _run_context(case), 'foreign.bin')
    input_asset = await case.a.app.artifact_service.create_run_input(context, 'input.txt', b'input', 'text/plain')
    for inaccessible in (foreign['id'], input_asset['id'], 'art_' + '0' * 32):
        with pytest.raises(FileNotFoundError):
            await case.b.app.artifact_service.commit_run_outputs(context, [mine['id'], inaccessible])
        async with case.a.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            assert (await uow.execute(sa.select(ArtifactReference.artifact_id))).first() is None
        assert (await case.a.app.artifact_service.read_run_output(context, mine['id']))['metadata'][
            'expires_at'
        ] is not None
    await _expire(case.a, context, mine['id'])
    with pytest.raises(ArtifactError) as failure:
        await case.b.app.artifact_service.commit_run_outputs(context, [mine['id']])
    assert failure.value.error_code == 'artifact_expired'
    for invalid in ([], [foreign['id'], foreign['id']], [None], ['art_' + '1' * 32] * 101):
        with pytest.raises(ValueError):
            await case.a.app.artifact_service.commit_run_outputs(context, invalid)


async def test_output_commit_and_finish_serialize_the_batch(artifact_replicas):
    case = artifact_replicas
    context = _run_context(case)
    assets = [await _create(case, context, name) for name in ('a.bin', 'b.bin')]
    ids = [asset['id'] for asset in assets]
    committed, expired = await asyncio.gather(
        case.a.app.artifact_service.commit_run_outputs(context, list(reversed(ids))),
        case.b.app.artifact_service.expire_run_outputs(context),
        return_exceptions=True,
    )
    assert not isinstance(expired, BaseException)
    rows = await _output_rows(case, context)
    if isinstance(committed, ArtifactError):
        assert committed.error_code == 'artifact_expired' and expired == 2
        assert all(row['expires_at'] is not None for row in rows)
        async with case.a.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            assert (await uow.execute(sa.select(ArtifactReference.artifact_id))).first() is None
    else:
        assert isinstance(committed, list) and expired == 0
        assert [asset['id'] for asset in committed] == list(reversed(ids))
        assert all(row['expires_at'] is None for row in rows)


async def test_output_batch_cancellation_rolls_back_storage(artifact_replicas):
    case = artifact_replicas
    context = _run_context(case)
    created = []
    locators = []
    with pytest.raises(asyncio.CancelledError):
        async with case.a.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            for name in ('first.bin', 'second.bin'):
                metadata = await _create(case, context, name)
                created.append(metadata['id'])
                content_ref = (
                    await uow.execute(
                        sa.select(Artifact.content_ref).where(
                            Artifact.id == metadata['id'],
                        )
                    )
                ).scalar_one()
                locator = (
                    await uow.execute(
                        sa.select(ContentObject.locator).where(
                            ContentObject.ref == content_ref,
                        )
                    )
                ).scalar_one()
                if locator is not None:
                    locators.append(locator)
            raise asyncio.CancelledError()
    for artifact_id in created:
        with pytest.raises(FileNotFoundError):
            await case.b.app.artifact_service.read_run_output(context, artifact_id)
    async with case.a.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
        assert (await uow.execute(sa.select(ContentObject.ref).where(ContentObject.owner.in_(created)))).first() is None
    store = case.a.app.storage_mgr.content_store
    await asyncio.sleep(0)
    if store._cleanup_tasks:
        await asyncio.gather(*store._cleanup_tasks)
    if case.minio:
        provider, _ = await store._s3('archive')
        assert locators and not any([await provider.exists(locator['key']) for locator in locators])


async def test_crashed_run_outputs_expire_without_finalizer(artifact_replicas):
    case = artifact_replicas
    context = _run_context(case)
    output = await _create(case, context)
    await _expire(case.a, context, output['id'])
    system = replace(case.a.context, trigger_principal=PrincipalContext(PrincipalType.SYSTEM))
    assert await case.b.app.artifact_service.collect_expired(system) == 1
    with pytest.raises(FileNotFoundError):
        await case.a.app.artifact_service.read_run_output(context, output['id'])


async def test_output_methods_require_trusted_run_context(artifact_replicas):
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
            ('commit_run_outputs', (['art_' + '0' * 32],)),
            ('expire_run_outputs', ()),
        ):
            with pytest.raises(PermissionError):
                await getattr(case.a.app.artifact_service, method)(context, *arguments)
