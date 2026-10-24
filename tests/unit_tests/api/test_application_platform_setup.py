from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import inspect
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import lark_oapi
import pytest
from pydantic import TypeAdapter

from langbot.pkg.api.application.api import ApplicationAPI
from langbot.pkg.api.application.contracts import ApplicationAPIException
from langbot.pkg.api.application.platform_setup import operations
from langbot.pkg.api.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext
from langbot.pkg.core.errors import TaskCapacityError
from langbot.pkg.platform.credential_setup import CredentialSetupError, _bind_session_scope, get_credential_setup


def context(**changes):
    return RequestContext(
        instance_uuid='instance-a',
        workspace=WorkspaceContext('workspace-a', 'membership-a', 'developer', frozenset({'resource.manage'})),
        placement_generation=1,
        request_id='request-a',
        auth_type='user-token',
        principal=PrincipalContext(PrincipalType.ACCOUNT, account_uuid='account-a'),
        **changes,
    )


@pytest.fixture
def ap(monkeypatch):
    @contextlib.asynccontextmanager
    async def tenant_scope(workspace):
        yield

    def create_user_task(coro, **kwargs):
        return SimpleNamespace(task=asyncio.create_task(coro))

    application = SimpleNamespace(
        task_mgr=SimpleNamespace(create_user_task=Mock(side_effect=create_user_task)),
        workspace_service=SimpleNamespace(
            get_execution_binding=AsyncMock(return_value=SimpleNamespace(instance_uuid='instance-a'))
        ),
        persistence_mgr=SimpleNamespace(tenant_scope=tenant_scope),
    )
    monkeypatch.setattr('langbot.pkg.api.application.api.get_workspace_language', AsyncMock(return_value='en_US'))
    monkeypatch.setattr(ApplicationAPI, '_record', AsyncMock())
    return application


@pytest.mark.asyncio
async def test_catalog_covers_all_credential_flows_and_checks_permission_before_start(ap):
    api = ApplicationAPI(ap, operations=operations())
    assert len(api.operation_catalog()) == 18
    assert {op['permission'] for op in api.operation_catalog()} == {'resource.manage'}
    viewer = dataclasses.replace(
        context(), workspace=WorkspaceContext('workspace-a', 'membership-a', 'viewer', frozenset())
    )
    with pytest.raises(ApplicationAPIException) as exc:
        await api.execute('platform.setup.lark.start', viewer, {})
    assert exc.value.error.code == 'permission_denied'
    ap.task_mgr.create_user_task.assert_not_called()
    assert not hasattr(ap, 'credential_setup_service')


@pytest.mark.asyncio
async def test_setup_service_is_shared_with_transport_and_does_not_need_request_globals(ap, monkeypatch):
    release = asyncio.Event()
    completed = asyncio.Event()

    async def register(*, on_qr_code, source):
        on_qr_code({'url': 'https://example.test/qr'})
        await release.wait()
        completed.set()
        return {'client_id': 'app-a', 'client_secret': 'secret-a'}

    monkeypatch.setattr(lark_oapi, 'aregister_app', register)
    api = ApplicationAPI(ap, operations=operations())
    ctx = context()
    started = await api.execute('platform.setup.lark.start', ctx, {})
    service = get_credential_setup(ap)
    assert get_credential_setup(ap) is service
    assert await service.lark_status(started['session_id'], ctx) == {'status': 'waiting'}
    release.set()
    await completed.wait()
    result = await api.execute('platform.setup.lark.status', ctx, {'session_id': started['session_id']})
    assert result == {'status': 'success', 'app_id': 'app-a', 'app_secret': 'secret-a'}
    with pytest.raises(CredentialSetupError) as exc:
        await service.lark_status(started['session_id'], ctx)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_task_admission_error_is_preserved_as_domain_status(ap):
    ap.task_mgr.create_user_task.side_effect = TaskCapacityError('capacity exhausted')
    with pytest.raises(CredentialSetupError) as exc:
        await get_credential_setup(ap).lark_start(context())
    assert exc.value.status_code == 429
    assert 'Too many active' in str(exc.value)


_CASES = [
    ('lark', '_create_app_sessions', {'app_id': 'id', 'app_secret': 'secret'}),
    (
        'weixin',
        '_weixin_login_sessions',
        {
            'qr_data_url': 'data:qr',
            'expire_at': 1.0,
            'token': 'token',
            'base_url': 'https://example.test',
            'account_id': 'id',
        },
    ),
    ('dingtalk', '_dingtalk_sessions', {'client_id': 'id', 'client_secret': 'secret'}),
    ('wecombot', '_wecombot_sessions', {'botid': 'id', 'secret': 'secret'}),
    ('qqofficial', '_qqofficial_sessions', {'appid': 'id', 'secret': 'secret', 'user_openid': 'user'}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize('platform,store_name,credentials', _CASES)
async def test_each_platform_preserves_exact_owner_scoping_and_credentials(ap, platform, store_name, credentials):
    service = get_credential_setup(ap)
    status = getattr(service, f'{platform}_status')
    cancel = getattr(service, f'{platform}_cancel')
    store = inspect.getclosurevars(status).nonlocals[store_name]
    session = {'status': 'success', 'created_at': time.time(), **credentials}
    owner = context()
    _bind_session_scope(session, owner)
    store['session-a'] = session
    foreign = dataclasses.replace(owner, principal=PrincipalContext(PrincipalType.ACCOUNT, account_uuid='account-b'))
    for ctx in (
        foreign,
        dataclasses.replace(owner, placement_generation=2),
        dataclasses.replace(owner, workspace=dataclasses.replace(owner.workspace, workspace_uuid='workspace-b')),
    ):
        with pytest.raises(CredentialSetupError) as exc:
            await status('session-a', ctx)
        assert exc.value.status_code == 404
        with pytest.raises(CredentialSetupError):
            await cancel('session-a', ctx)
        assert store['session-a'] is session
    result = await status('session-a', owner)
    spec = next(op for op in operations() if op.operation_id == f'platform.setup.{platform}.status')
    assert TypeAdapter(spec.output_type).validate_python(result, strict=True) == result
    assert result == {'status': 'success', **credentials}
    assert 'session-a' not in store


@pytest.mark.asyncio
@pytest.mark.parametrize('platform,store_name,credentials', _CASES)
async def test_each_platform_cancel_stops_its_owned_task(ap, platform, store_name, credentials):
    service = get_credential_setup(ap)
    status = getattr(service, f'{platform}_status')
    store = inspect.getclosurevars(status).nonlocals[store_name]
    task = SimpleNamespace(done=Mock(return_value=False), cancel=Mock())
    session = {'status': 'waiting', 'created_at': time.time(), 'task': task, **credentials}
    _bind_session_scope(session, context())
    store['session-a'] = session
    assert await getattr(service, f'{platform}_cancel')('session-a', context()) == {}
    task.cancel.assert_called_once_with()
    assert not store


@pytest.mark.asyncio
async def test_slack_cancel_checks_ownership_before_discard(ap):
    from langbot.pkg.api.http.service.slack_setup import SlackSetupError

    ap.slack_setup_service = SimpleNamespace(
        owned=Mock(side_effect=SlackSetupError('session_not_found')), discard=Mock()
    )
    api = ApplicationAPI(ap, operations=operations())
    with pytest.raises(ApplicationAPIException) as exc:
        await api.execute('platform.setup.slack.cancel', context(), {'session_id': 'foreign-session'})
    assert exc.value.error.status_code == 404
    ap.slack_setup_service.discard.assert_not_called()
