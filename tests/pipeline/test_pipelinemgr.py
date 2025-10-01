"""
PipelineManager unit tests
"""

import pytest
from unittest.mock import AsyncMock, Mock
import sqlalchemy

from pkg.pipeline.pipelinemgr import PipelineManager, RuntimePipeline, StageInstContainer
from pkg.pipeline import stage, entities as pipeline_entities
from pkg.entity.persistence import pipeline as persistence_pipeline


@pytest.mark.asyncio
async def test_pipeline_manager_initialize(mock_app):
    """Test pipeline manager initialization"""
    mock_app.persistence_mgr.execute_async = AsyncMock(return_value=Mock(all=Mock(return_value=[])))

    manager = PipelineManager(mock_app)
    await manager.initialize()

    assert manager.stage_dict is not None
    assert len(manager.pipelines) == 0


@pytest.mark.asyncio
async def test_load_pipeline(mock_app):
    """Test loading a single pipeline"""
    mock_app.persistence_mgr.execute_async = AsyncMock(return_value=Mock(all=Mock(return_value=[])))

    manager = PipelineManager(mock_app)
    await manager.initialize()

    # Create test pipeline entity
    pipeline_entity = Mock(spec=persistence_pipeline.LegacyPipeline)
    pipeline_entity.uuid = 'test-uuid'
    pipeline_entity.stages = []
    pipeline_entity.config = {'test': 'config'}

    await manager.load_pipeline(pipeline_entity)

    assert len(manager.pipelines) == 1
    assert manager.pipelines[0].pipeline_entity.uuid == 'test-uuid'


@pytest.mark.asyncio
async def test_get_pipeline_by_uuid(mock_app):
    """Test getting pipeline by UUID"""
    mock_app.persistence_mgr.execute_async = AsyncMock(return_value=Mock(all=Mock(return_value=[])))

    manager = PipelineManager(mock_app)
    await manager.initialize()

    # Create and add test pipeline
    pipeline_entity = Mock(spec=persistence_pipeline.LegacyPipeline)
    pipeline_entity.uuid = 'test-uuid'
    pipeline_entity.stages = []
    pipeline_entity.config = {}

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
    mock_app.persistence_mgr.execute_async = AsyncMock(return_value=Mock(all=Mock(return_value=[])))

    manager = PipelineManager(mock_app)
    await manager.initialize()

    # Create and add test pipeline
    pipeline_entity = Mock(spec=persistence_pipeline.LegacyPipeline)
    pipeline_entity.uuid = 'test-uuid'
    pipeline_entity.stages = []
    pipeline_entity.config = {}

    await manager.load_pipeline(pipeline_entity)
    assert len(manager.pipelines) == 1

    # Remove pipeline
    await manager.remove_pipeline('test-uuid')
    assert len(manager.pipelines) == 0


@pytest.mark.asyncio
async def test_runtime_pipeline_execute(mock_app, sample_query):
    """Test runtime pipeline execution"""
    # Create mock stage
    mock_stage = Mock(spec=stage.PipelineStage)
    mock_stage.process = AsyncMock(
        return_value=pipeline_entities.StageProcessResult(
            result_type=pipeline_entities.ResultType.CONTINUE, new_query=sample_query
        )
    )

    # Create stage container
    stage_container = StageInstContainer(inst_name='TestStage', inst=mock_stage)

    # Create pipeline entity
    pipeline_entity = Mock(spec=persistence_pipeline.LegacyPipeline)
    pipeline_entity.config = sample_query.pipeline_config

    # Create runtime pipeline
    runtime_pipeline = RuntimePipeline(mock_app, pipeline_entity, [stage_container])

    # Mock plugin connector
    event_ctx = Mock()
    event_ctx.is_prevented_default = Mock(return_value=False)
    mock_app.plugin_connector.emit_event = AsyncMock(return_value=event_ctx)

    # Execute pipeline
    await runtime_pipeline.run(sample_query)

    # Verify stage was called
    mock_stage.process.assert_called_once()
