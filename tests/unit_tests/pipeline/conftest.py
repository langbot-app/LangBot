"""
Shared test fixtures and configuration

This file provides infrastructure for all pipeline tests, including:
- Mock object factories
- Test fixtures
- Common test helper functions
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock
from typing import Any

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.provider.session as provider_session
import langbot_plugin.api.entities.builtin.provider.message as provider_message

from pkg.pipeline import entities as pipeline_entities


class MockApplication:
    """Mock Application object providing all basic dependencies needed by stages"""

    def __init__(self):
        self.logger = self._create_mock_logger()
        self.sess_mgr = self._create_mock_session_manager()
        self.model_mgr = self._create_mock_model_manager()
        self.tool_mgr = self._create_mock_tool_manager()
        self.plugin_connector = self._create_mock_plugin_connector()
        self.persistence_mgr = self._create_mock_persistence_manager()
        self.query_pool = self._create_mock_query_pool()
        self.instance_config = self._create_mock_instance_config()
        self.task_mgr = self._create_mock_task_manager()

    def _create_mock_logger(self):
        logger = Mock()
        logger.debug = Mock()
        logger.info = Mock()
        logger.error = Mock()
        logger.warning = Mock()
        return logger

    def _create_mock_session_manager(self):
        sess_mgr = AsyncMock()
        sess_mgr.get_session = AsyncMock()
        sess_mgr.get_conversation = AsyncMock()
        return sess_mgr

    def _create_mock_model_manager(self):
        model_mgr = AsyncMock()
        model_mgr.get_model_by_uuid = AsyncMock()
        return model_mgr

    def _create_mock_tool_manager(self):
        tool_mgr = AsyncMock()
        tool_mgr.get_all_tools = AsyncMock(return_value=[])
        return tool_mgr

    def _create_mock_plugin_connector(self):
        plugin_connector = AsyncMock()
        plugin_connector.emit_event = AsyncMock()
        return plugin_connector

    def _create_mock_persistence_manager(self):
        persistence_mgr = AsyncMock()
        persistence_mgr.execute_async = AsyncMock()
        return persistence_mgr

    def _create_mock_query_pool(self):
        query_pool = Mock()
        query_pool.cached_queries = {}
        query_pool.queries = []
        query_pool.condition = AsyncMock()
        return query_pool

    def _create_mock_instance_config(self):
        instance_config = Mock()
        instance_config.data = {
            'command': {'prefix': ['/', '!'], 'enable': True},
            'concurrency': {'pipeline': 10},
        }
        return instance_config

    def _create_mock_task_manager(self):
        task_mgr = Mock()
        task_mgr.create_task = Mock()
        return task_mgr


@pytest.fixture
def mock_app():
    """Provides Mock Application instance"""
    return MockApplication()


@pytest.fixture
def mock_session():
    """Provides Mock Session object"""
    session = Mock()
    session.launcher_type = provider_session.LauncherTypes.PERSON
    session.launcher_id = 12345
    session._semaphore = AsyncMock()
    session._semaphore.locked = Mock(return_value=False)
    session._semaphore.acquire = AsyncMock()
    session._semaphore.release = AsyncMock()
    return session


@pytest.fixture
def mock_conversation():
    """Provides Mock Conversation object"""
    conversation = Mock()
    conversation.uuid = 'test-conversation-uuid'

    # Create mock prompt with copy method
    mock_prompt = Mock()
    mock_prompt.messages = []
    mock_prompt.copy = Mock(return_value=Mock(messages=[]))
    conversation.prompt = mock_prompt

    # Create mock messages list with copy method
    mock_messages = Mock()
    mock_messages.copy = Mock(return_value=[])
    conversation.messages = mock_messages

    return conversation


@pytest.fixture
def mock_model():
    """Provides Mock Model object"""
    model = Mock()
    model.model_entity = Mock()
    model.model_entity.uuid = 'test-model-uuid'
    model.model_entity.abilities = ['func_call', 'vision']
    return model


@pytest.fixture
def mock_adapter():
    """Provides Mock Adapter object"""
    adapter = AsyncMock()
    adapter.is_stream_output_supported = AsyncMock(return_value=False)
    adapter.reply_message = AsyncMock()
    adapter.reply_message_chunk = AsyncMock()
    return adapter


@pytest.fixture
def sample_message_chain():
    """Provides sample message chain"""
    return platform_message.MessageChain(
        [
            platform_message.Plain(text='Hello, this is a test message'),
        ]
    )


@pytest.fixture
def sample_message_event(sample_message_chain):
    """Provides sample message event"""
    event = Mock()
    event.sender = Mock()
    event.sender.id = 12345
    event.time = 1609459200  # 2021-01-01 00:00:00
    return event


@pytest.fixture
def sample_query(sample_message_chain, sample_message_event, mock_adapter):
    """Provides sample Query object - using model_construct to bypass validation"""
    import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query

    # Use model_construct to bypass Pydantic validation for test purposes
    query = pipeline_query.Query.model_construct(
        query_id='test-query-id',
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id=12345,
        sender_id=12345,
        message_chain=sample_message_chain,
        message_event=sample_message_event,
        adapter=mock_adapter,
        pipeline_uuid='test-pipeline-uuid',
        bot_uuid='test-bot-uuid',
        pipeline_config={
            'ai': {
                'runner': {'runner': 'local-agent'},
                'local-agent': {'model': 'test-model-uuid', 'prompt': 'test-prompt'},
            },
            'output': {'misc': {'at-sender': False, 'quote-origin': False}},
            'trigger': {'misc': {'combine-quote-message': False}},
        },
        session=None,
        prompt=None,
        messages=[],
        user_message=None,
        use_funcs=[],
        use_llm_model_uuid=None,
        variables={},
        resp_messages=[],
        resp_message_chain=None,
        current_stage_name=None
    )
    return query


@pytest.fixture
def sample_pipeline_config():
    """Provides sample pipeline configuration"""
    return {
        'ai': {
            'runner': {'runner': 'local-agent'},
            'local-agent': {'model': 'test-model-uuid', 'prompt': 'test-prompt'},
        },
        'output': {'misc': {'at-sender': False, 'quote-origin': False}},
        'trigger': {'misc': {'combine-quote-message': False}},
        'ratelimit': {'enable': True, 'algo': 'fixwin', 'window': 60, 'limit': 10},
    }


def create_stage_result(
    result_type: pipeline_entities.ResultType,
    query: pipeline_query.Query,
    user_notice: str = '',
    console_notice: str = '',
    debug_notice: str = '',
    error_notice: str = '',
) -> pipeline_entities.StageProcessResult:
    """Helper function to create stage process result"""
    return pipeline_entities.StageProcessResult(
        result_type=result_type,
        new_query=query,
        user_notice=user_notice,
        console_notice=console_notice,
        debug_notice=debug_notice,
        error_notice=error_notice,
    )


def assert_result_continue(result: pipeline_entities.StageProcessResult):
    """Assert result is CONTINUE type"""
    assert result.result_type == pipeline_entities.ResultType.CONTINUE


def assert_result_interrupt(result: pipeline_entities.StageProcessResult):
    """Assert result is INTERRUPT type"""
    assert result.result_type == pipeline_entities.ResultType.INTERRUPT
