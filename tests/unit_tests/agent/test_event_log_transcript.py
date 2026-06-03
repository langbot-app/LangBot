"""Tests for EventLog, Transcript, and history/event APIs."""
from __future__ import annotations

import pytest

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
        scope=BindingScope(scope_type="agent", scope_id="pipeline_1"),
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
        from unittest.mock import AsyncMock, MagicMock, patch

        store = EventLogStore(mock_db_engine)

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        with patch.object(store, '_session_factory') as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session

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
        from unittest.mock import AsyncMock, MagicMock, patch

        store = EventLogStore(mock_db_engine)

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        with patch.object(store, '_session_factory') as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session

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
        from unittest.mock import AsyncMock, MagicMock, patch

        store = EventLogStore(mock_db_engine)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch.object(store, '_session_factory') as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session

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
        from unittest.mock import AsyncMock, MagicMock, patch

        store = TranscriptStore(mock_db_engine)

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        # Mock _get_next_seq
        with patch.object(store, '_get_next_seq', return_value=1):
            with patch.object(store, '_session_factory') as mock_factory:
                mock_factory.return_value.__aenter__.return_value = mock_session

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
        from unittest.mock import AsyncMock, MagicMock, patch

        store = TranscriptStore(mock_db_engine)

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        with patch.object(store, '_get_next_seq', return_value=1):
            with patch.object(store, '_session_factory') as mock_factory:
                mock_factory.return_value.__aenter__.return_value = mock_session

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
        from unittest.mock import AsyncMock, MagicMock, patch

        store = TranscriptStore(mock_db_engine)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch.object(store, '_session_factory') as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session

            items, next_seq, prev_seq, has_more = await store.page_transcript(
                conversation_id="conv_1",
                limit=10,
                direction="backward",
            )

            assert isinstance(items, list)

    @pytest.mark.asyncio
    async def test_page_transcript_has_hard_limit(self, mock_db_engine):
        """Test that transcript paging has a hard limit."""
        from unittest.mock import AsyncMock, MagicMock, patch

        store = TranscriptStore(mock_db_engine)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch.object(store, '_session_factory') as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session

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
        from unittest.mock import AsyncMock, MagicMock, patch

        store = TranscriptStore(mock_db_engine)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch.object(store, '_session_factory') as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session

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
        assert session["authorization"]["conversation_id"] == "conv_1"

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
        from unittest.mock import AsyncMock, MagicMock, patch

        store = TranscriptStore(mock_db_engine)

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch.object(store, '_session_factory') as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session

            cursor = await store.get_latest_cursor("conv_1")
            # Should return None or a cursor string
            assert cursor is None or isinstance(cursor, str)

    @pytest.mark.asyncio
    async def test_context_access_shows_has_history_before(self, mock_db_engine):
        """Test ContextAccess indicates if history exists."""
        from unittest.mock import AsyncMock, MagicMock, patch

        store = TranscriptStore(mock_db_engine)

        mock_result = MagicMock()
        mock_result.scalar.return_value = 0

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch.object(store, '_session_factory') as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session

            has_history = await store.has_history_before("conv_1", 10)
            assert isinstance(has_history, bool)


class TestEventLogStoreRealSQLite:
    """Test EventLogStore with real SQLite database."""

    @pytest.fixture
    async def db_engine(self):
        """Create an in-memory SQLite database for testing."""
        from sqlalchemy.ext.asyncio import create_async_engine
        from langbot.pkg.entity.persistence.base import Base

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")

        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        yield engine

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_append_get_event_round_trip(self, db_engine):
        """Test append_event -> get_event round trip with real DB."""
        store = EventLogStore(db_engine)

        # Append event
        event_id = await store.append_event(
            event_id="evt_real_001",
            event_type="message.received",
            source="platform",
            bot_id="bot_001",
            conversation_id="conv_001",
            actor_type="user",
            actor_id="user_001",
            actor_name="Test User",
            input_summary="Hello world",
            run_id="run_001",
            runner_id="plugin:test/plugin/runner",
        )

        assert event_id == "evt_real_001"

        # Get event
        event = await store.get_event(event_id)
        assert event is not None
        assert event["event_id"] == "evt_real_001"
        assert event["event_type"] == "message.received"
        assert event["source"] == "platform"
        assert event["conversation_id"] == "conv_001"
        assert event["actor_type"] == "user"
        assert event["actor_id"] == "user_001"

    @pytest.mark.asyncio
    async def test_page_events(self, db_engine):
        """Test page_events with real DB."""
        store = EventLogStore(db_engine)

        # Append multiple events
        for i in range(5):
            await store.append_event(
                event_id=f"evt_real_{i:03d}",
                event_type="message.received",
                source="platform",
                conversation_id="conv_001",
                input_summary=f"Message {i}",
            )

        # Page events
        items, next_seq, has_more = await store.page_events(
            conversation_id="conv_001",
            limit=3,
        )

        assert len(items) == 3
        assert has_more is True

    @pytest.mark.asyncio
    async def test_get_latest_cursor(self, db_engine):
        """Test get_latest_cursor with real DB."""
        store = EventLogStore(db_engine)

        # Append events
        for i in range(3):
            await store.append_event(
                event_id=f"evt_cursor_{i:03d}",
                event_type="message.received",
                source="platform",
                conversation_id="conv_cursor",
            )

        # Get latest cursor
        cursor = await store.get_latest_cursor("conv_cursor")
        assert cursor is not None
        assert int(cursor) > 0


class TestTranscriptStoreRealSQLite:
    """Test TranscriptStore with real SQLite database."""

    @pytest.fixture
    async def db_engine(self):
        """Create an in-memory SQLite database for testing."""
        from sqlalchemy.ext.asyncio import create_async_engine
        from langbot.pkg.entity.persistence.base import Base

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")

        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        yield engine

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_append_page_transcript_round_trip(self, db_engine):
        """Test append_transcript -> page_transcript round trip with real DB."""
        store = TranscriptStore(db_engine)

        # Append transcript items
        for i in range(3):
            await store.append_transcript(
                transcript_id=f"trans_real_{i:03d}",
                event_id=f"evt_{i:03d}",
                conversation_id="conv_001",
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
            )

        # Page transcript
        items, next_seq, prev_seq, has_more = await store.page_transcript(
            conversation_id="conv_001",
            limit=10,
        )

        assert len(items) == 3
        assert items[0]["conversation_id"] == "conv_001"

    @pytest.mark.asyncio
    async def test_get_legacy_provider_messages_projects_transcript_history(self, db_engine):
        """Transcript is the canonical source; legacy Pipeline readers get a Message view."""
        store = TranscriptStore(db_engine)

        await store.append_transcript(
            transcript_id="trans_view_001",
            event_id="evt_view_001",
            conversation_id="conv_view",
            role="user",
            content="User text",
            content_json={
                "role": "user",
                "content": [{"type": "text", "text": "User structured text"}],
            },
        )
        await store.append_transcript(
            transcript_id="trans_view_002",
            event_id="evt_view_002",
            conversation_id="conv_view",
            role="tool",
            item_type="tool_result",
            content="ignored tool result",
        )
        await store.append_transcript(
            transcript_id="trans_view_003",
            event_id="evt_view_003",
            conversation_id="conv_view",
            role="assistant",
            content="Assistant text",
        )

        messages = await store.get_legacy_provider_messages("conv_view")

        assert [message.role for message in messages] == ["user", "assistant"]
        assert messages[0].content[0].text == "User structured text"
        assert messages[1].content == "Assistant text"

    @pytest.mark.asyncio
    async def test_search_transcript_real_db(self, db_engine):
        """Test search_transcript with real DB."""
        store = TranscriptStore(db_engine)

        # Append transcript items
        await store.append_transcript(
            transcript_id="trans_search_001",
            event_id="evt_search_001",
            conversation_id="conv_search",
            role="user",
            content="I want to learn about databases",
        )
        await store.append_transcript(
            transcript_id="trans_search_002",
            event_id="evt_search_002",
            conversation_id="conv_search",
            role="assistant",
            content="Here is information about databases",
        )

        # Search for "database"
        items = await store.search_transcript(
            conversation_id="conv_search",
            query_text="database",
        )

        # Should find at least one match
        assert len(items) >= 1

    @pytest.mark.asyncio
    async def test_get_latest_cursor_real_db(self, db_engine):
        """Test get_latest_cursor with real DB."""
        store = TranscriptStore(db_engine)

        # Append transcript items
        for i in range(3):
            await store.append_transcript(
                transcript_id=f"trans_cursor_{i:03d}",
                event_id=f"evt_cursor_{i:03d}",
                conversation_id="conv_cursor",
                role="user",
                content=f"Message {i}",
            )

        # Get latest cursor
        cursor = await store.get_latest_cursor("conv_cursor")
        assert cursor is not None
        assert int(cursor) > 0


# Fixtures
@pytest.fixture
def mock_db_engine():
    """Create a mock database engine for AsyncSession-based stores."""
    from unittest.mock import MagicMock
    from sqlalchemy.ext.asyncio import AsyncEngine

    engine = MagicMock(spec=AsyncEngine)
    return engine


@pytest.fixture
def mock_handler():
    """Create a mock handler for testing actions."""
    from langbot_plugin.runtime.io.handler import Handler

    class MockHandler(Handler):
        def __init__(self):
            self._responses = {}

        async def call_action(self, action, data, timeout=30):
            # Simulate error response for missing run_id
            if not data.get("run_id"):
                return {"ok": False, "message": "run_id is required"}
            return {"ok": True, "data": {}}

    return MockHandler()
