"""Tests for RunnerAPIProxy history and event methods."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from langbot_plugin.api.proxies.runner import RunnerAPIProxy
from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
from langbot_plugin.api.entities.builtin.runner.resources import (
    AgentResources,
    ModelResource,
    ToolResource,
    KnowledgeBaseResource,
    StorageResource,
)
from langbot_plugin.api.entities.builtin.runner.runtime import AgentRuntimeContext
from langbot_plugin.api.entities.builtin.runner.trigger import AgentTrigger
from langbot_plugin.api.entities.builtin.runner.input import AgentInput
from langbot_plugin.api.entities.builtin.runner.event import AgentEventContext
from langbot_plugin.api.entities.builtin.runner.delivery import DeliveryContext
from langbot_plugin.api.entities.builtin.runner.context_access import (
    ContextAccess,
    ContextAPICapabilities,
)
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction


def create_mock_context(
    run_id: str = "test_run",
    conversation_id: str | None = None,
) -> RunnerContext:
    """Create a mock RunnerContext for testing."""
    return RunnerContext(
        run_id=run_id,
        trigger=AgentTrigger(type="message.received"),
        event=AgentEventContext(
            event_id="test_event",
            event_type="message.received",
            source="test",
            data={"conversation_id": conversation_id} if conversation_id else {},
        ),
        input=AgentInput(text="test input"),
        delivery=DeliveryContext(surface="test"),
        context=ContextAccess(
            available_apis=ContextAPICapabilities(
                prompt_get=True,
                history_page=True,
                history_search=True,
                event_get=True,
                event_page=True,
            ),
        ),
        runtime=AgentRuntimeContext(deadline_at=None),
        resources=AgentResources(
            models=[ModelResource(model_id="model_001")],
            tools=[ToolResource(tool_name="tool_001")],
            knowledge_bases=[KnowledgeBaseResource(kb_id="kb_001")],
            storage=StorageResource(plugin_storage=True, workspace_storage=False),
        ),
    )


class TestHistoryPageMethod:
    """Test history_page method."""

    @pytest.mark.anyio
    async def test_get_prompt_sends_run_id(self):
        """Test get_prompt sends run_id in request."""
        mock_handler = MagicMock()
        mock_handler.call_action = AsyncMock(
            return_value={
                "prompt": [{"role": "system", "content": "effective prompt"}],
            }
        )

        ctx = create_mock_context(run_id="run_prompt")
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        prompt = await proxy.get_prompt()

        assert prompt == [{"role": "system", "content": "effective prompt"}]
        mock_handler.call_action.assert_called_once()
        call_args = mock_handler.call_action.call_args
        assert call_args[0][0] == PluginToRuntimeAction.GET_PROMPT
        assert call_args[0][1]["run_id"] == "run_prompt"

    @pytest.mark.anyio
    async def test_history_page_sends_run_id(self):
        """Test history_page sends run_id in request."""
        mock_handler = MagicMock()
        mock_handler.call_action = AsyncMock(
            return_value={
                "items": [],
                "next_cursor": None,
                "prev_cursor": None,
                "has_more": False,
            }
        )

        ctx = create_mock_context(run_id="run_123")
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.history_page()

        mock_handler.call_action.assert_called_once()
        call_args = mock_handler.call_action.call_args
        assert call_args[0][0] == PluginToRuntimeAction.HISTORY_PAGE
        assert call_args[0][1]["run_id"] == "run_123"

    @pytest.mark.anyio
    async def test_history_page_with_parameters(self):
        """Test history_page passes all parameters."""
        mock_handler = MagicMock()
        mock_handler.call_action = AsyncMock(
            return_value={
                "items": [],
                "next_cursor": None,
                "prev_cursor": None,
                "has_more": False,
            }
        )

        ctx = create_mock_context()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.history_page(
            conversation_id="conv_1",
            before_cursor="10",
            limit=20,
            direction="forward",
            include_attachments=True,
        )

        call_args = mock_handler.call_action.call_args
        data = call_args[0][1]
        assert data["conversation_id"] == "conv_1"
        assert data["before_cursor"] == "10"
        assert data["limit"] == 20
        assert data["direction"] == "forward"
        assert data["include_attachments"] is True


class TestHistorySearchMethod:
    """Test history_search method."""

    @pytest.mark.anyio
    async def test_history_search_sends_run_id(self):
        """Test history_search sends run_id in request."""
        mock_handler = MagicMock()
        mock_handler.call_action = AsyncMock(
            return_value={
                "items": [],
                "total_count": 0,
                "query": "test",
            }
        )

        ctx = create_mock_context(run_id="run_456")
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.history_search(query="test query")

        call_args = mock_handler.call_action.call_args
        assert call_args[0][0] == PluginToRuntimeAction.HISTORY_SEARCH
        assert call_args[0][1]["run_id"] == "run_456"
        assert call_args[0][1]["query"] == "test query"

    @pytest.mark.anyio
    async def test_history_search_with_filters(self):
        """Test history_search passes filters."""
        mock_handler = MagicMock()
        mock_handler.call_action = AsyncMock(
            return_value={
                "items": [],
                "total_count": 0,
                "query": "test",
            }
        )

        ctx = create_mock_context()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.history_search(
            query="search term",
            filters={"roles": ["user"]},
            top_k=5,
        )

        call_args = mock_handler.call_action.call_args
        data = call_args[0][1]
        assert data["filters"] == {"roles": ["user"]}
        assert data["top_k"] == 5


class TestEventGetMethod:
    """Test event_get method."""

    @pytest.mark.anyio
    async def test_event_get_sends_run_id(self):
        """Test event_get sends run_id in request."""
        mock_handler = MagicMock()
        mock_handler.call_action = AsyncMock(
            return_value={
                "event_id": "event_1",
                "event_type": "message.received",
                "source": "platform",
            }
        )

        ctx = create_mock_context(run_id="run_789")
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.event_get(event_id="event_1")

        call_args = mock_handler.call_action.call_args
        assert call_args[0][0] == PluginToRuntimeAction.EVENT_GET
        assert call_args[0][1]["run_id"] == "run_789"
        assert call_args[0][1]["event_id"] == "event_1"


class TestEventPageMethod:
    """Test event_page method."""

    @pytest.mark.anyio
    async def test_event_page_sends_run_id(self):
        """Test event_page sends run_id in request."""
        mock_handler = MagicMock()
        mock_handler.call_action = AsyncMock(
            return_value={
                "items": [],
                "next_cursor": None,
                "has_more": False,
            }
        )

        ctx = create_mock_context(run_id="run_abc")
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.event_page()

        call_args = mock_handler.call_action.call_args
        assert call_args[0][0] == PluginToRuntimeAction.EVENT_PAGE
        assert call_args[0][1]["run_id"] == "run_abc"

    @pytest.mark.anyio
    async def test_event_page_with_parameters(self):
        """Test event_page passes all parameters."""
        mock_handler = MagicMock()
        mock_handler.call_action = AsyncMock(
            return_value={
                "items": [],
                "next_cursor": None,
                "has_more": False,
            }
        )

        ctx = create_mock_context()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.event_page(
            conversation_id="conv_1",
            event_types=["message.received", "message.completed"],
            before_cursor="50",
            limit=30,
        )

        call_args = mock_handler.call_action.call_args
        data = call_args[0][1]
        assert data["conversation_id"] == "conv_1"
        assert data["event_types"] == ["message.received", "message.completed"]
        assert data["before_cursor"] == "50"
        assert data["limit"] == 30
