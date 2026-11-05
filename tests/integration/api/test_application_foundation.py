"""Exercise the foundation without HTTP, with independent SQLite readback."""

import dataclasses
import hashlib
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.application import ApplicationAPI, ApplicationAPIException, Input, Operation
from langbot.pkg.api.authz import Permission
from langbot.pkg.api.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext
from langbot.pkg.api.http.service.apikey import ApiKeyService
from langbot.pkg.api.http.service.webhook import WebhookService
from langbot.pkg.entity.persistence.apikey import ApiKey
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.webhook import Webhook
from langbot.pkg.entity.persistence.workspace import Workspace, WorkspaceExecutionState
from langbot.pkg.persistence.mgr import PersistenceManager
from langbot.pkg.workspace.service import WorkspaceService


def context(workspace='workspace-a', permissions=frozenset(Permission), generation=1):
    return RequestContext(
        instance_uuid='foundation-instance',
        placement_generation=generation,
        request_id='test-request',
        auth_type='api-key',
        principal=PrincipalContext(PrincipalType.API_KEY, api_key_uuid='test-key'),
        workspace=WorkspaceContext(workspace, None, None, frozenset(permissions)),
    )


@pytest.fixture
async def foundation(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "foundation.db"}')
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.execute(
                sa.insert(Workspace),
                [
                    {
                        'uuid': name,
                        'instance_uuid': 'foundation-instance',
                        'name': name,
                        'slug': name,
                        'source': 'cloud_projection',
                    }
                    for name in ('workspace-a', 'workspace-b')
                ],
            )
            await connection.execute(
                sa.insert(WorkspaceExecutionState),
                [
                    {
                        'workspace_uuid': name,
                        'instance_uuid': 'foundation-instance',
                        'active_generation': 1,
                        'source': 'cloud',
                    }
                    for name in ('workspace-a', 'workspace-b')
                ],
            )
        ap = SimpleNamespace(instance_config=SimpleNamespace(data={}), logger=logging.getLogger('foundation'))
        ap.persistence_mgr = PersistenceManager(ap)
        ap.persistence_mgr.db = SimpleNamespace(get_engine=lambda: engine)
        ap.workspace_service = WorkspaceService(ap, instance_uuid='foundation-instance')
        ap.webhook_service = WebhookService(ap)
        ap.apikey_service = ApiKeyService(ap)
        api = ApplicationAPI(ap)
        yield api, ap, engine
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_webhook_lifecycle_secrets_and_workspace_isolation(foundation):
    api, _, engine = foundation
    created = await api.execute(
        'webhook.create', context(), {'name': 'same-name', 'url': 'https://example.test/?token=private'}
    )
    other = await api.execute(
        'webhook.create', context('workspace-b'), {'name': 'same-name', 'url': 'https://other.test/'}
    )
    assert created['id'] != other['id']
    viewer = context(permissions={Permission.RESOURCE_VIEW})
    assert (await api.execute('webhook.list', viewer, {}))[0]['url'] == '***'
    with pytest.raises(ApplicationAPIException) as denied:
        await api.execute('webhook.get', viewer, {'webhook_id': created['id'], 'include_secret': True})
    assert denied.value.error.code == 'permission_denied'
    with pytest.raises(ApplicationAPIException) as missing:
        await api.execute('webhook.get', context('workspace-b'), {'webhook_id': created['id']})
    assert missing.value.error.code == 'resource_not_found'
    await api.execute('webhook.update', context(), {'webhook_id': created['id'], 'name': 'renamed', 'url': '***'})
    async with engine.connect() as connection:
        row = (await connection.execute(sa.select(Webhook).where(Webhook.id == created['id']))).mappings().one()
        assert row['workspace_uuid'] == 'workspace-a'
        assert row['name'] == 'renamed'
        assert row['url'] == 'https://example.test/?token=private'
    assert await api.execute('webhook.delete', context(), {'webhook_id': created['id']}) is True
    assert await api.execute('webhook.list', context(), {}) == []
    assert len(await api.execute('webhook.list', context('workspace-b'), {})) == 1


@pytest.mark.asyncio
async def test_key_grants_are_persisted_without_secret_or_escalation(foundation):
    api, _, engine = foundation
    limited = context(permissions={Permission.API_KEY_MANAGE, Permission.RESOURCE_VIEW})
    with pytest.raises(ApplicationAPIException) as error:
        await api.execute('api_key.create', limited, {'name': 'escalation', 'scopes': ['resource.manage']})
    assert error.value.error.code == 'permission_denied'
    created = await api.execute('api_key.create', limited, {'name': 'reader', 'scopes': ['resource.view']})
    empty = await api.execute('api_key.create', limited, {'name': 'empty', 'scopes': []})
    async with engine.connect() as connection:
        rows = (await connection.execute(sa.select(ApiKey))).mappings().all()
        assert len(rows) == 2
        assert rows[0]['key_hash'] == hashlib.sha256(created['key'].encode()).hexdigest()
        assert rows[0]['scopes'] == ['resource.view']
        assert rows[1]['scopes'] == []
    listed = await api.execute('api_key.list', limited, {})
    assert all('key' not in row and 'key_hash' not in row for row in listed)
    assert empty['key'] != created['key']


@pytest.mark.asyncio
async def test_untrusted_fields_stale_placement_and_wrong_instance_fail_before_write(foundation):
    api, _, engine = foundation
    for payload in (
        {'name': 'bad', 'url': 'secret://private', 'workspace_uuid': 'workspace-b'},
        {'name': 'bad', 'url': 'secret://private', 'enabled': 'false'},
    ):
        with pytest.raises(ApplicationAPIException) as error:
            await api.execute('webhook.create', context(), payload)
        assert error.value.error.code == 'invalid_input'
        assert 'secret://private' not in str(error.value)
    with pytest.raises(ApplicationAPIException) as stale:
        await api.execute('webhook.create', context(generation=2), {'name': 'stale', 'url': 'https://example.test/'})
    assert stale.value.error.code == 'workspace_unavailable'
    with pytest.raises(ApplicationAPIException) as wrong_instance:
        await api.execute('webhook.list', dataclasses.replace(context(), instance_uuid='other-instance'), {})
    assert wrong_instance.value.error.code == 'invalid_authentication'
    async with engine.connect() as connection:
        assert (await connection.execute(sa.select(sa.func.count()).select_from(Webhook))).scalar_one() == 0


@pytest.mark.asyncio
async def test_every_registered_operation_denies_missing_permission():
    api = ApplicationAPI(SimpleNamespace())
    for spec in api._operations.values():
        principal = PrincipalContext(PrincipalType.ACCOUNT, account_uuid='user')
        denied_context = dataclasses.replace(context(permissions=set()), principal=principal)
        with pytest.raises(ApplicationAPIException) as error:
            if spec.streaming:
                await anext(api.stream(spec.operation_id, denied_context, {}))
            else:
                await api.execute(spec.operation_id, denied_context, {})
        assert error.value.error.code == 'permission_denied', spec.operation_id
        spec.as_dict()


@pytest.mark.asyncio
async def test_invalid_output_fails_and_cancellation_propagates(foundation):
    import asyncio

    _, ap, _ = foundation
    handler = AsyncMock(return_value='not-an-object')
    api = ApplicationAPI(ap, operations=[Operation('example', Permission.RESOURCE_VIEW, handler, Input, dict)])
    with pytest.raises(ApplicationAPIException) as error:
        await api.execute('example', context(), {})
    assert error.value.error.code == 'invalid_output'
    handler.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await api.execute('example', context(), {})
