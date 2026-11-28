from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.authz import PermissionDeniedError
from langbot.pkg.api.http.context import RequestContext, WorkspaceContext, PrincipalContext, PrincipalType
from langbot.pkg.api.http.service.workflow import WorkflowService
from langbot.pkg.api.http.service.workflow_run import run_workflow
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.workflow import Workflow, WorkflowExecution, WorkflowExecutionStep
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
                    conn, tables=[Workflow.__table__, WorkflowExecution.__table__, WorkflowExecutionStep.__table__]
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
        assert saved['workflow']['trigger'] == {'type': 'message'}
        assert not (await run_workflow(application, request_context(), 'wf', 'hello'))['replies']
        draft['nodes'][-1]['config']['text'] = '{{reply.sent}}'
        await service.update_workflow(manager, 'wf', {'graph': draft})
        assert (await service.workflow_response(manager, 'wf'))['issues'][0]['code'] == 'ref_not_upstream'
        invalid = await run_workflow(application, request_context(), 'wf', 'hello')
        assert invalid['status'] == 'failed' and not invalid['steps'] and not invalid['replies']
    finally:
        await engine.dispose()
