"""Tests for processor principal authorization and operation whitelist enforcement."""

import dataclasses
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.application import ApplicationAPI, ApplicationAPIException, Input, Operation
from langbot.pkg.api.application.processor_context import build_processor_request_context
from langbot.pkg.api.authz import Permission
from langbot.pkg.api.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext
from langbot.pkg.operation_trace.service import (
    OPERATION_LEVEL_MUTATION,
    OPERATION_LEVEL_READ,
    compute_dedupe_key,
    dedupe_material,
    hash_dedupe_material,
)
from langbot.pkg.workspace.errors import WorkspaceExecutionUnavailableError


class Payload(Input):
    item_id: str = 'item-1'


@pytest.fixture
def host(monkeypatch):
    @asynccontextmanager
    async def scope(workspace):
        yield

    monkeypatch.setattr('langbot.pkg.api.application.api.get_workspace_language', AsyncMock(return_value='en_US'))
    return SimpleNamespace(
        persistence_mgr=SimpleNamespace(tenant_scope=scope),
        workspace_service=SimpleNamespace(
            get_execution_binding=AsyncMock(
                return_value=SimpleNamespace(instance_uuid='instance-a', placement_generation=1)
            )
        ),
        workspace_settings_service=SimpleNamespace(
            effective_level=AsyncMock(return_value=OPERATION_LEVEL_READ),
            record=AsyncMock(),
        ),
        logger=Mock(),
    )


def build_test_api(host):
    read_op = Operation(
        'bot.list', Permission.RESOURCE_VIEW, AsyncMock(return_value=[]), Input, list[dict], side_effect=False
    )
    write_op = Operation(
        'bot.create', Permission.RESOURCE_MANAGE, AsyncMock(return_value={}), Payload, dict, side_effect=True
    )
    account_op = Operation(
        'account.only',
        Permission.RESOURCE_MANAGE,
        AsyncMock(return_value={}),
        Input,
        dict,
        side_effect=True,
        principals=frozenset({PrincipalType.ACCOUNT}),
    )
    api = ApplicationAPI(host, operations=[read_op, write_op, account_op])
    host.application_api = api
    return api


@pytest.mark.asyncio
async def test_processor_invoking_allowed_operations_succeeds(host):
    api = build_test_api(host)
    ctx = await build_processor_request_context(
        host,
        workspace_uuid='workspace-a',
        processor_kind='agent',
        processor_uuid='agent-uuid-123',
        run_id='run-uuid-456',
        operation_ids=['bot.list', 'bot.create'],
        trigger_actor='im-user-789',
    )
    assert ctx.auth_type == 'processor'
    assert ctx.principal.principal_type == PrincipalType.PROCESSOR
    assert ctx.principal.processor_kind == 'agent'
    assert ctx.principal.processor_uuid == 'agent-uuid-123'
    assert ctx.principal.run_id == 'run-uuid-456'
    assert ctx.principal.trigger_actor == 'im-user-789'
    assert ctx.allowed_operation_ids == frozenset({'bot.list', 'bot.create'})
    assert ctx.workspace.role is None
    assert ctx.workspace.membership_uuid is None
    assert Permission.RESOURCE_VIEW.value in ctx.workspace.permissions
    assert Permission.RESOURCE_MANAGE.value in ctx.workspace.permissions

    read_result = await api.execute('bot.list', ctx, {})
    assert read_result == []

    write_result = await api.execute('bot.create', ctx, {'item_id': 'custom-item'})
    assert write_result == {}


@pytest.mark.asyncio
async def test_processor_invoking_disallowed_operation_is_denied(host):
    api = build_test_api(host)
    ctx = await build_processor_request_context(
        host,
        workspace_uuid='workspace-a',
        processor_kind='pipeline',
        processor_uuid='pipeline-uuid-123',
        run_id='run-uuid-456',
        operation_ids=['bot.list'],
    )
    with pytest.raises(ApplicationAPIException) as exc_info:
        await api.execute('bot.create', ctx, {})
    assert exc_info.value.error.code == 'permission_denied'
    assert exc_info.value.error.status_code == 403


@pytest.mark.asyncio
async def test_processor_with_none_allowed_operation_ids_is_rejected(host):
    api = build_test_api(host)
    principal = PrincipalContext(
        principal_type=PrincipalType.PROCESSOR,
        processor_kind='event_processor',
        processor_uuid='processor-123',
        run_id='run-456',
    )
    workspace = WorkspaceContext(
        workspace_uuid='workspace-a',
        membership_uuid=None,
        role=None,
        permissions=frozenset({Permission.RESOURCE_VIEW.value}),
    )
    ctx = RequestContext(
        instance_uuid='instance-a',
        placement_generation=1,
        request_id='req-123',
        auth_type='processor',
        principal=principal,
        workspace=workspace,
        allowed_operation_ids=None,
    )
    with pytest.raises(ApplicationAPIException) as exc_info:
        await api.execute('bot.list', ctx, {})
    assert exc_info.value.error.code == 'permission_denied'
    assert exc_info.value.error.status_code == 403


@pytest.mark.asyncio
async def test_processor_invoking_account_only_operation_is_denied(host):
    api = build_test_api(host)
    ctx = await build_processor_request_context(
        host,
        workspace_uuid='workspace-a',
        processor_kind='agent',
        processor_uuid='agent-123',
        run_id='run-456',
        operation_ids=['account.only'],
    )
    with pytest.raises(ApplicationAPIException) as exc_info:
        await api.execute('account.only', ctx, {})
    assert exc_info.value.error.code == 'invalid_authentication'
    assert exc_info.value.error.status_code == 401


@pytest.mark.asyncio
async def test_cross_workspace_and_expired_generation_fail(host):
    api = build_test_api(host)
    ctx = await build_processor_request_context(
        host,
        workspace_uuid='workspace-a',
        processor_kind='agent',
        processor_uuid='agent-123',
        run_id='run-456',
        operation_ids=['bot.list'],
    )
    # 1. Wrong instance
    wrong_instance_ctx = dataclasses.replace(ctx, instance_uuid='foreign-instance')
    with pytest.raises(ApplicationAPIException) as exc_info:
        await api.execute('bot.list', wrong_instance_ctx, {})
    assert exc_info.value.error.code == 'invalid_authentication'
    assert exc_info.value.error.status_code == 401

    # 2. Expired generation
    host.workspace_service.get_execution_binding.side_effect = WorkspaceExecutionUnavailableError(
        'Workspace generation expired'
    )
    with pytest.raises(ApplicationAPIException) as exc_info:
        await api.execute('bot.list', ctx, {})
    assert exc_info.value.error.code == 'workspace_unavailable'
    assert exc_info.value.error.status_code == 409


@pytest.mark.asyncio
async def test_processor_write_operation_emits_audit_with_processor_and_run_id(host):
    api = build_test_api(host)
    host.workspace_settings_service.effective_level.return_value = OPERATION_LEVEL_MUTATION
    ctx = await build_processor_request_context(
        host,
        workspace_uuid='workspace-a',
        processor_kind='agent',
        processor_uuid='agent-uuid-777',
        run_id='run-uuid-888',
        operation_ids=['bot.create'],
        trigger_actor='im-user-999',
    )
    await api.execute('bot.create', ctx, {'item_id': 'bot-item-1'})

    host.workspace_settings_service.record.assert_awaited_once()
    kwargs = host.workspace_settings_service.record.await_args.kwargs
    assert kwargs['rule'].bucket == 'write'
    assert kwargs['rule'].action == 'create'
    assert kwargs['principal_type'] == 'processor'
    assert kwargs['actor_name'] == 'agent:agent-uuid-777'
    assert kwargs['actor_account_uuid'] is None
    assert kwargs['actor_role'] is None
    assert kwargs['dedupe_actor'] == 'processor:agent-uuid-777:run-uuid-888'
    assert kwargs['detail']['processor_kind'] == 'agent'
    assert kwargs['detail']['processor_uuid'] == 'agent-uuid-777'
    assert kwargs['detail']['run_id'] == 'run-uuid-888'
    assert kwargs['detail']['trigger_actor'] == 'im-user-999'
    assert kwargs['outcome'] == 'ok'
    assert kwargs['status_code'] == 200


@pytest.mark.asyncio
async def test_existing_principal_behavior_is_preserved_with_allowed_operation_ids(host):
    api = build_test_api(host)
    account_ctx = RequestContext(
        instance_uuid='instance-a',
        placement_generation=1,
        request_id='req-account-1',
        auth_type='user-token',
        principal=PrincipalContext(PrincipalType.ACCOUNT, account_uuid='acc-1'),
        workspace=WorkspaceContext(
            workspace_uuid='workspace-a',
            membership_uuid='mem-1',
            role='developer',
            permissions=frozenset({Permission.RESOURCE_VIEW.value, Permission.RESOURCE_MANAGE.value}),
        ),
        allowed_operation_ids=None,
    )
    # Calling without allowed_operation_ids allows any permitted operation
    assert await api.execute('bot.list', account_ctx, {}) == []

    # If allowed_operation_ids is provided on account context, it is also enforced
    restricted_account_ctx = dataclasses.replace(
        account_ctx,
        allowed_operation_ids=frozenset({'bot.list'}),
    )
    assert await api.execute('bot.list', restricted_account_ctx, {}) == []
    with pytest.raises(ApplicationAPIException) as exc_info:
        await api.execute('bot.create', restricted_account_ctx, {'item_id': 'b'})
    assert exc_info.value.error.code == 'permission_denied'


@pytest.mark.asyncio
async def test_processor_context_builder_validates_inputs(host):
    # Invalid processor_kind
    with pytest.raises(ValueError, match='Invalid processor_kind'):
        await build_processor_request_context(
            host,
            workspace_uuid='workspace-a',
            processor_kind='unknown_kind',
            processor_uuid='uuid-1',
            run_id='run-1',
            operation_ids=['bot.list'],
        )

    # Empty processor_uuid
    with pytest.raises(ValueError, match='processor_uuid is required'):
        await build_processor_request_context(
            host,
            workspace_uuid='workspace-a',
            processor_kind='agent',
            processor_uuid='   ',
            run_id='run-1',
            operation_ids=['bot.list'],
        )

    # Empty run_id
    with pytest.raises(ValueError, match='run_id is required'):
        await build_processor_request_context(
            host,
            workspace_uuid='workspace-a',
            processor_kind='agent',
            processor_uuid='uuid-1',
            run_id='',
            operation_ids=['bot.list'],
        )

    # Empty workspace_uuid
    with pytest.raises(ValueError, match='workspace_uuid is required'):
        await build_processor_request_context(
            host,
            workspace_uuid='  ',
            processor_kind='agent',
            processor_uuid='uuid-1',
            run_id='run-1',
            operation_ids=['bot.list'],
        )


def test_dedupe_material_isolates_processors_and_runs_while_preserving_accounts():
    # 1. Two different processors on same resource and action produce different materials and keys
    mat_proc_a = dedupe_material(
        actor_account_uuid=None,
        action='update',
        route='bot.update',
        resource_id='bot-1',
        dedupe_actor='processor:agent-A:run-1',
    )
    mat_proc_b = dedupe_material(
        actor_account_uuid=None,
        action='update',
        route='bot.update',
        resource_id='bot-1',
        dedupe_actor='processor:agent-B:run-1',
    )
    assert mat_proc_a == 'processor:agent-A:run-1|update|bot.update|bot-1'
    assert mat_proc_b == 'processor:agent-B:run-1|update|bot.update|bot-1'
    assert mat_proc_a != mat_proc_b
    assert hash_dedupe_material(mat_proc_a) != hash_dedupe_material(mat_proc_b)

    # 2. Same processor across two different runs produces different materials and keys
    mat_run_1 = dedupe_material(
        actor_account_uuid=None,
        action='update',
        route='bot.update',
        resource_id='bot-1',
        dedupe_actor='processor:agent-A:run-1',
    )
    mat_run_2 = dedupe_material(
        actor_account_uuid=None,
        action='update',
        route='bot.update',
        resource_id='bot-1',
        dedupe_actor='processor:agent-A:run-2',
    )
    assert mat_run_1 != mat_run_2
    assert compute_dedupe_key(
        actor_account_uuid=None,
        action='update',
        route='bot.update',
        resource_id='bot-1',
        dedupe_actor='processor:agent-A:run-1',
    ) != compute_dedupe_key(
        actor_account_uuid=None,
        action='update',
        route='bot.update',
        resource_id='bot-1',
        dedupe_actor='processor:agent-A:run-2',
    )

    # 3. Account identity behavior is strictly preserved
    mat_acc = dedupe_material(
        actor_account_uuid='acc-123',
        action='update',
        route='bot.update',
        resource_id='bot-1',
    )
    assert mat_acc == 'acc-123|update|bot.update|bot-1'


@pytest.mark.asyncio
async def test_distinct_processors_and_runs_pass_unique_dedupe_actors_to_service_record(host):
    api = build_test_api(host)
    host.workspace_settings_service.effective_level.return_value = OPERATION_LEVEL_MUTATION

    ctx_run1 = await build_processor_request_context(
        host,
        workspace_uuid='workspace-a',
        processor_kind='agent',
        processor_uuid='agent-1',
        run_id='run-1',
        operation_ids=['bot.create'],
    )
    ctx_run2 = await build_processor_request_context(
        host,
        workspace_uuid='workspace-a',
        processor_kind='agent',
        processor_uuid='agent-1',
        run_id='run-2',
        operation_ids=['bot.create'],
    )
    ctx_proc2 = await build_processor_request_context(
        host,
        workspace_uuid='workspace-a',
        processor_kind='pipeline',
        processor_uuid='pipeline-2',
        run_id='run-1',
        operation_ids=['bot.create'],
    )

    await api.execute('bot.create', ctx_run1, {'item_id': 'bot-item-1'})
    dedupe_actor_1 = host.workspace_settings_service.record.await_args.kwargs['dedupe_actor']

    host.workspace_settings_service.record.reset_mock()
    await api.execute('bot.create', ctx_run2, {'item_id': 'bot-item-1'})
    dedupe_actor_2 = host.workspace_settings_service.record.await_args.kwargs['dedupe_actor']

    host.workspace_settings_service.record.reset_mock()
    await api.execute('bot.create', ctx_proc2, {'item_id': 'bot-item-1'})
    dedupe_actor_3 = host.workspace_settings_service.record.await_args.kwargs['dedupe_actor']

    assert dedupe_actor_1 == 'processor:agent-1:run-1'
    assert dedupe_actor_2 == 'processor:agent-1:run-2'
    assert dedupe_actor_3 == 'processor:pipeline-2:run-1'
    assert len({dedupe_actor_1, dedupe_actor_2, dedupe_actor_3}) == 3
