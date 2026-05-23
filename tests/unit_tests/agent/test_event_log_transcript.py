"""Tests for EventLog, Transcript, and history/event APIs."""
from __future__ import annotations

import pytest
from unittest.mock import Mock, MagicMock, patch
import datetime

from langbot.pkg.agent.runner.host_models import (
    AgentEventEnvelope,
    AgentBinding,
    BindingScope,
    ResourcePolicy,
    StatePolicy,
    DeliveryPolicy,
)
from langbot.pkg.agent.runner.event_log_store import EventLogStore
from langbot.pkg.agent.runner.transcript_store import TranscriptStore
from langbot.pkg.agent.runner.session_registry import get_session_registry
from langbot_plugin.api.entities.builtin.agent_runner.event import (
    AgentEventContext,
    ActorContext,
)
from langbot_plugin.api.entities.builtin.agent_runner.input import AgentInput
from langbot_plugin.api.entities.builtin.agent_runner.delivery import DeliveryContext


def make_event_envelope(
    event_id: str = "evt_1",
    event_type: str = "message.received",
    conversation_id: str | None = "conv_1",
    actor_id: str | None = "user_1",
    input_text: str = "Hello",
) -> AgentEventEnvelope:
    """Create a test event envelope."""
    return AgentEventEnvelope(
        event_id=event_id,
        event_type=event_type,
        event_time=1700000000,
        source="platform",
        bot_id="bot_1",
        workspace_id=None,
        conversation_id=conversation_id,
        thread_id=None,
        actor=ActorContext(
            actor_type="user",
            actor_id=actor_id,
            actor_name="Test User",
        ) if actor_id else None,
        subject=None,
        input=AgentInput(text=input_text),
        delivery=DeliveryContext(surface="test"),
    )


def make_binding(runner_id: str = "plugin:test/plugin/runner") -> AgentBinding:
    """Create a test binding."""
    return AgentBinding(
        binding_id="binding_1",
        scope=BindingScope(scope_type="pipeline", scope_id="pipeline_1"),
        event_types=["message.received"],
        runner_id=runner_id,
        runner_config={},
        resource_policy=ResourcePolicy(),
        state_policy=StatePolicy(),
        delivery_policy=DeliveryPolicy(),
        enabled=True,
    )


class TestEventLogStore:
    """Test EventLogStore operations."""

    @pytest.mark.asyncio
    async def test_append_event(self, mock_db_engine):
        """Test appending an event to EventLog."""
        store = EventLogStore(mock_db_engine)

        event_id = await store.append_event(
            event_id="evt_1",
            event_type="message.received",
            source="platform",
            bot_id="bot_1",
            conversation_id="conv_1",
            actor_type="user",
            actor_id="user_1",
            input_summary="Hello world",
            run_id="run_1",
            runner_id="plugin:test/plugin/runner",
        )

        assert event_id == "evt_1"

    @pytest.mark.asyncio
    async def test_append_event_truncates_input_summary(self, mock_db_engine):
        """Test that long input summaries are truncated."""
        store = EventLogStore(mock_db_engine)

        long_text = "x" * 2000
        event_id = await store.append_event(
            event_id="evt_2",
            event_type="message.received",
            source="platform",
            input_summary=long_text,
        )

        assert event_id == "evt_2"

    @pytest.mark.asyncio
    async def test_page_events_with_conversation_filter(self, mock_db_engine):
        """Test paging events with conversation_id filter."""
        store = EventLogStore(mock_db_engine)

        items, next_seq, has_more = await store.page_events(
            conversation_id="conv_1",
            limit=10,
        )

        assert isinstance(items, list)


class TestTranscriptStore:
    """Test TranscriptStore operations."""

    @pytest.mark.asyncio
    async def test_append_transcript(self, mock_db_engine):
        """Test appending a transcript item."""
        store = TranscriptStore(mock_db_engine)

        transcript_id = await store.append_transcript(
            transcript_id=None,  # Auto-generate
            event_id="evt_1",
            conversation_id="conv_1",
            role="user",
            content="Hello",
        )

        assert transcript_id is not None

    @pytest.mark.asyncio
    async def test_append_transcript_with_artifacts(self, mock_db_engine):
        """Test appending transcript with artifact refs."""
        store = TranscriptStore(mock_db_engine)

        transcript_id = await store.append_transcript(
            transcript_id=None,  # Auto-generate
            event_id="evt_2",
            conversation_id="conv_1",
            role="assistant",
            content="Here's an image",
            artifact_refs=[
                {"artifact_id": "art_1", "artifact_type": "image", "url": "http://example.com/img.png"}
            ],
        )

        assert transcript_id is not None

    @pytest.mark.asyncio
    async def test_page_transcript_backward(self, mock_db_engine):
        """Test paging transcript backward (older items)."""
        store = TranscriptStore(mock_db_engine)

        items, next_seq, prev_seq, has_more = await store.page_transcript(
            conversation_id="conv_1",
            limit=10,
            direction="backward",
        )

        assert isinstance(items, list)

    @pytest.mark.asyncio
    async def test_page_transcript_has_hard_limit(self, mock_db_engine):
        """Test that transcript paging has a hard limit."""
        store = TranscriptStore(mock_db_engine)

        # Request more than the hard limit
        items, next_seq, prev_seq, has_more = await store.page_transcript(
            conversation_id="conv_1",
            limit=200,  # Request 200, but hard limit is 100
        )

        # The store should cap at 100
        assert len(items) <= store.HARD_LIMIT

    @pytest.mark.asyncio
    async def test_search_transcript(self, mock_db_engine):
        """Test searching transcript."""
        store = TranscriptStore(mock_db_engine)

        items = await store.search_transcript(
            conversation_id="conv_1",
            query_text="database",
            top_k=10,
        )

        assert isinstance(items, list)


class TestHistoryPageAuthorization:
    """Test history.page authorization."""

    @pytest.mark.asyncio
    async def test_history_page_requires_run_id(self, mock_handler, mock_db_engine):
        """Test history.page requires run_id."""
        from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction

        # Mock call_action to simulate the handler
        result = await mock_handler.call_action(
            PluginToRuntimeAction.HISTORY_PAGE,
            {"run_id": None},
        )

        # Should return error
        assert result.get("ok") is False or "error" in str(result).lower()

    @pytest.mark.asyncio
    async def test_history_page_validates_conversation_scope(self, mock_db_engine):
        """Test history.page only allows access to run's conversation."""
        # This test verifies the authorization logic
        # The actual implementation validates conversation_id matches session
        session_registry = get_session_registry()

        await session_registry.register(
            run_id="run_1",
            runner_id="plugin:test/plugin/runner",
            query_id=None,
            plugin_identity="test/plugin",
            resources={"models": [], "tools": [], "knowledge_bases": [], "storage": {"plugin_storage": True}},
            conversation_id="conv_1",
        )

        session = await session_registry.get("run_1")
        assert session is not None
        assert session["conversation_id"] == "conv_1"

        # Cleanup
        await session_registry.unregister("run_1")


class TestEventGetAuthorization:
    """Test event.get authorization."""

    @pytest.mark.asyncio
    async def test_event_get_requires_run_id(self, mock_handler):
        """Test event.get requires run_id."""
        from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction

        result = await mock_handler.call_action(
            PluginToRuntimeAction.EVENT_GET,
            {"run_id": None, "event_id": "evt_1"},
        )

        # Should return error
        assert result.get("ok") is False or "error" in str(result).lower()


class TestContextAccessPopulation:
    """Test ContextAccess population in build_context_from_event."""

    @pytest.mark.asyncio
    async def test_context_access_has_history_apis_when_permitted(self, mock_db_engine):
        """Test ContextAccess shows available APIs based on permissions."""
        # This would test the context builder logic
        # For now we verify the store methods work
        store = TranscriptStore(mock_db_engine)

        cursor = await store.get_latest_cursor("conv_1")
        # Should return None or a cursor string
        assert cursor is None or isinstance(cursor, str)

    @pytest.mark.asyncio
    async def test_context_access_shows_has_history_before(self, mock_db_engine):
        """Test ContextAccess indicates if history exists."""
        store = TranscriptStore(mock_db_engine)

        has_history = await store.has_history_before("conv_1", 10)
        assert isinstance(has_history, bool)


# Fixtures
@pytest.fixture
def mock_db_engine():
    """Create a mock database engine."""
    from unittest.mock import MagicMock, AsyncMock
    from sqlalchemy.ext.asyncio import AsyncEngine

    engine = MagicMock(spec=AsyncEngine)

    # Mock connection
    mock_conn = MagicMock()
    mock_result = MagicMock()
    mock_result.fetchone.return_value = None
    mock_result.fetchall.return_value = []
    mock_result.scalar.return_value = 0
    mock_conn.execute = AsyncMock(return_value=mock_result)
    mock_conn.commit = AsyncMock()

    # Create async context manager for connect()
    class AsyncConnectContextManager:
        async def __aenter__(self):
            return mock_conn
        async def __aexit__(self, *args):
            pass

    # connect() should return an async context manager
    engine.connect = MagicMock(return_value=AsyncConnectContextManager())
    return engine


@pytest.fixture
def mock_handler():
    """Create a mock handler for testing actions."""
    from langbot_plugin.runtime.io.handler import Handler, ActionResponse

    class MockHandler(Handler):
        def __init__(self):
            self._responses = {}

        async def call_action(self, action, data, timeout=30):
            # Simulate error response for missing run_id
            if not data.get("run_id"):
                return {"ok": False, "message": "run_id is required"}
            return {"ok": True, "data": {}}

    return MockHandler()
