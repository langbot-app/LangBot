"""Database-backed regressions for explicit OSS Space account binding."""

import datetime
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from langbot.pkg.api.http.service.user import ControlPlaneDirectoryRequiredError, UserService
from langbot.pkg.entity.errors.account import AccountEmailMismatchError
from langbot.pkg.entity.persistence.user import User

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def binding_context(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "binding.db"}')
    async with engine.begin() as connection:
        await connection.run_sync(User.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def identity_uow(digest):
        async with sessions() as session, session.begin():
            yield SimpleNamespace(session=session)

    async with sessions() as session, session.begin():
        session.add(
            User(uuid='local-owner', user='local@example.com', normalized_email='local@example.com', password='hash')
        )

    application = SimpleNamespace(
        persistence_mgr=SimpleNamespace(identity_discovery_uow=identity_uow),
        workspace_service=SimpleNamespace(
            instance_uuid='instance',
            policy=SimpleNamespace(multi_workspace_enabled=False),
            get_execution_binding=AsyncMock(
                return_value=SimpleNamespace(
                    workspace_uuid='workspace', workspace_created_at=datetime.datetime(2026, 1, 1)
                )
            ),
        ),
        space_service=SimpleNamespace(
            exchange_oauth_code=AsyncMock(return_value={'access_token': 'access', 'refresh_token': 'refresh'}),
            get_user_info_raw=AsyncMock(
                return_value={'account': {'uuid': 'space-owner', 'email': ' SPACE@Example.com '}, 'api_key': 'key'}
            ),
        ),
        instance_config=SimpleNamespace(
            data={'system': {'jwt': {'secret': 'test-secret-long-enough-for-jwt-32', 'expire': 3600}}}
        ),
    )
    service = UserService(application)
    service._update_space_provider_for_account = AsyncMock()
    yield service, sessions
    await engine.dispose()


async def test_sole_local_account_adopts_space_email_and_preserves_identity(binding_context):
    service, _ = binding_context
    old_token = await service.generate_jwt_token(await service.get_user_by_uuid('local-owner'))
    account = await service.bind_space_account('local@example.com', 'code')
    assert account.uuid == 'local-owner'
    assert account.user == account.normalized_email == 'space@example.com'
    assert account.password == 'hash'
    assert account.account_type == 'space'
    assert account.space_account_uuid == 'space-owner'
    assert account.space_access_token == 'access'
    assert account.space_refresh_token == 'refresh'
    assert account.space_api_key == 'key'
    assert await service.get_user_by_email('local@example.com') is None
    assert (await service.get_authenticated_account(old_token)).uuid == account.uuid
    new_token = await service.generate_jwt_token(account)
    assert (await service.get_authenticated_account(new_token)).user == 'space@example.com'
    service._update_space_provider_for_account.assert_awaited_once()


@pytest.mark.parametrize('status', ['active', 'disabled', 'deleted'])
async def test_multiple_accounts_keep_email_check(binding_context, status):
    service, sessions = binding_context
    async with sessions() as session, session.begin():
        session.add(
            User(
                uuid='other', user='other@example.com', normalized_email='other@example.com', password='', status=status
            )
        )
    with pytest.raises(AccountEmailMismatchError):
        await service.bind_space_account('local@example.com', 'code')
    account = await service.get_user_by_uuid('local-owner')
    assert account.user == 'local@example.com'
    assert account.space_account_uuid is None


async def test_same_email_binding_still_works_with_multiple_accounts(binding_context):
    service, sessions = binding_context
    async with sessions() as session, session.begin():
        session.add(User(uuid='other', user='other@example.com', normalized_email='other@example.com', password=''))
    service.ap.space_service.get_user_info_raw.return_value['account']['email'] = 'LOCAL@example.com'
    account = await service.bind_space_account('local@example.com', 'code')
    assert account.space_account_uuid == 'space-owner'


async def test_cloud_binding_is_rejected_before_oauth(binding_context):
    service, _ = binding_context
    service.ap.workspace_service.policy.multi_workspace_enabled = True
    with pytest.raises(ControlPlaneDirectoryRequiredError):
        await service.bind_space_account('local@example.com', 'code')
    service.ap.space_service.exchange_oauth_code.assert_not_awaited()


@pytest.mark.parametrize(
    'field,value', [('source', 'cloud_projection'), ('account_type', 'space'), ('space_account_uuid', 'already-bound')]
)
async def test_only_unbound_local_identity_can_replace_email(binding_context, field, value):
    service, sessions = binding_context
    async with sessions() as session, session.begin():
        account = await session.get(User, 1)
        setattr(account, field, value)
    with pytest.raises(AccountEmailMismatchError):
        await service.bind_space_account('local@example.com', 'code')


async def test_space_subject_bound_to_another_account_is_rejected(binding_context):
    service, sessions = binding_context
    async with sessions() as session, session.begin():
        session.add(
            User(
                uuid='other',
                user='other@example.com',
                normalized_email='other@example.com',
                password='',
                space_account_uuid='space-owner',
            )
        )
    service.ap.space_service.get_user_info_raw.return_value['account']['email'] = 'local@example.com'
    with pytest.raises(ValueError, match='already bound'):
        await service.bind_space_account('local@example.com', 'code')
    assert (await service.get_user_by_uuid('local-owner')).space_account_uuid is None
