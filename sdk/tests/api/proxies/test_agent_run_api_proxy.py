"""Tests for RunnerAPIProxy restricted API surface and permission validation.

These tests verify that RunnerAPIProxy:
1. Only exposes APIs explicitly authorized through ctx.resources
2. Validates resource access before execution
3. Does NOT expose unrestricted global APIs
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from langbot_plugin.api.proxies.runner import (
    RunnerAdminAPIProxy,
    RunnerAPIProxy,
    PermissionDeniedError,
)
from langbot_plugin.api.entities.builtin.runner.errors import AgentAPIException
from langbot_plugin.entities.io.errors import (
    ActionCallError,
    ActionCallTimeoutError,
    ConnectionClosedError,
)
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction
from langbot_plugin.api.entities.builtin.provider.message import Message
from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
from langbot_plugin.api.entities.builtin.runner.interaction import InteractionRequest
from langbot_plugin.api.entities.builtin.platform.events import (
    InteractionCallbackEvent,
    parse_eba_event,
)
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
from langbot_plugin.api.entities.builtin.runner.result import RunnerResult


class MockHandler:
    """Mock Handler for testing RunnerAPIProxy."""

    def __init__(self):
        self.call_action_mock = AsyncMock()
        self.call_action_generator_mock = AsyncMock()

    async def call_action(
        self,
        action: PluginToRuntimeAction,
        data: dict,
        timeout: float = 120,
        action_context=None,
        cancel_peer_on_cancel: bool = False,
    ):
        """Mock call_action that returns expected response."""
        return await self.call_action_mock(
            action,
            data,
            timeout,
            action_context=action_context,
            cancel_peer_on_cancel=cancel_peer_on_cancel,
        )

    def call_action_generator(
        self, action: PluginToRuntimeAction, data: dict, timeout: float = 120
    ):
        """Mock call_action_generator - returns an async generator."""
        return self.call_action_generator_mock(action, data, timeout)


def create_mock_context(
    run_id: str = "test_run",
    deadline_at: float | None = None,
    models: list[dict] | None = None,
    tools: list[dict] | None = None,
    knowledge_bases: list[dict] | None = None,
    storage: dict | None = None,
    available_apis: ContextAPICapabilities | None = None,
) -> RunnerContext:
    """Create a mock RunnerContext for testing."""
    if available_apis is None:
        available_apis = ContextAPICapabilities(
            history_page=True,
            history_search=True,
            event_get=True,
            event_page=True,
            state=True,
            storage=True,
            steering_pull=True,
        )

    return RunnerContext(
        run_id=run_id,
        trigger=AgentTrigger(type="user_message"),
        event=AgentEventContext(
            event_id="test_event",
            event_type="message.received",
            source="test",
        ),
        input=AgentInput(content="test input"),
        delivery=DeliveryContext(surface="test"),
        context=ContextAccess(
            available_apis=available_apis,
        ),
        runtime=AgentRuntimeContext(deadline_at=deadline_at),
        resources=AgentResources(
            models=[ModelResource.model_validate(m) for m in (models or [])],
            tools=[ToolResource.model_validate(t) for t in (tools or [])],
            knowledge_bases=[
                KnowledgeBaseResource.model_validate(kb)
                for kb in (knowledge_bases or [])
            ],
            storage=StorageResource.model_validate(
                storage or {"plugin_storage": False, "workspace_storage": False}
            ),
        ),
    )


class TestRunnerAPIProxyRestrictedAPISurface:
    """Tests to verify RunnerAPIProxy does NOT expose unrestricted global APIs."""

    def test_does_not_expose_get_bots(self):
        """RunnerAPIProxy should NOT have get_bots method."""
        ctx = create_mock_context()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=MagicMock())

        assert not hasattr(proxy, "get_bots"), (
            "RunnerAPIProxy should not expose get_bots (use RunnerResult.action_requested)"
        )

    def test_standard_interaction_callback_round_trips(self):
        event = InteractionCallbackEvent(
            callback_token="token", values={"choice": "yes"}, actor_id="user"
        )
        parsed = parse_eba_event(event.model_dump(mode="json"))
        assert isinstance(parsed, InteractionCallbackEvent)
        assert parsed.callback_token == "token"

    async def test_send_message_retains_run_authorization(self):
        from langbot_plugin.api.entities.builtin.platform.message import (
            MessageChain,
            Plain,
        )

        ctx = create_mock_context()
        handler = MagicMock()
        handler.call_action = AsyncMock(return_value={"result": None})
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=handler)
        await proxy.send_message(
            "bot", "group", "group", MessageChain([Plain(text="hi")])
        )
        assert handler.call_action.await_args.args[1]["run_id"] == ctx.run_id

    async def test_request_interaction_uses_independent_timeout_and_updates_deadline(
        self,
    ):
        ctx = create_mock_context(deadline_at=time.time() + 10)
        handler = MagicMock()
        handler.call_action = AsyncMock(
            return_value={
                "status": "submitted",
                "submission": {
                    "interaction_id": "one",
                    "action_id": "yes",
                    "values": {},
                },
                "deadline_at": 1234567890.0,
            }
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=handler)

        result = await proxy.request_interaction(
            InteractionRequest(interaction_id="one", title="Approve"), timeout=600
        )

        assert result.submission.action_id == "yes"
        assert ctx.runtime.deadline_at == 1234567890.0
        args = handler.call_action.await_args
        assert args.args[0] is PluginToRuntimeAction.REQUEST_INTERACTION
        assert args.args[2] == 630
        assert args.kwargs["cancel_peer_on_cancel"] is True

    async def test_request_interaction_extends_worker_deadline_before_waiting(self):
        original_deadline = time.time() + 0.03
        ctx = create_mock_context(deadline_at=original_deadline)
        handler = MagicMock()

        async def delayed_response(*args, **kwargs):
            assert ctx.runtime.deadline_at > original_deadline + 0.1
            await asyncio.sleep(0.06)
            return {
                "status": "submitted",
                "submission": {
                    "interaction_id": "one",
                    "action_id": "yes",
                    "values": {},
                },
                "deadline_at": original_deadline + 0.06,
            }

        handler.call_action = AsyncMock(side_effect=delayed_response)
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=handler)

        result = await proxy.request_interaction(
            InteractionRequest(interaction_id="one", title="Approve"), timeout=0.2
        )

        assert result.status == "submitted"
        assert ctx.runtime.deadline_at == original_deadline + 0.06

    async def test_request_interaction_restores_deadline_on_invalid_response(self):
        original_deadline = time.time() + 10
        ctx = create_mock_context(deadline_at=original_deadline)
        handler = MagicMock()
        handler.call_action = AsyncMock(return_value={"status": "invalid"})
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=handler)

        with pytest.raises(Exception):
            await proxy.request_interaction(
                InteractionRequest(interaction_id="one", title="Approve"), timeout=600
            )

        assert original_deadline <= ctx.runtime.deadline_at < original_deadline + 1

    async def test_list_tools_does_not_list_ungranted_resources(self):
        ctx = create_mock_context()
        handler = MagicMock()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=handler)
        assert await proxy.list_tools() == []
        handler.call_action.assert_not_called()

    def test_exposes_get_tool_detail_with_validation(self):
        """RunnerAPIProxy exposes get_tool_detail() for authorized tool schemas."""
        ctx = create_mock_context()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=MagicMock())

        assert hasattr(proxy, "get_tool_detail"), (
            "RunnerAPIProxy should expose get_tool_detail() for authorized function calling"
        )

    def test_does_not_expose_vector_upsert(self):
        """RunnerAPIProxy should NOT have vector_upsert method."""
        ctx = create_mock_context()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=MagicMock())

        assert not hasattr(proxy, "vector_upsert"), (
            "RunnerAPIProxy should not expose vector_upsert (no vector resources defined)"
        )

    def test_does_not_expose_vector_search(self):
        """RunnerAPIProxy should NOT have vector_search method."""
        ctx = create_mock_context()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=MagicMock())

        assert not hasattr(proxy, "vector_search"), (
            "RunnerAPIProxy should not expose vector_search (no vector resources defined)"
        )

    async def test_invoke_embedding_rejects_ungranted_model(self):
        ctx = create_mock_context()
        handler = MagicMock()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=handler)
        with pytest.raises(PermissionDeniedError):
            await proxy.invoke_embedding("ungranted", ["text"])
        handler.call_action.assert_not_called()

    async def test_get_llm_models_does_not_list_ungranted_resources(self):
        ctx = create_mock_context()
        handler = MagicMock()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=handler)
        assert await proxy.get_llm_models() == []
        handler.call_action.assert_not_called()

    async def test_list_knowledge_bases_does_not_list_ungranted_resources(self):
        ctx = create_mock_context()
        handler = MagicMock()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=handler)
        assert await proxy.list_knowledge_bases() == []
        handler.call_action.assert_not_called()

    def test_does_not_expose_get_config_file(self):
        """RunnerAPIProxy should NOT have get_config_file method."""
        ctx = create_mock_context()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=MagicMock())

        assert not hasattr(proxy, "get_config_file"), (
            "RunnerAPIProxy should not expose get_config_file (use sandbox file tools)"
        )

    def test_does_not_expose_get_file(self):
        """RunnerAPIProxy should NOT have Host file methods."""
        ctx = create_mock_context()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=MagicMock())

        assert not hasattr(proxy, "get_file")

    def test_exposes_allowed_resource_helpers(self):
        """RunnerAPIProxy exposes resource helper methods."""
        ctx = create_mock_context()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=MagicMock())

        assert hasattr(proxy, "get_allowed_models")
        assert hasattr(proxy, "get_allowed_tools")
        assert hasattr(proxy, "get_allowed_knowledge_bases")

    def test_exposes_storage_methods_with_validation(self):
        """RunnerAPIProxy exposes storage methods with permission validation."""
        ctx = create_mock_context()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=MagicMock())

        assert hasattr(proxy, "set_plugin_storage")
        assert hasattr(proxy, "get_plugin_storage")

    def test_exposes_run_ledger_methods(self):
        """RunnerAPIProxy exposes run-scoped ledger methods."""
        ctx = create_mock_context()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=MagicMock())

        assert hasattr(proxy, "run_get")
        assert hasattr(proxy, "run_list")
        assert hasattr(proxy, "run_events_page")
        assert hasattr(proxy, "run_cancel")
        assert hasattr(proxy, "run_append_result")
        assert hasattr(proxy, "run_finalize")
        assert hasattr(proxy, "delete_plugin_storage")
        assert hasattr(proxy, "set_workspace_storage")
        assert hasattr(proxy, "get_workspace_storage")
        assert hasattr(proxy, "delete_workspace_storage")

    def test_does_not_expose_control_plane_methods(self):
        """RunnerAPIProxy should not expose runtime/admin control-plane APIs."""
        ctx = create_mock_context()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=MagicMock())

        assert not hasattr(proxy, "runtime_register")
        assert not hasattr(proxy, "runtime_heartbeat")
        assert not hasattr(proxy, "runtime_list")
        assert not hasattr(proxy, "run_claim")
        assert not hasattr(proxy, "run_renew_claim")
        assert not hasattr(proxy, "run_release_claim")
        assert not hasattr(proxy, "run_stats")
        assert not hasattr(proxy, "runtime_stats")
        assert not hasattr(proxy, "runner_stats")

    def test_exposes_version_api(self):
        """RunnerAPIProxy exposes get_langbot_version (no authorization needed)."""
        ctx = create_mock_context()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=MagicMock())

        assert hasattr(proxy, "get_langbot_version")

    def test_exposes_prompt_api_with_available_api_gate(self):
        """RunnerAPIProxy exposes get_prompt only behind prompt_get capability."""
        ctx = create_mock_context()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=MagicMock())

        assert hasattr(proxy, "get_prompt")


class TestRunnerAPIProxyResourceValidation:
    """Tests for resource validation in RunnerAPIProxy."""

    @pytest.mark.anyio
    async def test_invoke_llm_with_authorized_model(self):
        """invoke_llm succeeds when model is in ctx.resources.models."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {
            "message": {"role": "assistant", "content": "Hello back"}
        }

        ctx = create_mock_context(
            run_id="run_llm_test", models=[{"model_id": "model_001"}]
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        messages = [Message(role="user", content="Hello")]
        await proxy.invoke_llm("model_001", messages)

        call_args = mock_handler.call_action_mock.call_args
        data = call_args[0][1]

        assert data["run_id"] == "run_llm_test"
        assert data["llm_model_uuid"] == "model_001"

    @pytest.mark.anyio
    async def test_invoke_llm_with_usage_returns_provider_usage(self):
        """invoke_llm_with_usage preserves optional provider usage metadata."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {
            "message": {"role": "assistant", "content": "Hello back"},
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 5,
                "total_tokens": 17,
                "prompt_tokens_details": {"cached_tokens": 7},
            },
        }

        ctx = create_mock_context(
            run_id="run_llm_usage_test", models=[{"model_id": "model_001"}]
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        result = await proxy.invoke_llm_with_usage(
            "model_001",
            [Message(role="user", content="Hello")],
        )

        assert result.message.content == "Hello back"
        assert result.usage is not None
        assert result.usage.prompt_tokens == 12
        assert result.usage.model_dump()["prompt_tokens_details"] == {
            "cached_tokens": 7
        }

    @pytest.mark.anyio
    async def test_invoke_llm_keeps_message_only_compatibility(self):
        """invoke_llm keeps the legacy Message return value when usage is present."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {
            "message": {"role": "assistant", "content": "Hello back"},
            "usage": {"prompt_tokens": 12, "completion_tokens": 5, "total_tokens": 17},
        }

        ctx = create_mock_context(models=[{"model_id": "model_001"}])
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        message = await proxy.invoke_llm(
            "model_001",
            [Message(role="user", content="Hello")],
        )

        assert isinstance(message, Message)
        assert message.content == "Hello back"

    @pytest.mark.anyio
    async def test_invoke_llm_with_unauthorized_model_raises_error(self):
        """invoke_llm raises PermissionDeniedError when model is NOT authorized."""
        mock_handler = MockHandler()

        ctx = create_mock_context(
            run_id="run_unauth",
            models=[{"model_id": "model_001"}],  # Only model_001 is authorized
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        messages = [Message(role="user", content="Hello")]

        with pytest.raises(PermissionDeniedError) as exc_info:
            await proxy.invoke_llm("model_999", messages)  # model_999 is NOT authorized

        assert "model_999" in str(exc_info.value)
        assert "not authorized" in str(exc_info.value)

    @pytest.mark.anyio
    async def test_invoke_llm_stream_requires_stream_operation(self):
        """invoke_llm_stream requires the model stream operation."""
        mock_handler = MockHandler()

        ctx = create_mock_context(
            run_id="run_stream_denied",
            models=[{"model_id": "model_001", "operations": ["invoke"]}],
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        messages = [Message(role="user", content="Hello")]

        with pytest.raises(PermissionDeniedError) as exc_info:
            async for _chunk in proxy.invoke_llm_stream("model_001", messages):
                pass

        assert "operation 'stream'" in str(exc_info.value)
        mock_handler.call_action_generator_mock.assert_not_called()

    @pytest.mark.anyio
    async def test_invoke_llm_stream_events_yields_usage_event(self):
        """invoke_llm_stream_events exposes usage-only stream events."""

        class StreamHandler(MockHandler):
            def call_action_generator(self, action, data, timeout=120):
                async def gen():
                    yield {"chunk": {"role": "assistant", "content": "Hi"}}
                    yield {
                        "usage": {
                            "prompt_tokens": 9,
                            "completion_tokens": 2,
                            "total_tokens": 11,
                            "prompt_tokens_details": {"cached_tokens": 4},
                        }
                    }

                return gen()

        ctx = create_mock_context(
            models=[{"model_id": "model_001", "operations": ["stream"]}]
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=StreamHandler())

        events = [
            event
            async for event in proxy.invoke_llm_stream_events(
                "model_001",
                [Message(role="user", content="Hello")],
            )
        ]

        assert events[0].chunk is not None
        assert events[0].chunk.content == "Hi"
        assert events[1].chunk is None
        assert events[1].usage is not None
        assert events[1].usage.total_tokens == 11
        assert events[1].usage.model_dump()["prompt_tokens_details"] == {
            "cached_tokens": 4
        }

    @pytest.mark.anyio
    async def test_invoke_llm_stream_ignores_usage_only_events(self):
        """invoke_llm_stream remains chunk-only for existing callers."""

        class StreamHandler(MockHandler):
            def call_action_generator(self, action, data, timeout=120):
                async def gen():
                    yield {"chunk": {"role": "assistant", "content": "Hi"}}
                    yield {"usage": {"prompt_tokens": 9, "completion_tokens": 2}}

                return gen()

        ctx = create_mock_context(
            models=[{"model_id": "model_001", "operations": ["stream"]}]
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=StreamHandler())

        chunks = [
            chunk
            async for chunk in proxy.invoke_llm_stream(
                "model_001",
                [Message(role="user", content="Hello")],
            )
        ]

        assert len(chunks) == 1
        assert chunks[0].content == "Hi"

    @pytest.mark.anyio
    async def test_call_tool_with_authorized_tool(self):
        """call_tool succeeds when tool is in ctx.resources.tools."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {"result": {"status": "success"}}

        ctx = create_mock_context(
            run_id="run_tool_test", tools=[{"tool_name": "web_search"}]
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.call_tool("web_search", {"query": "hello"})

        call_args = mock_handler.call_action_mock.call_args
        data = call_args[0][1]

        assert data["run_id"] == "run_tool_test"
        assert data["tool_name"] == "web_search"
        assert "query_id" not in data

    @pytest.mark.anyio
    async def test_call_tool_with_unauthorized_tool_raises_error(self):
        """call_tool raises PermissionDeniedError when tool is NOT authorized."""
        mock_handler = MockHandler()

        ctx = create_mock_context(
            run_id="run_unauth",
            tools=[{"tool_name": "web_search"}],  # Only web_search is authorized
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        with pytest.raises(PermissionDeniedError) as exc_info:
            await proxy.call_tool(
                "image_gen", {"prompt": "hello"}
            )  # image_gen NOT authorized

        assert "image_gen" in str(exc_info.value)
        assert "not authorized" in str(exc_info.value)

    @pytest.mark.anyio
    async def test_call_tool_requires_call_operation(self):
        """call_tool requires the tool call operation."""
        mock_handler = MockHandler()

        ctx = create_mock_context(
            run_id="run_tool_call_denied",
            tools=[{"tool_name": "web_search", "operations": ["detail"]}],
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        with pytest.raises(PermissionDeniedError) as exc_info:
            await proxy.call_tool("web_search", {"query": "hello"})

        assert "operation 'call'" in str(exc_info.value)
        mock_handler.call_action_mock.assert_not_called()

    @pytest.mark.anyio
    async def test_retrieve_knowledge_with_authorized_kb(self):
        """retrieve_knowledge succeeds when kb is in ctx.resources.knowledge_bases."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {"results": [{"text": "doc1"}]}

        ctx = create_mock_context(
            run_id="run_kb_test", knowledge_bases=[{"kb_id": "kb_001"}]
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.retrieve_knowledge("kb_001", "search query")

        call_args = mock_handler.call_action_mock.call_args
        data = call_args[0][1]

        assert data["run_id"] == "run_kb_test"
        assert data["kb_id"] == "kb_001"
        assert "query_id" not in data

    @pytest.mark.anyio
    async def test_retrieve_knowledge_with_unauthorized_kb_raises_error(self):
        """retrieve_knowledge raises PermissionDeniedError when kb is NOT authorized."""
        mock_handler = MockHandler()

        ctx = create_mock_context(
            run_id="run_unauth",
            knowledge_bases=[{"kb_id": "kb_001"}],  # Only kb_001 is authorized
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        with pytest.raises(PermissionDeniedError) as exc_info:
            await proxy.retrieve_knowledge(
                "kb_999", "search query"
            )  # kb_999 NOT authorized

        assert "kb_999" in str(exc_info.value)
        assert "not authorized" in str(exc_info.value)


class TestRunnerAPIProxyAvailableAPIGate:
    """Run-scoped pull APIs must fail locally when Host did not expose them."""

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        ("method_name", "capability_name", "args"),
        [
            ("history_page", "history_page", ()),
            ("history_search", "history_search", ("query",)),
            ("event_get", "event_get", ("event_1",)),
            ("event_page", "event_page", ()),
            ("get_prompt", "prompt_get", ()),
            ("state_get", "state", ("conversation", "external.key")),
            ("state_set", "state", ("conversation", "external.key", {"v": 1})),
            ("state_delete", "state", ("conversation", "external.key")),
            ("state_list", "state", ("conversation",)),
            ("run_get", "run_get", ()),
            ("run_list", "run_list", ()),
            ("run_events_page", "run_events_page", ()),
            ("run_cancel", "run_cancel", ()),
            (
                "run_append_result",
                "run_append_result",
                (RunnerResult.run_completed("test_run"),),
            ),
            ("run_finalize", "run_finalize", ()),
        ],
    )
    async def test_pull_api_requires_available_api_before_forwarding(
        self,
        method_name: str,
        capability_name: str,
        args: tuple,
    ):
        mock_handler = MockHandler()
        proxy = RunnerAPIProxy(
            ctx=create_mock_context(available_apis=ContextAPICapabilities()),
            plugin_runtime_handler=mock_handler,
        )

        with pytest.raises(PermissionDeniedError) as exc_info:
            await getattr(proxy, method_name)(*args)

        assert capability_name in str(exc_info.value)
        mock_handler.call_action_mock.assert_not_called()
        mock_handler.call_action_generator_mock.assert_not_called()

    @pytest.mark.anyio
    async def test_pull_api_gate_accepts_dict_context_payloads(self):
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {"items": []}
        proxy = RunnerAPIProxy(
            ctx=SimpleNamespace(
                run_id="run_dict_context",
                runtime=SimpleNamespace(deadline_at=None),
                context={"available_apis": {"steering_pull": True}},
                resources=SimpleNamespace(
                    models=[],
                    tools=[],
                    knowledge_bases=[],
                    files=[],
                ),
            ),
            plugin_runtime_handler=mock_handler,
        )

        await proxy.steering_pull()

        call_args = mock_handler.call_action_mock.call_args
        assert call_args[0][0] == PluginToRuntimeAction.STEERING_PULL
        assert call_args[0][1]["run_id"] == "run_dict_context"


class TestRunnerAPIProxyNoQueryId:
    """RunnerAPIProxy does not expose or forward query_id."""

    def test_query_id_property_is_not_exposed(self):
        ctx = create_mock_context(run_id="test_run")
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=MagicMock())

        assert not hasattr(proxy, "query_id")

    @pytest.mark.anyio
    async def test_retrieve_knowledge_does_not_send_query_id(self):
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {"results": []}

        ctx = create_mock_context(
            run_id="run_no_query",
            knowledge_bases=[{"kb_id": "kb_001"}],
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.retrieve_knowledge("kb_001", "search query")

        call_args = mock_handler.call_action_mock.call_args
        data = call_args[0][1]

        assert "query_id" not in data

    @pytest.mark.anyio
    async def test_call_tool_does_not_send_query_id(self):
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {"result": {}}

        ctx = create_mock_context(
            run_id="run_no_query",
            tools=[{"tool_name": "test_tool"}],
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.call_tool("test_tool", {"param": "value"})

        call_args = mock_handler.call_action_mock.call_args
        data = call_args[0][1]

        assert "query_id" not in data


class TestRunnerAPIProxyStoragePermission:
    """Tests for storage permission validation in RunnerAPIProxy."""

    @pytest.mark.anyio
    async def test_plugin_storage_when_disabled_raises_error(self):
        """set_plugin_storage raises PermissionDeniedError when storage is disabled."""
        mock_handler = MockHandler()

        ctx = create_mock_context(
            run_id="run_storage",
            storage={"plugin_storage": False, "workspace_storage": False},  # Disabled
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        with pytest.raises(PermissionDeniedError) as exc_info:
            await proxy.set_plugin_storage("key", b"value")

        assert "plugin storage" in str(exc_info.value).lower()
        assert "not authorized" in str(exc_info.value)

    @pytest.mark.anyio
    async def test_plugin_storage_when_enabled_succeeds(self):
        """set_plugin_storage succeeds when storage is enabled."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {}

        ctx = create_mock_context(
            run_id="run_storage",
            storage={
                "plugin_storage": True,
                "workspace_storage": False,
            },  # Plugin storage enabled
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.set_plugin_storage("key", b"value")

        # Should have called the action
        assert mock_handler.call_action_mock.called

    @pytest.mark.anyio
    async def test_workspace_storage_when_disabled_raises_error(self):
        """set_workspace_storage raises PermissionDeniedError when storage is disabled."""
        mock_handler = MockHandler()

        ctx = create_mock_context(
            run_id="run_storage",
            storage={"plugin_storage": False, "workspace_storage": False},  # Disabled
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        with pytest.raises(PermissionDeniedError) as exc_info:
            await proxy.set_workspace_storage("key", b"value")

        assert "workspace storage" in str(exc_info.value).lower()
        assert "not authorized" in str(exc_info.value)

    @pytest.mark.anyio
    async def test_workspace_storage_when_enabled_succeeds(self):
        """set_workspace_storage succeeds when storage is enabled."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {}

        ctx = create_mock_context(
            run_id="run_storage",
            storage={
                "plugin_storage": False,
                "workspace_storage": True,
            },  # Workspace storage enabled
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.set_workspace_storage("key", b"value")

        # Should have called the action
        assert mock_handler.call_action_mock.called

    @pytest.mark.anyio
    async def test_get_plugin_storage_when_disabled_raises_error(self):
        """get_plugin_storage raises PermissionDeniedError when storage is disabled."""
        mock_handler = MockHandler()

        ctx = create_mock_context(
            run_id="run_storage",
            storage={"plugin_storage": False, "workspace_storage": False},
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        with pytest.raises(PermissionDeniedError) as exc_info:
            await proxy.get_plugin_storage("key")

        assert "plugin storage" in str(exc_info.value).lower()


class TestRunnerAPIProxyTimeoutValues:
    """Tests for timeout values in RunnerAPIProxy."""

    @pytest.mark.anyio
    async def test_invoke_llm_default_timeout(self):
        """invoke_llm default timeout is 120 seconds."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {
            "message": {"role": "assistant", "content": "Hello"}
        }

        ctx = create_mock_context(models=[{"model_id": "model_001"}])
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.invoke_llm("model_001", [Message(role="user", content="Hello")])

        call_args = mock_handler.call_action_mock.call_args
        timeout = call_args[0][2]

        assert timeout == 120.0

    @pytest.mark.anyio
    async def test_invoke_llm_custom_timeout(self):
        """invoke_llm custom timeout is passed correctly."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {
            "message": {"role": "assistant", "content": "Hello"}
        }

        ctx = create_mock_context(models=[{"model_id": "model_001"}])
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.invoke_llm(
            "model_001", [Message(role="user", content="Hello")], timeout=60.0
        )

        call_args = mock_handler.call_action_mock.call_args
        timeout = call_args[0][2]

        assert timeout == 60.0

    @pytest.mark.anyio
    async def test_call_tool_timeout_is_180(self):
        """call_tool timeout is 180 seconds."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {"result": {}}

        ctx = create_mock_context(tools=[{"tool_name": "test_tool"}])
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.call_tool("test_tool", {"param": "value"})

        call_args = mock_handler.call_action_mock.call_args
        timeout = call_args[0][2]

        assert timeout == 180

    @pytest.mark.anyio
    async def test_retrieve_knowledge_timeout_is_30(self):
        """retrieve_knowledge timeout is 30 seconds."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {"results": []}

        ctx = create_mock_context(knowledge_bases=[{"kb_id": "kb_001"}])
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.retrieve_knowledge("kb_001", "search query")

        call_args = mock_handler.call_action_mock.call_args
        timeout = call_args[0][2]

        assert timeout == 30

    @pytest.mark.anyio
    async def test_invoke_llm_timeout_is_bounded_by_run_deadline(self):
        """invoke_llm timeout is capped by ctx.runtime.deadline_at."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {
            "message": {"role": "assistant", "content": "Hello"}
        }

        ctx = create_mock_context(
            deadline_at=time.time() + 5,
            models=[{"model_id": "model_001"}],
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.invoke_llm("model_001", [Message(role="user", content="Hello")])

        timeout = mock_handler.call_action_mock.call_args[0][2]
        payload_timeout = mock_handler.call_action_mock.call_args[0][1]["timeout"]

        assert 0 < timeout <= 5
        assert payload_timeout == timeout

    @pytest.mark.anyio
    async def test_call_tool_timeout_is_bounded_by_run_deadline(self):
        """tool calls use the remaining run deadline instead of the full default."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {"result": {}}

        ctx = create_mock_context(
            deadline_at=time.time() + 5,
            tools=[{"tool_name": "test_tool"}],
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.call_tool("test_tool", {"param": "value"})

        timeout = mock_handler.call_action_mock.call_args[0][2]

        assert 0 < timeout <= 5


class TestRunnerAPIProxyActionEnumCorrectness:
    """Tests to ensure correct action enum usage."""

    def test_retrieve_knowledge_uses_retrieve_knowledge_base_action(self):
        """retrieve_knowledge uses RETRIEVE_KNOWLEDGE_BASE (not unrestricted RETRIEVE_KNOWLEDGE)."""
        unrestricted_action = PluginToRuntimeAction.RETRIEVE_KNOWLEDGE
        restricted_action = PluginToRuntimeAction.RETRIEVE_KNOWLEDGE_BASE

        assert unrestricted_action.value == "retrieve_knowledge"
        assert restricted_action.value == "retrieve_knowledge_base"
        assert unrestricted_action != restricted_action

    @pytest.mark.anyio
    async def test_retrieve_knowledge_sends_correct_action(self):
        """retrieve_knowledge sends RETRIEVE_KNOWLEDGE_BASE action."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {"results": []}

        ctx = create_mock_context(knowledge_bases=[{"kb_id": "kb_001"}])
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.retrieve_knowledge("kb_001", "search query")

        call_args = mock_handler.call_action_mock.call_args
        action = call_args[0][0]

        assert action == PluginToRuntimeAction.RETRIEVE_KNOWLEDGE_BASE


class TestRunnerAPIProxyFieldConsistency:
    """Tests for field name consistency between SDK and Host handler."""

    @pytest.mark.anyio
    async def test_invoke_llm_sends_correct_fields(self):
        """INVOKE_LLM: SDK fields match Host handler expectations."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {
            "message": {"role": "assistant", "content": "Hello"}
        }

        ctx = create_mock_context(models=[{"model_id": "model_001"}])
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.invoke_llm("model_001", [Message(role="user", content="Hello")])

        call_args = mock_handler.call_action_mock.call_args
        data = call_args[0][1]

        # Host handler expects these fields
        assert "run_id" in data
        assert "llm_model_uuid" in data
        assert "messages" in data
        assert "funcs" in data
        assert "extra_args" in data
        assert "timeout" in data

    @pytest.mark.anyio
    async def test_invoke_llm_can_send_remove_think_override(self):
        """INVOKE_LLM: remove_think override is passed when supplied."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {
            "message": {"role": "assistant", "content": "Hello"}
        }

        ctx = create_mock_context(models=[{"model_id": "model_001"}])
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.invoke_llm(
            "model_001", [Message(role="user", content="Hello")], remove_think=True
        )

        call_args = mock_handler.call_action_mock.call_args
        data = call_args[0][1]

        assert data["remove_think"] is True

    @pytest.mark.anyio
    async def test_invoke_rerank_validates_authorized_model(self):
        """INVOKE_RERANK: SDK validates rerank model through ctx.resources.models."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {"results": []}

        ctx = create_mock_context(models=[{"model_id": "rerank_001"}])
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.invoke_rerank(
            "rerank_001", "query", ["doc"], extra_args={"top_n": 2}
        )

        call_args = mock_handler.call_action_mock.call_args
        data = call_args[0][1]
        assert data["extra_args"] == {"top_n": 2}

        with pytest.raises(PermissionDeniedError):
            await proxy.invoke_rerank("rerank_999", "query", ["doc"])

    @pytest.mark.anyio
    async def test_invoke_rerank_rejects_malformed_response(self):
        """INVOKE_RERANK requires Host to return results."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {"unexpected": []}

        ctx = create_mock_context(models=[{"model_id": "rerank_001"}])
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        with pytest.raises(AgentAPIException) as exc_info:
            await proxy.invoke_rerank("rerank_001", "query", ["doc"])

        assert exc_info.value.error.code == "host.malformed_response"
        assert exc_info.value.error.details["missing_key"] == "results"

    @pytest.mark.anyio
    async def test_call_tool_sends_correct_fields(self):
        """CALL_TOOL: SDK fields match Host handler expectations."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {"result": {}}

        ctx = create_mock_context(tools=[{"tool_name": "test_tool"}])
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.call_tool("test_tool", {"param": "value"})

        call_args = mock_handler.call_action_mock.call_args
        data = call_args[0][1]

        assert "run_id" in data
        assert "tool_name" in data
        assert "parameters" in data
        assert "query_id" not in data
        assert "session" not in data

    @pytest.mark.anyio
    async def test_retrieve_knowledge_sends_correct_fields(self):
        """RETRIEVE_KNOWLEDGE_BASE: SDK fields match Host handler expectations."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {"results": []}

        ctx = create_mock_context(knowledge_bases=[{"kb_id": "kb_001"}])
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.retrieve_knowledge(
            "kb_001", "search query", top_k=5, filters={"cat": "tech"}
        )

        call_args = mock_handler.call_action_mock.call_args
        data = call_args[0][1]

        assert "run_id" in data
        assert "query_id" not in data
        assert "kb_id" in data
        assert "query_text" in data
        assert "top_k" in data
        assert "filters" in data

    @pytest.mark.anyio
    async def test_steering_pull_returns_typed_result(self):
        """STEERING_PULL returns SteeringPullResult instead of a raw dict."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {
            "items": [
                {
                    "claimed_run_id": "run_1",
                    "runner_id": "plugin:test/demo/default",
                    "event": {
                        "event_id": "evt_1",
                        "event_type": "message.received",
                        "source": "platform",
                    },
                    "input": {"text": "follow up"},
                }
            ]
        }

        ctx = create_mock_context()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        result = await proxy.steering_pull(mode="one")

        assert result.items[0].input.text == "follow up"

    @pytest.mark.anyio
    async def test_action_error_is_wrapped_as_agent_api_exception(self):
        """Host action failures surface as structured AgentAPIException."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.side_effect = ActionCallError(
            "access denied",
            {
                "error": {
                    "code": "history.unauthorized",
                    "message": "access denied",
                    "retryable": False,
                    "details": {"conversation_id": "conv_1"},
                }
            },
        )

        ctx = create_mock_context(
            knowledge_bases=[{"kb_id": "kb_001"}],
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        with pytest.raises(AgentAPIException) as exc_info:
            await proxy.retrieve_knowledge("kb_001", "query")

        assert exc_info.value.error.code == "history.unauthorized"
        assert exc_info.value.error.details["conversation_id"] == "conv_1"

    @pytest.mark.anyio
    async def test_action_timeout_is_wrapped_as_agent_api_exception(self):
        """Transport timeouts must not escape the runner-facing API contract."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.side_effect = ActionCallTimeoutError(
            "slow host action"
        )

        ctx = create_mock_context(
            knowledge_bases=[{"kb_id": "kb_001"}],
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        with pytest.raises(AgentAPIException) as exc_info:
            await proxy.retrieve_knowledge("kb_001", "query")

        assert exc_info.value.error.code == "deadline_exceeded"
        assert exc_info.value.error.retryable is True
        assert (
            exc_info.value.error.details["action"]
            == PluginToRuntimeAction.RETRIEVE_KNOWLEDGE_BASE.value
        )

    @pytest.mark.anyio
    async def test_connection_closed_is_wrapped_as_agent_api_exception(self):
        """Connection failures must be normalized for runner error handling."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.side_effect = ConnectionClosedError(
            "connection closed"
        )

        ctx = create_mock_context(tools=[{"tool_name": "test_tool"}])
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        with pytest.raises(AgentAPIException) as exc_info:
            await proxy.call_tool("test_tool", {})

        assert exc_info.value.error.code == "runtime_error"
        assert exc_info.value.error.retryable is True
        assert (
            exc_info.value.error.details["action"]
            == PluginToRuntimeAction.CALL_TOOL.value
        )

    @pytest.mark.anyio
    async def test_expired_deadline_fails_fast_before_host_call(self):
        """Expired run deadlines should fail locally instead of issuing doomed calls."""
        mock_handler = MockHandler()

        ctx = create_mock_context(
            deadline_at=time.time() - 1,
            knowledge_bases=[{"kb_id": "kb_001"}],
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        with pytest.raises(AgentAPIException) as exc_info:
            await proxy.retrieve_knowledge("kb_001", "query")

        assert exc_info.value.error.code == "deadline_exceeded"
        mock_handler.call_action_mock.assert_not_called()

    @pytest.mark.anyio
    async def test_malformed_response_is_wrapped_as_agent_api_exception(self):
        """Malformed Host responses do not leak KeyError to runners."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {"unexpected": "shape"}

        ctx = create_mock_context(tools=[{"tool_name": "test_tool"}])
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        with pytest.raises(AgentAPIException) as exc_info:
            await proxy.call_tool("test_tool", {})

        assert exc_info.value.error.code == "host.malformed_response"
        assert exc_info.value.error.details["missing_key"] == "result"


class TestRunnerAPIProxyRunLedgerAPI:
    """Tests for Run Ledger API proxy methods."""

    @pytest.mark.anyio
    async def test_run_get_sends_current_and_target_run_id(self):
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {
            "id": 1,
            "run_id": "run_target",
            "runner_id": "plugin:test/plugin/default",
            "status": "running",
            "metadata": {},
        }

        ctx = create_mock_context(available_apis=ContextAPICapabilities(run_get=True))
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        result = await proxy.run_get("run_target")

        assert result.run_id == "run_target"
        action, data, _timeout = mock_handler.call_action_mock.call_args.args
        assert action == PluginToRuntimeAction.RUN_GET
        assert data == {"run_id": "test_run", "target_run_id": "run_target"}

    @pytest.mark.anyio
    async def test_run_list_sends_scope_filters(self):
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {
            "items": [],
            "next_cursor": None,
            "prev_cursor": None,
            "has_more": False,
        }

        ctx = create_mock_context(available_apis=ContextAPICapabilities(run_list=True))
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        result = await proxy.run_list(
            conversation_id="conv_1",
            statuses=["running"],
            before_cursor="10",
            limit=5,
        )

        assert result.items == []
        action, data, _timeout = mock_handler.call_action_mock.call_args.args
        assert action == PluginToRuntimeAction.RUN_LIST
        assert data["run_id"] == "test_run"
        assert data["conversation_id"] == "conv_1"
        assert data["statuses"] == ["running"]
        assert data["before_cursor"] == "10"
        assert data["limit"] == 5

    @pytest.mark.anyio
    async def test_run_events_page_sends_paging_fields(self):
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {
            "items": [
                {
                    "id": 1,
                    "run_id": "run_target",
                    "sequence": 1,
                    "type": "message.completed",
                    "data": {},
                    "metadata": {},
                }
            ],
            "next_cursor": None,
            "prev_cursor": "1",
            "has_more": False,
        }

        ctx = create_mock_context(
            available_apis=ContextAPICapabilities(run_events_page=True)
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        result = await proxy.run_events_page(
            "run_target",
            after_cursor="0",
            limit=1,
        )

        assert result.items[0].sequence == 1
        action, data, _timeout = mock_handler.call_action_mock.call_args.args
        assert action == PluginToRuntimeAction.RUN_EVENTS_PAGE
        assert data["run_id"] == "test_run"
        assert data["target_run_id"] == "run_target"
        assert data["after_cursor"] == "0"
        assert data["limit"] == 1

    @pytest.mark.anyio
    async def test_run_cancel_sends_current_and_target_run_id(self):
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {
            "id": 1,
            "run_id": "run_target",
            "runner_id": "plugin:test/plugin/default",
            "status": "running",
            "status_reason": "user requested",
            "cancel_requested_at": 123,
            "metadata": {},
        }

        ctx = create_mock_context(
            available_apis=ContextAPICapabilities(run_cancel=True)
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        result = await proxy.run_cancel("run_target", reason="user requested")

        assert result.run_id == "run_target"
        assert result.cancel_requested_at == 123
        action, data, _timeout = mock_handler.call_action_mock.call_args.args
        assert action == PluginToRuntimeAction.RUN_CANCEL
        assert data == {
            "run_id": "test_run",
            "target_run_id": "run_target",
            "reason": "user requested",
        }

    @pytest.mark.anyio
    async def test_run_append_result_sends_agent_run_result_payload(self):
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {
            "id": 2,
            "run_id": "run_target",
            "sequence": 3,
            "type": "run.completed",
            "data": {"finish_reason": "stop"},
            "metadata": {},
        }

        ctx = create_mock_context(
            available_apis=ContextAPICapabilities(run_append_result=True)
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)
        event = RunnerResult.run_completed(
            "run_target",
            finish_reason="stop",
            sequence=3,
        )

        result = await proxy.run_append_result(event)

        assert result.run_id == "run_target"
        assert result.sequence == 3
        assert result.type == "run.completed"
        action, data, _timeout = mock_handler.call_action_mock.call_args.args
        assert action == PluginToRuntimeAction.RUN_APPEND_RESULT
        assert data["run_id"] == "test_run"
        assert data["target_run_id"] == "run_target"
        assert data["result"] == event.model_dump(mode="json")
        assert data["result"]["type"] == "run.completed"

    @pytest.mark.anyio
    async def test_run_finalize_sends_terminal_fields(self):
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {
            "id": 1,
            "run_id": "run_target",
            "runner_id": "plugin:test/plugin/default",
            "status": "completed",
            "status_reason": "stop",
            "finished_at": 123,
            "metadata": {},
        }

        ctx = create_mock_context(
            available_apis=ContextAPICapabilities(run_finalize=True)
        )
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        result = await proxy.run_finalize(
            "run_target",
            status="completed",
            reason="stop",
        )

        assert result.run_id == "run_target"
        assert result.status == "completed"
        assert result.finished_at == 123
        action, data, _timeout = mock_handler.call_action_mock.call_args.args
        assert action == PluginToRuntimeAction.RUN_FINALIZE
        assert data == {
            "run_id": "test_run",
            "target_run_id": "run_target",
            "status": "completed",
            "reason": "stop",
        }


class TestRunnerAdminAPIProxy:
    """Tests for Host-authorized admin proxy methods."""

    @pytest.mark.anyio
    async def test_admin_run_list_omits_run_id(self):
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {
            "items": [
                {
                    "id": 1,
                    "run_id": "run_1",
                    "runner_id": "plugin:test/plugin/default",
                    "status": "completed",
                    "metadata": {},
                }
            ],
            "next_cursor": None,
            "prev_cursor": None,
            "has_more": False,
        }
        proxy = RunnerAdminAPIProxy(plugin_runtime_handler=mock_handler)

        page = await proxy.run_list(statuses=["completed"], limit=10)

        assert [run.run_id for run in page.items] == ["run_1"]
        action, data, _timeout = mock_handler.call_action_mock.call_args.args
        assert action == PluginToRuntimeAction.RUN_LIST
        assert "run_id" not in data
        assert data["statuses"] == ["completed"]
        assert data["limit"] == 10

    @pytest.mark.anyio
    async def test_admin_run_get_and_events_use_target_run_id_only(self):
        mock_handler = MockHandler()
        mock_handler.call_action_mock.side_effect = [
            {
                "id": 1,
                "run_id": "run_target",
                "runner_id": "plugin:test/plugin/default",
                "status": "completed",
                "metadata": {},
            },
            {
                "items": [
                    {
                        "id": 2,
                        "run_id": "run_target",
                        "sequence": 3,
                        "type": "run.completed",
                        "data": {},
                        "metadata": {},
                    }
                ],
                "next_cursor": None,
                "prev_cursor": "3",
                "has_more": False,
            },
        ]
        proxy = RunnerAdminAPIProxy(plugin_runtime_handler=mock_handler)

        run = await proxy.run_get("run_target")
        events = await proxy.run_events_page(
            "run_target", direction="backward", limit=5
        )

        assert run.run_id == "run_target"
        assert events.items[0].type == "run.completed"
        first_call = mock_handler.call_action_mock.call_args_list[0].args
        second_call = mock_handler.call_action_mock.call_args_list[1].args
        assert first_call[0] == PluginToRuntimeAction.RUN_GET
        assert first_call[1] == {"target_run_id": "run_target"}
        assert second_call[0] == PluginToRuntimeAction.RUN_EVENTS_PAGE
        assert "run_id" not in second_call[1]
        assert second_call[1]["target_run_id"] == "run_target"

    @pytest.mark.anyio
    async def test_admin_runtime_and_claim_apis_omit_run_id(self):
        mock_handler = MockHandler()
        mock_handler.call_action_mock.side_effect = [
            {
                "items": [
                    {
                        "runtime_id": "runtime_1",
                        "status": "online",
                        "labels": {"region": "local"},
                    }
                ],
                "next_cursor": None,
                "prev_cursor": None,
                "has_more": False,
            },
            {
                "id": 1,
                "run_id": "queued_run",
                "runner_id": "plugin:test/plugin/default",
                "status": "claimed",
                "queue_name": "default",
                "claimed_by_runtime_id": "runtime_1",
                "claim_token": "claim_token_1",
                "metadata": {},
            },
        ]
        proxy = RunnerAdminAPIProxy(plugin_runtime_handler=mock_handler)

        runtimes = await proxy.runtime_list(
            statuses=["online"], labels={"region": "local"}
        )
        claimed = await proxy.run_claim(
            runtime_id="runtime_1",
            queue_name="default",
            runner_ids=["plugin:test/plugin/default"],
        )

        assert runtimes.items[0].runtime_id == "runtime_1"
        assert claimed.run_id == "queued_run"
        runtime_call = mock_handler.call_action_mock.call_args_list[0].args
        claim_call = mock_handler.call_action_mock.call_args_list[1].args
        assert runtime_call[0] == PluginToRuntimeAction.RUNTIME_LIST
        assert "run_id" not in runtime_call[1]
        assert claim_call[0] == PluginToRuntimeAction.RUN_CLAIM
        assert "run_id" not in claim_call[1]
        assert claim_call[1]["runner_ids"] == ["plugin:test/plugin/default"]

    @pytest.mark.anyio
    async def test_admin_runtime_register_and_heartbeat_omit_run_id(self):
        mock_handler = MockHandler()
        mock_handler.call_action_mock.side_effect = [
            {
                "runtime_id": "runtime_1",
                "status": "online",
                "display_name": "Runtime 1",
                "endpoint": "http://runtime.local",
                "version": "1.2.3",
                "capabilities": {"queues": ["default"]},
                "labels": {"region": "local"},
                "metadata": {"owner": "test"},
            },
            {
                "runtime_id": "runtime_1",
                "status": "online",
                "last_heartbeat_at": 100,
            },
        ]
        proxy = RunnerAdminAPIProxy(plugin_runtime_handler=mock_handler)

        registered = await proxy.runtime_register(
            runtime_id="runtime_1",
            status="online",
            display_name="Runtime 1",
            endpoint="http://runtime.local",
            version="1.2.3",
            capabilities={"queues": ["default"]},
            labels={"region": "local"},
            metadata={"owner": "test"},
            heartbeat_deadline_at=160,
        )
        heartbeat = await proxy.runtime_heartbeat(
            "runtime_1",
            status="online",
            heartbeat_deadline_at=220,
        )

        assert registered.runtime_id == "runtime_1"
        assert heartbeat.last_heartbeat_at == 100
        register_call = mock_handler.call_action_mock.call_args_list[0].args
        heartbeat_call = mock_handler.call_action_mock.call_args_list[1].args
        assert register_call[0] == PluginToRuntimeAction.RUNTIME_REGISTER
        assert "run_id" not in register_call[1]
        assert register_call[1] == {
            "runtime_id": "runtime_1",
            "status": "online",
            "display_name": "Runtime 1",
            "endpoint": "http://runtime.local",
            "version": "1.2.3",
            "capabilities": {"queues": ["default"]},
            "labels": {"region": "local"},
            "metadata": {"owner": "test"},
            "heartbeat_deadline_at": 160,
        }
        assert heartbeat_call[0] == PluginToRuntimeAction.RUNTIME_HEARTBEAT
        assert "run_id" not in heartbeat_call[1]
        assert heartbeat_call[1] == {
            "runtime_id": "runtime_1",
            "status": "online",
            "capabilities": None,
            "labels": None,
            "metadata": None,
            "heartbeat_deadline_at": 220,
        }

    @pytest.mark.anyio
    async def test_admin_claim_renew_and_release_omit_run_id(self):
        mock_handler = MockHandler()
        mock_handler.call_action_mock.side_effect = [
            {
                "run_id": "run_target",
                "status": "claimed",
                "claimed_by_runtime_id": "runtime_1",
                "claim_token": "claim_token_1",
                "claim_lease_expires_at": 220,
                "metadata": {},
            },
            {
                "run_id": "run_target",
                "status": "queued",
                "claimed_by_runtime_id": None,
                "claim_token": None,
                "metadata": {},
            },
        ]
        proxy = RunnerAdminAPIProxy(plugin_runtime_handler=mock_handler)

        renewed = await proxy.run_renew_claim(
            "run_target",
            runtime_id="runtime_1",
            claim_token="claim_token_1",
            lease_seconds=120,
        )
        released = await proxy.run_release_claim(
            "run_target",
            runtime_id="runtime_1",
            claim_token="claim_token_1",
            reason="shutdown",
        )

        assert renewed.claim_lease_expires_at == 220
        assert released.status == "queued"
        renew_call = mock_handler.call_action_mock.call_args_list[0].args
        release_call = mock_handler.call_action_mock.call_args_list[1].args
        assert renew_call[0] == PluginToRuntimeAction.RUN_RENEW_CLAIM
        assert "run_id" not in renew_call[1]
        assert renew_call[1] == {
            "target_run_id": "run_target",
            "runtime_id": "runtime_1",
            "claim_token": "claim_token_1",
            "lease_seconds": 120,
        }
        assert release_call[0] == PluginToRuntimeAction.RUN_RELEASE_CLAIM
        assert "run_id" not in release_call[1]
        assert release_call[1] == {
            "target_run_id": "run_target",
            "runtime_id": "runtime_1",
            "claim_token": "claim_token_1",
            "reason": "shutdown",
        }

    @pytest.mark.anyio
    async def test_admin_runner_list_omits_run_id(self):
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = [
            {
                "runner_id": "plugin:test/plugin/default",
                "plugin": "test/plugin",
                "name": "default",
            }
        ]
        proxy = RunnerAdminAPIProxy(plugin_runtime_handler=mock_handler)

        runners = await proxy.runner_list(include_plugins=["test/plugin"])

        assert runners == [
            {
                "runner_id": "plugin:test/plugin/default",
                "plugin": "test/plugin",
                "name": "default",
            }
        ]
        action, data, _timeout = mock_handler.call_action_mock.call_args.args
        assert action == PluginToRuntimeAction.RUNNER_LIST
        assert "run_id" not in data
        assert data == {"include_plugins": ["test/plugin"]}

    @pytest.mark.anyio
    async def test_admin_runtime_reconcile_omits_run_id(self):
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {
            "stale_runtime_count": 2,
            "updated_runtime_count": 1,
        }
        proxy = RunnerAdminAPIProxy(plugin_runtime_handler=mock_handler)

        result = await proxy.runtime_reconcile(stale_after_seconds=60.5)

        assert result == {"stale_runtime_count": 2, "updated_runtime_count": 1}
        action, data, _timeout = mock_handler.call_action_mock.call_args.args
        assert action == PluginToRuntimeAction.RUNTIME_RECONCILE
        assert "run_id" not in data
        assert data == {"stale_after_seconds": 60.5}


class TestRunnerAPIProxyStateAPI:
    """Tests for State API proxy methods."""

    @pytest.mark.anyio
    async def test_state_get_sends_correct_fields(self):
        """STATE_GET: SDK fields match Host handler expectations."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {"value": {"key": "value"}}

        ctx = create_mock_context()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.state_get("conversation", "external.session_id")

        call_args = mock_handler.call_action_mock.call_args
        data = call_args[0][1]

        assert "run_id" in data
        assert data["run_id"] == "test_run"
        assert "scope" in data
        assert data["scope"] == "conversation"
        assert "key" in data
        assert data["key"] == "external.session_id"

    @pytest.mark.anyio
    async def test_state_set_sends_correct_fields(self):
        """STATE_SET: SDK fields match Host handler expectations."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {"success": True}

        ctx = create_mock_context()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.state_set("conversation", "external.session_id", "sess_123")

        call_args = mock_handler.call_action_mock.call_args
        data = call_args[0][1]

        assert "run_id" in data
        assert data["run_id"] == "test_run"
        assert "scope" in data
        assert data["scope"] == "conversation"
        assert "key" in data
        assert data["key"] == "external.session_id"
        assert "value" in data
        assert data["value"] == "sess_123"

    @pytest.mark.anyio
    async def test_state_delete_sends_correct_fields(self):
        """STATE_DELETE: SDK fields match Host handler expectations."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {"success": True}

        ctx = create_mock_context()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.state_delete("conversation", "external.session_id")

        call_args = mock_handler.call_action_mock.call_args
        data = call_args[0][1]

        assert "run_id" in data
        assert data["run_id"] == "test_run"
        assert "scope" in data
        assert data["scope"] == "conversation"
        assert "key" in data
        assert data["key"] == "external.session_id"

    @pytest.mark.anyio
    async def test_state_list_sends_correct_fields(self):
        """STATE_LIST: SDK fields match Host handler expectations."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {
            "keys": ["key1", "key2"],
            "has_more": False,
        }

        ctx = create_mock_context()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.state_list("conversation", prefix="external.", limit=50)

        call_args = mock_handler.call_action_mock.call_args
        data = call_args[0][1]

        assert "run_id" in data
        assert data["run_id"] == "test_run"
        assert "scope" in data
        assert data["scope"] == "conversation"
        assert "prefix" in data
        assert data["prefix"] == "external."
        assert "limit" in data
        assert data["limit"] == 50

    @pytest.mark.anyio
    async def test_state_get_returns_value(self):
        """STATE_GET returns value from response."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {"value": {"nested": "data"}}

        ctx = create_mock_context()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        result = await proxy.state_get("conversation", "test_key")

        assert result["value"] == {"nested": "data"}

    @pytest.mark.anyio
    async def test_state_set_returns_success(self):
        """STATE_SET returns success status."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {"success": True}

        ctx = create_mock_context()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        result = await proxy.state_set("conversation", "test_key", "test_value")

        assert result["success"] is True

    @pytest.mark.anyio
    async def test_state_list_returns_keys_and_has_more(self):
        """STATE_LIST returns keys and has_more flag."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {
            "keys": ["k1", "k2", "k3"],
            "has_more": True,
        }

        ctx = create_mock_context()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        result = await proxy.state_list("runner", limit=100)

        assert result["keys"] == ["k1", "k2", "k3"]
        assert result["has_more"] is True

    @pytest.mark.anyio
    async def test_state_methods_use_correct_action_enum(self):
        """State methods should use correct PluginToRuntimeAction enum values."""
        mock_handler = MockHandler()
        mock_handler.call_action_mock.return_value = {"value": None}

        ctx = create_mock_context()
        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        # Test each method uses correct action
        await proxy.state_get("conversation", "key")
        call_args = mock_handler.call_action_mock.call_args
        assert call_args[0][0] == PluginToRuntimeAction.STATE_GET

        mock_handler.call_action_mock.return_value = {"success": True}
        await proxy.state_set("conversation", "key", "value")
        call_args = mock_handler.call_action_mock.call_args
        assert call_args[0][0] == PluginToRuntimeAction.STATE_SET

        await proxy.state_delete("conversation", "key")
        call_args = mock_handler.call_action_mock.call_args
        assert call_args[0][0] == PluginToRuntimeAction.STATE_DELETE

        mock_handler.call_action_mock.return_value = {"keys": [], "has_more": False}
        await proxy.state_list("conversation")
        call_args = mock_handler.call_action_mock.call_args
        assert call_args[0][0] == PluginToRuntimeAction.STATE_LIST


@pytest.mark.asyncio
async def test_reply_stream_is_explicit_and_finishes_one_message():
    ctx = create_mock_context(
        tools=[
            {
                "tool_name": "event_reply",
                "tool_type": "platform",
                "operations": ["call"],
            }
        ],
        available_apis=ContextAPICapabilities(reply_stream=True),
    )
    handler = MockHandler()
    handler.call_action_mock.return_value = {"result": {"status": "completed"}}
    api = RunnerAPIProxy(ctx, handler)
    async with api.reply_stream() as stream:
        handler.call_action_mock.assert_not_awaited()
        await stream.update("Hello")
        await stream.update("Hello world")
    calls = handler.call_action_mock.await_args_list
    assert [c.args[1]["operation"] for c in calls] == ["update", "update", "finish"]
    assert {c.args[1]["stream_id"] for c in calls} == {calls[0].args[1]["stream_id"]}
    assert calls[-1].args[1]["text"] == "Hello world"
    with pytest.raises(ValueError, match="closed"):
        await stream.update("late")


@pytest.mark.asyncio
async def test_reply_stream_rejects_old_host_without_sending():
    ctx = create_mock_context(
        tools=[{"tool_name": "event_reply", "tool_type": "platform"}]
    )
    handler = MockHandler()
    api = RunnerAPIProxy(ctx, handler)
    with pytest.raises(PermissionDeniedError, match="reply_stream"):
        async with api.reply_stream():
            pass
    handler.call_action_mock.assert_not_awaited()
