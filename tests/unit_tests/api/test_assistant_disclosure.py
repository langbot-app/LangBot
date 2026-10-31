"""Unit tests for workspace assistant progressive disclosure meta tools."""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from langbot_plugin.api.entities.builtin.provider.message import Message

from langbot.pkg.api.application.api import ApplicationAPI
from langbot.pkg.api.http.authz import Permission
from langbot.pkg.api.http.context import (
    PrincipalContext,
    PrincipalType,
    RequestContext,
    WorkspaceContext,
)
from langbot.pkg.api.http.service.assistant import AssistantService
from langbot.pkg.api.http.service.assistant_disclosure import (
    build_system_prompt,
    format_domains_overview,
    is_write,
    workspace_call,
    workspace_describe,
    workspace_search,
)
from langbot.pkg.api.http.service.assistant_tools import (
    TOOLS,
    tool_definitions,
)
from langbot.pkg.entity.persistence.assistant import AssistantConversation


def make_context(manage: bool = True, audit: bool = False) -> RequestContext:
    permissions = {Permission.RESOURCE_VIEW.value, Permission.RUNTIME_OPERATE.value}
    if manage:
        permissions.add(Permission.RESOURCE_MANAGE.value)
    if audit:
        permissions.add(Permission.AUDIT_VIEW.value)
    return RequestContext(
        instance_uuid='test-instance',
        placement_generation=1,
        request_id='req-1',
        auth_type='user-token',
        principal=PrincipalContext(PrincipalType.ACCOUNT, account_uuid='alice'),
        workspace=WorkspaceContext('ws-1', None, 'developer', frozenset(permissions)),
    )


@pytest.fixture
def mock_app():
    @asynccontextmanager
    async def tenant_scope(workspace):
        yield

    copy_mock = AsyncMock(return_value='copied-pipeline-uuid')
    delete_mock = AsyncMock(return_value=None)
    get_pipelines_mock = AsyncMock(
        return_value=[
            {
                'uuid': 'pipe-1',
                'name': 'Main Pipeline',
                'description': 'Production pipeline',
            }
        ]
    )
    get_bots_mock = AsyncMock(return_value=[{'uuid': 'bot-1', 'name': 'Bot 1', 'pipeline_uuid': 'pipe-1'}])

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
        pipeline_service=SimpleNamespace(
            get_pipelines=get_pipelines_mock,
            copy_pipeline=copy_mock,
            delete_pipeline=delete_mock,
        ),
        bot_service=SimpleNamespace(
            get_bots=get_bots_mock,
        ),
    )
    api = ApplicationAPI(host)
    host.application_api = api
    return host


# 1. 工具名不重复
def test_tool_names_not_duplicated():
    ctx = make_context(manage=True, audit=True)
    defs = tool_definitions(ctx)
    names = [tool.name for tool in defs]

    assert len(names) == len(set(names)), f'Tool names contain duplicates: {names}'
    assert len(names) == 10

    original_tools = {
        'list_resources',
        'get_pipeline',
        'get_knowledge_schema',
        'list_operation_logs',
        'create_pipeline',
        'configure_pipeline',
        'create_knowledge_base',
    }
    meta_tools = {'workspace_search', 'workspace_describe', 'workspace_call'}

    assert original_tools.issubset(set(names))
    assert meta_tools.issubset(set(names))
    assert original_tools.isdisjoint(meta_tools)
    assert set(TOOLS.keys()) == (original_tools | meta_tools)


# 2. 只有 view 权限的成员搜不到写操作
def test_view_only_member_cannot_search_write_operations(mock_app):
    view_ctx = make_context(manage=False)
    manage_ctx = make_context(manage=True)

    # View-only search
    view_ops = workspace_search(mock_app, view_ctx, limit=10)
    assert len(view_ops) > 0
    for op in view_ops:
        assert op['risk'] == 'read', f'Expected only read operations, found {op["id"]} with risk {op["risk"]}'

    # Specifically search for write operation
    copy_view = workspace_search(mock_app, view_ctx, query='copy')
    assert not any(op['id'] == 'pipeline.copy' for op in copy_view)

    # Manage search can find write operation
    copy_manage = workspace_search(mock_app, manage_ctx, query='copy')
    assert any(op['id'] == 'pipeline.copy' for op in copy_manage)
    copy_op = next(op for op in copy_manage if op['id'] == 'pipeline.copy')
    assert copy_op['risk'] == 'write'


# 3. 调用 exposure == 'none' 的操作返回 not_found
@pytest.mark.asyncio
async def test_calling_exposure_none_returns_not_found(mock_app):
    ctx = make_context(manage=True)

    # monitoring.export.query is exposure='none'
    res_export = await workspace_call(mock_app, ctx, operation_id='monitoring.export.query')
    assert res_export['ok'] is False
    assert res_export['error']['code'] == 'not_found'

    # workspace.list is out of scope (exposure='none')
    res_workspace = await workspace_call(mock_app, ctx, operation_id='workspace.list')
    assert res_workspace['ok'] is False
    assert res_workspace['error']['code'] == 'not_found'

    # Non-existent operation
    res_invalid = await workspace_call(mock_app, ctx, operation_id='non_existent.operation')
    assert res_invalid['ok'] is False
    assert res_invalid['error']['code'] == 'not_found'


# 4. 结果被截断
@pytest.mark.asyncio
async def test_workspace_call_truncation(mock_app):
    ctx = make_context(manage=True)
    # Inject large response (> 16000 chars)
    mock_app.pipeline_service.get_pipelines.return_value = [{'id': f'pipe-{i}', 'data': 'x' * 2000} for i in range(15)]

    res = await workspace_call(mock_app, ctx, operation_id='pipeline.list')
    assert res.get('truncated') is True
    assert 'preview' in res
    assert len(res['preview']) == 16000
    assert 'hint' in res


# 5. workspace_describe 功能测试
def test_workspace_describe(mock_app):
    ctx = make_context(manage=True)
    desc = workspace_describe(mock_app, ctx, operation_id='pipeline.copy')
    assert desc['id'] == 'pipeline.copy'
    assert desc['risk'] == 'write'
    assert 'input_schema' in desc
    assert 'properties' in desc['input_schema']
    assert 'pipeline_uuid' in desc['input_schema']['properties']

    # Exposure='none' should return error
    desc_hidden = workspace_describe(mock_app, ctx, operation_id='workspace.list')
    assert 'error' in desc_hidden


# 6. is_write 逻辑测试
def test_is_write_logic():
    # Original tools
    assert is_write('create_pipeline') is True
    assert is_write('configure_pipeline') is True
    assert is_write('get_pipeline') is False
    assert is_write('list_resources') is False

    # Meta search / describe
    assert is_write('workspace_search', {'query': 'test'}) is False
    assert is_write('workspace_describe', {'operation_id': 'pipeline.copy'}) is False

    # Meta call
    assert is_write('workspace_call', {'operation_id': 'pipeline.copy'}) is True
    assert is_write('workspace_call', {'operation_id': 'pipeline.delete'}) is True
    assert is_write('workspace_call', {'operation_id': 'pipeline.list'}) is False
    assert is_write('workspace_call', {'operation_id': 'bot.list'}) is False


# 7. 领域概览与 SYSTEM_PROMPT 测试 (≤1500 字符，无过时表述)
def test_domains_overview_and_system_prompt(mock_app):
    ctx = make_context(manage=True)
    prompt = build_system_prompt(mock_app, ctx)

    # Obsolete phrases removed
    assert 'Use only the provided management tools' not in prompt
    assert 'this experiment has no chat-test or upload tool yet' not in prompt

    # Progressive disclosure and dedicated tool guidance present
    assert '先 search，再 describe，最后 call' in prompt
    assert 'configure_pipeline' in prompt
    assert 'list_operation_logs' in prompt

    # Overview length constraint
    from langbot.pkg.api.application.granted_operations import (
        domains,
        list_granted,
    )

    ops = list_granted(mock_app, ctx, consumer='assistant')
    domain_list = domains(ops)
    overview = format_domains_overview(domain_list, max_chars=1500)
    assert len(overview) <= 1500
    assert 'Available workspace capability domains:' in overview


# 8. 端到端审批和拒绝：workspace_call 写操作进入 approval，读操作直接执行，用户拒绝不执行
@pytest.fixture
async def assistant_env(tmp_path, mock_app):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path}/test_adj.db')
    metadata = sa.MetaData()
    sa.Table('users', metadata, sa.Column('uuid', sa.String, primary_key=True))
    sa.Table('workspaces', metadata, sa.Column('uuid', sa.String, primary_key=True))
    AssistantConversation.__table__.to_metadata(metadata)
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)

    async def execute(statement):
        async with engine.begin() as connection:
            return await connection.execute(statement)

    mock_app.persistence_mgr.execute_async = execute

    provider = SimpleNamespace(invoke_llm=AsyncMock())
    model = SimpleNamespace(
        provider=provider,
        model_entity=SimpleNamespace(name='test-model', abilities=['func_call'], extra_args={}),
    )
    mock_app.space_service = SimpleNamespace(get_recommended_assistant_model=AsyncMock(return_value={'uuid': 'model'}))
    mock_app.model_mgr = SimpleNamespace(get_model_by_uuid=AsyncMock(return_value=model))
    mock_app.logger = logging.getLogger('assistant-test')

    service = AssistantService(mock_app)
    yield service, mock_app, provider
    await engine.dispose()


@pytest.mark.asyncio
async def test_workspace_call_write_approval_and_read_direct(assistant_env):
    service, app, provider = assistant_env
    ctx = make_context(manage=True)

    # 1. Write operation enters approval
    write_msg = Message.model_validate(
        {
            'role': 'assistant',
            'content': 'I will copy the pipeline.',
            'tool_calls': [
                {
                    'id': 'call-copy',
                    'type': 'function',
                    'function': {
                        'name': 'workspace_call',
                        'arguments': '{"operation_id": "pipeline.copy", "arguments": {"pipeline_uuid": "pipe-1"}}',
                    },
                }
            ],
        }
    )
    provider.invoke_llm.side_effect = [
        write_msg,
        Message(role='assistant', content='Copy complete'),
    ]

    conv = await service.create(ctx)
    res = await service.turn(ctx, conv['uuid'], 0, text='Copy pipeline')
    assert res['status'] == 'approval'
    app.pipeline_service.copy_pipeline.assert_not_awaited()

    # Verify public_view enrichment
    view = service.public_view(res)
    assert len(view['pending']) == 1
    pending_item = view['pending'][0]
    assert pending_item['name'] == 'workspace_call'
    assert pending_item['arguments']['operation_id'] == 'pipeline.copy'
    assert pending_item['operation']['id'] == 'pipeline.copy'
    assert pending_item['operation']['risk'] == 'write'
    assert pending_item['operation']['label']['zh_Hans'] == '复制流水线'

    # 2. User approves -> executes
    res_approve = await service.turn(ctx, conv['uuid'], 1, approved=True)
    assert res_approve['status'] == 'ready'
    app.pipeline_service.copy_pipeline.assert_awaited_once()

    # 3. Read operation executes directly without approval
    read_msg = Message.model_validate(
        {
            'role': 'assistant',
            'content': 'Listing pipelines.',
            'tool_calls': [
                {
                    'id': 'call-list',
                    'type': 'function',
                    'function': {
                        'name': 'workspace_call',
                        'arguments': '{"operation_id": "pipeline.list", "arguments": {}}',
                    },
                }
            ],
        }
    )
    provider.invoke_llm.side_effect = [
        read_msg,
        Message(role='assistant', content='Listed'),
    ]

    conv_read = await service.create(ctx)
    res_read = await service.turn(ctx, conv_read['uuid'], 0, text='List pipelines')
    assert res_read['status'] == 'ready'
    app.pipeline_service.get_pipelines.assert_awaited()


@pytest.mark.asyncio
async def test_workspace_call_user_decline_does_not_execute(assistant_env):
    service, app, provider = assistant_env
    ctx = make_context(manage=True)

    write_msg = Message.model_validate(
        {
            'role': 'assistant',
            'content': 'I will copy the pipeline.',
            'tool_calls': [
                {
                    'id': 'call-copy',
                    'type': 'function',
                    'function': {
                        'name': 'workspace_call',
                        'arguments': '{"operation_id": "pipeline.copy", "arguments": {"pipeline_uuid": "pipe-1"}}',
                    },
                }
            ],
        }
    )
    provider.invoke_llm.side_effect = [
        write_msg,
        Message(role='assistant', content='Understood, cancelled.'),
    ]

    conv = await service.create(ctx)
    res = await service.turn(ctx, conv['uuid'], 0, text='Copy pipeline')
    assert res['status'] == 'approval'

    # User declines
    res_decline = await service.turn(ctx, conv['uuid'], 1, approved=False)
    assert res_decline['status'] == 'ready'
    app.pipeline_service.copy_pipeline.assert_not_awaited()

    # Tool message reflects denial
    tool_msg = next(m for m in service.public_view(res_decline)['messages'] if m['role'] == 'tool')
    assert tool_msg['tool']['result']['status'] == 'denied'
