"""Tests for TranscriptItem, HistoryPage, EventPage, AgentEventRecord entities."""

from __future__ import annotations

from langbot_plugin.api.entities.builtin.runner.transcript import TranscriptItem
from langbot_plugin.api.entities.builtin.runner.page_results import (
    HistoryPage,
    HistorySearchResult,
    AgentEventRecord,
    EventPage,
)


class TestTranscriptItem:
    """Test TranscriptItem serialization."""

    def test_transcript_item_basic(self):
        """Test basic TranscriptItem creation."""
        item = TranscriptItem(
            transcript_id="t1",
            event_id="e1",
            conversation_id="c1",
            role="user",
            content="Hello",
        )

        assert item.transcript_id == "t1"
        assert item.event_id == "e1"
        assert item.conversation_id == "c1"
        assert item.role == "user"
        assert item.content == "Hello"
        assert item.item_type == "message"  # default
        assert item.attachment_refs == []
        assert item.metadata == {}

    def test_transcript_item_serialization(self):
        """Test TranscriptItem model_dump."""
        item = TranscriptItem(
            transcript_id="t1",
            event_id="e1",
            conversation_id="c1",
            role="assistant",
            content="Hi there",
            attachment_refs=[{"id": "a1", "type": "image"}],
            seq=1,
            cursor="1",
            metadata={"sender_id": "user1"},
        )

        data = item.model_dump(mode="json")
        assert data["transcript_id"] == "t1"
        assert data["attachment_refs"] == [{"id": "a1", "type": "image"}]
        assert data["seq"] == 1

    def test_transcript_item_with_content_json(self):
        """Test TranscriptItem with structured content."""
        item = TranscriptItem(
            transcript_id="t2",
            event_id="e2",
            conversation_id="c1",
            role="assistant",
            content_json={"role": "assistant", "content": "Response"},
        )

        assert item.content_json == {"role": "assistant", "content": "Response"}

    def test_transcript_item_accepts_scope_fields(self):
        """Test TranscriptItem accepts host-provided scope fields."""
        item = TranscriptItem(
            transcript_id="t3",
            event_id="e3",
            conversation_id="c1",
            bot_id="bot1",
            workspace_id="ws1",
            role="user",
            content="Scoped message",
        )

        assert item.bot_id == "bot1"
        assert item.workspace_id == "ws1"

    def test_transcript_item_ignores_unknown_host_fields(self):
        """Test TranscriptItem ignores future Host response fields."""
        item = TranscriptItem.model_validate(
            {
                "transcript_id": "t4",
                "event_id": "e4",
                "conversation_id": "c1",
                "role": "user",
                "content": "Hi",
                "future_field": True,
            }
        )

        assert item.transcript_id == "t4"
        assert "future_field" not in item.model_dump()


class TestHistoryPage:
    """Test HistoryPage serialization."""

    def test_history_page_empty(self):
        """Test empty HistoryPage."""
        page = HistoryPage()

        assert page.items == []
        assert page.next_cursor is None
        assert page.prev_cursor is None
        assert page.has_more is False

    def test_history_page_with_items(self):
        """Test HistoryPage with items."""
        items = [
            TranscriptItem(
                transcript_id=f"t{i}",
                event_id=f"e{i}",
                conversation_id="c1",
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
            )
            for i in range(3)
        ]

        page = HistoryPage(
            items=items,
            next_cursor="10",
            prev_cursor="1",
            has_more=True,
            total_count=100,
        )

        assert len(page.items) == 3
        assert page.next_cursor == "10"
        assert page.has_more is True
        assert page.total_count == 100

    def test_history_page_serialization(self):
        """Test HistoryPage model_dump."""
        page = HistoryPage(
            items=[
                TranscriptItem(
                    transcript_id="t1",
                    event_id="e1",
                    conversation_id="c1",
                    bot_id="bot1",
                    workspace_id="ws1",
                    role="user",
                    content="Hi",
                )
            ],
            has_more=False,
        )

        data = page.model_dump(mode="json")
        assert "items" in data
        assert data["items"][0]["transcript_id"] == "t1"
        assert data["items"][0]["bot_id"] == "bot1"
        assert data["items"][0]["workspace_id"] == "ws1"

    def test_history_page_ignores_unknown_host_fields(self):
        """Test HistoryPage ignores future Host response fields."""
        page = HistoryPage.model_validate(
            {"items": [], "has_more": False, "future_cursor": "x"}
        )

        assert page.items == []
        assert "future_cursor" not in page.model_dump()


class TestHistorySearchResult:
    """Test HistorySearchResult serialization."""

    def test_history_search_result_basic(self):
        """Test basic HistorySearchResult."""
        result = HistorySearchResult(
            query="test query",
            items=[
                TranscriptItem(
                    transcript_id="t1",
                    event_id="e1",
                    conversation_id="c1",
                    role="user",
                    content="test query result",
                )
            ],
        )

        assert result.query == "test query"
        assert len(result.items) == 1


class TestAgentEventRecord:
    """Test AgentEventRecord serialization."""

    def test_event_record_basic(self):
        """Test basic AgentEventRecord."""
        record = AgentEventRecord(
            event_id="e1",
            event_type="message.received",
            source="platform",
        )

        assert record.event_id == "e1"
        assert record.event_type == "message.received"
        assert record.source == "platform"

    def test_event_record_full(self):
        """Test AgentEventRecord with all fields."""
        record = AgentEventRecord(
            event_id="e1",
            event_type="message.received",
            event_time=1700000000,
            source="platform",
            bot_id="bot1",
            workspace_id="ws1",
            conversation_id="c1",
            thread_id="t1",
            actor_type="user",
            actor_id="user1",
            actor_name="Alice",
            subject_type="message",
            subject_id="m1",
            input_summary="Hello",
            seq=1,
            cursor="1",
            metadata={"platform": "telegram"},
        )

        assert record.bot_id == "bot1"
        assert record.actor_name == "Alice"
        assert record.input_summary == "Hello"

    def test_event_record_serialization(self):
        """Test AgentEventRecord model_dump."""
        record = AgentEventRecord(
            event_id="e1",
            event_type="tool.call.started",
            source="runner",
            actor_type="runner",
            metadata={"tool_name": "search"},
        )

        data = record.model_dump(mode="json")
        assert data["event_type"] == "tool.call.started"
        assert data["metadata"]["tool_name"] == "search"

    def test_event_record_ignores_unknown_host_fields(self):
        """Test AgentEventRecord ignores future Host response fields."""
        record = AgentEventRecord.model_validate(
            {
                "event_id": "e2",
                "event_type": "message.received",
                "source": "platform",
                "correlation_id": "issue_123",
            }
        )

        assert record.event_id == "e2"
        assert "correlation_id" not in record.model_dump()


class TestEventPage:
    """Test EventPage serialization."""

    def test_event_page_empty(self):
        """Test empty EventPage."""
        page = EventPage()

        assert page.items == []
        assert page.next_cursor is None
        assert page.has_more is False

    def test_event_page_with_items(self):
        """Test EventPage with items."""
        items = [
            AgentEventRecord(
                event_id=f"e{i}",
                event_type="message.received",
                source="platform",
            )
            for i in range(3)
        ]

        page = EventPage(
            items=items,
            next_cursor="10",
            has_more=True,
        )

        assert len(page.items) == 3
        assert page.has_more is True

    def test_event_page_ignores_unknown_host_fields(self):
        """Test EventPage ignores future Host response fields."""
        page = EventPage.model_validate(
            {"items": [], "has_more": False, "future_cursor": "x"}
        )

        assert page.items == []
        assert "future_cursor" not in page.model_dump()
