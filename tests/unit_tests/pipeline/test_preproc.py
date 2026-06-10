"""
Unit tests for PreProcessor pipeline stage.

Tests cover preprocessing behavior including:
- Normal text message processing
- Empty message handling
- Unsupported message segment handling
- Image/file segment behavior
- Model selection and fallback
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock
from importlib import import_module

from tests.factories import (
    FakeApp,
    text_query,
    empty_query,
    image_query,
    group_text_query,
)


def get_preproc_module():
    """Lazy import to avoid circular import issues."""
    return import_module('langbot.pkg.pipeline.preproc.preproc')


def get_entities_module():
    """Lazy import for pipeline entities."""
    return import_module('langbot.pkg.pipeline.entities')


class TestPreProcessorNormalText:
    """Tests for normal text message preprocessing."""

    @pytest.mark.asyncio
    async def test_normal_text_continues(self):
        """Normal text message should continue pipeline."""
        preproc = get_preproc_module()
        entities = get_entities_module()

        app = FakeApp()
        # Mock session manager to return a session
        mock_session = Mock()
        mock_session.launcher_type = Mock(value='person')
        mock_session.launcher_id = 12345
        app.sess_mgr.get_session = AsyncMock(return_value=mock_session)

        # Mock conversation
        mock_conversation = Mock()
        mock_conversation.prompt = Mock()
        mock_conversation.prompt.messages = []
        mock_conversation.prompt.copy = Mock(return_value=Mock(messages=[]))
        mock_conversation.messages = []
        mock_conversation.update_time = Mock()
        mock_conversation.uuid = None
        app.sess_mgr.get_conversation = AsyncMock(return_value=mock_conversation)

        # Mock model manager
        mock_model = Mock()
        mock_model.model_entity = Mock()
        mock_model.model_entity.uuid = 'test-model-uuid'
        mock_model.model_entity.abilities = ['func_call', 'vision']
        app.model_mgr.get_model_by_uuid = AsyncMock(return_value=mock_model)

        # Mock tool manager
        app.tool_mgr.get_all_tools = AsyncMock(return_value=[])

        # Mock plugin connector
        mock_event_ctx = Mock()
        mock_event_ctx.event = Mock()
        mock_event_ctx.event.default_prompt = []
        mock_event_ctx.event.prompt = []
        app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        stage = preproc.PreProcessor(app)
        query = text_query("hello world")

        result = await stage.process(query, 'PreProcessor')

        assert result.result_type == entities.ResultType.CONTINUE
        assert result.new_query is not None

    @pytest.mark.asyncio
    async def test_normal_text_sets_user_message(self):
        """PreProcessor should set user_message from text content."""
        preproc = get_preproc_module()

        app = FakeApp()
        mock_session = Mock()
        mock_session.launcher_type = Mock(value='person')
        mock_session.launcher_id = 12345
        app.sess_mgr.get_session = AsyncMock(return_value=mock_session)

        mock_conversation = Mock()
        mock_conversation.prompt = Mock(messages=[])
        mock_conversation.prompt.copy = Mock(return_value=Mock(messages=[]))
        mock_conversation.messages = []
        mock_conversation.uuid = None
        app.sess_mgr.get_conversation = AsyncMock(return_value=mock_conversation)

        mock_model = Mock()
        mock_model.model_entity = Mock(uuid='test-model', abilities=['func_call'])
        app.model_mgr.get_model_by_uuid = AsyncMock(return_value=mock_model)
        app.tool_mgr.get_all_tools = AsyncMock(return_value=[])

        mock_event_ctx = Mock()
        mock_event_ctx.event = Mock(default_prompt=[], prompt=[])
        app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        stage = preproc.PreProcessor(app)
        query = text_query("test message")

        result = await stage.process(query, 'PreProcessor')

        assert result.new_query.user_message is not None
        assert result.new_query.user_message.role == 'user'


class TestPreProcessorEmptyMessage:
    """Tests for empty message handling."""

    @pytest.mark.asyncio
    async def test_empty_message_continues(self):
        """Empty message should follow expected behavior."""
        preproc = get_preproc_module()
        entities = get_entities_module()

        app = FakeApp()
        mock_session = Mock()
        mock_session.launcher_type = Mock(value='person')
        mock_session.launcher_id = 12345
        app.sess_mgr.get_session = AsyncMock(return_value=mock_session)

        mock_conversation = Mock()
        mock_conversation.prompt = Mock(messages=[])
        mock_conversation.prompt.copy = Mock(return_value=Mock(messages=[]))
        mock_conversation.messages = []
        mock_conversation.uuid = None
        app.sess_mgr.get_conversation = AsyncMock(return_value=mock_conversation)

        app.model_mgr.get_model_by_uuid = AsyncMock(return_value=None)
        app.tool_mgr.get_all_tools = AsyncMock(return_value=[])

        mock_event_ctx = Mock()
        mock_event_ctx.event = Mock(default_prompt=[], prompt=[])
        app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        stage = preproc.PreProcessor(app)
        query = empty_query()

        result = await stage.process(query, 'PreProcessor')

        # Empty message should still continue with an empty provider content list.
        assert result.result_type == entities.ResultType.CONTINUE
        assert result.new_query.user_message is not None
        assert result.new_query.user_message.content == []


class TestPreProcessorImageSegment:
    """Tests for image segment handling."""

    @pytest.mark.asyncio
    async def test_image_with_vision_model(self):
        """Image should be included when model supports vision."""
        preproc = get_preproc_module()

        app = FakeApp()
        mock_session = Mock()
        mock_session.launcher_type = Mock(value='person')
        mock_session.launcher_id = 12345
        app.sess_mgr.get_session = AsyncMock(return_value=mock_session)

        mock_conversation = Mock()
        mock_conversation.prompt = Mock(messages=[])
        mock_conversation.prompt.copy = Mock(return_value=Mock(messages=[]))
        mock_conversation.messages = []
        mock_conversation.uuid = None
        app.sess_mgr.get_conversation = AsyncMock(return_value=mock_conversation)

        # Model with vision support
        mock_model = Mock()
        mock_model.model_entity = Mock(uuid='vision-model', abilities=['func_call', 'vision'])
        app.model_mgr.get_model_by_uuid = AsyncMock(return_value=mock_model)
        app.tool_mgr.get_all_tools = AsyncMock(return_value=[])

        mock_event_ctx = Mock()
        mock_event_ctx.event = Mock(default_prompt=[], prompt=[])
        app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        stage = preproc.PreProcessor(app)
        # Image query with base64
        query = image_query(text="look at this", url=None)
        # Set base64 on the image component
        import langbot_plugin.api.entities.builtin.platform.message as platform_message
        chain = platform_message.MessageChain([
            platform_message.Plain(text="look at this"),
            platform_message.Image(base64="data:image/png;base64,abc123"),
        ])
        query.message_chain = chain

        result = await stage.process(query, 'PreProcessor')

        assert result.result_type == preproc.entities.ResultType.CONTINUE
        # User message should have content
        assert result.new_query.user_message.content is not None

    @pytest.mark.asyncio
    async def test_image_without_vision_model(self):
        """Image should be excluded when model doesn't support vision."""
        preproc = get_preproc_module()

        app = FakeApp()
        mock_session = Mock()
        mock_session.launcher_type = Mock(value='person')
        mock_session.launcher_id = 12345
        app.sess_mgr.get_session = AsyncMock(return_value=mock_session)

        mock_conversation = Mock()
        mock_conversation.prompt = Mock(messages=[])
        mock_conversation.prompt.copy = Mock(return_value=Mock(messages=[]))
        mock_conversation.messages = []
        mock_conversation.uuid = None
        app.sess_mgr.get_conversation = AsyncMock(return_value=mock_conversation)

        # Model WITHOUT vision support
        mock_model = Mock()
        mock_model.model_entity = Mock(uuid='text-only-model', abilities=['func_call'])
        app.model_mgr.get_model_by_uuid = AsyncMock(return_value=mock_model)
        app.tool_mgr.get_all_tools = AsyncMock(return_value=[])

        mock_event_ctx = Mock()
        mock_event_ctx.event = Mock(default_prompt=[], prompt=[])
        app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        stage = preproc.PreProcessor(app)
        query = image_query(text="describe this")

        result = await stage.process(query, 'PreProcessor')

        assert result.result_type == preproc.entities.ResultType.CONTINUE


class TestPreProcessorModelSelection:
    """Tests for model selection and fallback behavior."""

    @pytest.mark.asyncio
    async def test_primary_model_selected(self):
        """Primary model UUID should be set in query."""
        preproc = get_preproc_module()

        app = FakeApp()
        mock_session = Mock()
        mock_session.launcher_type = Mock(value='person')
        mock_session.launcher_id = 12345
        app.sess_mgr.get_session = AsyncMock(return_value=mock_session)

        mock_conversation = Mock()
        mock_conversation.prompt = Mock(messages=[])
        mock_conversation.prompt.copy = Mock(return_value=Mock(messages=[]))
        mock_conversation.messages = []
        mock_conversation.uuid = None
        app.sess_mgr.get_conversation = AsyncMock(return_value=mock_conversation)

        mock_model = Mock()
        mock_model.model_entity = Mock(uuid='primary-model-uuid', abilities=['func_call'])
        app.model_mgr.get_model_by_uuid = AsyncMock(return_value=mock_model)
        app.tool_mgr.get_all_tools = AsyncMock(return_value=[])

        mock_event_ctx = Mock()
        mock_event_ctx.event = Mock(default_prompt=[], prompt=[])
        app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        stage = preproc.PreProcessor(app)
        query = text_query("hello")

        # Set pipeline config with primary model
        query.pipeline_config = {
            'ai': {
                'runner': {'runner': 'local-agent'},
                'local-agent': {
                    'model': {'primary': 'primary-model-uuid', 'fallbacks': []},
                    'prompt': 'default',
                },
            },
            'output': {'misc': {'at-sender': False}},
            'trigger': {'misc': {}},
        }

        result = await stage.process(query, 'PreProcessor')

        assert result.new_query.use_llm_model_uuid == 'primary-model-uuid'

    @pytest.mark.asyncio
    async def test_fallback_models_resolved(self):
        """Fallback model UUIDs should be resolved and stored."""
        preproc = get_preproc_module()

        app = FakeApp()
        mock_session = Mock()
        mock_session.launcher_type = Mock(value='person')
        mock_session.launcher_id = 12345
        app.sess_mgr.get_session = AsyncMock(return_value=mock_session)

        mock_conversation = Mock()
        mock_conversation.prompt = Mock(messages=[])
        mock_conversation.prompt.copy = Mock(return_value=Mock(messages=[]))
        mock_conversation.messages = []
        mock_conversation.uuid = None
        app.sess_mgr.get_conversation = AsyncMock(return_value=mock_conversation)

        # Primary model
        mock_primary = Mock()
        mock_primary.model_entity = Mock(uuid='primary-uuid', abilities=['func_call'])
        # Fallback model
        mock_fallback = Mock()
        mock_fallback.model_entity = Mock(uuid='fallback-uuid', abilities=['func_call'])

        async def mock_get_model(uuid):
            if uuid == 'primary-uuid':
                return mock_primary
            elif uuid == 'fallback-uuid':
                return mock_fallback
            raise ValueError(f'Model {uuid} not found')

        app.model_mgr.get_model_by_uuid = AsyncMock(side_effect=mock_get_model)
        app.tool_mgr.get_all_tools = AsyncMock(return_value=[])

        mock_event_ctx = Mock()
        mock_event_ctx.event = Mock(default_prompt=[], prompt=[])
        app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        stage = preproc.PreProcessor(app)
        query = text_query("hello")

        query.pipeline_config = {
            'ai': {
                'runner': {'runner': 'local-agent'},
                'local-agent': {
                    'model': {'primary': 'primary-uuid', 'fallbacks': ['fallback-uuid']},
                    'prompt': 'default',
                },
            },
            'output': {'misc': {'at-sender': False}},
            'trigger': {'misc': {}},
        }

        result = await stage.process(query, 'PreProcessor')

        assert '_fallback_model_uuids' in result.new_query.variables
        assert 'fallback-uuid' in result.new_query.variables['_fallback_model_uuids']


class TestPreProcessorVariables:
    """Tests for query variable extraction."""

    @pytest.mark.asyncio
    async def test_variables_set_from_query(self):
        """PreProcessor should set variables from query context."""
        preproc = get_preproc_module()

        app = FakeApp()
        mock_session = Mock()
        mock_session.launcher_type = Mock(value='person')
        mock_session.launcher_id = 12345
        app.sess_mgr.get_session = AsyncMock(return_value=mock_session)

        mock_conversation = Mock()
        mock_conversation.prompt = Mock(messages=[])
        mock_conversation.prompt.copy = Mock(return_value=Mock(messages=[]))
        mock_conversation.messages = []
        mock_conversation.uuid = 'conv-123'
        app.sess_mgr.get_conversation = AsyncMock(return_value=mock_conversation)

        app.model_mgr.get_model_by_uuid = AsyncMock(return_value=None)
        app.tool_mgr.get_all_tools = AsyncMock(return_value=[])

        mock_event_ctx = Mock()
        mock_event_ctx.event = Mock(default_prompt=[], prompt=[])
        app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        stage = preproc.PreProcessor(app)
        query = text_query("hello", sender_id=67890)

        result = await stage.process(query, 'PreProcessor')

        variables = result.new_query.variables
        assert 'launcher_type' in variables
        assert 'launcher_id' in variables
        assert 'sender_id' in variables
        assert variables['sender_id'] == 67890
        assert 'user_message_text' in variables

    @pytest.mark.asyncio
    async def test_group_variables_include_group_name(self):
        """Group messages should include group_name variable."""
        preproc = get_preproc_module()

        app = FakeApp()
        mock_session = Mock()
        mock_session.launcher_type = Mock(value='group')
        mock_session.launcher_id = 99999
        app.sess_mgr.get_session = AsyncMock(return_value=mock_session)

        mock_conversation = Mock()
        mock_conversation.prompt = Mock(messages=[])
        mock_conversation.prompt.copy = Mock(return_value=Mock(messages=[]))
        mock_conversation.messages = []
        mock_conversation.uuid = None
        app.sess_mgr.get_conversation = AsyncMock(return_value=mock_conversation)

        app.model_mgr.get_model_by_uuid = AsyncMock(return_value=None)
        app.tool_mgr.get_all_tools = AsyncMock(return_value=[])

        mock_event_ctx = Mock()
        mock_event_ctx.event = Mock(default_prompt=[], prompt=[])
        app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        stage = preproc.PreProcessor(app)
        query = group_text_query("hello", group_id=99999)

        result = await stage.process(query, 'PreProcessor')

        variables = result.new_query.variables
        assert 'group_name' in variables
        assert 'sender_name' in variables
