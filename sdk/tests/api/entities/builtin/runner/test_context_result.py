"""Tests for RunnerContext and RunnerResult Protocol v1."""

from __future__ import annotations

import pytest
import pydantic

from langbot_plugin.api.entities.builtin.runner.context import (
    RunnerContext,
    AdapterContext,
)
from langbot_plugin.api.entities.builtin.runner.result import (
    RunnerResult,
    RunnerResultType,
)
from langbot_plugin.api.entities.builtin.runner.errors import AgentAPIError
from langbot_plugin.api.entities.builtin.runner.steering import SteeringPullResult
from langbot_plugin.api.entities.builtin.runner.trigger import AgentTrigger
from langbot_plugin.api.entities.builtin.runner.input import AgentInput
from langbot_plugin.api.entities.builtin.runner.resources import (
    AgentResources,
    ModelResource,
    ToolResource,
    SkillResource,
    StorageResource,
)
from langbot_plugin.api.entities.builtin.runner.runtime import AgentRuntimeContext
from langbot_plugin.api.entities.builtin.runner.state import (
    AgentRunState,
    VALID_STATE_SCOPES,
)
from langbot_plugin.api.entities.builtin.runner.event import (
    ConversationContext,
    AgentEventContext,
    ActorContext,
    SubjectContext,
)
from langbot_plugin.api.entities.builtin.runner.context_access import (
    ContextAccess,
)
from langbot_plugin.api.entities.builtin.runner.delivery import DeliveryContext
from langbot_plugin.api.entities.builtin.runner.manifest import (
    RunnerCapabilities,
    RunnerManifest,
    RunnerPermissions,
)
from langbot_plugin.api.entities.builtin.provider.message import (
    LLMInvokeResult,
    LLMStreamEvent,
    LLMTokenUsage,
    Message,
    MessageChunk,
    ContentElement,
)


class TestRunnerContextV1:
    """Test RunnerContext v1 validation."""

    def test_minimal_context_validate(self):
        """Test minimal required fields validation."""
        trigger = AgentTrigger(type="message.received", source="host_adapter")
        event = AgentEventContext(
            event_id="evt_1",
            event_type="message.received",
            source="platform",
        )
        input = AgentInput(text="Hello")
        resources = AgentResources()
        runtime = AgentRuntimeContext()
        delivery = DeliveryContext(surface="platform")

        ctx = RunnerContext(
            run_id="run_123",
            trigger=trigger,
            event=event,
            input=input,
            delivery=delivery,
            resources=resources,
            runtime=runtime,
        )

        assert ctx.run_id == "run_123"
        assert ctx.trigger.type == "message.received"
        assert ctx.input.text == "Hello"
        assert ctx.config == {}
        assert ctx.context is not None  # Has default
        assert ctx.context.available_apis.prompt_get is False
        assert "protocol_version" not in ctx.runtime.model_dump()
        assert "sdk_protocol_version" not in AgentRuntimeContext.model_fields

    def test_event_is_required(self):
        """Test that event is required for Protocol v1."""
        trigger = AgentTrigger(type="message.received")
        input = AgentInput(text="Hello")
        resources = AgentResources()
        runtime = AgentRuntimeContext()
        delivery = DeliveryContext(surface="platform")

        # Missing event should raise validation error
        with pytest.raises(pydantic.ValidationError):
            RunnerContext(
                run_id="run_123",
                trigger=trigger,
                # event missing - should fail
                input=input,
                delivery=delivery,
                resources=resources,
                runtime=runtime,
            )

    def test_history_messages_are_not_context_fields(self):
        """History messages are pulled through APIs, not embedded in context."""
        trigger = AgentTrigger(type="message.received")
        event = AgentEventContext(
            event_id="evt_1",
            event_type="message.received",
            source="platform",
        )
        input = AgentInput(text="Hello")
        resources = AgentResources()
        runtime = AgentRuntimeContext()
        delivery = DeliveryContext(surface="platform")

        ctx = RunnerContext(
            run_id="run_123",
            trigger=trigger,
            event=event,
            input=input,
            delivery=delivery,
            resources=resources,
            runtime=runtime,
        )

        assert "messages" not in RunnerContext.model_fields
        assert "bootstrap" not in RunnerContext.model_fields
        assert not hasattr(ctx, "bootstrap")

    def test_context_access_default(self):
        """Test ContextAccess default values."""
        context_access = ContextAccess()

        assert context_access.conversation_id is None
        assert context_access.has_history_before is False
        assert context_access.inline_policy.mode == "current_event"

    def test_adapter_context(self):
        """Test AdapterContext for non-core entry adapter fields."""
        adapter = AdapterContext(
            extra={"entrypoint": "host_adapter"},
        )

        assert adapter.extra["entrypoint"] == "host_adapter"
        assert set(AdapterContext.model_fields) == {"extra"}

    def test_full_context_validate(self):
        """Test full context with all optional fields."""
        trigger = AgentTrigger(
            type="message.received", source="host_adapter", timestamp=1234567890
        )
        conversation = ConversationContext(
            conversation_id="conv_1",
            thread_id="thread_1",
            launcher_type="person",
            launcher_id="12345",
            sender_id="user_1",
            bot_id="bot_123",
            workspace_id="ws_1",
        )
        event = AgentEventContext(
            event_id="evt_1",
            event_type="message.received",
            event_time=1234567890,
            source="platform",
        )
        actor = ActorContext(
            actor_type="user",
            actor_id="user_1",
            actor_name="Test User",
        )
        subject = SubjectContext(
            subject_type="message",
            subject_id="msg_1",
        )
        input = AgentInput(
            text="What's up?",
            contents=[ContentElement(type="text", text="What's up?")],
        )
        resources = AgentResources(
            models=[ModelResource(model_id="gpt-4", model_type="chat")],
            tools=[ToolResource(tool_name="search", tool_type="function")],
            skills=[
                SkillResource(
                    skill_name="pdf", display_name="PDF", description="Work with PDFs"
                )
            ],
            storage=StorageResource(plugin_storage=True, workspace_storage=True),
        )
        state = AgentRunState(
            conversation={"external.conversation_id": "conv_xyz"},
            actor={"memory.summary": "User likes coffee"},
        )
        runtime = AgentRuntimeContext(
            langbot_version="1.0.0",
            trace_id="trace_abc",
            deadline_at=1234568000,
        )
        delivery = DeliveryContext(
            surface="platform",
            supports_streaming=True,
        )
        context_access = ContextAccess(
            conversation_id="conv_1",
            has_history_before=True,
        )

        ctx = RunnerContext(
            run_id="run_full",
            trigger=trigger,
            conversation=conversation,
            event=event,
            actor=actor,
            subject=subject,
            input=input,
            delivery=delivery,
            resources=resources,
            context=context_access,
            state=state,
            runtime=runtime,
            config={"model": "gpt-4"},
        )

        assert ctx.run_id == "run_full"
        assert ctx.conversation.launcher_type == "person"
        assert ctx.resources.models[0].model_id == "gpt-4"
        assert ctx.resources.skills[0].skill_name == "pdf"
        assert ctx.config["model"] == "gpt-4"
        assert ctx.context.has_history_before is True

    def test_context_missing_required_field(self):
        """Test that missing required fields raise validation error."""
        with pytest.raises(pydantic.ValidationError):
            RunnerContext(
                # Missing run_id, trigger, event, input, delivery, resources, runtime
            )

    def test_context_model_validate_from_dict(self):
        """Test model_validate from dict (as LangBot will send)."""
        data = {
            "run_id": "run_dict",
            "trigger": {"type": "message.received", "source": "host_adapter"},
            "event": {
                "event_id": "evt_1",
                "event_type": "message.received",
                "source": "platform",
            },
            "input": {"text": "Hello from dict"},
            "delivery": {"surface": "platform"},
            "resources": {},
            "runtime": {},
        }

        ctx = RunnerContext.model_validate(data)
        assert ctx.run_id == "run_dict"
        assert ctx.input.text == "Hello from dict"
        assert ctx.event.event_type == "message.received"


class TestAgentRunState:
    """Test AgentRunState entity."""

    def test_state_default_factory(self):
        """Test state creates with all empty dicts."""
        state = AgentRunState()
        assert state.conversation == {}
        assert state.actor == {}
        assert state.subject == {}
        assert state.runner == {}

    def test_state_with_values(self):
        """Test state with actual values."""
        state = AgentRunState(
            conversation={
                "external.conversation_id": "abc",
                "external.thread_id": "xyz",
            },
            actor={"preferred_language": "zh"},
            subject={"group_topic": "general"},
            runner={"cache_version": 1},
        )

        assert state.conversation["external.conversation_id"] == "abc"
        assert state.actor["preferred_language"] == "zh"
        assert state.subject["group_topic"] == "general"
        assert state.runner["cache_version"] == 1

    def test_state_model_dump(self):
        """Test state serialization."""
        state = AgentRunState(
            conversation={"key": "value"},
        )
        dumped = state.model_dump()
        assert dumped["conversation"]["key"] == "value"
        assert dumped["actor"] == {}

    def test_valid_state_scopes_constant(self):
        """Test VALID_STATE_SCOPES contains all scopes."""
        assert "conversation" in VALID_STATE_SCOPES
        assert "actor" in VALID_STATE_SCOPES
        assert "subject" in VALID_STATE_SCOPES
        assert "runner" in VALID_STATE_SCOPES
        assert len(VALID_STATE_SCOPES) == 4


class TestRunnerResultV1:
    """Test RunnerResult v1 validation for each type."""

    def test_message_delta_validate(self):
        """Test message.delta result."""
        chunk = MessageChunk(role="assistant", content="Hello")
        result = RunnerResult.message_delta("run_1", chunk)

        assert result.run_id == "run_1"
        assert result.type == RunnerResultType.MESSAGE_DELTA
        assert "chunk" in result.data
        assert result.data["chunk"]["role"] == "assistant"

    def test_message_completed_validate(self):
        """Test message.completed result."""
        message = Message(role="assistant", content="Complete response")
        result = RunnerResult.message_completed("run_1", message)

        assert result.run_id == "run_1"
        assert result.type == RunnerResultType.MESSAGE_COMPLETED
        assert "message" in result.data
        assert result.data["message"]["role"] == "assistant"

    def test_tool_call_started_validate(self):
        """Test tool.call.started result."""
        result = RunnerResult.tool_call_started(
            run_id="run_1",
            tool_call_id="call_1",
            tool_name="weather",
            parameters={"city": "Tokyo"},
        )

        assert result.run_id == "run_1"
        assert result.type == RunnerResultType.TOOL_CALL_STARTED
        assert result.data["tool_call_id"] == "call_1"
        assert result.data["tool_name"] == "weather"
        assert result.data["parameters"]["city"] == "Tokyo"

    def test_tool_call_completed_validate(self):
        """Test tool.call.completed result."""
        result = RunnerResult.tool_call_completed(
            run_id="run_1",
            tool_call_id="call_1",
            tool_name="weather",
            result={"temp": 25, "condition": "sunny"},
            error=None,
        )

        assert result.run_id == "run_1"
        assert result.type == RunnerResultType.TOOL_CALL_COMPLETED
        assert result.data["result"]["temp"] == 25

    def test_tool_call_completed_with_error(self):
        """Test tool.call.completed with error."""
        result = RunnerResult.tool_call_completed(
            run_id="run_1",
            tool_call_id="call_2",
            tool_name="weather",
            result=None,
            error="API timeout",
        )

        assert result.run_id == "run_1"
        assert result.type == RunnerResultType.TOOL_CALL_COMPLETED
        assert result.data["error"] == "API timeout"

    def test_state_updated_validate(self):
        """Test state.updated result."""
        result = RunnerResult.state_updated(
            run_id="run_1",
            key="external.conversation_id",
            value="abc123",
            scope="conversation",
        )

        assert result.run_id == "run_1"
        assert result.type == RunnerResultType.STATE_UPDATED
        assert result.data["scope"] == "conversation"
        assert result.data["key"] == "external.conversation_id"
        assert result.data["value"] == "abc123"

    def test_state_updated_with_scope(self):
        """Test state.updated with explicit scope."""
        result = RunnerResult.state_updated(
            run_id="run_1",
            key="preferred_language",
            value="en",
            scope="actor",
        )

        assert result.run_id == "run_1"
        assert result.type == RunnerResultType.STATE_UPDATED
        assert result.data["scope"] == "actor"
        assert result.data["key"] == "preferred_language"
        assert result.data["value"] == "en"

    def test_state_updated_all_scopes(self):
        """Test state.updated with all valid scopes."""
        for scope in VALID_STATE_SCOPES:
            result = RunnerResult.state_updated(
                run_id="run_1",
                key="test_key",
                value="test_value",
                scope=scope,
            )
            assert result.data["scope"] == scope

    def test_state_updated_invalid_scope_raises(self):
        """Test state.updated with invalid scope raises ValueError."""
        with pytest.raises(ValueError, match="Invalid scope"):
            RunnerResult.state_updated(
                run_id="run_1",
                key="test_key",
                value="test_value",
                scope="invalid_scope",
            )

    def test_run_completed_validate(self):
        """Test run.completed result."""
        message = Message(role="assistant", content="Done")
        result = RunnerResult.run_completed(
            run_id="run_1", message=message, finish_reason="stop"
        )

        assert result.run_id == "run_1"
        assert result.type == RunnerResultType.RUN_COMPLETED
        assert result.data["finish_reason"] == "stop"
        assert result.data["message"]["role"] == "assistant"

    def test_run_completed_without_message(self):
        """Test run.completed without message (when message.completed already sent)."""
        result = RunnerResult.run_completed(run_id="run_1", finish_reason="stop")

        assert result.run_id == "run_1"
        assert result.type == RunnerResultType.RUN_COMPLETED
        assert result.data["finish_reason"] == "stop"
        assert "message" not in result.data

    def test_run_completed_accepts_terminal_usage(self):
        """Terminal run.completed may carry aggregate token usage."""
        result = RunnerResult.run_completed(
            run_id="run_1",
            finish_reason="stop",
            usage={
                "prompt_tokens": 10,
                "completion_tokens": 4,
                "total_tokens": 14,
                "prompt_tokens_details": {"cached_tokens": 6},
            },
        )

        assert result.usage is not None
        assert result.usage.total_tokens == 14
        assert result.usage.model_dump()["prompt_tokens_details"] == {
            "cached_tokens": 6
        }

        dumped = result.model_dump(mode="json")
        assert dumped["usage"]["prompt_tokens"] == 10
        assert dumped["usage"]["prompt_tokens_details"] == {"cached_tokens": 6}

    def test_run_failed_validate(self):
        """Test run.failed result."""
        result = RunnerResult.run_failed(
            run_id="run_1",
            error="Upstream timeout",
            code="upstream.timeout",
            retryable=True,
        )

        assert result.run_id == "run_1"
        assert result.type == RunnerResultType.RUN_FAILED
        assert result.data["error"] == "Upstream timeout"
        assert result.data["code"] == "upstream.timeout"
        assert result.data["retryable"] is True

    def test_run_failed_default_code(self):
        """Test run.failed with default code."""
        result = RunnerResult.run_failed(run_id="run_1", error="Something went wrong")

        assert result.data["code"] == "runner.error"

    def test_run_failed_accepts_partial_usage(self):
        """Terminal run.failed may carry usage collected before failure."""
        usage = LLMTokenUsage(
            prompt_tokens=8,
            completion_tokens=1,
            total_tokens=9,
            provider_request_id="req_1",
        )

        result = RunnerResult.run_failed(
            run_id="run_1",
            error="Context overflow",
            code="provider.context_overflow",
            retryable=False,
            usage=usage,
        )

        assert result.usage is not None
        assert result.usage.prompt_tokens == 8
        assert result.usage.model_dump()["provider_request_id"] == "req_1"

    def test_action_requested_validate(self):
        """Test action.requested result."""
        result = RunnerResult.action_requested(
            run_id="run_1",
            action="platform.message.edit",
            target={"message_id": "msg_1"},
            payload={"new_text": "Updated"},
        )

        assert result.run_id == "run_1"
        assert result.type == RunnerResultType.ACTION_REQUESTED
        assert result.data["action"] == "platform.message.edit"

    def test_result_model_dump_json(self):
        """Test model_dump(mode='json') for serialization."""
        message = Message(role="assistant", content="Test")
        result = RunnerResult.message_completed("run_1", message)

        dumped = result.model_dump(mode="json")
        assert dumped["type"] == "message.completed"
        assert isinstance(dumped["data"]["message"]["content"], str)

    def test_unknown_result_type_is_accepted_for_forward_compatibility(self):
        """SDK model accepts unknown result type strings for Protocol v1 evolution."""
        result = RunnerResult.model_validate(
            {
                "run_id": "run_1",
                "type": "future.result",
                "data": {"value": 1},
                "sequence": 7,
            }
        )

        assert result.type == "future.result"
        assert result.sequence == 7

    def test_sequence_can_be_set_by_factories(self):
        """Factories accept sequence for runtime-managed streams."""
        message = Message(role="assistant", content="Done")
        result = RunnerResult.message_completed("run_1", message, sequence=3)

        assert result.sequence == 3


class TestAgentRunAPIContractEntities:
    """Test SDK entities that back RunnerAPIProxy contract."""

    def test_agent_api_error_validate(self):
        error = AgentAPIError(
            code="history.unauthorized",
            message="not allowed",
            retryable=False,
            details={"scope": "conversation"},
        )

        assert error.code == "history.unauthorized"
        assert error.details["scope"] == "conversation"

    def test_agent_api_error_ignores_unknown_host_fields(self):
        error = AgentAPIError.model_validate(
            {
                "code": "history.unauthorized",
                "message": "not allowed",
                "retryable": False,
                "details": {},
                "request_id": "req_1",
            }
        )

        assert error.code == "history.unauthorized"
        assert "request_id" not in error.model_dump()

    def test_steering_pull_result_validate(self):
        result = SteeringPullResult.model_validate(
            {
                "items": [
                    {
                        "claimed_run_id": "run_1",
                        "runner_id": "plugin:test/demo/default",
                        "future_item_field": True,
                        "event": {
                            "event_id": "evt_1",
                            "event_type": "message.received",
                            "source": "platform",
                        },
                        "input": {"text": "follow up"},
                    }
                ],
                "future_page_field": True,
            }
        )

        assert result.items[0].input.text == "follow up"
        assert "future_item_field" not in result.items[0].model_dump()
        assert "future_page_field" not in result.model_dump()

    def test_runner_progress_and_cancellation_results_are_structured(self):
        progress = RunnerResult.run_progress(
            "run_1", progress=42.5, stage="tool", message="working"
        )
        assert progress.type == RunnerResultType.RUN_PROGRESS
        assert progress.data["progress"] == 42.5

        cancelled = RunnerResult.run_cancelled(
            "run_1", reason="user requested", cleanup_confirmed=True
        )
        assert cancelled.type == RunnerResultType.RUN_CANCELLED
        assert cancelled.data["cleanup_confirmed"] is True

    def test_llm_usage_results_preserve_provider_details(self):
        result = LLMInvokeResult.model_validate(
            {
                "message": {"role": "assistant", "content": "ok"},
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "total_tokens": 14,
                    "prompt_tokens_details": {"cached_tokens": 6},
                },
            }
        )
        event = LLMStreamEvent.model_validate(
            {
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "total_tokens": 14,
                    "prompt_tokens_details": {"cached_tokens": 6},
                }
            }
        )

        assert result.usage is not None
        assert result.usage.model_dump()["prompt_tokens_details"] == {
            "cached_tokens": 6
        }
        assert event.chunk is None
        assert event.usage is not None
        assert event.usage.total_tokens == 14


class TestAgentInput:
    """Test AgentInput helpers."""

    def test_to_text_from_text_field(self):
        """Test to_text when text field is set."""
        input = AgentInput(text="Hello world")
        assert input.to_text() == "Hello world"

    def test_to_text_from_contents(self):
        """Test to_text from content elements."""
        input = AgentInput(
            contents=[
                ContentElement(type="text", text="Hello"),
                ContentElement(type="text", text="world"),
            ]
        )
        assert input.to_text() == "Hello world"

    def test_to_text_empty(self):
        """Test to_text with no text."""
        input = AgentInput(
            contents=[
                ContentElement(
                    type="image_url", image_url={"url": "http://example.com"}
                )
            ]
        )
        assert input.to_text() == ""


class TestRunnerManifest:
    """Test RunnerManifest."""

    def test_manifest_minimal(self):
        """Test minimal manifest."""
        manifest = RunnerManifest(
            usages=["agent"],
            id="plugin:author/plugin/runner",
            name="default",
            label={"en_US": "Default Runner"},
        )

        assert manifest.id == "plugin:author/plugin/runner"
        assert manifest.name == "default"
        assert isinstance(manifest.capabilities, RunnerCapabilities)
        assert isinstance(manifest.permissions, RunnerPermissions)
        assert manifest.capabilities.streaming is False
        assert manifest.permissions.models == []

    def test_manifest_full(self):
        """Test full manifest."""
        manifest = RunnerManifest(
            usages=["agent"],
            id="plugin:author/plugin/runner",
            name="default",
            label={"en_US": "Runner"},
            description={"en_US": "A runner"},
            capabilities={"streaming": True, "tool_calling": True},
            permissions={
                "models": ["invoke", "stream"],
                "tools": ["detail", "call"],
                "history": ["page"],
            },
        )

        assert manifest.description == {"en_US": "A runner"}
        assert manifest.capabilities.streaming is True
        assert manifest.permissions.models == ["invoke", "stream"]
        assert manifest.permissions.history == ["page"]

    def test_manifest_rejects_unknown_capability_key(self):
        """Test non-standard capability keys are rejected."""
        with pytest.raises(pydantic.ValidationError, match="extra_forbidden"):
            RunnerManifest(
                usages=["agent"],
                id="plugin:author/plugin/runner",
                name="default",
                label={"en_US": "Runner"},
                capabilities={"event_context": True},
            )

    def test_manifest_rejects_platform_api_permission(self):
        """Test platform_api is not a Protocol v1 permission."""
        with pytest.raises(pydantic.ValidationError, match="extra_forbidden"):
            RunnerManifest(
                usages=["agent"],
                id="plugin:author/plugin/runner",
                name="default",
                label={"en_US": "Runner"},
                permissions={"platform_api": ["message.send"]},
            )


class TestEventContextProtocolV1:
    """Test event context for Protocol v1."""

    def test_event_context_required_fields(self):
        """Test event context required fields."""
        event = AgentEventContext(
            event_id="evt_1",
            event_type="message.received",
            source="platform",
        )

        assert event.event_id == "evt_1"
        assert event.event_type == "message.received"
        assert event.source == "platform"

    def test_event_context_missing_required(self):
        """Test event context with missing required fields."""
        with pytest.raises(pydantic.ValidationError):
            AgentEventContext(
                # Missing event_id, event_type, source
            )


class TestDeliveryContext:
    """Test DeliveryContext."""

    def test_delivery_context_required(self):
        """Test delivery context required field."""
        delivery = DeliveryContext(surface="platform")

        assert delivery.surface == "platform"
        assert delivery.supports_streaming is False
        assert delivery.reply_target is None

    def test_delivery_context_full(self):
        """Test full delivery context."""
        delivery = DeliveryContext(
            surface="webui",
            supports_streaming=True,
            supports_edit=True,
            max_message_size=4096,
        )

        assert delivery.surface == "webui"
        assert delivery.supports_streaming is True
        assert delivery.max_message_size == 4096


@pytest.mark.parametrize("usages", [None, [], ["invalid"], "agent"])
def test_runner_manifest_rejects_missing_or_invalid_usages(usages):
    data = {"id": "plugin:a/b/c", "name": "c", "label": {"en_US": "C"}}
    if usages is not None:
        data["usages"] = usages
    with pytest.raises(pydantic.ValidationError):
        RunnerManifest.model_validate(data)


def test_agent_api_exception_handles_string_argument():
    from langbot_plugin.api.entities.builtin.runner.errors import AgentAPIException

    exc = AgentAPIException("plain error string")
    assert exc.error.message == "plain error string"
    assert exc.error.code == "runner_error"
    assert str(exc) == "plain error string"
