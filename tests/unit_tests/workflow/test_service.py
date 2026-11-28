from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.authz import PermissionDeniedError
from langbot.pkg.api.http.context import RequestContext, WorkspaceContext, PrincipalContext, PrincipalType
from langbot.pkg.api.http.service.workflow import WorkflowService
from langbot.pkg.api.http.service.workflow_run import run_workflow
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.workflow import Workflow, WorkflowExecution, WorkflowExecutionStep, WorkflowMemory
from langbot.pkg.persistence.mgr import PersistenceManager


def request_context(workspace='workspace', permissions=frozenset({'runtime.operate'})):
    return RequestContext(
        'instance',
        1,
        'request',
        'test',
        PrincipalContext(PrincipalType.SYSTEM),
        WorkspaceContext(workspace, None, 'owner', permissions),
    )


@pytest.mark.asyncio
async def test_manual_run_requires_runtime_permission():
    with pytest.raises(PermissionDeniedError):
        await run_workflow(SimpleNamespace(), request_context(permissions=frozenset()), 'workflow', 'hello')


def test_workflow_read_masks_node_secrets_for_viewers():
    from langbot.pkg.api.http.controller.groups.workflows.workflows import WorkflowsRouterGroup

    router = object.__new__(WorkflowsRouterGroup)
    router.success = lambda *, data: data
    payload = {'workflow': {'nodes': [{'config': {'headers': {'Authorization': 'test-secret'}}}]}}
    result = router._read_response(request_context(permissions=frozenset({'resource.view'})), data=payload)
    assert result['workflow']['nodes'][0]['config']['headers']['Authorization'] == '***'
    assert payload['workflow']['nodes'][0]['config']['headers']['Authorization'] == 'test-secret'


@pytest.mark.parametrize('target', ['chat', 'agent', 'workflow'])
async def test_test_run_collects_target_reply(target, monkeypatch):
    from unittest.mock import AsyncMock
    from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain
    from langbot.pkg.api.http.service import pipeline_run

    async def execute(context, ident, *, runtime, message_context, **kwargs):
        if ident == 'parent':
            await runtime.dispatch({'target_type': target, 'target_uuid': 'child', 'text': 'replacement'})
        else:
            assert runtime.test and runtime.depth == 1 and message_context.message_content == 'replacement'
            await runtime.reply(MessageChain([Plain(text='captured')]))
        return 'execution', runtime

    monkeypatch.setattr(
        pipeline_run,
        'run_pipeline',
        AsyncMock(return_value={'status': 'completed', 'replies': [{'content': 'captured'}]}),
    )
    app = SimpleNamespace(
        workflow_service=SimpleNamespace(execute_workflow=execute, get_execution=AsyncMock(return_value={'steps': []})),
        agent_service=SimpleNamespace(debug_agent=AsyncMock(return_value={'final_text': 'captured'})),
    )
    result = await run_workflow(app, request_context(), 'parent', 'original')
    assert result['replies'] == ['captured']


@pytest.mark.asyncio
async def test_saved_and_draft_runs_are_workspace_scoped():
    from langbot.pkg.api.http.service.workflow import initial_graph

    engine = create_async_engine('sqlite+aiosqlite:///:memory:')

    async def execute(statement):
        async with engine.begin() as connection:
            return await connection.execute(statement)

    persistence = SimpleNamespace(execute_async=execute)
    persistence.serialize_model = PersistenceManager.serialize_model.__get__(persistence)
    application = SimpleNamespace(persistence_mgr=persistence)
    application.workflow_service = WorkflowService(application)
    service = application.workflow_service
    manager = request_context(permissions=frozenset({'runtime.operate', 'resource.manage'}))
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda conn: Base.metadata.create_all(
                    conn,
                    tables=[
                        Workflow.__table__,
                        WorkflowExecution.__table__,
                        WorkflowExecutionStep.__table__,
                        WorkflowMemory.__table__,
                    ],
                )
            )
            await connection.execute(
                sa.insert(Workflow).values(uuid='wf', workspace_uuid='workspace', name='Echo', graph=initial_graph())
            )
        draft = initial_graph()
        draft['nodes'].append(
            {'id': 'reply', 'type': 'reply', 'name': 'Reply', 'config': {'text': 'Echo {{start.text}}'}}
        )
        draft['edges'].append({'from': 'start', 'to': 'reply'})
        with pytest.raises(PermissionDeniedError):
            await run_workflow(application, request_context(), 'wf', 'hello', graph=draft)
        with pytest.raises(ValueError, match='not found'):
            await run_workflow(application, request_context('other'), 'wf', 'hello')
        result = await run_workflow(application, manager, 'wf', 'hello', graph=draft)
        assert result['status'] == 'completed', result['error']
        assert result['replies'] == ['Echo hello']
        assert [step['node_id'] for step in result['steps']] == ['start', 'reply']
        assert result['steps'][-1]['inputs'] == {'text': 'Echo hello'}
        assert await service.get_execution(request_context('other'), 'wf', result['execution_uuid']) is None
        saved = await service.workflow_response(manager, 'wf')
        assert not saved['issues'] and saved['workflow']['graph'] == initial_graph()
        assert saved['workflow']['triggers'] == [{'type': 'message'}]
        assert saved['workflow']['timezone'] == 'UTC'
        assert not (await run_workflow(application, request_context(), 'wf', 'hello'))['replies']
        draft['nodes'][-1]['config']['text'] = '{{reply.sent}}'
        await service.update_workflow(manager, 'wf', {'graph': draft})
        assert (await service.workflow_response(manager, 'wf'))['issues'][0]['code'] == 'ref_not_upstream'
        invalid = await run_workflow(application, request_context(), 'wf', 'hello')
        assert invalid['status'] == 'failed' and not invalid['steps'] and not invalid['replies']
    finally:
        await engine.dispose()


async def test_recent_history_excludes_other_sessions_and_returns_ten_turns():
    from datetime import datetime, timedelta
    import json
    from langbot.pkg.api.context import ExecutionContext

    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    try:
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda db: Base.metadata.create_all(
                    db, tables=[WorkflowExecution.__table__, WorkflowExecutionStep.__table__]
                )
            )
            stamp = datetime(2026, 1, 1)
            for index in range(16):
                stamp += timedelta(seconds=1)
                ident = str(index)
                await conn.execute(
                    sa.insert(WorkflowExecution).values(
                        uuid=ident,
                        workspace_uuid='workspace',
                        workflow_uuid='wf',
                        bot_uuid='bot' if index != 14 else 'other',
                        trigger='test' if index == 15 else 'message',
                        session_id='other' if index == 13 else 'session',
                        status='completed',
                        input_text='q' + ident,
                        started_at=stamp,
                    )
                )
                await conn.execute(
                    sa.insert(WorkflowExecutionStep).values(
                        workspace_uuid='workspace',
                        execution_uuid=ident,
                        seq=1,
                        node_id='reply',
                        node_type='reply',
                        node_name='reply',
                        status='completed',
                        inputs=json.dumps({'text': 'a' + ident}),
                        outputs='{}',
                        started_at=stamp,
                    )
                )
            service = WorkflowService(SimpleNamespace(persistence_mgr=SimpleNamespace(execute_async=conn.execute)))
            context = ExecutionContext('instance', 'workspace', 1, bot_uuid='bot')
            assert await service._recent_history(context, 'wf', 'session') == [
                item
                for index in range(3, 13)
                for item in ({'role': 'user', 'content': f'q{index}'}, {'role': 'assistant', 'content': f'a{index}'})
            ]
    finally:
        await engine.dispose()
