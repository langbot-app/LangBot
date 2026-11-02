import importlib
import socket
from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest

from langbot.pkg.workflow.entities import ExecutionContext
from langbot.pkg.workflow.nodes.http_request import _is_safe_url
from langbot.pkg.workflow.nodes.wait import WaitNode
from langbot.pkg.workflow.runtime import WorkflowRuntime, use_runtime
from langbot.pkg.api.http.context import ExecutionContext as WorkspaceExecutionContext


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'module,class_name',
    [
        ('condition', 'ConditionNode'),
        ('switch', 'SwitchNode'),
        ('loop', 'LoopNode'),
        ('iterator', 'IteratorNode'),
        ('merge', 'MergeNode'),
        ('parallel', 'ParallelNode'),
        ('set_variable', 'SetVariableNode'),
        ('variable_aggregator', 'VariableAggregatorNode'),
        ('data_transform', 'DataTransformNode'),
        ('store_data', 'StoreDataNode'),
        ('memory_store', 'MemoryStoreNode'),
        ('end', 'EndNode'),
    ],
)
async def test_logic_node_minimal_execution(module, class_name):
    node_class = getattr(importlib.import_module(f'langbot.pkg.workflow.nodes.{module}'), class_name)
    context = ExecutionContext(workflow_id='workflow', execution_id='execution')
    result = await node_class('node', {}).execute({}, context)
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_wait_is_bounded(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr('asyncio.sleep', sleep)
    result = await WaitNode('wait', {'duration': 24, 'duration_type': 'hours'}).execute(
        {}, ExecutionContext(workflow_id='workflow', execution_id='execution')
    )
    sleep.assert_awaited_once_with(300)
    assert result['waited_seconds'] == 300


@pytest.mark.parametrize('url', ['http://127.0.0.1', 'http://localhost', 'http://10.0.0.1', 'http://[::1]'])
def test_http_rejects_internal_addresses(url):
    assert not _is_safe_url(url)[0]


def test_http_rejects_private_dns(monkeypatch):
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *args: [(socket.AF_INET, 1, 6, '', ('192.168.1.1', 80))])
    assert not _is_safe_url('https://public.example')[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'module,class_name,config,response',
    [
        ('llm_call', 'LLMCallNode', {'model': 'model'}, 'hello'),
        (
            'parameter_extractor',
            'ParameterExtractorNode',
            {'model': 'model', 'parameters': [{'name': 'city'}]},
            '{"city":"Paris"}',
        ),
        (
            'question_classifier',
            'QuestionClassifierNode',
            {'model': 'model', 'categories': [{'name': 'travel'}]},
            'travel',
        ),
    ],
)
async def test_llm_nodes_propagate_workspace(module, class_name, config, response):
    from langbot_plugin.api.entities.builtin.provider.message import Message

    execution = WorkspaceExecutionContext('instance', 'workspace', 1)
    provider = SimpleNamespace(invoke_llm=AsyncMock(return_value=Message(role='assistant', content=response)))
    model = SimpleNamespace(provider=provider, model_entity=SimpleNamespace(abilities=[], name='Model', uuid='model'))
    application = SimpleNamespace(model_mgr=SimpleNamespace(get_model_by_uuid=AsyncMock(return_value=model)))
    node_class = getattr(importlib.import_module(f'langbot.pkg.workflow.nodes.{module}'), class_name)
    with use_runtime(WorkflowRuntime(execution)):
        result = await node_class('node', config, application).execute(
            {'input': 'hello'}, ExecutionContext(workflow_id='workflow', execution_id='execution')
        )
    assert isinstance(result, dict)
    application.model_mgr.get_model_by_uuid.assert_awaited_once_with(execution, 'model')
    assert provider.invoke_llm.call_args.kwargs['execution_context'] is execution
    assert provider.invoke_llm.call_args.kwargs['query'] is None


@pytest.mark.asyncio
async def test_pipeline_call_uses_scheduler_and_workspace():
    import asyncio
    from langbot.pkg.workflow.nodes.call_pipeline import CallPipelineNode

    execution = WorkspaceExecutionContext('instance', 'workspace', 1, bot_uuid='bot')

    async def enqueue(**kwargs):
        assert kwargs['execution_context'] is execution
        query = SimpleNamespace(variables=kwargs['variables'])
        query.variables['_cli_run_status'] = 'completed'
        asyncio.get_running_loop().call_soon(lambda: query._completion_event.set())
        return query

    application = SimpleNamespace(
        pipeline_service=SimpleNamespace(get_pipeline=AsyncMock(return_value={'uuid': 'pipeline'})),
        query_pool=SimpleNamespace(add_query=AsyncMock(side_effect=enqueue)),
    )
    with use_runtime(WorkflowRuntime(execution)):
        result = await CallPipelineNode('node', {'pipeline_uuid': 'pipeline'}, application).execute(
            {'query': 'hello'}, ExecutionContext(workflow_id='workflow', execution_id='execution')
        )
    assert result['result']['pipeline_uuid'] == 'pipeline'
    application.pipeline_service.get_pipeline.assert_awaited_once_with(execution, 'pipeline')


@pytest.mark.asyncio
async def test_nested_workflow_inherits_runtime_and_increments_depth():
    from langbot.pkg.workflow.nodes.call_workflow import CallWorkflowNode

    execution = WorkspaceExecutionContext('instance', 'workspace', 1)
    parent = WorkflowRuntime(execution, AsyncMock(), AsyncMock(), depth=2)
    service = SimpleNamespace(
        get_workflow=AsyncMock(return_value={'uuid': 'child'}),
        execute_workflow=AsyncMock(return_value=('child-execution', None)),
        get_execution=AsyncMock(return_value={'status': 'completed'}),
    )
    with use_runtime(parent):
        await CallWorkflowNode('node', {'workflow_uuid': 'child'}, SimpleNamespace(workflow_service=service)).execute(
            {}, ExecutionContext(workflow_id='parent', execution_id='execution')
        )
    child = service.execute_workflow.call_args.kwargs['runtime']
    assert child.execution_context is execution
    assert child.reply_sender is parent.reply_sender
    assert child.replies is parent.replies
    assert child.depth == 3
    service.get_execution.assert_awaited_once_with(execution, 'child', 'child-execution')


@pytest.mark.asyncio
async def test_all_metadata_nodes_have_importable_implementations():
    import logging
    from langbot.pkg.discover.engine import ComponentDiscoveryEngine
    from langbot.pkg.workflow.metadata import NodeMetadataLoader
    from langbot.pkg.workflow.registry import NodeTypeRegistry

    loader = NodeMetadataLoader()
    assert await loader.load_core_metadata() == 22
    assert not loader.get_load_errors()
    registry = NodeTypeRegistry()
    for metadata in loader.get_all_metadata().values():
        registry.register_metadata(metadata)
    registry.discover_nodes(ComponentDiscoveryEngine(SimpleNamespace(logger=logging.getLogger(__name__))))
    for metadata in loader.get_all_metadata().values():
        assert registry.get(metadata['name']) is not None
