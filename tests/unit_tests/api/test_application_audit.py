"""Trace operation outcomes without recording input values or changing failures."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.application import ApplicationAPI, ApplicationAPIException, Input, Operation
from langbot.pkg.api.authz import Permission
from langbot.pkg.api.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext
from langbot.pkg.operation_trace.service import OPERATION_LEVEL_MUTATION, OPERATION_LEVEL_READ


class Payload(Input):
    provider_uuid: str = 'provider-a'
    config: dict = {}


def context(allowed=True):
    return RequestContext(
        'instance-a',
        1,
        'request-a',
        'user-token',
        PrincipalContext(PrincipalType.ACCOUNT, account_uuid='account-a'),
        WorkspaceContext('workspace-a', 'member-a', 'developer', frozenset(Permission) if allowed else frozenset()),
    )


@pytest.fixture
def host(monkeypatch):
    @asynccontextmanager
    async def scope(workspace):
        yield

    monkeypatch.setattr('langbot.pkg.api.application.api.get_workspace_language', AsyncMock(return_value='en_US'))
    return SimpleNamespace(
        persistence_mgr=SimpleNamespace(tenant_scope=scope),
        workspace_service=SimpleNamespace(
            get_execution_binding=AsyncMock(return_value=SimpleNamespace(instance_uuid='instance-a'))
        ),
        workspace_settings_service=SimpleNamespace(
            effective_level=AsyncMock(return_value=OPERATION_LEVEL_READ), record=AsyncMock()
        ),
        logger=Mock(),
    )


def operation_api(host, handler, name='provider.update', *, write=True, streaming=False):
    return ApplicationAPI(
        host,
        operations=[
            Operation(name, Permission.RESOURCE_MANAGE, handler, Payload, dict, side_effect=write, streaming=streaming)
        ],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('name', 'write', 'action'),
    [
        ('provider.create', True, 'create'),
        ('provider.delete', True, 'delete'),
        ('provider.get', False, 'view'),
    ],
)
async def test_success_classifies_actions_and_excludes_configuration(host, name, write, action):
    await operation_api(host, AsyncMock(return_value={}), name, write=write).execute(
        name,
        context(),
        {
            'provider_uuid': 'provider-a',
            'config': {'api_key': 'private-secret', 'url': 'private-url'},
        },
    )
    call = host.workspace_settings_service.record.await_args
    assert call.args == ('workspace-a',)
    assert call.kwargs['rule'].action == action
    assert call.kwargs['rule'].bucket == ('write' if write else 'read')
    assert call.kwargs['outcome'] == 'ok'
    assert call.kwargs['resource_id'] == 'provider-a'
    assert 'private' not in repr(call)
    host.workspace_settings_service.record.assert_awaited_once()


@pytest.mark.asyncio
async def test_read_capture_honors_mutation_only_level(host):
    host.workspace_settings_service.effective_level.return_value = OPERATION_LEVEL_MUTATION
    await operation_api(host, AsyncMock(return_value={}), 'provider.get', write=False).execute(
        'provider.get', context(), {}
    )
    host.workspace_settings_service.record.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('error', 'outcome', 'status'),
    [(ValueError('invalid secret'), 'error', 400), (RuntimeError('private error'), 'unknown', 500)],
)
async def test_failed_mutation_records_once_without_error_payload(host, error, outcome, status):
    with pytest.raises(ApplicationAPIException):
        await operation_api(host, AsyncMock(side_effect=error)).execute(
            'provider.update', context(), {'config': {'api_key': 'private'}}
        )
    host.workspace_settings_service.record.assert_awaited_once()
    data = host.workspace_settings_service.record.await_args.kwargs
    assert (data['outcome'], data['status_code']) == (outcome, status)
    assert 'private' not in repr(data) and 'invalid secret' not in repr(data)


@pytest.mark.asyncio
async def test_denied_records_once_but_unknown_workspace_and_malformed_context_do_not(host):
    handler = AsyncMock(return_value={})
    api = operation_api(host, handler)
    with pytest.raises(ApplicationAPIException) as denied:
        await api.execute('provider.update', context(False), {})
    assert denied.value.error.code == 'permission_denied'
    assert host.workspace_settings_service.record.await_args.kwargs['outcome'] == 'denied'
    host.workspace_settings_service.record.assert_awaited_once()
    handler.assert_not_awaited()
    host.workspace_settings_service.record.reset_mock()
    for invalid in (None, replace(context(), instance_uuid='foreign')):
        with pytest.raises(ApplicationAPIException):
            await api.execute('provider.update', invalid, {})
    host.workspace_settings_service.record.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_result_and_cancellation_record_unknown_and_keep_original_failure(host):
    api = operation_api(host, AsyncMock(return_value='invalid'))
    with pytest.raises(ApplicationAPIException) as error:
        await api.execute('provider.update', context(), {})
    assert error.value.error.code == 'invalid_output'
    assert host.workspace_settings_service.record.await_args.kwargs['outcome'] == 'unknown'
    api = operation_api(host, AsyncMock(side_effect=asyncio.CancelledError()))
    with pytest.raises(asyncio.CancelledError):
        await api.execute('provider.update', context(), {})
    assert host.workspace_settings_service.record.await_args.kwargs['status_code'] == 499
    host.workspace_settings_service.record.side_effect = RuntimeError('audit failed')
    host.logger.exception.side_effect = RuntimeError('logger failed')
    with pytest.raises(ApplicationAPIException) as original:
        await operation_api(host, AsyncMock(side_effect=ValueError('original'))).execute(
            'provider.update', context(), {}
        )
    assert original.value.error.message == 'original'


@pytest.mark.asyncio
async def test_late_stream_failure_is_recorded_once(host):
    async def handler(ap, ctx, payload):
        async def source():
            yield {}
            raise RuntimeError('private stream error')

        return source()

    api = operation_api(host, handler, streaming=True)
    with pytest.raises(ApplicationAPIException):
        async for _ in api.stream('provider.update', context(), {}):
            pass
    host.workspace_settings_service.record.assert_awaited_once()
    assert host.workspace_settings_service.record.await_args.kwargs['outcome'] == 'unknown'


@pytest.mark.asyncio
async def test_domain_audit_exclusion_applies_only_to_success(host):
    name = 'workspace.member.update'
    await operation_api(host, AsyncMock(return_value={}), name).execute(name, context(), {})
    host.workspace_settings_service.record.assert_not_awaited()
    with pytest.raises(ApplicationAPIException):
        await operation_api(host, AsyncMock(side_effect=ValueError('last owner')), name).execute(name, context(), {})
    host.workspace_settings_service.record.assert_awaited_once()
    assert host.workspace_settings_service.record.await_args.kwargs['outcome'] == 'error'
