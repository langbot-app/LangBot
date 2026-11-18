"""Tests for SDK PluginConnectionHandler runtime action forwarding.

Tests focus on:
- State API handlers (STATE_GET, STATE_SET, STATE_DELETE, STATE_LIST)
- History/Event API handlers (HISTORY_PAGE, HISTORY_SEARCH, EVENT_GET, EVENT_PAGE)
- caller_plugin_identity injection in all pull API handlers

These tests instantiate real PluginConnectionHandler and verify:
- Actions are registered in handler.actions
- Forwarding calls context.control_handler.call_action with correct action and payload
- caller_plugin_identity is injected from plugin container when available
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock
from types import SimpleNamespace

from langbot_plugin.runtime.io.handlers.plugin import PluginConnectionHandler
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction


class FakeConnection:
    """Minimal fake connection for PluginConnectionHandler testing."""

    async def send(self, message: str) -> None:
        pass

    async def receive(self) -> str:
        return ""

    async def close(self) -> None:
        pass


def make_fake_context():
    """Create a minimal fake runtime context for testing."""
    control_handler = SimpleNamespace()
    control_handler.call_action = AsyncMock(return_value={"ok": True})

    plugin_mgr = SimpleNamespace()
    plugin_mgr.plugins = []

    context = SimpleNamespace()
    context.control_handler = control_handler
    context.plugin_mgr = plugin_mgr

    return context


class TestPluginConnectionHandlerPullAPIRegistration:
    """Tests for pull API handler registration in PluginConnectionHandler."""

    @pytest.mark.anyio
    async def test_all_pull_api_handlers_registered(self):
        """All pull API handlers are registered in handler.actions."""
        fake_context = make_fake_context()
        handler = PluginConnectionHandler(FakeConnection(), fake_context)

        # Verify all pull API actions are registered
        expected_actions = [
            PluginToRuntimeAction.GET_PROMPT,
            PluginToRuntimeAction.HISTORY_PAGE,
            PluginToRuntimeAction.HISTORY_SEARCH,
            PluginToRuntimeAction.EVENT_GET,
            PluginToRuntimeAction.EVENT_PAGE,
            PluginToRuntimeAction.STEERING_PULL,
            PluginToRuntimeAction.STATE_GET,
            PluginToRuntimeAction.STATE_SET,
            PluginToRuntimeAction.STATE_DELETE,
            PluginToRuntimeAction.STATE_LIST,
            PluginToRuntimeAction.RUN_GET,
            PluginToRuntimeAction.RUN_LIST,
            PluginToRuntimeAction.RUN_EVENTS_PAGE,
            PluginToRuntimeAction.RUN_CANCEL,
            PluginToRuntimeAction.RUN_APPEND_RESULT,
            PluginToRuntimeAction.RUN_FINALIZE,
            PluginToRuntimeAction.RUNTIME_REGISTER,
            PluginToRuntimeAction.RUNTIME_HEARTBEAT,
            PluginToRuntimeAction.RUNTIME_LIST,
            PluginToRuntimeAction.RUN_CLAIM,
            PluginToRuntimeAction.RUN_RENEW_CLAIM,
            PluginToRuntimeAction.RUN_RELEASE_CLAIM,
            PluginToRuntimeAction.RUNNER_LIST,
            PluginToRuntimeAction.RUNTIME_RECONCILE,
        ]

        for action in expected_actions:
            assert action.value in handler.actions, (
                f"Action {action.value} not registered"
            )


class TestPluginConnectionHandlerPullAPIForwarding:
    """Tests for pull API action forwarding to control_handler.call_action."""

    @pytest.mark.anyio
    async def test_state_get_forwards_correctly(self):
        """STATE_GET forwards to control_handler.call_action with correct parameters."""
        fake_context = make_fake_context()
        handler = PluginConnectionHandler(FakeConnection(), fake_context)

        payload = {
            "run_id": "run_001",
            "scope": "conversation",
            "key": "external.test_key",
        }
        resp = await handler.actions[PluginToRuntimeAction.STATE_GET.value](payload)

        assert resp.code == 0
        assert resp.data == {"ok": True}
        fake_context.control_handler.call_action.assert_called_once()

        call_args = fake_context.control_handler.call_action.call_args
        assert call_args[0][0] == PluginToRuntimeAction.STATE_GET

        forwarded_payload = call_args[0][1]
        assert forwarded_payload["run_id"] == "run_001"
        assert forwarded_payload["scope"] == "conversation"
        assert forwarded_payload["key"] == "external.test_key"

        # timeout is passed as keyword argument
        assert call_args[1].get("timeout") == 15

    @pytest.mark.anyio
    async def test_state_set_forwards_correctly(self):
        """STATE_SET forwards to control_handler.call_action with correct parameters."""
        fake_context = make_fake_context()
        handler = PluginConnectionHandler(FakeConnection(), fake_context)

        payload = {
            "run_id": "run_001",
            "scope": "conversation",
            "key": "external.test_key",
            "value": {"data": "test_value"},
        }
        resp = await handler.actions[PluginToRuntimeAction.STATE_SET.value](payload)

        assert resp.code == 0
        fake_context.control_handler.call_action.assert_called_once()

        call_args = fake_context.control_handler.call_action.call_args
        assert call_args[0][0] == PluginToRuntimeAction.STATE_SET

        forwarded_payload = call_args[0][1]
        assert forwarded_payload["run_id"] == "run_001"
        assert forwarded_payload["scope"] == "conversation"
        assert forwarded_payload["key"] == "external.test_key"
        assert forwarded_payload["value"] == {"data": "test_value"}

        # timeout is passed as keyword argument
        assert call_args[1].get("timeout") == 15

    @pytest.mark.anyio
    async def test_state_delete_forwards_correctly(self):
        """STATE_DELETE forwards to control_handler.call_action with correct parameters."""
        fake_context = make_fake_context()
        handler = PluginConnectionHandler(FakeConnection(), fake_context)

        payload = {
            "run_id": "run_001",
            "scope": "conversation",
            "key": "external.test_key",
        }
        resp = await handler.actions[PluginToRuntimeAction.STATE_DELETE.value](payload)

        assert resp.code == 0
        fake_context.control_handler.call_action.assert_called_once()

        call_args = fake_context.control_handler.call_action.call_args
        assert call_args[0][0] == PluginToRuntimeAction.STATE_DELETE
        assert call_args[1].get("timeout") == 15

    @pytest.mark.anyio
    async def test_state_list_forwards_correctly(self):
        """STATE_LIST forwards to control_handler.call_action with correct parameters."""
        fake_context = make_fake_context()
        handler = PluginConnectionHandler(FakeConnection(), fake_context)

        payload = {
            "run_id": "run_001",
            "scope": "conversation",
            "prefix": "external.",
            "limit": 50,
        }
        resp = await handler.actions[PluginToRuntimeAction.STATE_LIST.value](payload)

        assert resp.code == 0
        fake_context.control_handler.call_action.assert_called_once()

        call_args = fake_context.control_handler.call_action.call_args
        assert call_args[0][0] == PluginToRuntimeAction.STATE_LIST

        forwarded_payload = call_args[0][1]
        assert forwarded_payload["run_id"] == "run_001"
        assert forwarded_payload["scope"] == "conversation"
        assert forwarded_payload["prefix"] == "external."
        assert forwarded_payload["limit"] == 50
        assert call_args[1].get("timeout") == 15

    @pytest.mark.anyio
    async def test_history_page_forwards_correctly(self):
        """HISTORY_PAGE forwards to control_handler.call_action with correct parameters."""
        fake_context = make_fake_context()
        handler = PluginConnectionHandler(FakeConnection(), fake_context)

        payload = {"run_id": "run_001", "limit": 50, "cursor": None}
        resp = await handler.actions[PluginToRuntimeAction.HISTORY_PAGE.value](payload)

        assert resp.code == 0
        fake_context.control_handler.call_action.assert_called_once()

        call_args = fake_context.control_handler.call_action.call_args
        assert call_args[0][0] == PluginToRuntimeAction.HISTORY_PAGE

        forwarded_payload = call_args[0][1]
        assert forwarded_payload["run_id"] == "run_001"
        assert forwarded_payload["limit"] == 50

        # timeout is passed as keyword argument
        assert call_args[1].get("timeout") == 30

    @pytest.mark.anyio
    async def test_get_prompt_forwards_correctly(self):
        """GET_PROMPT forwards to control_handler.call_action with correct parameters."""
        fake_context = make_fake_context()
        handler = PluginConnectionHandler(FakeConnection(), fake_context)

        payload = {"run_id": "run_001"}
        resp = await handler.actions[PluginToRuntimeAction.GET_PROMPT.value](payload)

        assert resp.code == 0
        fake_context.control_handler.call_action.assert_called_once()

        call_args = fake_context.control_handler.call_action.call_args
        assert call_args[0][0] == PluginToRuntimeAction.GET_PROMPT

        forwarded_payload = call_args[0][1]
        assert forwarded_payload["run_id"] == "run_001"
        assert call_args[1].get("timeout") == 15

    @pytest.mark.anyio
    async def test_history_search_forwards_correctly(self):
        """HISTORY_SEARCH forwards to control_handler.call_action with correct parameters."""
        fake_context = make_fake_context()
        handler = PluginConnectionHandler(FakeConnection(), fake_context)

        payload = {"run_id": "run_001", "query": "test query", "top_k": 10}
        resp = await handler.actions[PluginToRuntimeAction.HISTORY_SEARCH.value](
            payload
        )

        assert resp.code == 0
        fake_context.control_handler.call_action.assert_called_once()

        call_args = fake_context.control_handler.call_action.call_args
        assert call_args[0][0] == PluginToRuntimeAction.HISTORY_SEARCH
        assert call_args[1].get("timeout") == 30

    @pytest.mark.anyio
    async def test_event_get_forwards_correctly(self):
        """EVENT_GET forwards to control_handler.call_action with correct parameters."""
        fake_context = make_fake_context()
        handler = PluginConnectionHandler(FakeConnection(), fake_context)

        payload = {"run_id": "run_001", "event_id": "event_001"}
        resp = await handler.actions[PluginToRuntimeAction.EVENT_GET.value](payload)

        assert resp.code == 0
        fake_context.control_handler.call_action.assert_called_once()

        call_args = fake_context.control_handler.call_action.call_args
        assert call_args[0][0] == PluginToRuntimeAction.EVENT_GET

        forwarded_payload = call_args[0][1]
        assert forwarded_payload["run_id"] == "run_001"
        assert forwarded_payload["event_id"] == "event_001"

        # timeout is passed as keyword argument
        assert call_args[1].get("timeout") == 15

    @pytest.mark.anyio
    async def test_event_page_forwards_correctly(self):
        """EVENT_PAGE forwards to control_handler.call_action with correct parameters."""
        fake_context = make_fake_context()
        handler = PluginConnectionHandler(FakeConnection(), fake_context)

        payload = {"run_id": "run_001", "limit": 50}
        resp = await handler.actions[PluginToRuntimeAction.EVENT_PAGE.value](payload)

        assert resp.code == 0
        fake_context.control_handler.call_action.assert_called_once()

        call_args = fake_context.control_handler.call_action.call_args
        assert call_args[0][0] == PluginToRuntimeAction.EVENT_PAGE
        assert call_args[1].get("timeout") == 30

    @pytest.mark.anyio
    async def test_steering_pull_forwards_correctly(self):
        """STEERING_PULL forwards to control_handler.call_action with correct parameters."""
        fake_context = make_fake_context()
        handler = PluginConnectionHandler(FakeConnection(), fake_context)

        payload = {"run_id": "run_001", "mode": "one-at-a-time", "limit": 1}
        resp = await handler.actions[PluginToRuntimeAction.STEERING_PULL.value](payload)

        assert resp.code == 0
        fake_context.control_handler.call_action.assert_called_once()

        call_args = fake_context.control_handler.call_action.call_args
        assert call_args[0][0] == PluginToRuntimeAction.STEERING_PULL

        forwarded_payload = call_args[0][1]
        assert forwarded_payload["run_id"] == "run_001"
        assert forwarded_payload["mode"] == "one-at-a-time"
        assert forwarded_payload["limit"] == 1
        assert call_args[1].get("timeout") == 15


class TestPluginConnectionHandlerCallerIdentity:
    """Tests for caller_plugin_identity injection from plugin container."""

    @pytest.mark.anyio
    async def test_caller_plugin_identity_injected_when_plugin_matches(self):
        """caller_plugin_identity is injected when handler matches a plugin container."""
        fake_context = make_fake_context()
        handler = PluginConnectionHandler(FakeConnection(), fake_context)

        # Create a fake plugin container that references this handler
        plugin_container = SimpleNamespace(
            _runtime_plugin_handler=handler,
            manifest=SimpleNamespace(
                metadata=SimpleNamespace(
                    author="test-author",
                    name="test-plugin",
                )
            ),
        )
        fake_context.plugin_mgr.plugins = [plugin_container]

        payload = {
            "run_id": "run_001",
            "scope": "conversation",
            "key": "external.k",
            "caller_plugin_identity": "attacker/plugin",
        }
        resp = await handler.actions[PluginToRuntimeAction.STATE_GET.value](payload)

        assert resp.code == 0
        fake_context.control_handler.call_action.assert_called_once()

        call_args = fake_context.control_handler.call_action.call_args
        forwarded_payload = call_args[0][1]
        assert forwarded_payload["caller_plugin_identity"] == "test-author/test-plugin"

    @pytest.mark.anyio
    async def test_spoofed_caller_plugin_identity_stripped_without_plugin_container(
        self,
    ):
        """caller_plugin_identity from an unregistered connection is stripped."""
        fake_context = make_fake_context()
        handler = PluginConnectionHandler(FakeConnection(), fake_context)

        fake_context.plugin_mgr.plugins = []

        payload = {
            "run_id": "run_001",
            "scope": "conversation",
            "key": "external.k",
            "caller_plugin_identity": "attacker/plugin",
        }
        resp = await handler.actions[PluginToRuntimeAction.STATE_GET.value](payload)

        assert resp.code == 0
        fake_context.control_handler.call_action.assert_called_once()

        call_args = fake_context.control_handler.call_action.call_args
        forwarded_payload = call_args[0][1]
        assert "caller_plugin_identity" not in forwarded_payload

    @pytest.mark.anyio
    async def test_no_caller_plugin_identity_when_no_plugin_container(self):
        """caller_plugin_identity is NOT injected when no plugin container matches."""
        fake_context = make_fake_context()
        handler = PluginConnectionHandler(FakeConnection(), fake_context)

        # No plugin containers
        fake_context.plugin_mgr.plugins = []

        payload = {"run_id": "run_001", "scope": "conversation", "key": "external.k"}
        resp = await handler.actions[PluginToRuntimeAction.STATE_GET.value](payload)

        assert resp.code == 0
        fake_context.control_handler.call_action.assert_called_once()

        call_args = fake_context.control_handler.call_action.call_args
        forwarded_payload = call_args[0][1]
        assert "caller_plugin_identity" not in forwarded_payload

    @pytest.mark.anyio
    async def test_no_caller_plugin_identity_when_handler_not_matched(self):
        """caller_plugin_identity is NOT injected when plugin container doesn't reference this handler."""
        fake_context = make_fake_context()
        handler = PluginConnectionHandler(FakeConnection(), fake_context)

        # Plugin container references a different handler
        other_handler = SimpleNamespace()
        plugin_container = SimpleNamespace(
            _runtime_plugin_handler=other_handler,  # Different handler
            manifest=SimpleNamespace(
                metadata=SimpleNamespace(
                    author="other-author",
                    name="other-plugin",
                )
            ),
        )
        fake_context.plugin_mgr.plugins = [plugin_container]

        payload = {"run_id": "run_001", "scope": "conversation", "key": "external.k"}
        resp = await handler.actions[PluginToRuntimeAction.STATE_GET.value](payload)

        assert resp.code == 0
        call_args = fake_context.control_handler.call_action.call_args
        forwarded_payload = call_args[0][1]
        assert "caller_plugin_identity" not in forwarded_payload

    @pytest.mark.anyio
    async def test_all_pull_apis_inject_caller_plugin_identity(self):
        """All pull API handlers inject caller_plugin_identity when plugin container matches."""
        fake_context = make_fake_context()
        handler = PluginConnectionHandler(FakeConnection(), fake_context)

        # Create a fake plugin container
        plugin_container = SimpleNamespace(
            _runtime_plugin_handler=handler,
            manifest=SimpleNamespace(
                metadata=SimpleNamespace(
                    author="my-author",
                    name="my-plugin",
                )
            ),
        )
        fake_context.plugin_mgr.plugins = [plugin_container]

        # Test all pull API actions
        pull_actions = [
            (
                PluginToRuntimeAction.STATE_GET,
                {"run_id": "r", "scope": "conversation", "key": "k"},
            ),
            (
                PluginToRuntimeAction.STATE_SET,
                {"run_id": "r", "scope": "conversation", "key": "k", "value": {}},
            ),
            (
                PluginToRuntimeAction.STATE_DELETE,
                {"run_id": "r", "scope": "conversation", "key": "k"},
            ),
            (
                PluginToRuntimeAction.STATE_LIST,
                {"run_id": "r", "scope": "conversation"},
            ),
            (PluginToRuntimeAction.GET_PROMPT, {"run_id": "r"}),
            (PluginToRuntimeAction.HISTORY_PAGE, {"run_id": "r", "limit": 10}),
            (PluginToRuntimeAction.HISTORY_SEARCH, {"run_id": "r", "query": "q"}),
            (PluginToRuntimeAction.EVENT_GET, {"run_id": "r", "event_id": "e"}),
            (PluginToRuntimeAction.EVENT_PAGE, {"run_id": "r", "limit": 10}),
            (PluginToRuntimeAction.STEERING_PULL, {"run_id": "r"}),
            (PluginToRuntimeAction.RUN_GET, {"run_id": "r"}),
            (PluginToRuntimeAction.RUN_LIST, {"run_id": "r"}),
            (PluginToRuntimeAction.RUN_EVENTS_PAGE, {"run_id": "r"}),
            (PluginToRuntimeAction.RUN_CANCEL, {"run_id": "r"}),
            (
                PluginToRuntimeAction.RUN_APPEND_RESULT,
                {
                    "run_id": "r",
                    "target_run_id": "r",
                    "sequence": 1,
                    "result": {"type": "run.completed", "data": {}},
                },
            ),
            (
                PluginToRuntimeAction.RUN_FINALIZE,
                {"run_id": "r", "status": "completed"},
            ),
            (
                PluginToRuntimeAction.RUNTIME_REGISTER,
                {"run_id": "r", "runtime_id": "runtime-1"},
            ),
            (
                PluginToRuntimeAction.RUNTIME_HEARTBEAT,
                {"run_id": "r", "runtime_id": "runtime-1"},
            ),
            (PluginToRuntimeAction.RUNTIME_LIST, {"run_id": "r"}),
            (
                PluginToRuntimeAction.RUN_CLAIM,
                {"run_id": "r", "runtime_id": "runtime-1"},
            ),
            (
                PluginToRuntimeAction.RUN_RENEW_CLAIM,
                {
                    "run_id": "r",
                    "target_run_id": "target-r",
                    "runtime_id": "runtime-1",
                    "claim_token": "token",
                },
            ),
            (
                PluginToRuntimeAction.RUN_RELEASE_CLAIM,
                {
                    "run_id": "r",
                    "target_run_id": "target-r",
                    "runtime_id": "runtime-1",
                    "claim_token": "token",
                },
            ),
            (PluginToRuntimeAction.RUNNER_LIST, {}),
            (PluginToRuntimeAction.RUNTIME_RECONCILE, {}),
        ]

        for action, payload in pull_actions:
            fake_context.control_handler.call_action.reset_mock()

            resp = await handler.actions[action.value](payload)

            assert resp.code == 0, f"Action {action.value} returned error"

            call_args = fake_context.control_handler.call_action.call_args
            forwarded_payload = call_args[0][1]
            assert (
                forwarded_payload.get("caller_plugin_identity") == "my-author/my-plugin"
            ), f"caller_plugin_identity not injected for {action.value}"

    @pytest.mark.anyio
    async def test_admin_pull_apis_without_run_id_inject_real_plugin_identity(self):
        """Admin pull APIs without run_id still use runtime-owned caller identity."""
        fake_context = make_fake_context()
        handler = PluginConnectionHandler(FakeConnection(), fake_context)
        plugin_container = SimpleNamespace(
            _runtime_plugin_handler=handler,
            manifest=SimpleNamespace(
                metadata=SimpleNamespace(
                    author="control-author",
                    name="control-plugin",
                )
            ),
        )
        fake_context.plugin_mgr.plugins = [plugin_container]

        admin_actions = [
            (
                PluginToRuntimeAction.RUN_LIST,
                {"caller_plugin_identity": "attacker/plugin", "statuses": ["running"]},
            ),
            (
                PluginToRuntimeAction.RUNTIME_LIST,
                {"caller_plugin_identity": "attacker/plugin", "statuses": ["online"]},
            ),
            (
                PluginToRuntimeAction.RUNNER_LIST,
                {
                    "caller_plugin_identity": "attacker/plugin",
                    "include_plugins": ["control-author/control-plugin"],
                },
            ),
            (
                PluginToRuntimeAction.RUNTIME_RECONCILE,
                {
                    "caller_plugin_identity": "attacker/plugin",
                    "stale_after_seconds": 60.0,
                },
            ),
        ]

        for action, payload in admin_actions:
            fake_context.control_handler.call_action.reset_mock()

            resp = await handler.actions[action.value](payload)

            assert resp.code == 0
            forwarded_payload = fake_context.control_handler.call_action.call_args[0][1]
            assert "run_id" not in forwarded_payload
            assert (
                forwarded_payload["caller_plugin_identity"]
                == "control-author/control-plugin"
            )


class TestRunnerAPIProxyPullAPIPayloads:
    """Tests for pull API payload structure via RunnerAPIProxy.

    These tests verify the proxy layer sends correct payloads to the mock handler.
    """

    @pytest.mark.anyio
    async def test_state_api_payloads_via_proxy(self):
        """State API payloads are correctly forwarded via proxy."""
        from langbot_plugin.api.proxies.runner import RunnerAPIProxy
        from langbot_plugin.api.entities.builtin.runner.context import (
            RunnerContext,
        )
        from langbot_plugin.api.entities.builtin.runner.resources import (
            AgentResources,
        )
        from langbot_plugin.api.entities.builtin.runner.trigger import (
            AgentTrigger,
        )
        from langbot_plugin.api.entities.builtin.runner.input import AgentInput
        from langbot_plugin.api.entities.builtin.runner.event import (
            AgentEventContext,
        )
        from langbot_plugin.api.entities.builtin.runner.delivery import (
            DeliveryContext,
        )
        from langbot_plugin.api.entities.builtin.runner.runtime import (
            AgentRuntimeContext,
        )

        mock_handler = SimpleNamespace()
        mock_handler.call_action = AsyncMock(
            return_value={"value": None, "success": True}
        )

        ctx = RunnerContext(
            run_id="proxy_run",
            trigger=AgentTrigger(type="user_message"),
            event=AgentEventContext(event_id="e1", event_type="test", source="test"),
            input=AgentInput(content="test"),
            delivery=DeliveryContext(surface="test"),
            context={"available_apis": {"state": True}},
            runtime=AgentRuntimeContext(),
            resources=AgentResources(),
        )

        proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=mock_handler)

        await proxy.state_get("conversation", "key")

        call_args = mock_handler.call_action.call_args
        assert call_args[0][0] == PluginToRuntimeAction.STATE_GET
        assert call_args[0][1]["run_id"] == "proxy_run"
        assert call_args[0][1]["scope"] == "conversation"
        assert call_args[0][1]["key"] == "key"
