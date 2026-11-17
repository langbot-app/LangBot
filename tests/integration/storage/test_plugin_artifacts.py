"""Installation-private Artifact ownership uses live explicit Workspace grants."""
# ruff: noqa: F811

from dataclasses import replace
import uuid

import pytest
import sqlalchemy as sa

from langbot.pkg.api.application import ApplicationAPIException
from langbot.pkg.api.authz import PermissionDeniedError
from langbot.pkg.api.context import PrincipalContext, PrincipalType
from langbot.pkg.entity.persistence.artifact import Artifact, ArtifactReference
from langbot.pkg.entity.persistence.plugin import PluginSetting
from langbot.pkg.storage.artifacts import ArtifactError, MAX_PLUGIN_ARTIFACT_BYTES
from tests.integration.storage.test_artifact_run_outputs import _start_run, _end_run
from tests.integration.storage.test_artifacts import (
    artifact_replicas,  # noqa: F401
    persistence_case,  # noqa: F401
    replicas,  # noqa: F401
    _expire,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
OPERATIONS = frozenset(
    'artifact.' + name
    for name in (
        'create',
        'get',
        'read',
        'read_content',
        'retain',
        'release',
        'delete',
    )
)


async def plugin_context(case, name='one', operations=OPERATIONS):
    installation = str(uuid.uuid4())
    grants = {'workspace_operations': sorted(operations), 'capabilities': []}
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        await uow.execute(
            sa.insert(PluginSetting).values(
                workspace_uuid=case.context.workspace_uuid,
                plugin_author='artifact-test',
                plugin_name=name,
                installation_uuid=installation,
                permission_declaration=grants,
                permission_snapshot=grants,
                permission_grants=grants,
            )
        )
    return replace(
        case.context,
        auth_type='plugin',
        principal=PrincipalContext(PrincipalType.PLUGIN, installation_uuid=installation),
        allowed_operation_ids=operations,
    )


async def test_plugin_artifact_owner_and_excluded_conversions(artifact_replicas):
    case = artifact_replicas
    first, second = await plugin_context(case), await plugin_context(case, 'two')
    item = await case.a.app.application_api.execute(
        'artifact.create',
        first,
        {
            'filename': 'plugin.txt',
            'content': b'plugin private',
            'mime_type': 'text/plain',
        },
    )
    read = await case.b.app.artifact_service.read(first, item['id'])
    assert read['content'] == b'plugin private'
    for context in (second, case.context):
        for action in ('get', 'read', 'read_content', 'retain', 'release', 'delete'):
            with pytest.raises(ApplicationAPIException) as failure:
                await case.b.app.application_api.execute('artifact.' + action, context, {'artifact_id': item['id']})
            assert failure.value.error.status_code == 404
    own = await case.a.app.artifact_service.create(case.context, 'account.txt', b'account')
    with pytest.raises(ApplicationAPIException) as failure:
        await case.a.app.application_api.execute('artifact.retain', first, {'artifact_id': own['id']})
    assert failure.value.error.status_code == 404
    with pytest.raises(ApplicationAPIException):
        await case.a.app.application_api.execute(
            'artifact.skill_resource.create',
            first,
            {
                'skill_name': 'any',
                'revision': 'any',
                'path': 'a',
            },
        )
    with pytest.raises(ApplicationAPIException):
        await case.a.app.application_api.execute(
            'artifact.publication.set',
            first,
            {
                'producer_type': 'agent',
                'producer_id': 'any',
                'enabled': True,
            },
        )


async def test_plugin_artifact_revocation_disable_and_reinstall(artifact_replicas):
    case = artifact_replicas
    context = await plugin_context(case)
    item = await case.a.app.artifact_service.create(context, 'p.txt', b'persist')
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        await uow.execute(
            sa.update(PluginSetting).values(permission_grants={'workspace_operations': [], 'capabilities': []})
        )
    with pytest.raises(ApplicationAPIException) as failure:
        await case.b.app.application_api.execute('artifact.get', context, {'artifact_id': item['id']})
    assert failure.value.error.status_code == 403
    grants = {'workspace_operations': sorted(OPERATIONS), 'capabilities': []}
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        await uow.execute(sa.update(PluginSetting).values(permission_grants=grants, enabled=False))
    with pytest.raises(ApplicationAPIException) as failure:
        await case.b.app.application_api.execute('artifact.read', context, {'artifact_id': item['id']})
    assert failure.value.error.status_code == 403
    new_id = str(uuid.uuid4())
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        await uow.execute(sa.update(PluginSetting).values(enabled=True, installation_uuid=new_id))
    for current in (context, replace(context, principal=replace(context.principal, installation_uuid=new_id))):
        with pytest.raises(ApplicationAPIException) as failure:
            await case.b.app.application_api.execute('artifact.get', current, {'artifact_id': item['id']})
        assert failure.value.error.status_code == 404


async def test_plugin_artifact_caps_and_exact_operation_grant(artifact_replicas, monkeypatch):
    case = artifact_replicas
    context = await plugin_context(case)
    service = case.a.app.artifact_service
    with pytest.raises(ArtifactError) as failure:
        await service.create(context, 'large.bin', b'x' * (MAX_PLUGIN_ARTIFACT_BYTES + 1))
    assert failure.value.status_code == 413
    item = await service.create(context, 'small.txt', b'hello', 'text/plain')
    limited = replace(context, allowed_operation_ids=frozenset({'artifact.read_content'}))
    assert await service.read_content(limited, item['id'])
    with pytest.raises(PermissionDeniedError):
        await service.read(limited, item['id'])
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        await uow.execute(
            sa.update(Artifact).where(Artifact.id == item['id']).values(size=MAX_PLUGIN_ARTIFACT_BYTES + 1)
        )

    async def forbidden(*args, **kwargs):
        pytest.fail('Oversized plugin artifact must be denied before reading bytes')

    monkeypatch.setattr(case.a.app.storage_mgr.content_store, '_read', forbidden)
    with pytest.raises(ArtifactError) as failure:
        await service.read(context, item['id'])
    assert failure.value.status_code == 413


async def test_plugin_artifact_pin_release_gc_and_run_lease(artifact_replicas):
    case = artifact_replicas
    context = await plugin_context(case)
    service = case.a.app.artifact_service
    item = await service.create(context, 'plugin.bin', b'persist')
    await service.retain(context, item['id'])
    with pytest.raises(ArtifactError, match='in use'):
        await service.delete(context, item['id'])
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        pin = (await uow.execute(sa.select(ArtifactReference.__table__))).mappings().one()
        assert pin['holder_id'] == 'plugin:' + context.principal.installation_uuid
    run = await _start_run(case)
    run_context = replace(context, principal=replace(context.principal, run_id=run.trigger_principal.run_id))
    assert await service.get(run_context, item['id'])
    await _end_run(case, run)
    with pytest.raises(ArtifactError):
        await service.get(run_context, item['id'])
    await service.release(context, item['id'])
    await _expire(case.a, case.context, item['id'])
    system = replace(case.a.context, trigger_principal=PrincipalContext(PrincipalType.SYSTEM))
    assert await service.collect_expired(system) == 1


async def test_uninstall_releases_only_orphan_plugin_pin_with_grace(artifact_replicas):
    case = artifact_replicas
    context = await plugin_context(case)
    service = case.a.app.artifact_service
    item = await service.create(context, 'retained.txt', b'keep until uninstall grace')
    await service.retain(context, item['id'])
    system = replace(case.a.context, trigger_principal=PrincipalContext(PrincipalType.SYSTEM))
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        await uow.execute(sa.update(PluginSetting).values(enabled=False))
    assert await service.collect_expired(system) == 0
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        assert (await uow.execute(sa.select(ArtifactReference.artifact_id))).first()
        assert (await uow.execute(sa.select(Artifact.expires_at))).scalar_one() is None
        await uow.execute(sa.delete(PluginSetting))
    assert await service.collect_expired(system) == 0
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        assert not (await uow.execute(sa.select(ArtifactReference.artifact_id))).first()
        assert (await uow.execute(sa.select(Artifact.expires_at))).scalar_one() is not None
    await _expire(case.a, case.context, item['id'])
    assert await service.collect_expired(system) == 1


@pytest.mark.parametrize('extra', [0, 1])
async def test_plugin_rendered_content_reserves_rpc_envelope_budget(artifact_replicas, monkeypatch, extra):
    import json
    from langbot.pkg.storage import artifact_reader
    from langbot.pkg.storage.artifacts import MAX_PLUGIN_CONTENT_RESPONSE_BYTES

    case = artifact_replicas
    context = await plugin_context(case)
    service = case.a.app.artifact_service
    item = await service.create(context, 'small.txt', b'small source', 'text/plain')
    overhead = len(json.dumps([{'type': 'text', 'text': ''}]).encode('utf-8'))
    expanded = [{'type': 'text', 'text': 'x' * (MAX_PLUGIN_CONTENT_RESPONSE_BYTES - overhead + extra)}]

    async def expanded_renderer(*args, **kwargs):
        return expanded

    monkeypatch.setattr(artifact_reader, 'read_artifact_content', expanded_renderer)
    if extra:
        with pytest.raises(ArtifactError) as failure:
            await service.read_content(context, item['id'])
        assert failure.value.error_code == 'artifact_too_large'
    else:
        result = await service.read_content(context, item['id'])
        assert len(json.dumps(result).encode('utf-8')) == MAX_PLUGIN_CONTENT_RESPONSE_BYTES
