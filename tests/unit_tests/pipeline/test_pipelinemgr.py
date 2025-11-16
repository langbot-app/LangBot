"""
PipelineManager unit tests
"""

import pytest
from unittest.mock import AsyncMock, Mock
from importlib import import_module


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
    pipeline_entity.stages = []
    pipeline_entity.config = {'test': 'config'}
    pipeline_entity.extensions_preferences = {'plugins': []}

    await manager.load_pipeline(pipeline_entity)

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
    pipeline_entity.stages = []
    pipeline_entity.config = {}
    pipeline_entity.extensions_preferences = {'plugins': []}

    await manager.load_pipeline(pipeline_entity)

    # Test retrieval
    result = await manager.get_pipeline_by_uuid('test-uuid')
    assert result is not None
    assert result.pipeline_entity.uuid == 'test-uuid'

    # Test non-existent UUID
    result = await manager.get_pipeline_by_uuid('non-existent')
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
    pipeline_entity.stages = []
    pipeline_entity.config = {}
    pipeline_entity.extensions_preferences = {'plugins': []}

    await manager.load_pipeline(pipeline_entity)
    assert len(manager.pipelines) == 1

    # Remove pipeline
    await manager.remove_pipeline('test-uuid')
    assert len(manager.pipelines) == 0


@pytest.mark.asyncio
async def test_runtime_pipeline_execute(mock_app, sample_query):
    """Test runtime pipeline execution"""
    pipelinemgr = get_pipelinemgr_module()
    stage = get_stage_module()
    persistence_pipeline = get_persistence_pipeline_module()

    # Create mock stage that returns a simple result dict (avoiding Pydantic validation)
    mock_result = Mock()
    mock_result.result_type = Mock()
    mock_result.result_type.value = 'CONTINUE'  # Simulate enum value
    mock_result.new_query = sample_query
    mock_result.user_notice = ''
    mock_result.console_notice = ''
    mock_result.debug_notice = ''
    mock_result.error_notice = ''

    # Make it look like ResultType.CONTINUE
    from unittest.mock import MagicMock

    CONTINUE = MagicMock()
    CONTINUE.__eq__ = lambda self, other: True  # Always equal for comparison
    mock_result.result_type = CONTINUE

    mock_stage = Mock(spec=stage.PipelineStage)
    mock_stage.process = AsyncMock(return_value=mock_result)

    # Create stage container
    stage_container = pipelinemgr.StageInstContainer(inst_name='TestStage', inst=mock_stage)

    # Create pipeline entity
    pipeline_entity = Mock(spec=persistence_pipeline.LegacyPipeline)
    pipeline_entity.config = sample_query.pipeline_config
    pipeline_entity.extensions_preferences = {'plugins': []}

    # Create runtime pipeline
    runtime_pipeline = pipelinemgr.RuntimePipeline(mock_app, pipeline_entity, [stage_container])

    # Mock plugin connector
    event_ctx = Mock()
    event_ctx.is_prevented_default = Mock(return_value=False)
    mock_app.plugin_connector.emit_event = AsyncMock(return_value=event_ctx)

    # Add query to cached_queries to prevent KeyError in finally block
    mock_app.query_pool.cached_queries[sample_query.query_id] = sample_query

    # Execute pipeline
    await runtime_pipeline.run(sample_query)

    # Verify stage was called
    mock_stage.process.assert_called_once()
