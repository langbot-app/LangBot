"""Exercise approval and isolation with real SQLite state and a scripted model boundary."""

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, create_autospec

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from langbot_plugin.api.entities.builtin.provider.message import Message

from langbot.pkg.api.http.authz import Permission
from langbot.pkg.api.http.context import RequestContext, PrincipalContext, PrincipalType, WorkspaceContext
from langbot.pkg.api.http.service.assistant import AssistantError, AssistantService
from langbot.pkg.api.http.service.assistant_tools import execute_tool, validate_call
from langbot.pkg.entity.persistence.assistant import AssistantConversation


def context(account='alice', workspace='workspace-a', manage=True):
    permissions = {Permission.RESOURCE_VIEW, Permission.RUNTIME_OPERATE}
    if manage:
        permissions.add(Permission.RESOURCE_MANAGE)
    return RequestContext(
        instance_uuid='instance',
        placement_generation=1,
        request_id='request',
        auth_type='user-token',
        principal=PrincipalContext(PrincipalType.ACCOUNT, account_uuid=account),
        workspace=WorkspaceContext(workspace, None, 'developer', frozenset(permissions)),
    )


def proposal():
    return Message.model_validate(
        {
            'role': 'assistant',
            'content': 'Create this draft?',
            'tool_calls': [
                {
                    'id': 'call-1',
                    'type': 'function',
                    'function': {
                        'name': 'create_pipeline',
                        'arguments': '{"name":"Demo","description":"Test draft"}',
                    },
                }
            ],
            'provider_specific_fields': {'thought_signature': 'preserved'},
        }
    )


@pytest.fixture
async def assistant(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path}/assistant.db')
    metadata = sa.MetaData()
    sa.Table('users', metadata, sa.Column('uuid', sa.String, primary_key=True))
    sa.Table('workspaces', metadata, sa.Column('uuid', sa.String, primary_key=True))
    AssistantConversation.__table__.to_metadata(metadata)
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)

    async def execute(statement):
        async with engine.begin() as connection:
            return await connection.execute(statement)

    provider = SimpleNamespace(
        invoke_llm=AsyncMock(side_effect=[proposal(), Message(role='assistant', content='Done')])
    )
    model = SimpleNamespace(
        provider=provider, model_entity=SimpleNamespace(name='test-model', abilities=['func_call'], extra_args={})
    )
    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(execute_async=execute),
        logger=logging.getLogger('assistant-test'),
        space_service=SimpleNamespace(get_recommended_chat_model=AsyncMock(return_value={'uuid': 'model'})),
        model_mgr=SimpleNamespace(get_model_by_uuid=AsyncMock(return_value=model)),
        pipeline_service=SimpleNamespace(create_pipeline=AsyncMock(return_value='created-pipeline')),
    )
    yield AssistantService(ap), ap, provider
    await engine.dispose()


@pytest.mark.asyncio
async def test_confirmation_is_exact_once_and_private(assistant):
    service, ap, provider = assistant
    ctx = context()
    conversation = await service.create(ctx)
    pending = await service.turn(ctx, conversation['uuid'], 0, text='Create a draft')
    assert pending['status'] == 'approval'
    ap.pipeline_service.create_pipeline.assert_not_awaited()
    assert service.public_view(pending)['pending'][0]['arguments']['name'] == 'Demo'
    for other in (context(account='bob'), context(workspace='workspace-b')):
        with pytest.raises(AssistantError, match='conversation_not_found'):
            await service.get(other, conversation['uuid'])
    results = await asyncio.gather(
        service.turn(ctx, conversation['uuid'], 1, approved=True),
        service.turn(ctx, conversation['uuid'], 1, approved=True),
        return_exceptions=True,
    )
    assert sum(isinstance(result, AssistantError) for result in results) == 1
    ap.pipeline_service.create_pipeline.assert_awaited_once()
    assert ap.pipeline_service.create_pipeline.call_args.args[1]['name'] == 'Demo'
    saved = await service.get(ctx, conversation['uuid'])
    assert saved['status'] == 'ready'
    assert saved['messages'][1]['provider_specific_fields']['thought_signature'] == 'preserved'
    assert provider.invoke_llm.call_args.kwargs['query'] is None
    assert provider.invoke_llm.call_args.kwargs['execution_context'].workspace_uuid == ctx.workspace_uuid
    tool_message = next(message for message in service.public_view(saved)['messages'] if message['role'] == 'tool')
    assert tool_message['tool'] == {
        'name': 'create_pipeline',
        'arguments': {'name': 'Demo', 'description': 'Test draft'},
        'result': {'uuid': 'created-pipeline', 'url': '/home/pipelines?id=created-pipeline', 'configured': False},
    }


@pytest.mark.asyncio
async def test_denial_and_revoked_write_permission(assistant):
    service, ap, provider = assistant
    ctx = context()
    conversation = await service.create(ctx)
    await service.turn(ctx, conversation['uuid'], 0, text='Create')
    denied = await service.turn(context(manage=False), conversation['uuid'], 1, approved=False)
    assert denied['status'] == 'ready'
    ap.pipeline_service.create_pipeline.assert_not_awaited()
    provider.invoke_llm.side_effect = [proposal()]
    second = await service.create(ctx)
    await service.turn(ctx, second['uuid'], 0, text='Create')
    failed = await service.turn(context(manage=False), second['uuid'], 1, approved=True)
    assert failed['status'] == 'failed'
    ap.pipeline_service.create_pipeline.assert_not_awaited()


@pytest.mark.asyncio
async def test_uncertain_write_cannot_be_replayed(assistant):
    service, ap, _ = assistant
    ctx = context()
    conversation = await service.create(ctx)
    await service.turn(ctx, conversation['uuid'], 0, text='Create')
    ap.pipeline_service.create_pipeline.side_effect = TimeoutError()
    failed = await service.turn(ctx, conversation['uuid'], 1, approved=True)
    assert failed['status'] == 'failed'
    with pytest.raises(AssistantError, match='stale_turn'):
        await service.turn(ctx, conversation['uuid'], 1, approved=True)
    ap.pipeline_service.create_pipeline.assert_awaited_once()


def test_tool_arguments_cannot_select_identity_or_shell():
    with pytest.raises(ValueError):
        validate_call(context(), 'create_pipeline', {'name': 'test', 'workspace_uuid': 'other'})
    with pytest.raises(ValueError):
        validate_call(context(), 'exec', {'command': 'echo unsafe'})


def test_rejected_malformed_tool_call_remains_readable():
    message = proposal().model_dump(mode='json')
    message['tool_calls'][0]['function']['arguments'] = '{invalid'
    conversation = dict(
        uuid='chat',
        revision=1,
        status='ready',
        error=None,
        model_name=None,
        model_uuid=None,
        messages=[message, {'role': 'tool', 'tool_call_id': 'call-1', 'content': '{"error":"Invalid arguments"}'}],
    )
    visible = AssistantService.public_view(conversation)['messages'][-1]['tool']
    assert visible['result']['error'] == 'Invalid arguments'
    assert visible['arguments'] == {'unparsed': '{invalid'}


@pytest.mark.asyncio
async def test_resource_readers_match_application_services():
    from langbot.pkg.core.app import Application
    from langbot.pkg.api.http.service.model import LLMModelsService, EmbeddingModelsService
    from langbot.pkg.api.http.service.pipeline import PipelineService
    from langbot.pkg.api.http.service.knowledge import KnowledgeService

    ap = create_autospec(Application, instance=True, spec_set=True)
    ap.llm_model_service = create_autospec(LLMModelsService, instance=True)
    ap.embedding_models_service = create_autospec(EmbeddingModelsService, instance=True)
    ap.pipeline_service = create_autospec(PipelineService, instance=True)
    ap.knowledge_service = create_autospec(KnowledgeService, instance=True)
    ctx = context()
    for kind, reader in (
        ('models', ap.llm_model_service.get_llm_models),
        ('embedding_models', ap.embedding_models_service.get_embedding_models),
        ('pipelines', ap.pipeline_service.get_pipelines),
        ('knowledge_bases', ap.knowledge_service.get_knowledge_bases),
        ('knowledge_engines', ap.knowledge_service.list_knowledge_engines),
    ):
        reader.return_value = [{'name': kind}]
        if kind != 'knowledge_engines':
            reader.return_value[0]['config'] = {'large_or_private': 'omitted from discovery'}
        assert await execute_tool(ap, ctx, 'list_resources', {'kind': kind}) == {
            'total': 1,
            'items': [{'name': kind}],
        }
        reader.assert_awaited_once_with(ctx)


@pytest.mark.asyncio
async def test_model_switch_preserves_history_and_rejects_invalid_selection(assistant):
    service, ap, provider = assistant
    ctx = context()
    conversation = await service.create(ctx)
    cid = conversation['uuid']
    await service.turn(ctx, cid, 0, text='Create')
    with pytest.raises(AssistantError, match='invalid_input'):
        await service.turn(ctx, cid, 1, approved=True, model_uuid='other')
    ap.pipeline_service.create_pipeline.assert_not_awaited()
    await service.turn(ctx, cid, 1, approved=True)
    for invalid in (ValueError('not in workspace'), SimpleNamespace(model_entity=SimpleNamespace(abilities=[]))):
        ap.model_mgr.get_model_by_uuid.side_effect = [invalid]
        with pytest.raises(AssistantError, match='model_unavailable'):
            await service.turn(ctx, cid, 2, text='Continue', model_uuid='invalid')
        saved = await service.get(ctx, cid)
        assert saved['revision'] == 2 and saved['status'] == 'ready'
    next_provider = SimpleNamespace(invoke_llm=AsyncMock(return_value=Message(role='assistant', content='Switched')))
    ap.model_mgr.get_model_by_uuid.side_effect = None
    ap.model_mgr.get_model_by_uuid.return_value = SimpleNamespace(
        provider=next_provider,
        model_entity=SimpleNamespace(name='second-model', abilities=['func_call'], extra_args={}),
    )
    switched = await service.turn(ctx, cid, 2, text='Continue', model_uuid='second')
    assert switched['status'] == 'ready'
    assert service.public_view(switched)['model_uuid'] == 'second'
    assert switched['model_name'] == 'second-model'
    history = next_provider.invoke_llm.call_args.kwargs['messages']
    assert [m.content for m in history if m.role == 'user'] == ['Create', 'Continue']
    assert any(m.role == 'tool' for m in history)
    assert all(m.provider_specific_fields is None for m in history)
    ap.model_mgr.get_model_by_uuid.assert_awaited_with(
        next_provider.invoke_llm.call_args.kwargs['execution_context'], 'second'
    )
