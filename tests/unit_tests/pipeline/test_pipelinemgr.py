"""
PipelineManager unit tests
"""

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from importlib import import_module

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.workspace.entities import WorkspaceExecutionBinding
from langbot.pkg.workspace.errors import WorkspaceGenerationMismatchError, WorkspaceInvariantError


def _context(pipeline_uuid: str = 'test-uuid') -> ExecutionContext:
    return ExecutionContext(
        instance_uuid='test-instance',
        workspace_uuid='test-workspace',
        placement_generation=1,
        pipeline_uuid=pipeline_uuid,
    )


def get_pipelinemgr_module():
    return import_module('langbot.pkg.pipeline.pipelinemgr')


def get_stage_module():
    return import_module('langbot.pkg.pipeline.stage')


def get_entities_module():
    return import_module('langbot.pkg.pipeline.entities')


def get_persistence_pipeline_module():
    return import_module('langbot.pkg.entity.persistence.pipeline')


@pytest.mark.asyncio
async def test_pipeline_manager_initialize(mock_app):
    """Test pipeline manager initialization"""
    pipelinemgr = get_pipelinemgr_module()

    mock_app.persistence_mgr.execute_async = AsyncMock(return_value=Mock(all=Mock(return_value=[])))

    manager = pipelinemgr.PipelineManager(mock_app)
    await manager.initialize()

    assert manager.stage_dict is not None
    assert len(manager.pipelines) == 0


@pytest.mark.asyncio
async def test_cloud_startup_reuses_validated_pipeline_binding(mock_app):
    class TenantUow:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

    binding = WorkspaceExecutionBinding(
        instance_uuid='test-instance',
        workspace_uuid='test-workspace',
        placement_generation=1,
        write_fenced=False,
        state='active',
    )
    pipeline_entity = Mock(
        uuid='test-uuid',
        workspace_uuid='test-workspace',
        stages=[],
        config={},
        extensions_preferences={},
    )
    mock_app.persistence_mgr.mode = SimpleNamespace(value='cloud_runtime')
    mock_app.persistence_mgr.tenant_uow = lambda _workspace_uuid: TenantUow()
    mock_app.persistence_mgr.execute_async = AsyncMock(return_value=Mock(all=Mock(return_value=[pipeline_entity])))
    mock_app.workspace_service.list_active_execution_bindings = AsyncMock(return_value=[binding])
    mock_app.workspace_service.get_execution_binding = AsyncMock(
        side_effect=AssertionError('startup pipeline loader repeated a validated binding lookup')
    )
    manager = get_pipelinemgr_module().PipelineManager(mock_app)
    manager.stage_dict = {}

    await manager.load_pipelines_from_db()

    assert len(manager.pipelines) == 1
    mock_app.workspace_service.get_execution_binding.assert_not_awaited()


def test_generation_advance_prunes_superseded_workspace_pipelines(mock_app):
    class NoGlobalIterationDict(dict):
        def __iter__(self):
            raise AssertionError('generation advance scanned every pipeline')

        def items(self):
            raise AssertionError('generation advance scanned every pipeline')

        def values(self):
            raise AssertionError('generation advance scanned every pipeline')

    pipelinemgr = get_pipelinemgr_module()
    manager = pipelinemgr.PipelineManager(mock_app)
    old_context = _context()
    next_context = ExecutionContext(
        instance_uuid=old_context.instance_uuid,
        workspace_uuid=old_context.workspace_uuid,
        placement_generation=2,
        pipeline_uuid=old_context.pipeline_uuid,
    )
    old_pipeline = SimpleNamespace(
        execution_context=old_context,
        workspace_uuid=old_context.workspace_uuid,
        placement_generation=old_context.placement_generation,
    )
    other_pipelines = [
        SimpleNamespace(
            execution_context=ExecutionContext(
                instance_uuid='test-instance',
                workspace_uuid=f'workspace-{index}',
                placement_generation=1,
                pipeline_uuid=f'pipeline-{index}',
            ),
            workspace_uuid=f'workspace-{index}',
            placement_generation=1,
        )
        for index in range(1_000)
    ]
    manager.pipelines = [old_pipeline, *other_pipelines]

    manager._observe_execution_context(old_context)
    manager._pipelines_by_key = NoGlobalIterationDict(manager._pipelines_by_key)
    manager._observe_execution_context(next_context)
    manager._pipelines_by_key = dict(manager._pipelines_by_key)

    assert manager.pipelines == other_pipelines
    with pytest.raises(WorkspaceInvariantError, match='rolled back'):
        manager._observe_execution_context(old_context)


@pytest.mark.asyncio
async def test_load_pipeline(mock_app):
    """Test loading a single pipeline"""
    pipelinemgr = get_pipelinemgr_module()
    persistence_pipeline = get_persistence_pipeline_module()

    mock_app.persistence_mgr.execute_async = AsyncMock(return_value=Mock(all=Mock(return_value=[])))

    manager = pipelinemgr.PipelineManager(mock_app)
    await manager.initialize()

    # Create test pipeline entity
    pipeline_entity = Mock(spec=persistence_pipeline.LegacyPipeline)
    pipeline_entity.uuid = 'test-uuid'
    pipeline_entity.workspace_uuid = 'test-workspace'
    pipeline_entity.stages = []
    pipeline_entity.config = {'test': 'config'}
    pipeline_entity.extensions_preferences = {'plugins': []}

    await manager.load_pipeline(_context(), pipeline_entity)

    assert len(manager.pipelines) == 1
    assert manager.pipelines[0].pipeline_entity.uuid == 'test-uuid'


@pytest.mark.asyncio
async def test_get_pipeline_by_uuid(mock_app):
    """Test getting pipeline by UUID"""
    pipelinemgr = get_pipelinemgr_module()
    persistence_pipeline = get_persistence_pipeline_module()

    mock_app.persistence_mgr.execute_async = AsyncMock(return_value=Mock(all=Mock(return_value=[])))

    manager = pipelinemgr.PipelineManager(mock_app)
    await manager.initialize()

    # Create and add test pipeline
    pipeline_entity = Mock(spec=persistence_pipeline.LegacyPipeline)
    pipeline_entity.uuid = 'test-uuid'
    pipeline_entity.workspace_uuid = 'test-workspace'
    pipeline_entity.stages = []
    pipeline_entity.config = {}
    pipeline_entity.extensions_preferences = {'plugins': []}

    await manager.load_pipeline(_context(), pipeline_entity)

    # Test retrieval
    result = await manager.get_pipeline_by_uuid(_context(), 'test-uuid')
    assert result is not None
    assert result.pipeline_entity.uuid == 'test-uuid'

    # Test non-existent UUID
    result = await manager.get_pipeline_by_uuid(_context('non-existent'), 'non-existent')
    assert result is None


@pytest.mark.asyncio
async def test_remove_pipeline(mock_app):
    """Test removing a pipeline"""
    pipelinemgr = get_pipelinemgr_module()
    persistence_pipeline = get_persistence_pipeline_module()

    mock_app.persistence_mgr.execute_async = AsyncMock(return_value=Mock(all=Mock(return_value=[])))

    manager = pipelinemgr.PipelineManager(mock_app)
    await manager.initialize()

    # Create and add test pipeline
    pipeline_entity = Mock(spec=persistence_pipeline.LegacyPipeline)
    pipeline_entity.uuid = 'test-uuid'
    pipeline_entity.workspace_uuid = 'test-workspace'
    pipeline_entity.stages = []
    pipeline_entity.config = {}
    pipeline_entity.extensions_preferences = {'plugins': []}

    await manager.load_pipeline(_context(), pipeline_entity)
    assert len(manager.pipelines) == 1

    # Remove pipeline
    await manager.remove_pipeline(_context(), 'test-uuid')
    assert len(manager.pipelines) == 0


@pytest.mark.asyncio
async def test_runtime_pipeline_execute(mock_app, sample_query):
    """Test runtime pipeline execution with real Pydantic models."""
    pipelinemgr = get_pipelinemgr_module()
    stage = get_stage_module()
    persistence_pipeline = get_persistence_pipeline_module()
    entities = get_entities_module()

    # Create result using real Pydantic model (not Mock) to ensure validation
    real_result = entities.StageProcessResult(
        result_type=entities.ResultType.CONTINUE,
        new_query=sample_query,
        user_notice='',
        console_notice='',
        debug_notice='',
        error_notice='',
    )

    mock_stage = Mock(spec=stage.PipelineStage)
    mock_stage.process = AsyncMock(return_value=real_result)

    # Create stage container
    stage_container = pipelinemgr.StageInstContainer(inst_name='TestStage', inst=mock_stage)

    # Create pipeline entity
    pipeline_entity = Mock(spec=persistence_pipeline.LegacyPipeline)
    pipeline_entity.uuid = 'test-pipeline-uuid'
    pipeline_entity.workspace_uuid = 'test-workspace'
    pipeline_entity.config = sample_query.pipeline_config
    pipeline_entity.extensions_preferences = {'plugins': []}

    # Create runtime pipeline
    runtime_pipeline = pipelinemgr.RuntimePipeline(
        mock_app,
        pipeline_entity,
        [stage_container],
        _context('test-pipeline-uuid'),
    )

    # Mock plugin connector
    event_ctx = Mock()
    event_ctx.is_prevented_default = Mock(return_value=False)
    mock_app.plugin_connector.emit_event = AsyncMock(return_value=event_ctx)

    # Execute pipeline
    await runtime_pipeline.run(sample_query)

    # Verify stage was called
    mock_stage.process.assert_called_once()
    mock_app.query_pool.remove_query.assert_awaited_once_with(sample_query)


@pytest.mark.asyncio
async def test_runtime_pipeline_rejects_stale_generation_before_side_effects(
    mock_app,
    sample_query,
):
    pipelinemgr = get_pipelinemgr_module()
    persistence_pipeline = get_persistence_pipeline_module()
    pipeline_entity = Mock(spec=persistence_pipeline.LegacyPipeline)
    pipeline_entity.uuid = 'test-pipeline-uuid'
    pipeline_entity.workspace_uuid = 'test-workspace'
    pipeline_entity.config = sample_query.pipeline_config
    pipeline_entity.extensions_preferences = {'plugins': []}
    runtime_pipeline = pipelinemgr.RuntimePipeline(
        mock_app,
        pipeline_entity,
        [],
        _context('test-pipeline-uuid'),
    )
    mock_app.workspace_service.get_execution_binding.side_effect = WorkspaceGenerationMismatchError('stale generation')

    with pytest.raises(WorkspaceGenerationMismatchError):
        await runtime_pipeline.run(sample_query)

    mock_app.plugin_connector.emit_event.assert_not_awaited()
    sample_query.adapter.reply_message.assert_not_awaited()
    sample_query.adapter.reply_message_chunk.assert_not_awaited()


@pytest.mark.asyncio
async def test_runtime_pipeline_revalidates_after_awaited_stage(
    mock_app,
    sample_query,
):
    pipelinemgr = get_pipelinemgr_module()
    stage = get_stage_module()
    persistence_pipeline = get_persistence_pipeline_module()
    entities = get_entities_module()
    pipeline_entity = Mock(spec=persistence_pipeline.LegacyPipeline)
    pipeline_entity.uuid = 'test-pipeline-uuid'
    pipeline_entity.workspace_uuid = 'test-workspace'
    pipeline_entity.config = sample_query.pipeline_config
    pipeline_entity.extensions_preferences = {'plugins': []}

    result = entities.StageProcessResult(
        result_type=entities.ResultType.CONTINUE,
        new_query=sample_query,
        user_notice='must not be sent',
        console_notice='',
        debug_notice='',
        error_notice='',
    )

    async def stage_process(*_args):
        mock_app.workspace_service.get_execution_binding.side_effect = WorkspaceGenerationMismatchError(
            'generation changed during stage'
        )
        return result

    mock_stage = Mock(spec=stage.PipelineStage)
    mock_stage.process = Mock(side_effect=stage_process)
    runtime_pipeline = pipelinemgr.RuntimePipeline(
        mock_app,
        pipeline_entity,
        [pipelinemgr.StageInstContainer(inst_name='TestStage', inst=mock_stage)],
        _context('test-pipeline-uuid'),
    )

    with pytest.raises(WorkspaceGenerationMismatchError):
        await runtime_pipeline._execute_from_stage(0, sample_query)

    sample_query.adapter.reply_message.assert_not_awaited()
    sample_query.adapter.reply_message_chunk.assert_not_awaited()


def test_runtime_pipeline_prefers_local_agent_mcp_resources(mock_app):
    """Local Agent resource selection should override legacy extension prefs."""
    pipelinemgr = get_pipelinemgr_module()
    persistence_pipeline = get_persistence_pipeline_module()

    pipeline_entity = Mock(spec=persistence_pipeline.LegacyPipeline)
    pipeline_entity.uuid = 'test-uuid'
    pipeline_entity.workspace_uuid = 'test-workspace'
    pipeline_entity.config = {
        'ai': {
            'local-agent': {
                'mcp-resources': [{'server_uuid': 'srv-new', 'uri': 'file:///new.md'}],
                'mcp-resource-agent-read-enabled': False,
            }
        }
    }
    pipeline_entity.extensions_preferences = {
        'mcp_resources': [{'server_uuid': 'srv-old', 'uri': 'file:///old.md'}],
        'mcp_resource_agent_read_enabled': True,
    }

    runtime_pipeline = pipelinemgr.RuntimePipeline(mock_app, pipeline_entity, [], _context())

    assert runtime_pipeline.mcp_resource_attachments == [{'server_uuid': 'srv-new', 'uri': 'file:///new.md'}]
    assert runtime_pipeline.mcp_resource_agent_read_enabled is False


def test_runtime_pipeline_falls_back_to_extension_mcp_resources(mock_app):
    """Existing extension prefs remain compatible until a Local Agent value exists."""
    pipelinemgr = get_pipelinemgr_module()
    persistence_pipeline = get_persistence_pipeline_module()

    pipeline_entity = Mock(spec=persistence_pipeline.LegacyPipeline)
    pipeline_entity.uuid = 'test-uuid'
    pipeline_entity.workspace_uuid = 'test-workspace'
    pipeline_entity.config = {'ai': {'local-agent': {}}}
    pipeline_entity.extensions_preferences = {
        'mcp_resources': [{'server_uuid': 'srv-old', 'uri': 'file:///old.md'}],
        'mcp_resource_agent_read_enabled': False,
    }

    runtime_pipeline = pipelinemgr.RuntimePipeline(mock_app, pipeline_entity, [], _context())

    assert runtime_pipeline.mcp_resource_attachments == [{'server_uuid': 'srv-old', 'uri': 'file:///old.md'}]
    assert runtime_pipeline.mcp_resource_agent_read_enabled is False
