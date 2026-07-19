from __future__ import annotations

import datetime
import hashlib
import logging
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from langbot.pkg.api.http.authz import Permission, PermissionDeniedError
from langbot.pkg.api.http.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext
from langbot.pkg.api.http.service.apikey import ApiKeyService
from langbot.pkg.entity.persistence.apikey import ApiKey
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.entity.persistence.workspace import (
    Workspace,
    WorkspaceExecutionSource,
    WorkspaceExecutionState,
    WorkspaceSource,
)
from langbot.pkg.workspace.policy import SingleWorkspacePolicy
from langbot.pkg.workspace.errors import WorkspaceNotFoundError
from langbot.pkg.workspace.service import WorkspaceService


pytestmark = pytest.mark.asyncio


class _PersistenceManager:
    def __init__(self, engine):
        self.engine = engine

    def get_db_engine(self):
        return self.engine

    async def execute_async(self, *args, **kwargs):
        async with self.engine.connect() as connection:
            result = await connection.execute(*args, **kwargs)
            await connection.commit()
            return result

    @staticmethod
    def serialize_model(model, row, masked_columns=()):
        return {
            column.name: (
                getattr(row, column.name).isoformat()
                if isinstance(getattr(row, column.name), datetime.datetime)
                else getattr(row, column.name)
            )
            for column in model.__table__.columns
            if column.name not in masked_columns
        }


def _context(workspace_uuid: str, account_uuid: str, permissions: set[Permission]) -> RequestContext:
    return RequestContext(
        instance_uuid='api-key-instance',
        placement_generation=1,
        request_id=str(uuid.uuid4()),
        auth_type='user-token',
        principal=PrincipalContext(PrincipalType.ACCOUNT, account_uuid=account_uuid),
        workspace=WorkspaceContext(
            workspace_uuid=workspace_uuid,
            membership_uuid=str(uuid.uuid4()),
            role='owner',
            permissions=frozenset(permission.value for permission in permissions),
        ),
    )


@pytest.fixture
async def api_key_context(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "api-keys.db"}')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    application = SimpleNamespace(
        persistence_mgr=_PersistenceManager(engine),
        instance_config=SimpleNamespace(data={'api': {'global_api_key': ''}}),
        logger=logging.getLogger('api-key-test'),
    )
    application.workspace_service = WorkspaceService(application, instance_uuid='api-key-instance')
    workspace = await application.workspace_service.ensure_singleton_workspace()
    account_uuid = str(uuid.uuid4())
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory.begin() as session:
        session.add(
            User(
                uuid=account_uuid,
                user='owner@example.com',
                normalized_email='owner@example.com',
                password='hash',
                account_type='local',
            )
        )
    service = ApiKeyService(application)
    context = _context(workspace.uuid, account_uuid, set(Permission))
    yield application, service, context, engine
    await engine.dispose()


async def test_secret_is_returned_once_and_only_hash_is_persisted(api_key_context):
    _application, service, context, engine = api_key_context

    created = await service.create_api_key(context, 'Automation', 'CI key')
    secret = created['key']
    assert secret.startswith('lbk_')
    assert created['secret_available'] is True
    assert 'key_hash' not in created

    listed = await service.get_api_keys(context)
    assert len(listed) == 1
    assert 'key' not in listed[0]
    assert 'key_hash' not in listed[0]
    assert listed[0]['secret_available'] is False

    async with engine.connect() as connection:
        stored = await connection.scalar(sqlalchemy.select(ApiKey.key_hash))
    assert stored == hashlib.sha256(secret.encode()).hexdigest()
    assert secret not in stored


async def test_authentication_derives_workspace_scopes_and_updates_usage(api_key_context):
    _application, service, context, engine = api_key_context
    created = await service.create_api_key(
        context,
        'Read only',
        scopes=[Permission.RESOURCE_VIEW.value],
    )

    identity = await service.authenticate_api_key(created['key'])
    assert identity is not None
    assert identity.workspace_uuid == context.workspace_uuid
    assert identity.permissions == frozenset({Permission.RESOURCE_VIEW.value})

    async with engine.connect() as connection:
        last_used_at = await connection.scalar(sqlalchemy.select(ApiKey.last_used_at))
    assert last_used_at is not None


async def test_revoked_expired_and_unknown_keys_fail_closed(api_key_context):
    _application, service, context, _engine = api_key_context
    created = await service.create_api_key(context, 'Revocable')
    await service.delete_api_key(context, created['id'])
    assert await service.authenticate_api_key(created['key']) is None
    assert await service.verify_api_key('') is False
    assert await service.verify_api_key('plain-secret') is False
    assert await service.verify_api_key('lbk_unknown') is False

    expired_secret = 'lbk_expired'
    await service.ap.persistence_mgr.execute_async(
        sqlalchemy.insert(ApiKey).values(
            workspace_uuid=context.workspace_uuid,
            name='Expired',
            key_hash=hashlib.sha256(expired_secret.encode()).hexdigest(),
            scopes=[Permission.RESOURCE_VIEW.value],
            status='active',
            expires_at=datetime.datetime.now(datetime.UTC).replace(tzinfo=None) - datetime.timedelta(seconds=1),
        )
    )
    assert await service.authenticate_api_key(expired_secret) is None


async def test_revoke_winning_last_used_update_race_fails_authentication(api_key_context):
    application, service, context, _engine = api_key_context
    created = await service.create_api_key(context, 'Racing revoke')
    original_execute = application.persistence_mgr.execute_async
    injected_revoke = False

    async def execute_with_revoke(statement, *args, **kwargs):
        nonlocal injected_revoke
        if (
            not injected_revoke
            and isinstance(statement, sqlalchemy.sql.dml.Update)
            and statement.table.name == ApiKey.__tablename__
        ):
            injected_revoke = True
            await original_execute(sqlalchemy.update(ApiKey).where(ApiKey.id == created['id']).values(status='revoked'))
        return await original_execute(statement, *args, **kwargs)

    application.persistence_mgr.execute_async = execute_with_revoke

    assert await service.authenticate_api_key(created['key']) is None
    assert injected_revoke is True


async def test_cross_workspace_crud_and_secret_guessing_are_isolated(api_key_context):
    application, service, first_context, engine = api_key_context
    second_workspace_uuid = str(uuid.uuid4())
    async with async_sessionmaker(engine, expire_on_commit=False).begin() as session:
        session.add(
            Workspace(
                uuid=second_workspace_uuid,
                instance_uuid='api-key-instance',
                name='Second',
                slug='second',
                source=WorkspaceSource.CLOUD_PROJECTION.value,
            )
        )
        session.add(
            WorkspaceExecutionState(
                workspace_uuid=second_workspace_uuid,
                instance_uuid='api-key-instance',
                active_generation=3,
                state='active',
                write_fenced=False,
                source=WorkspaceExecutionSource.CLOUD.value,
            )
        )
    second_context = _context(second_workspace_uuid, first_context.account_uuid or '', set(Permission))
    created = await service.create_api_key(first_context, 'First only')

    assert await service.get_api_key(second_context, created['id']) is None
    assert await service.get_api_keys(second_context) == []
    identity = await service.authenticate_api_key(created['key'])
    assert identity is not None
    assert identity.workspace_uuid == first_context.workspace_uuid
    assert identity.workspace_uuid != second_workspace_uuid

    # Prove the explicit multi-Workspace policy does not change key-derived routing.
    application.workspace_service.policy = SingleWorkspacePolicy(workspace_limit=10, multi_workspace_enabled=True)
    identity = await service.authenticate_api_key(created['key'])
    assert identity is not None
    assert identity.workspace_uuid == first_context.workspace_uuid


async def test_global_config_key_is_oss_singleton_only(api_key_context):
    application, service, _context_value, _engine = api_key_context
    application.instance_config.data['api']['global_api_key'] = 'configured-secret'

    identity = await service.authenticate_api_key('configured-secret')
    assert identity is not None
    assert identity.api_key_uuid == 'global-oss-api-key'

    application.workspace_service.policy = SingleWorkspacePolicy(workspace_limit=10, multi_workspace_enabled=True)
    assert await service.authenticate_api_key('configured-secret') is None


async def test_explicit_scopes_cannot_exceed_callers_workspace_permissions(api_key_context):
    _application, service, context, _engine = api_key_context
    limited_context = _context(
        context.workspace_uuid,
        context.account_uuid or '',
        {Permission.API_KEY_MANAGE, Permission.RESOURCE_VIEW},
    )

    created = await service.create_api_key(
        limited_context,
        'Read only',
        scopes=[Permission.RESOURCE_VIEW.value],
    )
    identity = await service.authenticate_api_key(created['key'])
    assert identity is not None
    assert identity.permissions == frozenset({Permission.RESOURCE_VIEW.value})

    with pytest.raises(PermissionDeniedError) as exc_info:
        await service.create_api_key(
            limited_context,
            'Escalated',
            scopes=[Permission.WORKSPACE_DELETE.value],
        )
    assert exc_info.value.permission == Permission.WORKSPACE_DELETE.value


# Preserve the pre-tenancy CRUD and verification regression matrix while
# exercising it through the new Workspace-bound API.  The assertions reflect
# intentional security changes: secrets are returned once, deletion revokes,
# and missing Workspace resources are reported as not found.
class TestApiKeyServiceGetApiKeys:
    async def test_get_api_keys_empty_list(self, api_key_context):
        _application, service, context, _engine = api_key_context

        assert await service.get_api_keys(context) == []

    async def test_get_api_keys_returns_serialized_list(self, api_key_context):
        _application, service, context, _engine = api_key_context
        await service.create_api_key(context, 'Test Key 1', 'First test key')
        await service.create_api_key(context, 'Test Key 2', 'Second test key')

        result = await service.get_api_keys(context)

        assert [item['name'] for item in result] == ['Test Key 1', 'Test Key 2']
        assert [item['description'] for item in result] == ['First test key', 'Second test key']
        assert all('key' not in item and 'key_hash' not in item for item in result)


class TestApiKeyServiceCreateApiKey:
    async def test_create_api_key_generates_key_with_prefix(self, api_key_context):
        _application, service, context, _engine = api_key_context

        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(
                'langbot.pkg.api.http.service.apikey.secrets.token_urlsafe', lambda _size: 'fixed-token'
            )
            result = await service.create_api_key(context, 'New Key', 'Test description')

        assert result['key'] == 'lbk_fixed-token'
        assert result['name'] == 'New Key'
        assert result['description'] == 'Test description'
        assert result['secret_available'] is True

    async def test_create_api_key_without_description(self, api_key_context):
        _application, service, context, _engine = api_key_context

        result = await service.create_api_key(context, 'No Desc Key')

        assert result['description'] == ''


class TestApiKeyServiceGetApiKey:
    async def test_get_api_key_by_id_found(self, api_key_context):
        _application, service, context, _engine = api_key_context
        created = await service.create_api_key(context, 'Found Key', 'Found')

        result = await service.get_api_key(context, created['id'])

        assert result is not None
        assert result['id'] == created['id']
        assert result['name'] == 'Found Key'
        assert 'key' not in result and 'key_hash' not in result

    async def test_get_api_key_by_id_not_found(self, api_key_context):
        _application, service, context, _engine = api_key_context

        assert await service.get_api_key(context, 999) is None

    async def test_get_api_key_by_id_zero(self, api_key_context):
        _application, service, context, _engine = api_key_context

        assert await service.get_api_key(context, 0) is None


class TestApiKeyServiceVerifyApiKey:
    async def test_verify_api_key_valid(self, api_key_context):
        _application, service, context, _engine = api_key_context
        created = await service.create_api_key(context, 'Valid')

        assert await service.verify_api_key(created['key']) is True

    async def test_verify_api_key_invalid(self, api_key_context):
        _application, service, _context, _engine = api_key_context

        assert await service.verify_api_key('lbk_invalid_key') is False

    async def test_verify_api_key_empty_string(self, api_key_context):
        _application, service, _context, _engine = api_key_context

        assert await service.verify_api_key('') is False

    async def test_verify_api_key_unknown_key(self, api_key_context):
        _application, service, _context, _engine = api_key_context

        assert await service.verify_api_key('unknown_key') is False

    async def test_verify_global_api_key_match(self, api_key_context):
        application, service, context, _engine = api_key_context
        application.instance_config.data['api']['global_api_key'] = 'my-global-secret'

        identity = await service.authenticate_api_key('my-global-secret')

        assert identity is not None
        assert identity.workspace_uuid == context.workspace_uuid
        assert identity.api_key_uuid == 'global-oss-api-key'

    async def test_verify_global_api_key_no_prefix_required(self, api_key_context):
        application, service, _context, _engine = api_key_context
        application.instance_config.data['api']['global_api_key'] = 'plainsecret123'

        assert await service.verify_api_key('plainsecret123') is True

    async def test_verify_global_api_key_mismatch_falls_back_to_db(self, api_key_context):
        application, service, context, _engine = api_key_context
        application.instance_config.data['api']['global_api_key'] = 'my-global-secret'
        created = await service.create_api_key(context, 'DB key')

        identity = await service.authenticate_api_key(created['key'])

        assert identity is not None
        assert identity.api_key_uuid == created['uuid']

    async def test_verify_empty_global_api_key_disabled(self, api_key_context):
        application, service, _context, _engine = api_key_context
        application.instance_config.data['api']['global_api_key'] = ''

        assert await service.verify_api_key('') is False
        assert await service.verify_api_key('   ') is False

    async def test_verify_api_key_missing_global_config_key(self, api_key_context):
        application, service, _context, _engine = api_key_context
        application.instance_config.data = {'api': {}}

        assert await service.verify_api_key('lbk_some_key') is False


class TestApiKeyServiceDeleteApiKey:
    async def test_delete_api_key_by_id(self, api_key_context):
        _application, service, context, _engine = api_key_context
        created = await service.create_api_key(context, 'Delete me')

        await service.delete_api_key(context, created['id'])

        stored = await service.get_api_key(context, created['id'])
        assert stored is not None
        assert stored['status'] == 'revoked'
        assert await service.verify_api_key(created['key']) is False

    async def test_delete_api_key_nonexistent_id(self, api_key_context):
        _application, service, context, _engine = api_key_context

        with pytest.raises(WorkspaceNotFoundError, match='API key not found'):
            await service.delete_api_key(context, 999)


class TestApiKeyServiceUpdateApiKey:
    async def test_update_api_key_name_only(self, api_key_context):
        _application, service, context, _engine = api_key_context
        created = await service.create_api_key(context, 'Original', 'Description')

        await service.update_api_key(context, created['id'], name='Updated Name')

        stored = await service.get_api_key(context, created['id'])
        assert stored is not None
        assert stored['name'] == 'Updated Name'
        assert stored['description'] == 'Description'

    async def test_update_api_key_description_only(self, api_key_context):
        _application, service, context, _engine = api_key_context
        created = await service.create_api_key(context, 'Original', 'Description')

        await service.update_api_key(context, created['id'], description='Updated description')

        stored = await service.get_api_key(context, created['id'])
        assert stored is not None
        assert stored['name'] == 'Original'
        assert stored['description'] == 'Updated description'

    async def test_update_api_key_both_fields(self, api_key_context):
        _application, service, context, _engine = api_key_context
        created = await service.create_api_key(context, 'Original', 'Description')

        await service.update_api_key(
            context,
            created['id'],
            name='New Name',
            description='New description',
        )

        stored = await service.get_api_key(context, created['id'])
        assert stored is not None
        assert stored['name'] == 'New Name'
        assert stored['description'] == 'New description'

    async def test_update_api_key_no_fields(self, api_key_context):
        application, service, context, _engine = api_key_context
        created = await service.create_api_key(context, 'Original')
        original_execute = application.persistence_mgr.execute_async
        application.persistence_mgr.execute_async = AsyncMock(wraps=original_execute)

        await service.update_api_key(context, created['id'])

        application.persistence_mgr.execute_async.assert_not_awaited()
