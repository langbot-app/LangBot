"""Unit tests for granted operations access layer."""

from __future__ import annotations

import json
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.application.api import ApplicationAPI
from langbot.pkg.api.application.contracts import Input, Operation
from langbot.pkg.api.application.granted_operations import (
    GrantedOperation,
    call,
    domains,
    list_granted,
    requires_confirmation,
)
from langbot.pkg.api.authz import Permission
from langbot.pkg.api.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext


class DummyPayload(Input):
    item_id: str = 'item-1'


class DummySecretInput(Input):
    resource_uuid: str
    include_secret: bool = False


@pytest.fixture
def mock_host(monkeypatch):
    monkeypatch.setattr('langbot.pkg.api.application.api.get_workspace_language', AsyncMock(return_value='en_US'))

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def tenant_scope(workspace):
        yield

    host = SimpleNamespace(
        persistence_mgr=SimpleNamespace(tenant_scope=tenant_scope),
        workspace_service=SimpleNamespace(
            get_execution_binding=AsyncMock(
                return_value=SimpleNamespace(instance_uuid='test-instance', placement_generation=1)
            )
        ),
        workspace_settings_service=SimpleNamespace(
            effective_level=AsyncMock(return_value=1),
            record=AsyncMock(),
        ),
        logger=Mock(),
    )
    return host


def make_account_context(permissions: frozenset[str]) -> RequestContext:
    return RequestContext(
        instance_uuid='test-instance',
        placement_generation=1,
        request_id='req-1',
        auth_type='cookie',
        principal=PrincipalContext(
            principal_type=PrincipalType.ACCOUNT,
            account_uuid='acc-1',
        ),
        workspace=WorkspaceContext(
            workspace_uuid='ws-1',
            membership_uuid='mem-1',
            role='developer',
            permissions=permissions,
        ),
    )


# 1. 两种调用方的过滤规则
def test_assistant_filtering_rules(mock_host):
    api = ApplicationAPI(mock_host)
    mock_host.application_api = api

    # Member with only RESOURCE_VIEW permission
    view_only_context = make_account_context(frozenset({Permission.RESOURCE_VIEW.value}))
    granted_ops = list_granted(mock_host, view_only_context, consumer='assistant')
    granted_ids = {op.id for op in granted_ops}

    # Should include in-scope read operations with exposure in {'assistant', 'all'}
    assert 'bot.list' in granted_ids
    assert 'agent.list' in granted_ids
    # pipeline.migration.preview is exposure='assistant', requires RESOURCE_VIEW, account principal -> should be included!
    assert 'pipeline.migration.preview' in granted_ids

    # Should NOT include operations requiring RESOURCE_MANAGE
    assert 'bot.create' not in granted_ids
    assert 'bot.delete' not in granted_ids

    # Should NOT include operations with exposure='none' (e.g. streaming, out-of-scope)
    assert 'agent.debug.stream' not in granted_ids
    assert 'workspace.member.remove' not in granted_ids

    # Member with RESOURCE_MANAGE added
    manage_context = make_account_context(frozenset({Permission.RESOURCE_VIEW.value, Permission.RESOURCE_MANAGE.value}))
    granted_manage = list_granted(mock_host, manage_context, consumer='assistant')
    granted_manage_ids = {op.id for op in granted_manage}
    assert 'bot.create' in granted_manage_ids
    assert 'bot.delete' in granted_manage_ids


def test_processor_filtering_rules(mock_host, caplog):
    api = ApplicationAPI(mock_host)
    mock_host.application_api = api

    processor_context = RequestContext(
        instance_uuid='test-instance',
        placement_generation=1,
        request_id='req-proc',
        auth_type='processor',
        principal=PrincipalContext(
            principal_type=PrincipalType.PROCESSOR,
            processor_kind='agent',
            processor_uuid='agent-1',
            run_id='run-1',
        ),
        workspace=WorkspaceContext(
            workspace_uuid='ws-1',
            membership_uuid=None,
            role=None,
            permissions=frozenset({Permission.RESOURCE_VIEW.value, Permission.RESOURCE_MANAGE.value}),
        ),
        allowed_operation_ids=frozenset({'bot.list'}),
    )

    requested_granted = [
        'bot.list',  # exposure == 'all' -> kept
        'agent.create',  # exposure == 'all' -> kept
        'mcp.server.create',  # exposure == 'assistant' -> discarded
        'pipeline.migration.preview',  # exposure == 'assistant' -> discarded
        'agent.debug.stream',  # streaming -> discarded
        'nonexistent.operation.id',  # unknown -> discarded
    ]

    import logging

    with caplog.at_level(logging.WARNING):
        granted_ops = list_granted(mock_host, processor_context, consumer='processor', granted=requested_granted)

    granted_ids = [op.id for op in granted_ops]
    assert granted_ids == ['bot.list', 'agent.create']

    # Verify warning logged for discarded operations
    assert 'Discarded' in caplog.text
    assert 'mcp.server.create' in caplog.text
    assert 'nonexistent.operation.id' in caplog.text


def test_processor_fallback_to_context_allowed_operation_ids(mock_host):
    api = ApplicationAPI(mock_host)
    mock_host.application_api = api

    processor_context = RequestContext(
        instance_uuid='test-instance',
        placement_generation=1,
        request_id='req-proc',
        auth_type='processor',
        principal=PrincipalContext(
            principal_type=PrincipalType.PROCESSOR,
            processor_kind='agent',
            processor_uuid='agent-1',
            run_id='run-1',
        ),
        workspace=WorkspaceContext(
            workspace_uuid='ws-1',
            membership_uuid=None,
            role=None,
            permissions=frozenset({Permission.RESOURCE_VIEW.value}),
        ),
        allowed_operation_ids=frozenset({'bot.list', 'model.llm.list'}),
    )

    # granted=None -> falls back to context.allowed_operation_ids
    ops = list_granted(mock_host, processor_context, consumer='processor', granted=None)
    assert {op.id for op in ops} == {'bot.list', 'model.llm.list'}


# 2. include_secret 被去掉
def test_include_secret_stripped_from_schema(mock_host):
    api = ApplicationAPI(mock_host)
    mock_host.application_api = api

    context = make_account_context(frozenset({Permission.RESOURCE_VIEW.value}))
    ops = list_granted(mock_host, context, consumer='assistant')

    # Find bot.get, which defines include_secret in its original Input schema
    bot_get_op = next((op for op in ops if op.id == 'bot.get'), None)
    assert bot_get_op is not None
    assert 'include_secret' not in bot_get_op.input_schema.get('properties', {})
    assert 'include_secret' not in bot_get_op.input_schema.get('required', [])

    # Find model.llm.get
    llm_get_op = next((op for op in ops if op.id == 'model.llm.get'), None)
    assert llm_get_op is not None
    assert 'include_secret' not in llm_get_op.input_schema.get('properties', {})
    assert 'include_secret' not in llm_get_op.input_schema.get('required', [])


@pytest.mark.asyncio
async def test_include_secret_stripped_from_call_arguments(mock_host):
    received_args = {}

    async def mock_handler(ap, ctx, payload):
        received_args.update(payload.model_dump())
        return {'uuid': payload.bot_uuid, 'token': 'mock-secret-token'}

    class DummyBotGetInput(Input):
        bot_uuid: str
        include_secret: bool = False

    test_op = Operation(
        'bot.get',
        Permission.RESOURCE_VIEW,
        mock_handler,
        DummyBotGetInput,
        dict,
        side_effect=False,
    )
    api = ApplicationAPI(mock_host, operations=[test_op])
    mock_host.application_api = api

    ctx = make_account_context(frozenset({Permission.RESOURCE_VIEW.value}))
    res = await call(
        mock_host,
        ctx,
        'bot.get',
        {'bot_uuid': 'bot-123', 'include_secret': True},
        consumer='assistant',
    )
    assert res['ok'] is True
    # Verify handler received arguments without include_secret
    assert received_args == {'bot_uuid': 'bot-123', 'include_secret': False}


# 3. 不在允许列表里的操作返回 not_found
@pytest.mark.asyncio
async def test_not_found_for_disallowed_or_unknown_operations(mock_host):
    api = ApplicationAPI(mock_host)
    mock_host.application_api = api

    ctx = make_account_context(frozenset({Permission.RESOURCE_VIEW.value}))

    # 1. Operation exists, but member lacks permission (bot.create requires RESOURCE_MANAGE)
    res1 = await call(mock_host, ctx, 'bot.create', {'bot_data': {}}, consumer='assistant')
    assert res1['ok'] is False
    assert res1['error']['code'] == 'not_found'
    assert 'Operation not found' in res1['error']['message']

    # 2. Operation exists, but exposure is 'none' (workspace.member.remove)
    res2 = await call(mock_host, ctx, 'workspace.member.remove', {'account_uuid': 'acc-2'}, consumer='assistant')
    assert res2['ok'] is False
    assert res2['error']['code'] == 'not_found'

    # 3. Completely non-existent operation
    res3 = await call(mock_host, ctx, 'completely.fake.op', {}, consumer='assistant')
    assert res3['ok'] is False
    assert res3['error']['code'] == 'not_found'

    # 4. Processor calling operation not in granted list
    proc_ctx = RequestContext(
        instance_uuid='test-instance',
        placement_generation=1,
        request_id='req-proc',
        auth_type='processor',
        principal=PrincipalContext(
            principal_type=PrincipalType.PROCESSOR,
            processor_kind='agent',
            processor_uuid='agent-1',
            run_id='run-1',
        ),
        workspace=WorkspaceContext(
            workspace_uuid='ws-1',
            membership_uuid=None,
            role=None,
            permissions=frozenset({Permission.RESOURCE_VIEW.value}),
        ),
        allowed_operation_ids=frozenset({'bot.list'}),
    )
    res4 = await call(mock_host, proc_ctx, 'agent.list', {}, consumer='processor', granted=['bot.list'])
    assert res4['ok'] is False
    assert res4['error']['code'] == 'not_found'


# 4. 结果经过脱敏
@pytest.mark.asyncio
async def test_result_secrets_redacted(mock_host):
    async def mock_handler(ap, ctx, payload):
        return {
            'id': 'bot-1',
            'api_key': 'super-secret-key-999',
            'nested': {
                'token': 'bearer-secret-token',
                'name': 'public-name',
            },
        }

    test_op = Operation(
        'bot.get',
        Permission.RESOURCE_VIEW,
        mock_handler,
        Input,
        dict,
        side_effect=False,
    )
    api = ApplicationAPI(mock_host, operations=[test_op])
    mock_host.application_api = api

    ctx = make_account_context(frozenset({Permission.RESOURCE_VIEW.value}))
    res = await call(mock_host, ctx, 'bot.get', {}, consumer='assistant')

    assert res['ok'] is True
    assert res['result']['api_key'] == '***'
    assert res['result']['nested']['token'] == '***'
    assert res['result']['nested']['name'] == 'public-name'
    assert res['operation']['id'] == 'bot.get'
    assert res['operation']['risk'] == 'read'
    assert res['operation']['side_effect'] is False


# 5. 错误信息里没有输入值
@pytest.mark.asyncio
async def test_error_message_does_not_contain_input_values(mock_host):
    async def failing_handler(ap, ctx, payload):
        # Service throws an error that echoes input parameters
        raise ValueError(f'Item {payload.item_id} not found in partition secret_cluster_xyz')

    test_op = Operation(
        'bot.delete',
        Permission.RESOURCE_MANAGE,
        failing_handler,
        DummyPayload,
        dict,
        side_effect=True,
    )
    api = ApplicationAPI(mock_host, operations=[test_op])
    mock_host.application_api = api

    ctx = make_account_context(frozenset({Permission.RESOURCE_MANAGE.value}))
    sensitive_input = 'my-sensitive-token-12345'
    res = await call(
        mock_host,
        ctx,
        'bot.delete',
        {'item_id': sensitive_input},
        consumer='assistant',
    )
    assert res['ok'] is False
    assert sensitive_input not in res['error']['message']
    assert '[REDACTED]' in res['error']['message']


# 6. domains 的统计结果
def test_domains_aggregation(mock_host):
    api = ApplicationAPI(mock_host)
    mock_host.application_api = api

    ctx = make_account_context(frozenset({Permission.RESOURCE_VIEW.value, Permission.RESOURCE_MANAGE.value}))
    granted_ops = list_granted(mock_host, ctx, consumer='assistant')

    domain_summary = domains(granted_ops)
    assert isinstance(domain_summary, list)
    assert len(domain_summary) > 0

    total_counted = sum(d['count'] for d in domain_summary)
    assert total_counted == len(granted_ops)

    # Check structure
    for d in domain_summary:
        assert 'domain' in d
        assert 'label' in d
        assert 'zh_Hans' in d['label'] and 'en_US' in d['label']
        assert 'summary' in d
        assert 'count' in d
        assert d['count'] > 0

    # Empty list
    assert domains([]) == []


def test_requires_confirmation():
    # Read operations -> False
    assert requires_confirmation('bot.list') is False
    assert requires_confirmation('model.llm.get') is False

    # Write / dangerous operations -> True
    assert requires_confirmation('bot.create') is True
    assert requires_confirmation('bot.delete') is True

    # With dict or object
    assert requires_confirmation({'risk': 'read'}) is False
    assert requires_confirmation({'risk': 'write'}) is True
    assert requires_confirmation({'risk': 'dangerous'}) is True


def test_granted_operation_serialization():
    op = GrantedOperation(
        id='test.op',
        domain='test',
        label={'zh_Hans': '测试', 'en_US': 'Test'},
        summary='Test summary',
        description='Test description',
        risk='read',
        side_effect=False,
        permission='resource.view',
        input_schema={'type': 'object', 'properties': {}},
        output_schema={'type': 'object'},
    )
    # Direct serialization via json.dumps(asdict(op))
    serialized = json.dumps(asdict(op), ensure_ascii=False)
    data = json.loads(serialized)
    assert data['id'] == 'test.op'
    assert data['label']['zh_Hans'] == '测试'

    # as_dict method
    assert op.as_dict() == data

    # Mapping access
    assert op['id'] == 'test.op'
    assert op.get('domain') == 'test'
    assert dict(op)['permission'] == 'resource.view'
