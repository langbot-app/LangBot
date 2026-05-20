"""
Unit tests for ResponseWrapper (wrapper) pipeline stage.

Tests cover:
- MessageChain wrapping
- Command response wrapping
- Plugin response wrapping
- Assistant response wrapping with content/tool_calls
- Plugin event emission and INTERRUPT handling
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock, AsyncMock
from importlib import import_module

from tests.factories import (
    FakeApp,
    text_query,
)

import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.session as provider_session


def get_wrapper_module():
    """Lazy import to avoid circular import issues."""
    # Import pipelinemgr first to trigger stage registration
    import_module('langbot.pkg.pipeline.pipelinemgr')
    return import_module('langbot.pkg.pipeline.wrapper.wrapper')


def get_entities_module():
    """Lazy import for pipeline entities."""
    return import_module('langbot.pkg.pipeline.entities')


def make_wrapper_config():
    """Create a pipeline config for wrapper tests."""
    return {
        'output': {
            'misc': {
                'at-sender': False,
                'quote-origin': False,
                'track-function-calls': False,
            }
        }
    }


def make_session():
    """Create a valid Session object for tests."""
    return provider_session.Session(
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id=12345,
        sender_id=12345,
        use_prompt_name="default",
        using_conversation=None,
        conversations=[],
    )


class TestResponseWrapperInit:
    """Tests for ResponseWrapper initialization."""

    @pytest.mark.asyncio
    async def test_initialize_passes(self):
        """Initialize should complete without error."""
        wrapper = get_wrapper_module()

        app = FakeApp()
        stage = wrapper.ResponseWrapper(app)

        pipeline_config = {}

        await stage.initialize(pipeline_config)


class TestResponseWrapperMessageChain:
    """Tests for MessageChain wrapping."""

    @pytest.mark.asyncio
    async def test_message_chain_direct_append(self):
        """MessageChain in resp_messages should be directly appended."""
        wrapper = get_wrapper_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = wrapper.ResponseWrapper(app)

        pipeline_config = make_wrapper_config()

        await stage.initialize(pipeline_config)

        query = text_query("hello")
        query.pipeline_config = pipeline_config
        query.resp_messages = [
            platform_message.MessageChain([platform_message.Plain(text="response")])
        ]
        query.resp_message_chain = []

        results = []
        async for result in stage.process(query, 'ResponseWrapper'):
            results.append(result)

        assert len(results) == 1
        assert results[0].result_type == entities.ResultType.CONTINUE
        assert len(results[0].new_query.resp_message_chain) == 1


class TestResponseWrapperCommand:
    """Tests for command response wrapping."""

    @pytest.mark.asyncio
    async def test_command_response_prefix(self):
        """Command response should have [bot] prefix."""
        wrapper = get_wrapper_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = wrapper.ResponseWrapper(app)

        pipeline_config = make_wrapper_config()

        await stage.initialize(pipeline_config)

        query = text_query("hello")
        query.pipeline_config = pipeline_config
        query.resp_message_chain = []

        # Create a command response message
        command_resp = Mock()
        command_resp.role = 'command'
        command_resp.get_content_platform_message_chain = Mock(
            return_value=platform_message.MessageChain([platform_message.Plain(text="Help info")])
        )
        query.resp_messages = [command_resp]

        results = []
        async for result in stage.process(query, 'ResponseWrapper'):
            results.append(result)

        assert len(results) == 1
        assert results[0].result_type == entities.ResultType.CONTINUE
        # Check that prefix was added (via get_content_platform_message_chain)
        command_resp.get_content_platform_message_chain.assert_called_once()


class TestResponseWrapperPlugin:
    """Tests for plugin response wrapping."""

    @pytest.mark.asyncio
    async def test_plugin_response_direct(self):
        """Plugin response should be wrapped without prefix."""
        wrapper = get_wrapper_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = wrapper.ResponseWrapper(app)

        pipeline_config = make_wrapper_config()

        await stage.initialize(pipeline_config)

        query = text_query("hello")
        query.pipeline_config = pipeline_config
        query.resp_message_chain = []

        # Create a plugin response message
        plugin_resp = Mock()
        plugin_resp.role = 'plugin'
        plugin_resp.get_content_platform_message_chain = Mock(
            return_value=platform_message.MessageChain([platform_message.Plain(text="Plugin response")])
        )
        query.resp_messages = [plugin_resp]

        results = []
        async for result in stage.process(query, 'ResponseWrapper'):
            results.append(result)

        assert len(results) == 1
        assert results[0].result_type == entities.ResultType.CONTINUE


class TestResponseWrapperAssistant:
    """Tests for assistant response wrapping."""

    @pytest.mark.asyncio
    async def test_assistant_content_response(self):
        """Assistant with content should emit event and wrap."""
        wrapper = get_wrapper_module()
        entities = get_entities_module()

        app = FakeApp()

        # Mock session manager to return a valid Session
        session = make_session()
        app.sess_mgr.get_session = AsyncMock(return_value=session)

        # Mock plugin connector - normal event (not prevented)
        mock_event_ctx = Mock()
        mock_event_ctx.is_prevented_default = Mock(return_value=False)
        mock_event_ctx.event = Mock()
        mock_event_ctx.event.reply_message_chain = None
        app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        stage = wrapper.ResponseWrapper(app)

        pipeline_config = make_wrapper_config()

        await stage.initialize(pipeline_config)

        query = text_query("hello")
        query.pipeline_config = pipeline_config
        query.resp_message_chain = []

        # Create assistant response with content
        assistant_resp = Mock()
        assistant_resp.role = 'assistant'
        assistant_resp.content = "Hello back!"
        assistant_resp.tool_calls = None
        assistant_resp.get_content_platform_message_chain = Mock(
            return_value=platform_message.MessageChain([platform_message.Plain(text="Hello back!")])
        )
        query.resp_messages = [assistant_resp]

        results = []
        async for result in stage.process(query, 'ResponseWrapper'):
            results.append(result)

        assert len(results) == 1
        assert results[0].result_type == entities.ResultType.CONTINUE
        # Event should have been emitted
        app.plugin_connector.emit_event.assert_called()

    @pytest.mark.asyncio
    async def test_assistant_empty_content(self):
        """Assistant with empty content should not emit event."""
        wrapper = get_wrapper_module()

        app = FakeApp()
        app.plugin_connector.emit_event = AsyncMock()
        stage = wrapper.ResponseWrapper(app)

        pipeline_config = make_wrapper_config()

        await stage.initialize(pipeline_config)

        query = text_query("hello")
        query.pipeline_config = pipeline_config
        query.resp_message_chain = []

        # Create assistant response with empty content
        assistant_resp = Mock()
        assistant_resp.role = 'assistant'
        assistant_resp.content = None
        assistant_resp.tool_calls = None
        query.resp_messages = [assistant_resp]

        results = []
        async for result in stage.process(query, 'ResponseWrapper'):
            results.append(result)

        assert results == []
        assert query.resp_message_chain == []
        app.plugin_connector.emit_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_assistant_tool_calls(self):
        """Assistant with tool_calls should show function call message."""
        wrapper = get_wrapper_module()
        entities = get_entities_module()

        app = FakeApp()

        # Mock session manager to return a valid Session
        session = make_session()
        app.sess_mgr.get_session = AsyncMock(return_value=session)

        # Mock plugin connector
        mock_event_ctx = Mock()
        mock_event_ctx.is_prevented_default = Mock(return_value=False)
        mock_event_ctx.event = Mock()
        mock_event_ctx.event.reply_message_chain = None
        app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        stage = wrapper.ResponseWrapper(app)

        pipeline_config = make_wrapper_config()
        pipeline_config['output']['misc']['track-function-calls'] = True

        await stage.initialize(pipeline_config)

        query = text_query("hello")
        query.pipeline_config = pipeline_config
        query.resp_message_chain = []

        # Create assistant response with tool_calls
        mock_tool_call = Mock()
        mock_tool_call.function = Mock()
        mock_tool_call.function.name = 'test_function'

        assistant_resp = Mock()
        assistant_resp.role = 'assistant'
        assistant_resp.content = "Processing..."
        assistant_resp.tool_calls = [mock_tool_call]
        assistant_resp.get_content_platform_message_chain = Mock(
            return_value=platform_message.MessageChain([platform_message.Plain(text="Processing...")])
        )
        query.resp_messages = [assistant_resp]

        results = []
        async for result in stage.process(query, 'ResponseWrapper'):
            results.append(result)

        assert len(results) == 2
        for result in results:
            assert result.result_type == entities.ResultType.CONTINUE
        assert app.plugin_connector.emit_event.await_count == 2


class TestResponseWrapperInterrupt:
    """Tests for INTERRUPT behavior when plugin prevents default."""

    @pytest.mark.asyncio
    async def test_event_prevented_interrupts(self):
        """Plugin event prevented should return INTERRUPT."""
        wrapper = get_wrapper_module()
        entities = get_entities_module()

        app = FakeApp()

        # Mock session manager to return a valid Session
        session = make_session()
        app.sess_mgr.get_session = AsyncMock(return_value=session)

        # Mock plugin connector - event is prevented
        mock_event_ctx = Mock()
        mock_event_ctx.is_prevented_default = Mock(return_value=True)
        app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        stage = wrapper.ResponseWrapper(app)

        pipeline_config = make_wrapper_config()

        await stage.initialize(pipeline_config)

        query = text_query("hello")
        query.pipeline_config = pipeline_config
        query.resp_message_chain = []

        # Create assistant response with content
        assistant_resp = Mock()
        assistant_resp.role = 'assistant'
        assistant_resp.content = "Hello!"
        assistant_resp.tool_calls = None
        assistant_resp.get_content_platform_message_chain = Mock(
            return_value=platform_message.MessageChain([platform_message.Plain(text="Hello!")])
        )
        query.resp_messages = [assistant_resp]

        results = []
        async for result in stage.process(query, 'ResponseWrapper'):
            results.append(result)

        assert len(results) == 1
        assert results[0].result_type == entities.ResultType.INTERRUPT


class TestResponseWrapperCustomReply:
    """Tests for custom reply from plugin event."""

    @pytest.mark.asyncio
    async def test_custom_reply_chain_used(self):
        """Plugin reply_message_chain should replace default."""
        wrapper = get_wrapper_module()
        entities = get_entities_module()

        app = FakeApp()

        # Mock session manager to return a valid Session
        session = make_session()
        app.sess_mgr.get_session = AsyncMock(return_value=session)

        # Mock plugin connector with custom reply
        custom_chain = platform_message.MessageChain([platform_message.Plain(text="Custom reply")])
        mock_event_ctx = Mock()
        mock_event_ctx.is_prevented_default = Mock(return_value=False)
        mock_event_ctx.event = Mock()
        mock_event_ctx.event.reply_message_chain = custom_chain
        app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        stage = wrapper.ResponseWrapper(app)

        pipeline_config = make_wrapper_config()

        await stage.initialize(pipeline_config)

        query = text_query("hello")
        query.pipeline_config = pipeline_config
        query.resp_message_chain = []

        # Create assistant response
        assistant_resp = Mock()
        assistant_resp.role = 'assistant'
        assistant_resp.content = "Default reply"
        assistant_resp.tool_calls = None
        assistant_resp.get_content_platform_message_chain = Mock(
            return_value=platform_message.MessageChain([platform_message.Plain(text="Default reply")])
        )
        query.resp_messages = [assistant_resp]

        results = []
        async for result in stage.process(query, 'ResponseWrapper'):
            results.append(result)

        assert len(results) == 1
        assert results[0].result_type == entities.ResultType.CONTINUE
        # Custom chain should be in resp_message_chain
        assert len(results[0].new_query.resp_message_chain) == 1
        # Should be the custom chain
        chain = results[0].new_query.resp_message_chain[0]
        assert "Custom reply" in str(chain)


class TestResponseWrapperVariables:
    """Tests for bound plugins variable."""

    @pytest.mark.asyncio
    async def test_bound_plugins_passed_to_event(self):
        """_pipeline_bound_plugins should be passed to emit_event."""
        wrapper = get_wrapper_module()
        get_entities_module()

        app = FakeApp()

        # Mock session manager to return a valid Session
        session = make_session()
        app.sess_mgr.get_session = AsyncMock(return_value=session)

        # Mock plugin connector
        mock_event_ctx = Mock()
        mock_event_ctx.is_prevented_default = Mock(return_value=False)
        mock_event_ctx.event = Mock()
        mock_event_ctx.event.reply_message_chain = None
        app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        stage = wrapper.ResponseWrapper(app)

        pipeline_config = make_wrapper_config()

        await stage.initialize(pipeline_config)

        query = text_query("hello")
        query.pipeline_config = pipeline_config
        query.resp_message_chain = []
        query.variables['_pipeline_bound_plugins'] = ['plugin1', 'plugin2']

        # Create assistant response
        assistant_resp = Mock()
        assistant_resp.role = 'assistant'
        assistant_resp.content = "Hello"
        assistant_resp.tool_calls = None
        assistant_resp.get_content_platform_message_chain = Mock(
            return_value=platform_message.MessageChain([platform_message.Plain(text="Hello")])
        )
        query.resp_messages = [assistant_resp]

        results = []
        async for result in stage.process(query, 'ResponseWrapper'):
            results.append(result)

        # Check that bound_plugins was passed
        emit_call = app.plugin_connector.emit_event.call_args
        assert emit_call[0][1] == ['plugin1', 'plugin2']  # Second argument is bound_plugins
