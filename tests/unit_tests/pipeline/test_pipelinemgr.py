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


@pytest.mark.asyncio
async def test_runtime_pipeline_delivers_latest_chunk_as_final(mock_app, sample_query):
    """The terminal chunk, not the first chunk, controls final stream delivery."""
    pipelinemgr = get_pipelinemgr_module()
    persistence_pipeline = get_persistence_pipeline_module()
    entities = get_entities_module()
    provider_message = import_module('langbot_plugin.api.entities.builtin.provider.message')

    pipeline_entity = Mock(spec=persistence_pipeline.LegacyPipeline)
    pipeline_entity.config = sample_query.pipeline_config
    pipeline_entity.extensions_preferences = {'plugins': []}
    runtime_pipeline = pipelinemgr.RuntimePipeline(mock_app, pipeline_entity, [])

    first_chunk = provider_message.MessageChunk(role='assistant', content='Starting', is_final=False)
    final_chunk = provider_message.MessageChunk(role='assistant', content='Done', is_final=True)
    sample_query.resp_messages = [first_chunk, final_chunk]
    sample_query.adapter.is_stream_output_supported = AsyncMock(return_value=True)
    result = entities.StageProcessResult(
        result_type=entities.ResultType.CONTINUE,
        new_query=sample_query,
        user_notice='StartingDone',
    )

    await runtime_pipeline._check_output(sample_query, result)

    sample_query.adapter.reply_message_chunk.assert_awaited_once()
    call = sample_query.adapter.reply_message_chunk.await_args.kwargs
    assert call['bot_message'] is final_chunk
    assert call['is_final'] is True


@pytest.mark.asyncio
async def test_response_back_stage_delivers_latest_chunk_as_final(mock_app, sample_query):
    respback = import_module('langbot.pkg.pipeline.respback.respback')
    provider_message = import_module('langbot_plugin.api.entities.builtin.provider.message')
    platform_message = import_module('langbot_plugin.api.entities.builtin.platform.message')

    first_chunk = provider_message.MessageChunk(role='assistant', content='Starting', is_final=False)
    final_chunk = provider_message.MessageChunk(role='assistant', content='Done', is_final=True)
    sample_query.resp_messages = [first_chunk, final_chunk]
    sample_query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='StartingDone')])]
    sample_query.pipeline_config['output']['force-delay'] = {'min': 0, 'max': 0}
    sample_query.adapter.is_stream_output_supported = AsyncMock(return_value=True)

    await respback.SendResponseBackStage(mock_app).process(sample_query, 'response-back')

    sample_query.adapter.reply_message_chunk.assert_awaited_once()
    call = sample_query.adapter.reply_message_chunk.await_args.kwargs
    assert call['bot_message'] is final_chunk
    assert call['is_final'] is True


@pytest.mark.asyncio
async def test_response_back_stage_keeps_consuming_after_stream_delivery_failure(mock_app, sample_query):
    respback = import_module('langbot.pkg.pipeline.respback.respback')
    provider_message = import_module('langbot_plugin.api.entities.builtin.provider.message')
    platform_message = import_module('langbot_plugin.api.entities.builtin.platform.message')

    chunk = provider_message.MessageChunk(role='assistant', content='Progress', is_final=False)
    sample_query.resp_messages = [chunk]
    sample_query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='Progress')])]
    sample_query.pipeline_config['output']['force-delay'] = {'min': 0, 'max': 0}
    sample_query.adapter.is_stream_output_supported = AsyncMock(return_value=True)
    sample_query.adapter.reply_message_chunk.side_effect = RuntimeError('stream update failed')

    result = await respback.SendResponseBackStage(mock_app).process(sample_query, 'response-back')

    assert result.result_type.name == 'CONTINUE'
    sample_query.adapter.reply_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_response_back_stage_falls_back_to_plain_message_for_failed_final_chunk(mock_app, sample_query):
    respback = import_module('langbot.pkg.pipeline.respback.respback')
    provider_message = import_module('langbot_plugin.api.entities.builtin.provider.message')
    platform_message = import_module('langbot_plugin.api.entities.builtin.platform.message')

    chunk = provider_message.MessageChunk(role='assistant', content='Final answer', is_final=True)
    sample_query.resp_messages = [chunk]
    sample_query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='Final answer')])]
    sample_query.pipeline_config['output']['force-delay'] = {'min': 0, 'max': 0}
    sample_query.adapter.is_stream_output_supported = AsyncMock(return_value=True)
    sample_query.adapter.reply_message_chunk.side_effect = RuntimeError('stream update failed')

    result = await respback.SendResponseBackStage(mock_app).process(sample_query, 'response-back')

    assert result.result_type.name == 'CONTINUE'
    sample_query.adapter.reply_message.assert_awaited_once()


def test_runtime_pipeline_prefers_runner_mcp_resources(mock_app):
    """Runner resource selection should override extension preferences."""
    pipelinemgr = get_pipelinemgr_module()
    persistence_pipeline = get_persistence_pipeline_module()

    pipeline_entity = Mock(spec=persistence_pipeline.LegacyPipeline)
    pipeline_entity.config = {
        'ai': {
            'runner': {'id': 'plugin:langbot-team/LocalAgent/default'},
            'runner_config': {
                'plugin:langbot-team/LocalAgent/default': {
                    'mcp-resources': [{'server_uuid': 'srv-new', 'uri': 'file:///new.md'}],
                    'mcp-resource-agent-read-enabled': False,
                },
            },
        }
    }
    pipeline_entity.extensions_preferences = {
        'mcp_resources': [{'server_uuid': 'srv-old', 'uri': 'file:///old.md'}],
        'mcp_resource_agent_read_enabled': True,
    }

    runtime_pipeline = pipelinemgr.RuntimePipeline(mock_app, pipeline_entity, [])

    assert runtime_pipeline.mcp_resource_attachments == [{'server_uuid': 'srv-new', 'uri': 'file:///new.md'}]
    assert runtime_pipeline.mcp_resource_agent_read_enabled is False


def test_runtime_pipeline_falls_back_to_extension_mcp_resources(mock_app):
    """Extension preferences apply when the current runner has no override."""
    pipelinemgr = get_pipelinemgr_module()
    persistence_pipeline = get_persistence_pipeline_module()

    pipeline_entity = Mock(spec=persistence_pipeline.LegacyPipeline)
    pipeline_entity.config = {
        'ai': {
            'runner': {'id': 'plugin:langbot-team/LocalAgent/default'},
            'runner_config': {'plugin:langbot-team/LocalAgent/default': {}},
        }
    }
    pipeline_entity.extensions_preferences = {
        'mcp_resources': [{'server_uuid': 'srv-old', 'uri': 'file:///old.md'}],
        'mcp_resource_agent_read_enabled': False,
    }

    runtime_pipeline = pipelinemgr.RuntimePipeline(mock_app, pipeline_entity, [])

    assert runtime_pipeline.mcp_resource_attachments == [{'server_uuid': 'srv-old', 'uri': 'file:///old.md'}]
    assert runtime_pipeline.mcp_resource_agent_read_enabled is False


@pytest.mark.parametrize('invalid_value', [0, None, 'false', [], {}])
def test_runtime_pipeline_mcp_resource_read_flag_fails_closed(mock_app, invalid_value):
    pipelinemgr = get_pipelinemgr_module()
    persistence_pipeline = get_persistence_pipeline_module()

    pipeline_entity = Mock(spec=persistence_pipeline.LegacyPipeline)
    pipeline_entity.config = {
        'ai': {
            'runner': {'id': 'plugin:test/runner/default'},
            'runner_config': {
                'plugin:test/runner/default': {
                    'mcp-resource-agent-read-enabled': invalid_value,
                }
            },
        }
    }
    pipeline_entity.extensions_preferences = {'mcp_resource_agent_read_enabled': True}

    runtime_pipeline = pipelinemgr.RuntimePipeline(mock_app, pipeline_entity, [])

    assert runtime_pipeline.mcp_resource_agent_read_enabled is False


@pytest.mark.parametrize('invalid_value', [0, None, 'false', [], {}])
def test_runtime_pipeline_extension_enable_all_flags_fail_closed(mock_app, invalid_value):
    pipelinemgr = get_pipelinemgr_module()
    persistence_pipeline = get_persistence_pipeline_module()

    pipeline_entity = Mock(spec=persistence_pipeline.LegacyPipeline)
    pipeline_entity.config = {}
    pipeline_entity.extensions_preferences = {
        'enable_all_plugins': invalid_value,
        'plugins': [{'author': 'allowed', 'name': 'plugin'}],
        'enable_all_mcp_servers': invalid_value,
        'mcp_servers': ['bound-mcp'],
    }

    runtime_pipeline = pipelinemgr.RuntimePipeline(mock_app, pipeline_entity, [])

    assert runtime_pipeline.enable_all_plugins is False
    assert runtime_pipeline.bound_plugins == ['allowed/plugin']
    assert runtime_pipeline.enable_all_mcp_servers is False
    assert runtime_pipeline.bound_mcp_servers == ['bound-mcp']


@pytest.mark.parametrize('invalid_preferences', [None, [], '', 0, False])
def test_runtime_pipeline_malformed_extension_root_disables_all_extensions(
    mock_app,
    invalid_preferences,
):
    pipelinemgr = get_pipelinemgr_module()
    persistence_pipeline = get_persistence_pipeline_module()

    pipeline_entity = Mock(spec=persistence_pipeline.LegacyPipeline)
    pipeline_entity.config = {}
    pipeline_entity.extensions_preferences = invalid_preferences

    runtime_pipeline = pipelinemgr.RuntimePipeline(mock_app, pipeline_entity, [])

    assert runtime_pipeline.enable_all_plugins is False
    assert runtime_pipeline.bound_plugins == []
    assert runtime_pipeline.enable_all_mcp_servers is False
    assert runtime_pipeline.bound_mcp_servers == []
    assert runtime_pipeline.mcp_resource_attachments == []
    assert runtime_pipeline.mcp_resource_agent_read_enabled is False


def test_runtime_pipeline_malformed_extension_lists_are_empty_allowlists(mock_app):
    pipelinemgr = get_pipelinemgr_module()
    persistence_pipeline = get_persistence_pipeline_module()

    pipeline_entity = Mock(spec=persistence_pipeline.LegacyPipeline)
    pipeline_entity.config = {}
    pipeline_entity.extensions_preferences = {
        'enable_all_plugins': True,
        'plugins': 'allowed/plugin',
        'enable_all_mcp_servers': True,
        'mcp_servers': 'bound-mcp',
        'mcp_resources': 'file:///README.md',
        'mcp_resource_agent_read_enabled': True,
    }

    runtime_pipeline = pipelinemgr.RuntimePipeline(mock_app, pipeline_entity, [])

    assert runtime_pipeline.enable_all_plugins is False
    assert runtime_pipeline.bound_plugins == []
    assert runtime_pipeline.enable_all_mcp_servers is False
    assert runtime_pipeline.bound_mcp_servers == []
    assert runtime_pipeline.mcp_resource_attachments == []
    assert runtime_pipeline.mcp_resource_agent_read_enabled is False
