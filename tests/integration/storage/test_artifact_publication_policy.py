"""Publication is approved by a named caller and revalidated when a run commits."""
# ruff: noqa: F811

from dataclasses import replace
import datetime as dt
import json
import uuid

import pytest
import sqlalchemy as sa

from langbot.pkg.api.authz import PermissionDeniedError
from langbot.pkg.api.context import PrincipalContext, PrincipalType
from langbot.pkg.api.mcp.context import bind_request_context, reset_request_context
from langbot.pkg.api.mcp.server import LangBotMCPServer
from langbot.pkg.entity.persistence.agent import Agent
from langbot.pkg.entity.persistence.apikey import ApiKey
from langbot.pkg.entity.persistence.artifact_publication import ArtifactPublication
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.entity.persistence.workspace import WorkspaceMembership
from langbot.pkg.storage.artifacts import ArtifactError
from langbot.pkg.workspace.errors import WorkspaceNotFoundError
from tests.integration.storage.test_artifact_run_inputs import _run_context
from tests.integration.storage.test_artifacts import (
    _data,
    artifact_replicas,  # noqa: F401 -- pytest fixture
    persistence_case,  # noqa: F401 -- fixture dependency
    replicas,  # noqa: F401 -- fixture dependency
)
from tests.utils.artifact_store import seed_run


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _producer(case):
    producer_id = str(uuid.uuid4())
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        await uow.execute(
            sa.insert(Agent).values(
                uuid=producer_id,
                workspace_uuid=case.context.workspace_uuid,
                kind='agent',
                name='Publication producer',
                config={'untrusted_publication_owner': 'ignored'},
            )
        )
    return producer_id


def _url(producer_id):
    return f'/api/v1/artifacts/producers/agent/{producer_id}/publication'


async def test_http_policy_is_explicit_self_owned_and_revoke_invalidates_frozen_run(artifact_replicas):
    case = artifact_replicas
    producer_id = await _producer(case)
    url = _url(producer_id)
    policy = await _data(await case.a.client.get(url, headers=case.headers))
    assert policy['enabled'] is False and policy['revision'] is None
    forged = await case.a.client.put(url, headers=case.headers, json={'enabled': True, 'manager_id': str(uuid.uuid4())})
    assert forged.status_code == 400
    enabled = await _data(await case.a.client.put(url, headers=case.headers, json={'enabled': True}))
    assert enabled['manager_type'] == 'account' and enabled['manager_id'] == case.context.account_uuid
    snapshot = await case.b.app.artifact_publication_service.snapshot_for_run(case.b.context, 'agent', producer_id)
    assert snapshot == enabled
    manager = await case.b.app.artifact_publication_service.manager_for_commit(case.b.context, snapshot)
    assert manager.account_uuid == case.context.account_uuid
    assert 'resource.manage' in manager.workspace.permissions
    disabled = await _data(await case.a.client.delete(url, headers=case.headers))
    assert disabled['enabled'] is False and disabled['revision'] != enabled['revision']
    with pytest.raises(PermissionDeniedError):
        await case.a.app.artifact_publication_service.manager_for_commit(case.a.context, snapshot)
    assert await case.a.app.artifact_publication_service.snapshot_for_run(case.a.context, 'agent', producer_id) is None
    next_producer = await _producer(case)
    assert (await _data(await case.a.client.get(_url(next_producer), headers=case.headers)))['enabled'] is False


async def test_other_workspace_admin_cannot_take_over_an_existing_policy(artifact_replicas):
    case = artifact_replicas
    producer_id = await _producer(case)
    service = case.a.app.artifact_publication_service
    await service.set(case.context, 'agent', producer_id, True)
    other_uuid = str(uuid.uuid4())
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        await uow.execute(
            sa.insert(User).values(
                uuid=other_uuid,
                user='other-policy-admin',
                normalized_email='policy-admin@example.test',
                password='unused',
            )
        )
        await uow.execute(
            sa.insert(WorkspaceMembership).values(
                workspace_uuid=case.context.workspace_uuid,
                account_uuid=other_uuid,
                role='admin',
            )
        )
    other = replace(case.context, principal=PrincipalContext(PrincipalType.ACCOUNT, account_uuid=other_uuid))
    for method in ('get', 'disable'):
        with pytest.raises(FileNotFoundError):
            await getattr(service, method)(other, 'agent', producer_id)
    with pytest.raises(FileNotFoundError):
        await service.set(other, 'agent', producer_id, True)
    assert (await service.get(case.context, 'agent', producer_id))['manager_id'] == case.context.account_uuid


@pytest.mark.parametrize('revocation', ['account', 'membership', 'role'])
async def test_commit_rechecks_account_membership_and_current_permissions(artifact_replicas, revocation):
    case = artifact_replicas
    producer_id = await _producer(case)
    policy = await case.a.app.artifact_publication_service.set(case.context, 'agent', producer_id, True)
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        if revocation == 'account':
            await uow.execute(sa.update(User).where(User.uuid == case.context.account_uuid).values(status='disabled'))
        else:
            await uow.execute(
                sa.update(WorkspaceMembership)
                .where(
                    WorkspaceMembership.workspace_uuid == case.context.workspace_uuid,
                    WorkspaceMembership.account_uuid == case.context.account_uuid,
                )
                .values(**({'status': 'disabled'} if revocation == 'membership' else {'role': 'viewer'}))
            )
    with pytest.raises((ArtifactError, PermissionDeniedError, WorkspaceNotFoundError)):
        await case.b.app.artifact_publication_service.manager_for_commit(case.b.context, policy)


@pytest.mark.parametrize('revocation', ['status', 'expiry', 'scopes'])
async def test_named_key_approval_is_revalidated_without_a_secret(artifact_replicas, revocation):
    case = artifact_replicas
    producer_id = await _producer(case)
    key_uuid = str(uuid.uuid4())
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        await uow.execute(
            sa.insert(ApiKey).values(
                uuid=key_uuid,
                workspace_uuid=case.context.workspace_uuid,
                name='publication',
                key_hash=uuid.uuid4().hex,
                scopes=['resource.view', 'resource.manage'],
            )
        )
    key = replace(case.context, principal=PrincipalContext(PrincipalType.API_KEY, api_key_uuid=key_uuid))
    service = case.a.app.artifact_publication_service
    policy = await service.set(key, 'agent', producer_id, True)
    assert policy['manager_type'] == 'api_key' and policy['manager_id'] == key_uuid
    assert (await service.manager_for_commit(case.a.context, policy)).principal.api_key_uuid == key_uuid
    changes = (
        {'status': 'revoked'}
        if revocation == 'status'
        else {
            'expires_at': dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - dt.timedelta(seconds=1),
        }
        if revocation == 'expiry'
        else {'scopes': ['resource.view']}
    )
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        await uow.execute(sa.update(ApiKey).where(ApiKey.uuid == key_uuid).values(**changes))
    with pytest.raises((ArtifactError, PermissionDeniedError)):
        await service.manager_for_commit(case.a.context, policy)


async def test_mcp_uses_same_self_policy_and_run_commit_publishes_only_to_that_manager(artifact_replicas):
    case = artifact_replicas
    producer_id = await _producer(case)
    server = LangBotMCPServer(case.a.app)
    token = bind_request_context(case.context)
    try:
        content, _structured = await server.mcp.call_tool(
            'set_artifact_publication',
            {
                'producer_type': 'agent',
                'producer_id': producer_id,
                'enabled': True,
            },
        )
        policy = json.loads(content[0].text)
        assert policy['manager_id'] == case.context.account_uuid
        read, _structured = await server.mcp.call_tool(
            'get_artifact_publication', {'producer_type': 'agent', 'producer_id': producer_id}
        )
        assert json.loads(read[0].text) == policy
    finally:
        reset_request_context(token)
    run_context = _run_context(case)
    await seed_run(case.a.app, run_context, run_context.trigger_principal.run_id)
    output = await case.a.app.artifact_service.create_run_output(
        run_context, 'published.txt', b'published output', 'text/plain'
    )
    committed = await case.a.app.artifact_service.commit_run_outputs(run_context, [output['id']], publication=policy)
    assert committed[0]['lifecycle'] == 'persistent'
    assert (await case.b.app.artifact_service.read(case.context, output['id']))['content'] == b'published output'
    other = replace(case.context, principal=PrincipalContext(PrincipalType.API_KEY, api_key_uuid=str(uuid.uuid4())))
    with pytest.raises(FileNotFoundError):
        await case.b.app.artifact_service.read(other, output['id'])

    await case.b.app.artifact_publication_service.set(case.context, 'agent', producer_id, False)
    with pytest.raises(PermissionDeniedError):
        await case.a.app.artifact_service.commit_run_outputs(run_context, [output['id']], publication=policy)


async def test_unknown_or_deleted_producer_and_sentinel_principal_cannot_publish(artifact_replicas):
    case = artifact_replicas
    service = case.a.app.artifact_publication_service
    with pytest.raises(FileNotFoundError):
        await service.set(case.context, 'agent', str(uuid.uuid4()), True)
    producer_id = await _producer(case)
    policy = await service.set(case.context, 'agent', producer_id, True)
    sentinel = replace(
        case.context, principal=PrincipalContext(PrincipalType.API_KEY, api_key_uuid='global-oss-api-key')
    )
    with pytest.raises(PermissionDeniedError):
        await service.set(sentinel, 'agent', producer_id, True)
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        await uow.execute(sa.delete(Agent).where(Agent.uuid == producer_id))
    with pytest.raises(FileNotFoundError):
        await service.manager_for_commit(case.a.context, policy)
    await service.remove_producer(case.a.context, 'agent', producer_id)
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        assert (await uow.execute(sa.select(ArtifactPublication.producer_id))).first() is None
