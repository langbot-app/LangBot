"""
PreProcessor stage unit tests
"""

import pytest
from unittest.mock import AsyncMock, Mock

from pkg.pipeline.preproc.preproc import PreProcessor
from pkg.pipeline import entities as pipeline_entities
import langbot_plugin.api.entities.builtin.provider.session as provider_session


@pytest.mark.asyncio
async def test_preproc_basic_flow(mock_app, sample_query, mock_session, mock_conversation, mock_model):
    """Test preprocessor basic flow"""
    # Setup mocks
    mock_app.sess_mgr.get_session.return_value = mock_session
    mock_app.sess_mgr.get_conversation.return_value = mock_conversation
    mock_app.model_mgr.get_model_by_uuid.return_value = mock_model

    # Create event context mock
    event_ctx = Mock()
    event_ctx.event = Mock()
    event_ctx.event.default_prompt = []
    event_ctx.event.prompt = []
    event_ctx.is_prevented_default = Mock(return_value=False)
    mock_app.plugin_connector.emit_event.return_value = event_ctx

    # Create processor
    processor = PreProcessor(mock_app)
    await processor.initialize({})

    # Execute processing
    result = await processor.process(sample_query, 'PreProcessor')

    # Verify results
    assert result.result_type == pipeline_entities.ResultType.CONTINUE
    assert result.new_query.session == mock_session
    assert result.new_query.use_llm_model_uuid == 'test-model-uuid'

    # Verify calls
    mock_app.sess_mgr.get_session.assert_called_once()
    mock_app.sess_mgr.get_conversation.assert_called_once()
    mock_app.model_mgr.get_model_by_uuid.assert_called_once_with('test-model-uuid')


@pytest.mark.asyncio
async def test_preproc_without_vision_support(mock_app, sample_query, mock_session, mock_conversation, mock_model):
    """Test processing when model doesn't support vision"""
    # Setup model without vision support
    mock_model.model_entity.abilities = ['func_call']  # No 'vision'

    mock_app.sess_mgr.get_session.return_value = mock_session
    mock_app.sess_mgr.get_conversation.return_value = mock_conversation
    mock_app.model_mgr.get_model_by_uuid.return_value = mock_model

    event_ctx = Mock()
    event_ctx.event = Mock()
    event_ctx.event.default_prompt = []
    event_ctx.event.prompt = []
    event_ctx.is_prevented_default = Mock(return_value=False)
    mock_app.plugin_connector.emit_event.return_value = event_ctx

    processor = PreProcessor(mock_app)
    await processor.initialize({})

    result = await processor.process(sample_query, 'PreProcessor')

    assert result.result_type == pipeline_entities.ResultType.CONTINUE


@pytest.mark.asyncio
async def test_preproc_variables_setting(mock_app, sample_query, mock_session, mock_conversation, mock_model):
    """Test variable setting"""
    mock_app.sess_mgr.get_session.return_value = mock_session
    mock_app.sess_mgr.get_conversation.return_value = mock_conversation
    mock_app.model_mgr.get_model_by_uuid.return_value = mock_model

    event_ctx = Mock()
    event_ctx.event = Mock()
    event_ctx.event.default_prompt = []
    event_ctx.event.prompt = []
    event_ctx.is_prevented_default = Mock(return_value=False)
    mock_app.plugin_connector.emit_event.return_value = event_ctx

    processor = PreProcessor(mock_app)
    await processor.initialize({})

    result = await processor.process(sample_query, 'PreProcessor')

    # Verify variables are set
    assert 'session_id' in result.new_query.variables
    assert 'conversation_id' in result.new_query.variables
    assert 'msg_create_time' in result.new_query.variables
    assert 'user_message_text' in result.new_query.variables
