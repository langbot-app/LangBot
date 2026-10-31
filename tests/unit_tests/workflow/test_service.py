from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.authz import PermissionDeniedError
from langbot.pkg.api.http.context import RequestContext, WorkspaceContext, PrincipalContext, PrincipalType
from langbot.pkg.api.http.service.workflow import WorkflowService
from langbot.pkg.api.http.service.workflow_run import run_workflow
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.workflow import Workflow, WorkflowExecution, WorkflowNodeExecution
from langbot.pkg.persistence.mgr import PersistenceManager
from langbot.pkg.workflow.registry import NodeTypeRegistry
from langbot.pkg.workflow.nodes.message_trigger import MessageTriggerNode
from langbot.pkg.workflow.nodes.condition import ConditionNode
from langbot.pkg.workflow.nodes.reply_message import ReplyMessageNode


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
async def test_scoped_execution_persists_nodes_and_collects_replies(monkeypatch):
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda conn: Base.metadata.create_all(
                conn, tables=[Workflow.__table__, WorkflowExecution.__table__, WorkflowNodeExecution.__table__]
            )
        )
        await connection.execute(
            sa.insert(Workflow).values(
                uuid='workflow',
                workspace_uuid='workspace',
                name='Echo',
                definition={
                    'nodes': [
                        {'id': 'trigger', 'type': 'trigger.message_trigger'},
                        {
                            'id': 'condition',
                            'type': 'control.condition',
                            'config': {'condition_type': 'expression', 'expression': 'True'},
                        },
                        {
                            'id': 'reply',
                            'type': 'action.reply_message',
                            'config': {'message_template': 'Echo {{input}}'},
                        },
                    ],
                    'edges': [
                        {
                            'id': 'first',
                            'source': 'trigger',
                            'source_port': 'message',
                            'target': 'condition',
                            'target_port': 'input',
                        },
                        {
                            'id': 'second',
                            'source': 'condition',
                            'source_port': 'true',
                            'target': 'reply',
                            'target_port': 'input',
                        },
                    ],
                },
            )
        )

    async def execute(statement):
        async with engine.begin() as connection:
            return await connection.execute(statement)

    registry = NodeTypeRegistry()
    for node_class in (MessageTriggerNode, ConditionNode, ReplyMessageNode):
        registry.register(node_class.type_name, node_class)
    monkeypatch.setattr(NodeTypeRegistry, '_instance', registry)
    persistence = SimpleNamespace(execute_async=execute)
    persistence.serialize_model = PersistenceManager.serialize_model.__get__(persistence)
    application = SimpleNamespace(persistence_mgr=persistence)
    application.workflow_service = WorkflowService(application)
    try:
        assert await application.workflow_service.get_workflow(request_context('other'), 'workflow') is None
        with pytest.raises(ValueError, match='not found'):
            await run_workflow(application, request_context('other'), 'workflow', 'hello')
        result = await run_workflow(application, request_context(), 'workflow', 'hello')
        assert result['status'] == 'completed', result
        assert result['replies'] == ['Echo hello']
        execution = await application.workflow_service.get_execution(
            request_context(), 'workflow', result['execution_uuid']
        )
        assert len(execution['node_executions']) == 3
        assert all(node['status'] == 'completed' for node in execution['node_executions'])
        assert (
            await application.workflow_service.get_execution(
                request_context('other'), 'workflow', result['execution_uuid']
            )
            is None
        )
    finally:
        await engine.dispose()
