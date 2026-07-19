"""Unit tests for SessionManager.

Tests cover:
- Session creation and retrieval
- Conversation creation with prompts
- Session concurrency semaphore
"""

from __future__ import annotations

import pytest
import asyncio
from types import SimpleNamespace
from unittest.mock import Mock
from importlib import import_module

import langbot_plugin.api.entities.builtin.provider.session as provider_session
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.pipeline.pool import (
    ExecutionContextMismatchError,
    ExecutionContextRequiredError,
)


TEST_CONTEXT = ExecutionContext(
    instance_uuid='instance-test',
    workspace_uuid='workspace-test',
    placement_generation=1,
)
TEST_BOT_UUID = 'bot-123'


def bind_query_context(query, *, context=TEST_CONTEXT, bot_uuid=TEST_BOT_UUID):
    """Attach the trusted runtime scope expected by the session manager."""
    query.bot_uuid = bot_uuid
    query._execution_context = context
    return query


def bind_session_context(session, query):
    """Make a mocked legacy Session belong to the Query execution scope."""
    session.bot_uuid = query.bot_uuid
    session._langbot_session_key = (
        TEST_CONTEXT.instance_uuid,
        TEST_CONTEXT.workspace_uuid,
        TEST_CONTEXT.placement_generation,
        query.bot_uuid,
        query.launcher_type.value,
        query.launcher_id,
    )
    return session


def scoped_query(
    *,
    workspace_uuid='workspace-test',
    bot_uuid=TEST_BOT_UUID,
    placement_generation=1,
    pipeline_uuid=None,
):
    """Create a small Query-like object with a complete trusted scope."""
    context = ExecutionContext(
        instance_uuid='instance-test',
        workspace_uuid=workspace_uuid,
        placement_generation=placement_generation,
        bot_uuid=bot_uuid,
        pipeline_uuid=pipeline_uuid,
        query_uuid=f'query-{workspace_uuid}-{bot_uuid}',
    )
    return SimpleNamespace(
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id='same-launcher',
        sender_id='same-sender',
        bot_uuid=bot_uuid,
        _execution_context=context,
    )


def get_session_module():
    """Lazy import to avoid circular import issues."""
    return import_module('langbot.pkg.provider.session.sessionmgr')


class TestSessionManagerInit:
    """Tests for SessionManager initialization."""

    def test_init_stores_app_reference(self):
        """Test that __init__ stores the Application reference."""
        sessionmgr = get_session_module()

        mock_app = Mock()
        manager = sessionmgr.SessionManager(mock_app)
        assert manager.ap is mock_app

    def test_init_empty_session_list(self):
        """Test that session_list starts empty."""
        sessionmgr = get_session_module()

        mock_app = Mock()
        manager = sessionmgr.SessionManager(mock_app)
        assert manager.session_list == []

    @pytest.mark.asyncio
    async def test_initialize_empty(self):
        """Test that initialize does nothing (current implementation)."""
        sessionmgr = get_session_module()

        mock_app = Mock()
        manager = sessionmgr.SessionManager(mock_app)
        await manager.initialize()
        # Should not raise or change state
        assert manager.session_list == []


class TestSessionManagerGetSession:
    """Tests for get_session method."""

    @pytest.fixture
    def mock_app_with_config(self):
        """Create mock app with instance config."""
        mock_app = Mock()
        mock_app.instance_config = Mock()
        mock_app.instance_config.data = {'concurrency': {'session': 5}}
        return mock_app

    @pytest.fixture
    def sample_query(self):
        """Create sample query for testing."""
        query = Mock(spec=pipeline_query.Query)
        query.launcher_type = provider_session.LauncherTypes.PERSON
        query.launcher_id = '12345'
        query.sender_id = '12345'
        return bind_query_context(query)

    @pytest.mark.asyncio
    async def test_creates_new_session_when_not_found(self, mock_app_with_config, sample_query):
        """Test that get_session creates new session when not found."""
        sessionmgr = get_session_module()

        manager = sessionmgr.SessionManager(mock_app_with_config)
        session = await manager.get_session(sample_query)

        assert session is not None
        assert session.launcher_type == sample_query.launcher_type
        assert session.launcher_id == sample_query.launcher_id
        assert session.sender_id == sample_query.sender_id
        assert len(manager.session_list) == 1

    @pytest.mark.asyncio
    async def test_returns_existing_session_when_found(self, mock_app_with_config, sample_query):
        """Test that get_session returns existing session when found."""
        sessionmgr = get_session_module()

        manager = sessionmgr.SessionManager(mock_app_with_config)

        # First call creates session
        session1 = await manager.get_session(sample_query)

        # Second call should return same session
        session2 = await manager.get_session(sample_query)

        assert session1 is session2
        assert len(manager.session_list) == 1

    @pytest.mark.asyncio
    async def test_session_has_semaphore(self, mock_app_with_config, sample_query):
        """Test that created session has semaphore for concurrency."""
        sessionmgr = get_session_module()

        manager = sessionmgr.SessionManager(mock_app_with_config)
        session = await manager.get_session(sample_query)

        assert hasattr(session, '_semaphore')
        assert session._semaphore is not None
        assert isinstance(session._semaphore, asyncio.Semaphore)

    @pytest.mark.asyncio
    async def test_different_launchers_have_different_sessions(self, mock_app_with_config):
        """Test that different launcher_id creates different sessions."""
        sessionmgr = get_session_module()

        manager = sessionmgr.SessionManager(mock_app_with_config)

        query1 = Mock(spec=pipeline_query.Query)
        query1.launcher_type = provider_session.LauncherTypes.PERSON
        query1.launcher_id = 'user1'
        query1.sender_id = 'user1'
        bind_query_context(query1)

        query2 = Mock(spec=pipeline_query.Query)
        query2.launcher_type = provider_session.LauncherTypes.PERSON
        query2.launcher_id = 'user2'
        query2.sender_id = 'user2'
        bind_query_context(query2)

        session1 = await manager.get_session(query1)
        session2 = await manager.get_session(query2)

        assert session1 is not session2
        assert len(manager.session_list) == 2

    @pytest.mark.asyncio
    async def test_different_launcher_types_have_different_sessions(self, mock_app_with_config):
        """Test that different launcher_type creates different sessions."""
        sessionmgr = get_session_module()

        manager = sessionmgr.SessionManager(mock_app_with_config)

        query1 = Mock(spec=pipeline_query.Query)
        query1.launcher_type = provider_session.LauncherTypes.PERSON
        query1.launcher_id = 'same_id'
        query1.sender_id = 'same_id'
        bind_query_context(query1)

        query2 = Mock(spec=pipeline_query.Query)
        query2.launcher_type = provider_session.LauncherTypes.GROUP
        query2.launcher_id = 'same_id'
        query2.sender_id = 'same_id'
        bind_query_context(query2)

        session1 = await manager.get_session(query1)
        session2 = await manager.get_session(query2)

        assert session1 is not session2
        assert len(manager.session_list) == 2


class TestSessionManagerGetConversation:
    """Tests for get_conversation method."""

    @pytest.fixture
    def mock_app_with_config(self):
        """Create mock app with instance config."""
        mock_app = Mock()
        mock_app.instance_config = Mock()
        mock_app.instance_config.data = {'concurrency': {'session': 5}}
        return mock_app

    @pytest.fixture
    def sample_session(self):
        """Create sample session for testing."""
        session = Mock(spec=provider_session.Session)
        session.launcher_type = provider_session.LauncherTypes.PERSON
        session.launcher_id = '12345'
        session.sender_id = '12345'
        session.conversations = []
        session.using_conversation = None
        return session

    @pytest.fixture
    def sample_query(self):
        """Create sample query for testing."""
        query = Mock(spec=pipeline_query.Query)
        query.launcher_type = provider_session.LauncherTypes.PERSON
        query.launcher_id = '12345'
        query.sender_id = '12345'
        return bind_query_context(query)

    @pytest.mark.asyncio
    async def test_creates_conversation_with_prompt(self, mock_app_with_config, sample_query, sample_session):
        """Test that get_conversation creates conversation with prompt."""
        sessionmgr = get_session_module()

        manager = sessionmgr.SessionManager(mock_app_with_config)
        bind_session_context(sample_session, sample_query)

        prompt_config = [{'role': 'system', 'content': 'You are a helpful assistant.'}]
        pipeline_uuid = 'pipeline-123'
        bot_uuid = 'bot-123'

        conversation = await manager.get_conversation(
            sample_query, sample_session, prompt_config, pipeline_uuid, bot_uuid
        )

        assert conversation is not None
        assert conversation.pipeline_uuid == pipeline_uuid
        assert conversation.bot_uuid == bot_uuid
        assert conversation.prompt is not None
        assert len(sample_session.conversations) == 1

    @pytest.mark.asyncio
    async def test_uses_existing_conversation_when_pipeline_matches(
        self, mock_app_with_config, sample_query, sample_session
    ):
        """Test that get_conversation uses existing conversation when pipeline matches."""
        sessionmgr = get_session_module()

        manager = sessionmgr.SessionManager(mock_app_with_config)
        bind_session_context(sample_session, sample_query)

        prompt_config = [{'role': 'system', 'content': 'You are a helpful assistant.'}]
        pipeline_uuid = 'pipeline-123'
        bot_uuid = 'bot-123'

        # First call creates conversation
        conv1 = await manager.get_conversation(sample_query, sample_session, prompt_config, pipeline_uuid, bot_uuid)

        # Second call with same pipeline should return same conversation
        conv2 = await manager.get_conversation(sample_query, sample_session, prompt_config, pipeline_uuid, bot_uuid)

        assert conv1 is conv2
        assert len(sample_session.conversations) == 1

    @pytest.mark.asyncio
    async def test_creates_new_conversation_when_pipeline_changes(
        self, mock_app_with_config, sample_query, sample_session
    ):
        """Test that get_conversation creates new conversation when pipeline changes."""
        sessionmgr = get_session_module()

        manager = sessionmgr.SessionManager(mock_app_with_config)
        bind_session_context(sample_session, sample_query)

        prompt_config = [{'role': 'system', 'content': 'You are a helpful assistant.'}]

        # First call with pipeline1
        conv1 = await manager.get_conversation(sample_query, sample_session, prompt_config, 'pipeline-1', TEST_BOT_UUID)

        # Second call with different pipeline should create new conversation
        conv2 = await manager.get_conversation(sample_query, sample_session, prompt_config, 'pipeline-2', TEST_BOT_UUID)

        assert conv1 is not conv2
        assert len(sample_session.conversations) == 2
        assert sample_session.using_conversation is conv2

    @pytest.mark.asyncio
    async def test_conversation_has_empty_messages(self, mock_app_with_config, sample_query, sample_session):
        """Test that created conversation has empty messages list."""
        sessionmgr = get_session_module()

        manager = sessionmgr.SessionManager(mock_app_with_config)
        bind_session_context(sample_session, sample_query)

        prompt_config = [{'role': 'system', 'content': 'You are a helpful assistant.'}]

        conversation = await manager.get_conversation(
            sample_query, sample_session, prompt_config, 'pipeline-123', 'bot-123'
        )

        assert conversation.messages == []

    @pytest.mark.asyncio
    async def test_prompt_messages_from_config(self, mock_app_with_config, sample_query, sample_session):
        """Test that prompt messages are created from prompt_config."""
        sessionmgr = get_session_module()

        manager = sessionmgr.SessionManager(mock_app_with_config)
        bind_session_context(sample_session, sample_query)

        prompt_config = [{'role': 'system', 'content': 'System message'}, {'role': 'user', 'content': 'User message'}]

        conversation = await manager.get_conversation(
            sample_query, sample_session, prompt_config, 'pipeline-123', 'bot-123'
        )

        assert conversation.prompt.name == 'default'
        assert len(conversation.prompt.messages) == 2


class TestSessionManagerWorkspaceIsolation:
    """Regression coverage for workspace, bot, and placement fencing."""

    @staticmethod
    def manager():
        mock_app = Mock()
        mock_app.instance_config.data = {'concurrency': {'session': 5}}
        return get_session_module().SessionManager(mock_app)

    @pytest.mark.asyncio
    async def test_get_session_requires_trusted_query_scope(self):
        query = SimpleNamespace(
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='same-launcher',
            sender_id='same-sender',
            bot_uuid=TEST_BOT_UUID,
        )

        with pytest.raises(ExecutionContextRequiredError):
            await self.manager().get_session(query)

    @pytest.mark.asyncio
    async def test_same_launcher_in_two_workspaces_does_not_share_session(self):
        manager = self.manager()

        first = await manager.get_session(scoped_query(workspace_uuid='workspace-a'))
        second = await manager.get_session(scoped_query(workspace_uuid='workspace-b'))

        assert first is not second
        assert len(manager.session_list) == 2

    @pytest.mark.asyncio
    async def test_same_launcher_in_two_bots_does_not_share_session(self):
        manager = self.manager()

        first = await manager.get_session(scoped_query(bot_uuid='bot-a'))
        second = await manager.get_session(scoped_query(bot_uuid='bot-b'))

        assert first is not second

    @pytest.mark.asyncio
    async def test_new_placement_generation_does_not_reuse_old_session(self):
        manager = self.manager()

        first = await manager.get_session(scoped_query(placement_generation=1))
        second = await manager.get_session(scoped_query(placement_generation=2))

        assert first is not second

    @pytest.mark.asyncio
    async def test_conversation_rejects_session_from_another_workspace(self):
        manager = self.manager()
        query_a = scoped_query(workspace_uuid='workspace-a')
        query_b = scoped_query(workspace_uuid='workspace-b')
        session_a = await manager.get_session(query_a)

        with pytest.raises(ExecutionContextMismatchError):
            await manager.get_conversation(query_b, session_a, [], 'pipeline-1', TEST_BOT_UUID)

    @pytest.mark.asyncio
    async def test_conversation_rejects_substituted_bot_argument(self):
        manager = self.manager()
        query = scoped_query(bot_uuid='bot-a')
        session = await manager.get_session(query)

        with pytest.raises(ExecutionContextMismatchError):
            await manager.get_conversation(query, session, [], 'pipeline-1', 'bot-b')
